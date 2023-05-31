#!/usr/bin/env python3
"""Helper for cross-compiling distutils-based Python extensions.

distutils has never had a proper cross-compilation story. This is a hack, which
miraculously works, to get around that.

The gist is we compile the package replacing calls to the compiler and linker
with wrappers that adjusting include paths and flags as necessary for
cross-compiling and then pass the command long to emscripten.
"""
import json
import os
import sys
from pathlib import Path

from __main__ import __file__ as INVOKED_PATH_STR

INVOKED_PATH = Path(INVOKED_PATH_STR)

SYMLINKS = {
    "cc",
    "c++",
    "ld",
    "ar",
    "gcc",
    "ranlib",
    "strip",
    "gfortran",
    "cargo",
    "cmake",
}
IS_COMPILER_INVOCATION = INVOKED_PATH.name in SYMLINKS

if IS_COMPILER_INVOCATION:
    # If possible load from environment variable, if necessary load from disk.
    if "PYWASMCROSS_ARGS" in os.environ:
        PYWASMCROSS_ARGS = json.loads(os.environ["PYWASMCROSS_ARGS"])
    else:
        try:
            with open(INVOKED_PATH.parent / "pywasmcross_env.json") as f:
                PYWASMCROSS_ARGS = json.load(f)
        except FileNotFoundError:
            raise RuntimeError(
                "Invalid invocation: can't find PYWASMCROSS_ARGS."
                f" Invoked from {INVOKED_PATH}."
            ) from None

    sys.path = PYWASMCROSS_ARGS.pop("PYTHONPATH")
    os.environ["PATH"] = PYWASMCROSS_ARGS.pop("PATH")
    # restore __name__ so that relative imports work as we expect
    __name__ = PYWASMCROSS_ARGS.pop("orig__name__")


import dataclasses
import re
import shutil
import subprocess
from collections.abc import Iterable, Iterator
from typing import Literal, NoReturn


@dataclasses.dataclass(eq=False, order=False, kw_only=True)
class BuildArgs:
    """
    Common arguments for building a package.
    """

    pkgname: str = ""
    cflags: str = ""
    cxxflags: str = ""
    ldflags: str = ""
    target_install_dir: str = ""  # The path to the target Python installation
    host_install_dir: str = ""  # Directory for installing built host packages.
    builddir: str = ""  # The path to run pypa/build
    pythoninclude: str = ""
    exports: Literal["whole_archive", "requested", "pyinit"] | list[str] = "pyinit"
    compression_level: int = 6


def replay_f2c(args: list[str], dryrun: bool = False) -> list[str] | None:
    """Apply f2c to compilation arguments

    Parameters
    ----------
    args
       input compiler arguments
    dryrun
       if False run f2c on detected fortran files

    Returns
    -------
    new_args
       output compiler arguments


    Examples
    --------

    >>> replay_f2c(['gfortran', 'test.f'], dryrun=True)
    ['gcc', 'test.c']
    """

    from pyodide_build._f2c_fixes import fix_f2c_input, fix_f2c_output

    new_args = ["gcc"]
    found_source = False
    for arg in args[1:]:
        if arg.endswith(".f") or arg.endswith(".F"):
            filepath = Path(arg).resolve()
            if not dryrun:
                fix_f2c_input(arg)
                if arg.endswith(".F"):
                    # .F files apparently expect to be run through the C
                    # preprocessor (they have #ifdef's in them)
                    # Use gfortran frontend, as gcc frontend might not be
                    # present on osx
                    # The file-system might be not case-sensitive,
                    # so take care to handle this by renaming.
                    # For preprocessing and further operation the
                    # expected file-name and extension needs to be preserved.
                    subprocess.check_call(
                        [
                            "gfortran",
                            "-E",
                            "-C",
                            "-P",
                            filepath,
                            "-o",
                            filepath.with_suffix(".f77"),
                        ]
                    )
                    filepath = filepath.with_suffix(".f77")
                # -R flag is important, it means that Fortran functions that
                # return real e.g. sdot will be transformed into C functions
                # that return float. For historic reasons, by default f2c
                # transform them into functions that return a double. Using -R
                # allows to match what OpenBLAS has done when they f2ced their
                # Fortran files, see
                # https://github.com/xianyi/OpenBLAS/pull/3539#issuecomment-1493897254
                # for more details
                with (
                    open(filepath) as input_pipe,
                    open(filepath.with_suffix(".c"), "w") as output_pipe,
                ):
                    subprocess.check_call(
                        ["f2c", "-R"],
                        stdin=input_pipe,
                        stdout=output_pipe,
                        cwd=filepath.parent,
                    )
                fix_f2c_output(arg[:-2] + ".c")
            new_args.append(arg[:-2] + ".c")
            found_source = True
        else:
            new_args.append(arg)

    new_args_str = " ".join(args)
    if ".so" in new_args_str and "libgfortran.so" not in new_args_str:
        found_source = True

    if not found_source:
        print(f"f2c: source not found, skipping: {new_args_str}")
        return None
    return new_args


def get_library_output(line: list[str]) -> str | None:
    """
    Check if the command is a linker invocation. If so, return the name of the
    output file.
    """
    SHAREDLIB_REGEX = re.compile(r"\.so(.\d+)*$")
    for arg in line:
        if not arg.startswith("-") and SHAREDLIB_REGEX.search(arg):
            return arg
    return None


def replay_genargs_handle_dashl(arg: str, used_libs: set[str]) -> str | None:
    """
    Figure out how to replace a `-lsomelib` argument.

    Parameters
    ----------
    arg
        The argument we are replacing. Must start with `-l`.

    used_libs
        The libraries we've used so far in this command. emcc fails out if `-lsomelib`
        occurs twice, so we have to track this.

    Returns
    -------
        The new argument, or None to delete the argument.
    """
    assert arg.startswith("-l")

    if arg == "-lffi":
        return None

    if arg == "-lgfortran":
        return None

    # WASM link doesn't like libraries being included twice
    # skip second one
    if arg in used_libs:
        return None
    used_libs.add(arg)
    return arg


def replay_genargs_handle_dashI(arg: str, target_install_dir: str) -> str | None:
    """
    Figure out how to replace a `-Iincludepath` argument.

    Parameters
    ----------
    arg
        The argument we are replacing. Must start with `-I`.

    target_install_dir
        The target_install_dir argument.

    Returns
    -------
        The new argument, or None to delete the argument.
    """
    assert arg.startswith("-I")
    if (
        str(Path(arg[2:]).resolve()).startswith(sys.prefix + "/include/python")
        and "site-packages" not in arg
    ):
        return arg.replace("-I" + sys.prefix, "-I" + target_install_dir)
    # Don't include any system directories
    if arg[2:].startswith("/usr"):
        return None
    return arg


def replay_genargs_handle_linker_opts(arg: str) -> str | None:
    """
    ignore some link flags
    it should not check if `arg == "-Wl,-xxx"` and ignore directly here,
    because arg may be something like "-Wl,-xxx,-yyy" where we only want
    to ignore "-xxx" but not "-yyy".
    """

    assert arg.startswith("-Wl")
    link_opts = arg.split(",")[1:]
    new_link_opts = ["-Wl"]
    for opt in link_opts:
        if opt in [
            "-Bsymbolic-functions",
            # breaks emscripten see https://github.com/emscripten-core/emscripten/issues/14460
            "--strip-all",
            "-strip-all",
            # wasm-ld does not regconize some link flags
            "--sort-common",
            "--as-needed",
        ]:
            continue

        if opt.startswith(
            (
                "--sysroot=",  # ignore unsupported --sysroot compile argument used in conda
                "--version-script=",
                "-R/",  # wasm-ld does not accept -R (runtime libraries)
                "-R.",  # wasm-ld does not accept -R (runtime libraries)
                "--exclude-libs=",
            )
        ):
            continue

        new_link_opts.append(opt)
    if len(new_link_opts) > 1:
        return ",".join(new_link_opts)
    else:
        return None


def replay_genargs_handle_argument(arg: str) -> str | None:
    """
    Figure out how to replace a general argument.

    Parameters
    ----------
    arg
        The argument we are replacing. Must not start with `-I` or `-l`.

    Returns
    -------
        The new argument, or None to delete the argument.
    """
    assert not arg.startswith("-I")  # should be handled by other functions
    assert not arg.startswith("-l")
    assert not arg.startswith("-Wl,")

    # Don't include any system directories
    if arg.startswith("-L/usr"):
        return None

    # fmt: off
    if arg in [
        # threading is disabled for now
        "-pthread",
        # this only applies to compiling fortran code, but we already f2c'd
        "-ffixed-form",
        "-fallow-argument-mismatch",
        # On Mac, we need to omit some darwin-specific arguments
        "-bundle", "-undefined", "dynamic_lookup",
        # This flag is needed to build numpy with SIMD optimization which we currently disable
        "-mpopcnt",
        # gcc flag that clang does not support
        "-Bsymbolic-functions",
        '-fno-second-underscore',
        '-fstack-protector',  # doesn't work?
        '-fno-strict-overflow',  # warning: argument unused during compilation
    ]:
        return None
    # fmt: on
    return arg


def get_cmake_compiler_flags() -> list[str]:
    """
    GeneraTe cmake compiler flags.
    emcmake will set these values to emcc, em++, ...
    but we need to set them to cc, c++, in order to make them pass to pywasmcross.
    Returns
    -------
    The commandline flags to pass to cmake.
    """
    compiler_flags = {
        "CMAKE_C_COMPILER": "cc",
        "CMAKE_CXX_COMPILER": "c++",
        "CMAKE_AR": "ar",
        "CMAKE_C_COMPILER_AR": "ar",
        "CMAKE_CXX_COMPILER_AR": "ar",
    }

    flags = []
    symlinks_dir = Path(sys.argv[0]).parent
    for key, value in compiler_flags.items():
        assert value in SYMLINKS

        flags.append(f"-D{key}={symlinks_dir / value}")

    return flags


def _calculate_object_exports_readobj_parse(output: str) -> list[str]:
    """
    >>> _calculate_object_exports_readobj_parse(
    ...     '''
    ...     Format: WASM \\n Arch: wasm32 \\n AddressSize: 32bit
    ...     Sections [
    ...         Section { \\n Type: TYPE (0x1)   \\n Size: 5  \\n Offset: 8  \\n }
    ...         Section { \\n Type: IMPORT (0x2) \\n Size: 32 \\n Offset: 19 \\n }
    ...     ]
    ...     Symbol {
    ...         Name: g2 \\n Type: FUNCTION (0x0) \\n
    ...         Flags [ (0x0) \\n ]
    ...         ElementIndex: 0x2
    ...     }
    ...     Symbol {
    ...         Name: f2 \\n Type: FUNCTION (0x0) \\n
    ...         Flags [ (0x4) \\n VISIBILITY_HIDDEN (0x4) \\n ]
    ...         ElementIndex: 0x1
    ...     }
    ...     Symbol {
    ...         Name: l  \\n Type: FUNCTION (0x0)
    ...         Flags [ (0x10)\\n UNDEFINED (0x10) \\n ]
    ...         ImportModule: env
    ...         ElementIndex: 0x0
    ...     }
    ...     '''
    ... )
    ['g2']
    """
    result = []
    insymbol = False
    for line in output.split("\n"):
        line = line.strip()
        if line == "Symbol {":
            insymbol = True
            export = True
            name = None
            symbol_lines = [line]
            continue
        if not insymbol:
            continue
        symbol_lines.append(line)
        if line.startswith("Name:"):
            name = line.removeprefix("Name:").strip()
        if line.startswith(("BINDING_LOCAL", "UNDEFINED", "VISIBILITY_HIDDEN")):
            export = False
        if line == "}":
            insymbol = False
            if export:
                if not name:
                    raise RuntimeError(
                        "Didn't find symbol's name:\n" + "\n".join(symbol_lines)
                    )
                result.append(name)
    return result


def calculate_object_exports_readobj(objects: list[str]) -> list[str] | None:
    readobj_path = shutil.which("llvm-readobj")
    if not readobj_path:
        which_emcc = shutil.which("emcc")
        assert which_emcc
        emcc = Path(which_emcc)
        readobj_path = str((emcc / "../../bin/llvm-readobj").resolve())
    args = [
        readobj_path,
        "--section-details",
        "-st",
    ] + objects
    completedprocess = subprocess.run(
        args, encoding="utf8", capture_output=True, env={"PATH": os.environ["PATH"]}
    )
    if completedprocess.returncode:
        print(f"Command '{' '.join(args)}' failed. Output to stderr was:")
        print(completedprocess.stderr)
        sys.exit(completedprocess.returncode)

    if "bitcode files are not supported" in completedprocess.stderr:
        return None

    return _calculate_object_exports_readobj_parse(completedprocess.stdout)


def calculate_object_exports_nm(objects: list[str]) -> list[str]:
    args = ["emnm", "-j", "--export-symbols"] + objects
    result = subprocess.run(
        args, encoding="utf8", capture_output=True, env={"PATH": os.environ["PATH"]}
    )
    if result.returncode:
        print(f"Command '{' '.join(args)}' failed. Output to stderr was:")
        print(result.stderr)
        sys.exit(result.returncode)
    return result.stdout.splitlines()


def filter_objects(line: list[str]) -> list[str]:
    """
    Collect up all the object files and archive files being linked.
    """
    return [
        arg
        for arg in line
        if arg.endswith((".a", ".o"))
        or arg.startswith(
            "@"
        )  # response file (https://gcc.gnu.org/wiki/Response_Files)
    ]


def calculate_exports(line: list[str], export_all: bool) -> Iterable[str]:
    """
    List out symbols from object files and archive files that are marked as public.
    If ``export_all`` is ``True``, then return all public symbols.
    If not, return only the public symbols that begin with `PyInit`.
    """
    objects = filter_objects(line)
    exports = None
    # Using emnm is simpler but it cannot handle bitcode. If we're only
    # exporting the PyInit symbols, save effort by using nm.
    if export_all:
        exports = calculate_object_exports_readobj(objects)
    if exports is None:
        # Either export_all is false or we are linking at least one bitcode
        # object. Fall back to a more conservative estimate of the symbols
        # exported. This can export things with `__visibility__("hidden")`
        exports = calculate_object_exports_nm(objects)
    if export_all:
        return exports
    return (x for x in exports if x.startswith("PyInit"))


def get_export_flags(
    line: list[str],
    exports: Literal["whole_archive", "requested", "pyinit"] | list[str],
) -> Iterator[str]:
    """
    If "whole_archive" was requested, no action is needed. Otherwise, add
    `-sSIDE_MODULE=2` and the appropriate export list.
    """
    if exports == "whole_archive":
        return
    yield "-sSIDE_MODULE=2"
    if isinstance(exports, str):
        export_list = calculate_exports(line, exports == "requested")
    else:
        export_list = exports
    prefixed_exports = ["_" + x for x in export_list]
    yield f"-sEXPORTED_FUNCTIONS={prefixed_exports!r}"


def handle_command_generate_args(  # noqa: C901
    line: list[str], build_args: BuildArgs, is_link_command: bool
) -> list[str]:
    """
    A helper command for `handle_command` that generates the new arguments for
    the compilation.

    Unlike `handle_command` this avoids I/O: it doesn't sys.exit, it doesn't run
    subprocesses, it doesn't create any files, and it doesn't write to stdout.

    Parameters
    ----------
    line The original compilation command as a list e.g., ["gcc", "-c",
        "input.c", "-o", "output.c"]

    build_args The arguments that pywasmcross was invoked with

    is_link_command Is this a linker invocation?

    Returns
    -------
        An updated argument list suitable for use with emscripten.


    Examples
    --------

    >>> from collections import namedtuple
    >>> Args = namedtuple('args', ['cflags', 'cxxflags', 'ldflags', 'target_install_dir'])
    >>> args = Args(cflags='', cxxflags='', ldflags='', target_install_dir='')
    >>> handle_command_generate_args(['gcc', 'test.c'], args, False)
    ['emcc', 'test.c', '-Werror=implicit-function-declaration', '-Werror=mismatched-parameter-types', '-Werror=return-type']
    """
    if "-print-multiarch" in line:
        return ["echo", "wasm32-emscripten"]
    for arg in line:
        if arg.startswith("-print-file-name"):
            return line
    if len(line) == 2 and line[1] == "-v":
        return ["emcc", "-v"]

    cmd = line[0]
    if cmd == "ar":
        line[0] = "emar"
        return line
    elif cmd == "c++" or cmd == "g++":
        new_args = ["em++"]
    elif cmd == "cc" or cmd == "gcc" or cmd == "ld":
        new_args = ["emcc"]
        # distutils doesn't use the c++ compiler when compiling c++ <sigh>
        if any(arg.endswith((".cpp", ".cc")) for arg in line):
            new_args = ["em++"]
    elif cmd == "cmake":
        # If it is a build/install command, or running a script, we don't do anything.
        if "--build" in line or "--install" in line or "-P" in line:
            return line

        flags = get_cmake_compiler_flags()
        line[:1] = [
            "emcmake",
            "cmake",
            *flags,
            # Since we create a temporary directory and install compiler symlinks every time,
            # CMakeCache.txt will contain invalid paths to the compiler when re-running,
            # so we need to tell CMake to ignore the existing cache and build from scratch.
            "--fresh",
        ]
        return line
    elif cmd == "ranlib":
        line[0] = "emranlib"
        return line
    elif cmd == "strip":
        line[0] = "emstrip"
        return line
    else:
        return line

    used_libs: set[str] = set()
    # Go through and adjust arguments
    for arg in line[1:]:
        if new_args[-1].startswith("-B") and "compiler_compat" in arg:
            # conda uses custom compiler search paths with the compiler_compat folder.
            # Ignore it.
            del new_args[-1]
            continue

        if arg.startswith("-l"):
            result = replay_genargs_handle_dashl(arg, used_libs)
        elif arg.startswith("-I"):
            result = replay_genargs_handle_dashI(arg, build_args.target_install_dir)
        elif arg.startswith("-Wl"):
            result = replay_genargs_handle_linker_opts(arg)
        else:
            result = replay_genargs_handle_argument(arg)

        if result:
            new_args.append(result)

    new_args.extend(
        [
            "-Werror=implicit-function-declaration",
            "-Werror=mismatched-parameter-types",
            "-Werror=return-type",
        ]
    )

    # set linker and C flags to error on anything to do with function declarations being wrong.
    # Better to fail at compile or link time.
    if is_link_command:
        new_args.append("-Wl,--fatal-warnings")
        new_args.extend(build_args.ldflags.split())
        new_args.extend(get_export_flags(line, build_args.exports))

    if "-c" in line:
        if new_args[0] == "emcc":
            new_args.extend(build_args.cflags.split())
        elif new_args[0] == "em++":
            new_args.extend(build_args.cflags.split() + build_args.cxxflags.split())

        if build_args.pythoninclude:
            new_args.extend(["-I", build_args.pythoninclude])

    return new_args


def handle_command(
    line: list[str],
    build_args: BuildArgs,
) -> NoReturn:
    """Handle a compilation command. Exit with an appropriate exit code when done.

    Parameters
    ----------
    line : iterable
       an iterable with the compilation arguments
    build_args : BuildArgs
       a container with additional compilation options
    """
    # some libraries have different names on wasm e.g. png16 = png
    is_link_cmd = get_library_output(line) is not None

    if line[0] == "gfortran":
        if "-dumpversion" in line:
            sys.exit(subprocess.run(line).returncode)
        tmp = replay_f2c(line)
        if tmp is None:
            sys.exit(0)
        line = tmp

    new_args = handle_command_generate_args(line, build_args, is_link_cmd)

    if build_args.pkgname == "scipy":
        from pyodide_build._f2c_fixes import scipy_fixes

        scipy_fixes(new_args)

    returncode = subprocess.run(new_args).returncode

    sys.exit(returncode)


def compiler_main():
    build_args = BuildArgs(**PYWASMCROSS_ARGS)
    basename = Path(sys.argv[0]).name
    args = list(sys.argv)
    args[0] = basename
    sys.exit(handle_command(args, build_args))


if IS_COMPILER_INVOCATION:
    compiler_main()
