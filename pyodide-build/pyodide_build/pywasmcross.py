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

IS_MAIN = __name__ == "__main__"
if IS_MAIN:
    PYWASMCROSS_ARGS = json.loads(os.environ["PYWASMCROSS_ARGS"])
    # restore __name__ so that relative imports work as we expect
    __name__ = PYWASMCROSS_ARGS.pop("orig__name__")
    sys.path = PYWASMCROSS_ARGS.pop("PYTHONPATH")

    PYWASMCROSS_ARGS["pythoninclude"] = os.environ["PYTHONINCLUDE"]

import re
import subprocess
from collections import namedtuple
from pathlib import Path, PurePosixPath
from typing import Any, MutableMapping, NoReturn

from pyodide_build import common
from pyodide_build._f2c_fixes import fix_f2c_input, fix_f2c_output, scipy_fixes

symlinks = {"cc", "c++", "ld", "ar", "gcc", "gfortran", "cargo"}


def symlink_dir():
    return Path(common.get_make_flag("TOOLSDIR")) / "symlinks"


ReplayArgs = namedtuple(
    "ReplayArgs",
    [
        "pkgname",
        "cflags",
        "cxxflags",
        "ldflags",
        "target_install_dir",
        "replace_libs",
        "builddir",
        "pythoninclude",
    ],
)


def make_command_wrapper_symlinks(env: MutableMapping[str, str]) -> None:
    """
    Makes sure all the symlinks that make this script look like a compiler
    exist.
    """
    exec_path = Path(__file__).resolve()
    SYMLINKDIR = symlink_dir()
    for symlink in symlinks:
        symlink_path = SYMLINKDIR / symlink
        if os.path.lexists(symlink_path) and not symlink_path.exists():
            # remove broken symlink so it can be re-created
            symlink_path.unlink()
        try:
            symlink_path.symlink_to(exec_path)
        except FileExistsError:
            pass
        if symlink == "c++":
            var = "CXX"
        else:
            var = symlink.upper()
        env[var] = symlink


def compile(
    env: dict[str, str],
    *,
    pkgname: str,
    backend_flags: str,
    cflags: str,
    cxxflags: str,
    ldflags: str,
    target_install_dir: str,
    replace_libs: str,
) -> None:
    kwargs = dict(
        pkgname=pkgname,
        backend_flags=backend_flags,
        cflags=cflags,
        cxxflags=cxxflags,
        ldflags=ldflags,
        target_install_dir=target_install_dir,
        replace_libs=replace_libs,
    )

    args = environment_substitute_args(kwargs, env)
    backend_flags = args.pop("backend_flags")
    args["builddir"] = str(Path(".").absolute())

    env = dict(env)
    SYMLINKDIR = symlink_dir()
    env["PATH"] = f"{SYMLINKDIR}:{env['PATH']}"
    sysconfig_dir = Path(os.environ["TARGETINSTALLDIR"]) / "sysconfigdata"
    args["PYTHONPATH"] = sys.path + [str(sysconfig_dir)]
    args["orig__name__"] = __name__
    make_command_wrapper_symlinks(env)
    env["PYWASMCROSS_ARGS"] = json.dumps(args)
    env["_PYTHON_HOST_PLATFORM"] = common.platform()
    env["_PYTHON_SYSCONFIGDATA_NAME"] = os.environ["SYSCONFIG_NAME"]

    from .pypabuild import build

    try:
        build(env, backend_flags)
    except BaseException:
        build_log_path = Path("build.log")
        if build_log_path.exists():
            build_log_path.unlink()
        raise


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


def parse_replace_libs(replace_libs: str) -> dict[str, str]:
    """
    Parameters
    ----------
    replace_libs
        The `--replace-libs` argument, should be a string like "a=b;c=d".

    Returns
    -------
        The input string converted to a dictionary

    Examples
    --------
    >>> parse_replace_libs("a=b;c=d;e=f")
    {'a': 'b', 'c': 'd', 'e': 'f'}
    """
    result = {}
    for l in replace_libs.split(";"):
        if not l:
            continue
        from_lib, to_lib = l.split("=")
        if to_lib:
            result[from_lib] = to_lib
    return result


def replay_genargs_handle_dashl(
    arg: str, replace_libs: dict[str, str], used_libs: set[str]
) -> str | None:
    """
    Figure out how to replace a `-lsomelib` argument.

    Parameters
    ----------
    arg
        The argument we are replacing. Must start with `-l`.

    replace_libs
        The dictionary of libraries we are replacing

    used_libs
        The libraries we've used so far in this command. emcc fails out if `-lsomelib`
        occurs twice, so we have to track this.

    Returns
    -------
        The new argument, or None to delete the argument.
    """
    assert arg.startswith("-l")
    for lib_name in replace_libs.keys():
        # this enables glob style **/* matching
        if PurePosixPath(arg[2:]).match(lib_name):
            arg = "-l" + replace_libs[lib_name]

    if arg == "-lffi":
        return None

    # See https://github.com/emscripten-core/emscripten/issues/8650
    if arg in ["-lfreetype", "-lz", "-lpng", "-lgfortran"]:
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


def replay_genargs_handle_linker_opts(arg):
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
        # ignore unsupported --sysroot compile argument used in conda
        if opt.startswith("--sysroot="):
            continue
        if opt.startswith("--version-script="):
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
    >>> Args = namedtuple('args', ['cflags', 'cxxflags', 'ldflags', 'replace_libs','target_install_dir'])
    >>> args = Args(cflags='', cxxflags='', ldflags='', replace_libs='',target_install_dir='')
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
        # The native build is possibly multithreaded, but the emscripten one
        # definitely isn't
        arg = re.sub(r"/python([0-9]\.[0-9]+)m", r"/python\1", arg)
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

        replace_libs = parse_replace_libs(args.replace_libs)
        if arg.startswith("-l"):
            result = replay_genargs_handle_dashl(arg, replace_libs, used_libs)
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
    if returncode != 0:
        sys.exit(returncode)

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


if IS_MAIN:
    path = os.environ["PATH"]
    SYMLINKDIR = symlink_dir()
    while f"{SYMLINKDIR}:" in path:
        path = path.replace(f"{SYMLINKDIR}:", "")
    os.environ["PATH"] = path

    REPLAY_ARGS = ReplayArgs(**PYWASMCROSS_ARGS)

    basename = Path(sys.argv[0]).name
    args = list(sys.argv)
    args[0] = basename
    if basename in symlinks:
        sys.exit(handle_command(args, REPLAY_ARGS))
    else:
        raise Exception(f"Unexpected invocation '{basename}'")
