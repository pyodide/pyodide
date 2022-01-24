#!/usr/bin/env python3
"""Helper for cross-compiling distutils-based Python extensions.

distutils has never had a proper cross-compilation story. This is a hack, which
miraculously works, to get around that.

The gist is:

- Compile the package natively, replacing calls to the compiler and linker with
  wrappers that store the arguments in a log, and then delegate along to the
  real native compiler and linker.

- Remove all the native build products.

- Play back the log, replacing the native compiler with emscripten and
  adjusting include paths and flags as necessary for cross-compiling to
  emscripten. This overwrites the results from the original native compilation.

While this results in more work than strictly necessary (it builds a native
version of the package, even though we then throw it away), it seems to be the
only reliable way to automatically build a package that interleaves
configuration with build.
"""


from collections import namedtuple
import importlib.machinery
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import shutil
import sys


from typing import List, Dict, Set, Optional, overload

# absolute import is necessary as this file will be symlinked
# under tools
from pyodide_build import common
from pyodide_build._f2c_fixes import fix_f2c_output


symlinks = set(["cc", "c++", "ld", "ar", "gcc", "gfortran"])

ReplayArgs = namedtuple(
    "ReplayArgs",
    [
        "cflags",
        "cxxflags",
        "ldflags",
        "host_install_dir",
        "target_install_dir",
        "replace_libs",
    ],
)


def capture_command(command: str, args: List[str]) -> int:
    """
    This is called when this script is called through a symlink that looks like
    a compiler or linker.

    It writes the arguments to the build.log, and then delegates to the real
    native compiler or linker (unless it decides to skip host compilation).

    Returns
    -------
        The exit code of the real native compiler invocation
    """
    TOOLSDIR = Path(common.get_make_flag("TOOLSDIR"))
    # Remove the symlink compiler from the PATH, so we can delegate to the
    # native compiler
    env = dict(os.environ)
    path = env["PATH"]
    while str(TOOLSDIR) + ":" in path:
        path = path.replace(str(TOOLSDIR) + ":", "")
    env["PATH"] = path

    skip_host = "SKIP_HOST" in os.environ

    # Skip compilations of C/Fortran extensions for the target environment.
    # We still need to generate the output files for distutils to continue
    # the build.
    # TODO: This may need slight tuning for new projects. In particular,
    #       currently ar is not skipped, so a known failure would happen when
    #       we create some object files (that are empty as gcc is skipped), on
    #       which we run the actual ar command.
    skip = False
    if (
        command in ["gcc", "cc", "c++", "gfortran", "ld"]
        and "-o" in args
        # do not skip numpy as it is needed as build time
        # dependency by other packages (e.g. matplotlib)
        and skip_host
    ):
        out_idx = args.index("-o")
        if (out_idx + 1) < len(args):
            # get the index of the output file path
            out_idx += 1
            with open(args[out_idx], "wb") as fh:
                fh.write(b"")
            skip = True

    with open("build.log", "a") as fd:
        # TODO: store skip status in the build.log
        json.dump([command] + args, fd)
        fd.write("\n")

    if skip:
        return 0
    compiler_command = [command]
    if shutil.which("ccache") is not None:
        # Enable ccache if it's installed
        compiler_command.insert(0, "ccache")

    return subprocess.run(compiler_command + args, env=env).returncode


def capture_make_command_wrapper_symlinks(env: Dict[str, str]):
    """
    Makes sure all the symlinks that make this script look like a compiler
    exist.
    """
    TOOLSDIR = Path(common.get_make_flag("TOOLSDIR"))
    exec_path = Path(__file__).resolve()
    for symlink in symlinks:
        symlink_path = TOOLSDIR / symlink
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


def capture_compile(*, host_install_dir: str, skip_host: bool, env: Dict[str, str]):
    TOOLSDIR = Path(common.get_make_flag("TOOLSDIR"))
    env = dict(env)
    env["PATH"] = str(TOOLSDIR) + ":" + env["PATH"]
    capture_make_command_wrapper_symlinks(env)

    cmd = [sys.executable, "setup.py"]
    if skip_host:
        env["SKIP_HOST"] = "1"
        cmd.append("build")
    else:
        assert host_install_dir, "Missing host_install_dir"
        cmd.extend(["install", "--home", host_install_dir])

    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        build_log_path = Path("build.log")
        if build_log_path.exists():
            build_log_path.unlink()
        result.check_returncode()
    clean_out_native_artifacts()


def replay_f2c(args: List[str], dryrun: bool = False) -> Optional[List[str]]:
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
        if arg.endswith(".f"):
            filename = os.path.abspath(arg)
            if not dryrun:
                subprocess.check_call(
                    ["f2c", os.path.basename(filename)], cwd=os.path.dirname(filename)
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


def get_library_output(line: List[str]) -> Optional[str]:
    """
    Check if the command is a linker invocation. If so, return the name of the
    output file.
    """
    for arg in line:
        if arg.endswith(".so") and not arg.startswith("-"):
            return arg
    return None


def parse_replace_libs(replace_libs: str) -> Dict[str, str]:
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
    arg: str, replace_libs: Dict[str, str], used_libs: Set[str]
) -> Optional[str]:
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


def replay_genargs_handle_dashI(arg: str, target_install_dir: str) -> Optional[str]:
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


def replay_genargs_handle_argument(arg: str) -> Optional[str]:
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


def replay_command_generate_args(
    line: List[str], args: ReplayArgs, is_link_command: bool
) -> List[str]:
    """
    A helper command for `replay_command` that generates the new arguments for
    the compilation.

    Unlike `replay_command` this avoids I/O: it doesn't sys.exit, it doesn't run
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
    """
    replace_libs = parse_replace_libs(args.replace_libs)
    cmd = line[0]
    if cmd == "ar":
        new_args = ["emar"]
    elif cmd == "c++" or cmd == "g++":
        new_args = ["em++"]
    elif cmd == "cc" or cmd == "gcc" or cmd == "ld":
        new_args = ["emcc"]
        # distutils doesn't use the c++ compiler when compiling c++ <sigh>
        if any(arg.endswith((".cpp", ".cc")) for arg in line):
            new_args = ["em++"]
    else:
        raise AssertionError(f"Unexpected command {line[0]}")

    if is_link_command:
        new_args.extend(args.ldflags.split())
    elif new_args[0] == "emcc":
        new_args.extend(args.cflags.split())
    elif new_args[0] == "em++":
        new_args.extend(args.cflags.split() + args.cxxflags.split())

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

    used_libs: Set[str] = set()
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

        # don't include libraries from native builds
        if args.host_install_dir and (
            arg.startswith("-L" + args.host_install_dir)
            or arg.startswith("-l" + args.host_install_dir)
        ):
            continue

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


def replay_command(
    line: List[str], args: ReplayArgs, dryrun: bool = False
) -> Optional[List[str]]:
    """Handle a compilation command

    Parameters
    ----------
    line : iterable
       an iterable with the compilation arguments
    args : {object, namedtuple}
       an container with additional compilation options,
       in particular containing ``args.cflags``, ``args.cxxflags``, and ``args.ldflags``
    dryrun : bool, default=False
       if True do not run the resulting command, only return it

    Examples
    --------

    >>> from collections import namedtuple
    >>> Args = namedtuple('args', ['cflags', 'cxxflags', 'ldflags', 'host_install_dir','replace_libs','target_install_dir'])
    >>> args = Args(cflags='', cxxflags='', ldflags='', host_install_dir='',replace_libs='',target_install_dir='')
    >>> replay_command(['gcc', 'test.c'], args, dryrun=True)
    emcc test.c
    ['emcc', 'test.c']
    """
    # some libraries have different names on wasm e.g. png16 = png

    # This is a special case to skip the compilation tests in numpy that aren't
    # actually part of the build
    for arg in line:
        if r"/file.c" in arg or "_configtest" in arg:
            return None
        if re.match(r"/tmp/.*/source\.[bco]+", arg):
            return None
        if arg == "-print-multiarch":
            return None
        if arg.startswith("/tmp"):
            return None
        if arg.startswith("-print-file-name"):
            return None
        if arg == "/dev/null":
            return None

    library_output = get_library_output(line)
    is_link_cmd = library_output is not None

    if line[0] == "gfortran":
        tmp = replay_f2c(line)
        if tmp is None:
            return None
        line = tmp

    new_args = replay_command_generate_args(line, args, is_link_cmd)

    # This can only be used for incremental rebuilds -- it generates
    # an error during clean build of numpy
    # if os.path.isfile(output):
    #     print('SKIPPING: ' + ' '.join(new_args))
    #     return

    print(" ".join(new_args))

    if not dryrun:
        returncode = subprocess.run(new_args).returncode
        if returncode != 0:
            sys.exit(returncode)

    # Emscripten .so files shouldn't have the native platform slug
    if library_output:
        renamed = library_output
        for ext in importlib.machinery.EXTENSION_SUFFIXES:
            if ext == ".so":
                continue
            if renamed.endswith(ext):
                renamed = renamed[: -len(ext)] + ".so"
                break
        if not dryrun and library_output != renamed:
            os.rename(library_output, renamed)
    return new_args


def environment_substitute_args(
    args: Dict[str, str], env: Dict[str, str] = None
) -> Dict[str, str]:
    if env is None:
        env = dict(os.environ)
    subbed_args = {}
    for arg, value in args.items():
        for e_name, e_value in env.items():
            value = value.replace(f"$({e_name})", e_value)
        subbed_args[arg] = value
    return subbed_args


@overload
def replay_compile(
    *,
    cflags: str,
    cxxflags: str,
    ldflags: str,
    host_install_dir: str,
    target_install_dir: str,
    replace_libs: str,
    replay_from: int = 1,
):
    ...


@overload
def replay_compile(*, _this_is_just_here_to_appease_mypy: str):
    ...


def replay_compile(replay_from: int = 1, **kwargs):
    args = ReplayArgs(**environment_substitute_args(kwargs))
    # If pure Python, there will be no build.log file, which is fine -- just do
    # nothing
    build_log_path = Path("build.log")
    if not build_log_path.is_file():
        return

    lines_str = (
        subprocess.check_output(["wc", "-l", str(build_log_path)])
        .decode()
        .split(" ")[0]
    )
    num_lines = str(lines_str)
    with open(build_log_path, "r") as fd:
        num_lines = sum(1 for _1 in fd)  # type: ignore
        fd.seek(0)
        for idx, line_str in enumerate(fd):
            if idx < replay_from - 1:
                continue
            line = json.loads(line_str)
            print(f"[line {idx + 1} of {num_lines}]")
            replay_command(line, args)


def clean_out_native_artifacts():
    for root, dirs, files in os.walk("."):
        for file in files:
            path = Path(root) / file
            if path.suffix in (".o", ".so", ".a"):
                path.unlink()


if __name__ == "__main__":
    basename = Path(sys.argv[0]).name
    if basename in symlinks:
        sys.exit(capture_command(basename, sys.argv[1:]))
    else:
        raise Exception(f"Unexpected invocation '{basename}'")
