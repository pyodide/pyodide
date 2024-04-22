#!/usr/bin/env python3
"""Helper for cross-compiling Python binary extensions.

Python has never had a proper cross-compilation story. This is a hack, which
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
    "lld",
    "ar",
    "gcc",
    "ranlib",
    "strip",
    "gfortran",
    "cargo",
    "cmake",
    "meson",
    "install_name_tool",
    "otool",
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
    os.environ["PATH"] = (
        os.environ["BUILD_ENV_SCRIPTS_DIR"] + ":" + PYWASMCROSS_ARGS.pop("PATH")
    )
    # restore __name__ so that relative imports work as we expect
    __name__ = PYWASMCROSS_ARGS.pop("orig__name__")


import subprocess
from collections.abc import Iterable, Iterator
from typing import Literal, NamedTuple


class CrossCompileArgs(NamedTuple):
    """
    Arguments for cross-compiling a package.
    """

    cflags: str = ""
    cxxflags: str = ""
    ldflags: str = ""

    # The name of the package being compiled
    # This is used to apply package-specific fixes, such as scipy
    pkgname: str = ""
    target_install_dir: str = ""  # The path to the target Python installation
    pythoninclude: str = ""  # path to the cross-compiled Python include directory
    exports: Literal["whole_archive", "requested", "pyinit"] | list[str] = "pyinit"


def is_link_cmd(line: list[str]) -> bool:
    """
    Check if the command is a linker invocation.
    """
    import re

    SHAREDLIB_REGEX = re.compile(r"\.so(.\d+)*$")
    for arg in line:
        if not arg.startswith("-") and SHAREDLIB_REGEX.search(arg):
            return True

    return False


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

    # Don't include any system directories
    if arg[2:].startswith("/usr"):
        return None

    # Replace local Python include paths with the cross compiled ones
    include_path = str(Path(arg[2:]).resolve())
    if include_path.startswith(sys.prefix + "/include/python"):
        return arg.replace("-I" + sys.prefix, "-I" + target_install_dir)

    if include_path.startswith(sys.base_prefix + "/include/python"):
        return arg.replace("-I" + sys.base_prefix, "-I" + target_install_dir)

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
            # wasm-ld does not recognize some link flags
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
        "-mno-sse2", # warning: argument unused during compilation
        "-mno-avx2", # warning: argument unused during compilation
        "-std=legacy", # fortran flag that clang does not support
    ]:
        return None

    if arg.startswith((
        "-J",  # fortran flag that clang does not support
    )):
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
    import shutil

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
    line: list[str], build_args: CrossCompileArgs
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

    Returns
    -------
        An updated argument list suitable for use with emscripten.

    Examples
    --------

    >>> from collections import namedtuple
    >>> Args = namedtuple('args', ['cflags', 'cxxflags', 'ldflags', 'target_install_dir'])
    >>> args = Args(cflags='', cxxflags='', ldflags='', target_install_dir='')
    >>> handle_command_generate_args(['gcc', 'test.c'], args)
    ['emcc', 'test.c', '-Werror=implicit-function-declaration', '-Werror=mismatched-parameter-types', '-Werror=return-type']
    """
    if "-print-multiarch" in line:
        return ["echo", "wasm32-emscripten"]
    if len(line) == 2 and line[1] == "-v":
        return ["emcc", "-v"]

    cmd = line[0]
    if cmd == "c++" or cmd == "g++":
        new_args = ["em++"]
    elif cmd in ("cc", "gcc", "ld", "lld"):
        new_args = ["emcc"]
        # distutils doesn't use the c++ compiler when compiling c++ <sigh>
        if any(arg.endswith((".cpp", ".cc")) for arg in line):
            new_args = ["em++"]
    elif cmd == "ar":
        line[0] = "emar"
        return line
    elif cmd == "cmake":
        # If it is a build/install command, or running a script, we don't do anything.
        if "--build" in line or "--install" in line or "-P" in line or "-E" in line:
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
    elif cmd == "meson":
        if line[:2] != ["meson", "setup"]:
            return line

        if "MESON_CROSS_FILE" in os.environ:
            line[:2] = [
                "meson",
                "setup",
                "--cross-file",
                os.environ["MESON_CROSS_FILE"],
            ]

        return line
    elif cmd in ("install_name_tool", "otool"):
        # In MacOS, meson tries to run install_name_tool to fix the rpath of the shared library
        # assuming that it is a ELF file. We need to skip this step.
        # See: https://github.com/mesonbuild/meson/issues/8027
        return ["echo", *line]
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
    if is_link_cmd(line):
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
    build_args: CrossCompileArgs,
) -> int:
    """Handle a compilation command. Exit with an appropriate exit code when done.

    Parameters
    ----------
    line : iterable
       an iterable with the compilation arguments
    build_args : BuildArgs
       a container with additional compilation options
    """

    if line[0] == "gfortran":
        from pyodide_build._f2c_fixes import replay_f2c

        tmp = replay_f2c(line)
        if tmp is None:
            # No source file, it's a query for information about the compiler. Pretend we're
            # gfortran by letting gfortran handle it
            return subprocess.run(line).returncode

        line = tmp

    new_args = handle_command_generate_args(line, build_args)

    if build_args.pkgname == "scipy":
        from pyodide_build._f2c_fixes import scipy_fixes

        scipy_fixes(new_args)

    result = subprocess.run(new_args)
    return result.returncode


def compiler_main():
    build_args = CrossCompileArgs(
        pkgname=PYWASMCROSS_ARGS["pkgname"],
        cflags=PYWASMCROSS_ARGS["cflags"],
        cxxflags=PYWASMCROSS_ARGS["cxxflags"],
        ldflags=PYWASMCROSS_ARGS["ldflags"],
        target_install_dir=PYWASMCROSS_ARGS["target_install_dir"],
        pythoninclude=PYWASMCROSS_ARGS["pythoninclude"],
        exports=PYWASMCROSS_ARGS["exports"],
    )
    basename = Path(sys.argv[0]).name
    args = list(sys.argv)
    args[0] = basename
    sys.exit(handle_command(args, build_args))


if IS_COMPILER_INVOCATION:
    compiler_main()
