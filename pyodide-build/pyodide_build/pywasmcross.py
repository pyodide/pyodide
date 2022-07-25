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

SYMLINKS = {"cc", "c++", "ld", "ar", "gcc", "gfortran", "cargo"}
IS_COMPILER_INVOCATION = INVOKED_PATH.name in SYMLINKS

if IS_COMPILER_INVOCATION:
    # If possible load from environment variable, if necessary load from disk.
    if "PYWASMCROSS_ARGS" in os.environ:
        PYWASMCROSS_ARGS = json.loads(os.environ["PYWASMCROSS_ARGS"])
    try:
        with open(INVOKED_PATH.parent / "pywasmcross_env.json") as f:
            PYWASMCROSS_ARGS = json.load(f)
    except FileNotFoundError:
        raise RuntimeError(
            "Invalid invocation: can't find PYWASMCROSS_ARGS."
            f" Invoked from {INVOKED_PATH}."
        )

    sys.path = PYWASMCROSS_ARGS.pop("PYTHONPATH")
    os.environ["PATH"] = PYWASMCROSS_ARGS.pop("PATH")
    # restore __name__ so that relative imports work as we expect
    __name__ = PYWASMCROSS_ARGS.pop("orig__name__")


import shutil
import subprocess
from collections import namedtuple
from collections.abc import Iterable, Iterator, MutableMapping
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from typing import Any, Literal, NoReturn

from pyodide_build import common
from pyodide_build._f2c_fixes import fix_f2c_input, fix_f2c_output, scipy_fixes


def symlink_dir() -> Path:
    return Path(common.get_make_flag("TOOLSDIR")) / "symlinks"


ReplayArgs = namedtuple(
    "ReplayArgs",
    [
        "pkgname",
        "cflags",
        "cxxflags",
        "ldflags",
        "target_install_dir",
        "builddir",
        "pythoninclude",
        "exports",
    ],
)


def make_command_wrapper_symlinks(
    symlink_dir: Path, env: MutableMapping[str, str]
) -> None:
    """
    Makes sure all the symlinks that make this script look like a compiler
    exist.
    """
    exec_path = Path(__file__).resolve()
    for symlink in SYMLINKS:
        symlink_path = symlink_dir / symlink
        if os.path.lexists(symlink_path) and not symlink_path.exists():
            # remove broken symlink so it can be re-created
            symlink_path.unlink()
        try:
            pywasmcross_exe = shutil.which("_pywasmcross")
            if pywasmcross_exe:
                symlink_path.symlink_to(pywasmcross_exe)
            else:
                symlink_path.symlink_to(exec_path)
        except FileExistsError:
            pass
        if symlink == "c++":
            var = "CXX"
        else:
            var = symlink.upper()
        env[var] = symlink


@contextmanager
def get_build_env(
    env: dict[str, str],
    *,
    pkgname: str,
    cflags: str,
    cxxflags: str,
    ldflags: str,
    target_install_dir: str,
    exports: str | list[str],
) -> Iterator[dict[str, str]]:
    kwargs = dict(
        pkgname=pkgname,
        cflags=cflags,
        cxxflags=cxxflags,
        ldflags=ldflags,
        target_install_dir=target_install_dir,
    )

    args = environment_substitute_args(kwargs, env)
    args["builddir"] = str(Path(".").absolute())
    args["exports"] = exports

    with TemporaryDirectory() as symlink_dir_str:
        symlink_dir = Path(symlink_dir_str)
        env = dict(env)
        make_command_wrapper_symlinks(symlink_dir, env)

        sysconfig_dir = Path(os.environ["TARGETINSTALLDIR"]) / "sysconfigdata"
        args["PYTHONPATH"] = sys.path + [str(sysconfig_dir)]
        args["orig__name__"] = __name__
        args["pythoninclude"] = os.environ["PYTHONINCLUDE"]
        args["PATH"] = env["PATH"]

        pywasmcross_env = json.dumps(args)
        # Store into environment variable and to disk. In most cases we will
        # load from the environment variable but if some other tool filters
        # environment variables we will load from disk instead.
        env["PYWASMCROSS_ARGS"] = pywasmcross_env
        (symlink_dir / "pywasmcross_env.json").write_text(pywasmcross_env)

        env["PATH"] = f"{symlink_dir}:{env['PATH']}"
        env["_PYTHON_HOST_PLATFORM"] = common.platform()
        env["_PYTHON_SYSCONFIGDATA_NAME"] = os.environ["SYSCONFIG_NAME"]
        env["PYTHONPATH"] = str(sysconfig_dir)
        yield env


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
                    subprocess.check_call(
                        [
                            "gcc",
                            "-E",
                            "-C",
                            "-P",
                            filepath,
                            "-o",
                            filepath.with_suffix(".f"),
                        ]
                    )
                    filepath = filepath.with_suffix(".f")
                subprocess.check_call(["f2c", filepath.name], cwd=filepath.parent)
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
    for arg in line:
        if arg.endswith(".so") and not arg.startswith("-"):
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
        # don't use -shared, SIDE_MODULE is already used
        # and -shared breaks it
        "-shared",
        # threading is disabled for now
        "-pthread",
        # this only applies to compiling fortran code, but we already f2c'd
        "-ffixed-form",
        # On Mac, we need to omit some darwin-specific arguments
        "-bundle", "-undefined", "dynamic_lookup",
        # This flag is needed to build numpy with SIMD optimization which we currently disable
        "-mpopcnt",
        # gcc flag that clang does not support
        "-Bsymbolic-functions",
        '-fno-second-underscore',
    ]:
        return None
    # fmt: on
    return arg


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
    which_emcc = shutil.which("emcc")
    assert which_emcc
    emcc = Path(which_emcc)
    args = [
        str((emcc / "../../bin/llvm-readobj").resolve()),
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


def calculate_exports(line: list[str], export_all: bool) -> Iterable[str]:
    """
    Collect up all the object files and archive files being linked and list out
    symbols in them that are marked as public. If ``export_all`` is ``True``,
    then return all public symbols. If not, return only the public symbols that
    begin with `PyInit`.
    """
    objects = [arg for arg in line if arg.endswith((".a", ".o"))]
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


def handle_command_generate_args(
    line: list[str], args: ReplayArgs, is_link_command: bool
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

    args The arguments that pywasmcross was invoked with

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
    ['emcc', '-Werror=implicit-function-declaration', '-Werror=mismatched-parameter-types', '-Werror=return-type', 'test.c']
    """
    if "-print-multiarch" in line:
        return ["echo", "wasm32-emscripten"]
    for arg in line:
        if arg.startswith("-print-file-name"):
            return line

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
    else:
        return line

    # set linker and C flags to error on anything to do with function declarations being wrong.
    # In webassembly, any conflicts mean that a randomly selected 50% of calls to the function
    # will fail. Better to fail at compile or link time.
    if is_link_command:
        new_args.append("-Wl,--fatal-warnings")
    new_args.extend(
        [
            "-Werror=implicit-function-declaration",
            "-Werror=mismatched-parameter-types",
            "-Werror=return-type",
        ]
    )

    if is_link_command:
        new_args.extend(args.ldflags.split())
        new_args.extend(get_export_flags(line, args.exports))

    if "-c" in line:
        if new_args[0] == "emcc":
            new_args.extend(args.cflags.split())
        elif new_args[0] == "em++":
            new_args.extend(args.cflags.split() + args.cxxflags.split())
        new_args.extend(["-I", args.pythoninclude])

    optflags_valid = [f"-O{tok}" for tok in "01234sz"]
    optflag = None
    # Identify the optflag (e.g. -O3) in cflags/cxxflags/ldflags. Last one has
    # priority.
    for arg in reversed(new_args):
        if arg in optflags_valid:
            optflag = arg
            break
    debugflag = None
    # Identify the debug flag (e.g. -g0) in cflags/cxxflags/ldflags. Last one has
    # priority.
    for arg in reversed(new_args):
        if arg.startswith("-g"):
            debugflag = arg
            break

    used_libs: set[str] = set()
    # Go through and adjust arguments
    for arg in line[1:]:
        if arg in optflags_valid and optflag is not None:
            # There are multiple contradictory optflags provided, use the one
            # from cflags/cxxflags/ldflags
            continue
        if arg.startswith("-g") and debugflag is not None:
            continue
        if new_args[-1].startswith("-B") and "compiler_compat" in arg:
            # conda uses custom compiler search paths with the compiler_compat folder.
            # Ignore it.
            del new_args[-1]
            continue

        if arg.startswith("-l"):
            result = replay_genargs_handle_dashl(arg, used_libs)
        elif arg.startswith("-I"):
            result = replay_genargs_handle_dashI(arg, args.target_install_dir)
        elif arg.startswith("-Wl"):
            result = replay_genargs_handle_linker_opts(arg)
        else:
            result = replay_genargs_handle_argument(arg)

        if result:
            new_args.append(result)

    return new_args


def handle_command(
    line: list[str],
    args: ReplayArgs,
) -> NoReturn:
    """Handle a compilation command. Exit with an appropriate exit code when done.

    Parameters
    ----------
    line : iterable
       an iterable with the compilation arguments
    args : {object, namedtuple}
       an container with additional compilation options, in particular
       containing ``args.cflags``, ``args.cxxflags``, and ``args.ldflags``
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

    new_args = handle_command_generate_args(line, args, is_link_cmd)

    if args.pkgname == "scipy":
        scipy_fixes(new_args)

    # FIXME: For some unknown reason,
    #        opencv-python tries to link a same library (libopencv_world.a) multiple times,
    #        which leads to 'duplicated symbols' error.
    if args.pkgname == "opencv-python":
        duplicated_lib = "libopencv_world.a"
        _new_args = []
        for arg in new_args:
            if duplicated_lib in arg and arg in _new_args:
                continue
            _new_args.append(arg)

        new_args = _new_args

    returncode = subprocess.run(new_args).returncode

    sys.exit(returncode)


def environment_substitute_args(
    args: dict[str, str], env: dict[str, str] | None = None
) -> dict[str, Any]:
    if env is None:
        env = dict(os.environ)
    subbed_args = {}
    for arg, value in args.items():
        if isinstance(value, str):
            for e_name, e_value in env.items():
                value = value.replace(f"$({e_name})", e_value)
        subbed_args[arg] = value
    return subbed_args


def compiler_main():
    replay_args = ReplayArgs(**PYWASMCROSS_ARGS)
    basename = Path(sys.argv[0]).name
    args = list(sys.argv)
    args[0] = basename
    sys.exit(handle_command(args, replay_args))


if IS_COMPILER_INVOCATION:
    compiler_main()
