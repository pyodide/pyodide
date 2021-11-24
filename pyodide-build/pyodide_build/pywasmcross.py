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


import argparse
import importlib.machinery
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import shutil
import sys


# absolute import is necessary as this file will be symlinked
# under tools
from pyodide_build import common
from pyodide_build._f2c_fixes import fix_f2c_clapack_calls


symlinks = set(["cc", "c++", "ld", "ar", "gcc", "gfortran"])


class EnvironmentRewritingArgument(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        for e_name, e_value in os.environ.items():
            values = values.replace(f"$({e_name})", e_value)
        setattr(namespace, self.dest, values)


def collect_args(basename):
    """
    This is called when this script is called through a symlink that looks like
    a compiler or linker.

    It writes the arguments to the build.log, and then delegates to the real
    native compiler or linker.
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
        basename in ["gcc", "cc", "c++", "gfortran", "ld"]
        and "-o" in sys.argv[1:]
        # do not skip numpy as it is needed as build time
        # dependency by other packages (e.g. matplotlib)
        and skip_host
    ):
        out_idx = sys.argv.index("-o")
        if (out_idx + 1) < len(sys.argv):
            # get the index of the output file path
            out_idx += 1
            with open(sys.argv[out_idx], "wb") as fh:
                fh.write(b"")
            skip = True

    with open("build.log", "a") as fd:
        # TODO: store skip status in the build.log
        json.dump([basename] + sys.argv[1:], fd)
        fd.write("\n")

    if skip:
        sys.exit(0)
    compiler_command = [basename]
    if shutil.which("ccache") is not None:
        # Enable ccache if it's installed
        compiler_command.insert(0, "ccache")

    sys.exit(subprocess.run(compiler_command + sys.argv[1:], env=env).returncode)


def make_symlinks(env):
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


def capture_compile(args):
    TOOLSDIR = Path(common.get_make_flag("TOOLSDIR"))
    env = dict(os.environ)
    make_symlinks(env)
    env["PATH"] = str(TOOLSDIR) + ":" + os.environ["PATH"]

    cmd = [sys.executable, "setup.py", "install"]
    if args.install_dir == "skip":
        cmd[-1] = "build"
    elif args.install_dir != "":
        cmd.extend(["--home", args.install_dir])

    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        build_log_path = Path("build.log")
        if build_log_path.exists():
            build_log_path.unlink()
        sys.exit(result.returncode)


def f2c(args, dryrun=False):
    """Apply f2c to compilation arguments

    Parameters
    ----------
    args : iterable
       input compiler arguments
    dryrun : bool, default=True
       if False run f2c on detected fortran files

    Returns
    -------
    new_args : list
       output compiler arguments


    Examples
    --------

    >>> f2c(['gfortran', 'test.f'], dryrun=True)
    ['gfortran', 'test.c']
    """
    new_args = []
    found_source = False
    for arg in args:
        if arg.endswith(".f"):
            filename = os.path.abspath(arg)
            if not dryrun:
                subprocess.check_call(
                    ["f2c", os.path.basename(filename)], cwd=os.path.dirname(filename)
                )
                fix_f2c_clapack_calls(arg[:-2] + ".c")
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


def handle_command(line, args, dryrun=False):
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
    >>> Args = namedtuple('args', ['cflags', 'cxxflags', 'ldflags', 'host','replace_libs','install_dir'])
    >>> args = Args(cflags='', cxxflags='', ldflags='', host='',replace_libs='',install_dir='')
    >>> handle_command(['gcc', 'test.c'], args, dryrun=True)
    emcc test.c
    ['emcc', 'test.c']
    """
    # some libraries have different names on wasm e.g. png16 = png
    replace_libs = {}
    for l in args.replace_libs.split(";"):
        if len(l) > 0:
            from_lib, to_lib = l.split("=")
            replace_libs[from_lib] = to_lib

    # This is a special case to skip the compilation tests in numpy that aren't
    # actually part of the build
    for arg in line:
        if r"/file.c" in arg or "_configtest" in arg:
            return
        if re.match(r"/tmp/.*/source\.[bco]+", arg):
            return
        if arg == "-print-multiarch":
            return
        if arg.startswith("/tmp"):
            return

    if line[0] == "gfortran":
        result = f2c(line)
        if result is None:
            return
        line = result
        new_args = ["emcc"]
    elif line[0] == "ar":
        new_args = ["emar"]
    elif line[0] == "c++":
        new_args = ["em++"]
    else:
        new_args = ["emcc"]
        # distutils doesn't use the c++ compiler when compiling c++ <sigh>
        if any(arg.endswith((".cpp", ".cc")) for arg in line):
            new_args = ["em++"]
    library_output = False
    for arg in line:
        if arg.endswith(".so") and not arg.startswith("-"):
            library_output = True

    if library_output:
        new_args.extend(args.ldflags.split())
    elif new_args[0] == "emcc":
        new_args.extend(args.cflags.split())
    elif new_args[0] == "em++":
        new_args.extend(args.cflags.split() + args.cxxflags.split())

    optflags_valid = [f"-O{tok}" for tok in "01234sz"]
    optflag = None
    # Identify the optflag (e.g. -O3) in cflags/cxxflags/ldflags. Last one has
    # priority.
    for arg in new_args[::-1]:
        if arg in optflags_valid:
            optflag = arg
            break

    used_libs = set()

    # Go through and adjust arguments
    for arg in line[1:]:
        if arg in optflags_valid and optflag is not None and arg != optflag:
            # There are multiple contradictory optflags provided, use the one
            # from cflags/cxxflags/ldflags
            continue

        if arg.startswith("-I"):
            if (
                str(Path(arg[2:]).resolve()).startswith(sys.prefix + "/include/python")
                and "site-packages" not in arg
            ):
                arg = arg.replace("-I" + sys.prefix, "-I" + args.target)
            # Don't include any system directories
            elif arg[2:].startswith("/usr"):
                continue
        # Don't include any system directories
        if arg.startswith("-L/usr"):
            continue
        if arg.startswith("-l"):
            for lib_name in replace_libs.keys():
                # this enables glob style **/* matching
                if PurePosixPath(arg[2:]).match(lib_name):
                    if len(replace_libs[lib_name]) > 0:
                        arg = "-l" + replace_libs[lib_name]
                    else:
                        continue
        if arg.startswith("-l"):
            # WASM link doesn't like libraries being included twice
            # skip second one
            if arg in used_libs:
                continue
            used_libs.add(arg)
        # some gcc flags that clang does not support actually
        if arg == "-Bsymbolic-functions":
            continue
        # ignore some link flags
        # it should not check if `arg == "-Wl,-xxx"` and ignore directly here,
        # because arg may be something like "-Wl,-xxx,-yyy" where we only want
        # to ignore "-xxx" but not "-yyy".
        if arg.startswith("-Wl"):
            arg = arg.replace(",-Bsymbolic-functions", "")
            # breaks emscripten see https://github.com/emscripten-core/emscripten/issues/14460
            arg = arg.replace(",--strip-all", "")
            # wasm-ld does not regconize some link flags
            arg = arg.replace(",--sort-common", "")
            arg = arg.replace(",--as-needed", "")
            if arg == "-Wl":
                continue
        # threading is disabled for now
        if arg == "-pthread":
            continue
        # this only applies to compiling fortran code, but we already f2c'd
        if arg == "-ffixed-form":
            continue
        # On Mac, we need to omit some darwin-specific arguments
        if arg in ["-bundle", "-undefined", "dynamic_lookup"]:
            continue
        if arg == "-lffi":
            continue
        # This flag is needed to build numpy with SIMD optimization
        if arg == "-mpopcnt":
            continue
        # The native build is possibly multithreaded, but the emscripten one
        # definitely isn't
        arg = re.sub(r"/python([0-9]\.[0-9]+)m", r"/python\1", arg)
        if arg.endswith(".so"):
            output = arg
        # don't include libraries from native builds
        if (
            len(args.install_dir) > 0
            and arg.startswith("-l" + args.install_dir)
            or arg.startswith("-L" + args.install_dir)
        ):
            continue

        if new_args[-1].startswith("-B") and "compiler_compat" in arg:
            # conda uses custom compiler search paths with the compiler_compat folder.
            # Ignore it.
            del new_args[-1]
            continue

        # ignore unsupported --sysroot compile argument used in conda
        if arg.startswith("-Wl,--sysroot"):
            continue

        # See https://github.com/emscripten-core/emscripten/issues/8650
        if arg in ["-lfreetype", "-lz", "-lpng", "-lgfortran"]:
            continue
        # don't use -shared, SIDE_MODULE is already used
        # and -shared breaks it
        if arg in ["-shared"]:
            continue

        new_args.append(arg)

    # This can only be used for incremental rebuilds -- it generates
    # an error during clean build of numpy
    # if os.path.isfile(output):
    #     print('SKIPPING: ' + ' '.join(new_args))
    #     return

    print(" ".join(new_args))

    if not dryrun:
        result = subprocess.run(new_args)
        if result.returncode != 0:
            sys.exit(result.returncode)

    # Emscripten .so files shouldn't have the native platform slug
    if library_output:
        renamed = output
        for ext in importlib.machinery.EXTENSION_SUFFIXES:
            if ext == ".so":
                continue
            if renamed.endswith(ext):
                renamed = renamed[: -len(ext)] + ".so"
                break
        if not dryrun and output != renamed:
            os.rename(output, renamed)
    return new_args


def replay_compile(args):
    # If pure Python, there will be no build.log file, which is fine -- just do
    # nothing
    build_log_path = Path("build.log")
    if build_log_path.is_file():
        with open(build_log_path, "r") as fd:
            for line in fd:
                line = json.loads(line)
                handle_command(line, args)


def clean_out_native_artifacts():
    for root, dirs, files in os.walk("."):
        for file in files:
            path = Path(root) / file
            if path.suffix in (".o", ".so", ".a"):
                path.unlink()


def install_for_distribution(args):
    commands = [
        sys.executable,
        "setup.py",
        "install",
        "--skip-build",
        "--prefix=install",
        "--old-and-unmanageable",
    ]
    try:
        subprocess.check_call(commands)
    except Exception:
        print(
            f'Warning: {" ".join(str(arg) for arg in commands)} failed '
            f"with distutils, possibly due to the use of distutils "
            f"that does not support the --old-and-unmanageable "
            "argument. Re-trying the install without this argument."
        )
        subprocess.check_call(commands[:-1])


def build_wrap(args):
    build_log_path = Path("build.log")
    if not build_log_path.is_file():
        capture_compile(args)
    clean_out_native_artifacts()
    replay_compile(args)
    install_for_distribution(args)


def make_parser(parser):
    basename = Path(sys.argv[0]).name
    if basename in symlinks:
        # skip parsing of all arguments
        parser._actions = []
    else:
        parser.description = (
            "Cross compile a Python distutils package. "
            "Run from the root directory of the package's source.\n\n"
            "Note: this is a private endpoint that should not be used "
            "outside of the Pyodide Makefile."
        )
        parser.add_argument(
            "--cflags",
            type=str,
            nargs="?",
            default=common.get_make_flag("SIDE_MODULE_CFLAGS"),
            help="Extra compiling flags",
            action=EnvironmentRewritingArgument,
        )
        parser.add_argument(
            "--cxxflags",
            type=str,
            nargs="?",
            default=common.get_make_flag("SIDE_MODULE_CXXFLAGS"),
            help="Extra C++ specific compiling flags",
            action=EnvironmentRewritingArgument,
        )
        parser.add_argument(
            "--ldflags",
            type=str,
            nargs="?",
            default=common.get_make_flag("SIDE_MODULE_LDFLAGS"),
            help="Extra linking flags",
            action=EnvironmentRewritingArgument,
        )
        parser.add_argument(
            "--target",
            type=str,
            nargs="?",
            default=common.get_make_flag("TARGETPYTHONROOT"),
            help="The path to the target Python installation",
        )
        parser.add_argument(
            "--install-dir",
            type=str,
            nargs="?",
            default="",
            help=(
                "Directory for installing built host packages. Defaults to setup.py "
                "default. Set to 'skip' to skip installation. Installation is "
                "needed if you want to build other packages that depend on this one."
            ),
        )
        parser.add_argument(
            "--replace-libs",
            type=str,
            nargs="?",
            default="",
            help="Libraries to replace in final link",
            action=EnvironmentRewritingArgument,
        )
    return parser


def main(args):
    basename = Path(sys.argv[0]).name
    if basename in symlinks:
        collect_args(basename)
    else:
        build_wrap(args)


if __name__ == "__main__":
    basename = Path(sys.argv[0]).name
    if basename in symlinks:
        main(None)
    else:
        parser = make_parser(argparse.ArgumentParser())
        args = parser.parse_args()
        main(args)
