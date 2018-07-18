#!/usr/bin/env python3

"""Helper for cross-compiling distutils-based Python extensions.

distutils has never had a proper cross-compilation story. This is a hack, which
miraculously works, to get around that.

The gist is:

- Compile the package natively, replacing calls to the compiler and linker with
  wrappers that store the arguments in a log, and then delegate along to the
  real native compiler and linker.

- Remove all of the native build products.

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
from pathlib import Path
import re
import subprocess
import sys


# absolute import is necessary as this file will be symlinked
# under tools
from pyodide_build import common


ROOTDIR = common.ROOTDIR
symlinks = set(['cc', 'c++', 'ld', 'ar', 'gcc'])
symlinks = set(['cc', 'c++', 'ld', 'ar', 'gcc', 'gfortran'])


def collect_args(basename):
    """
    This is called when this script is called through a symlink that looks like
    a compiler or linker.

    It writes the arguments to the build.log, and then delegates to the real
    native compiler or linker.
    """
    # Remove the symlink compiler from the PATH, so we can delegate to the
    # native compiler
    env = dict(os.environ)
    path = env['PATH']
    while str(ROOTDIR) + ':' in path:
        path = path.replace(str(ROOTDIR) + ':', '')
    env['PATH'] = path

    with open('build.log', 'a') as fd:
        json.dump([basename] + sys.argv[1:], fd)
        fd.write('\n')

    sys.exit(
        subprocess.run(
            [basename] + sys.argv[1:],
            env=env).returncode)


def make_symlinks(env):
    """
    Makes sure all of the symlinks that make this script look like a compiler
    exist.
    """
    exec_path = Path(__file__).resolve()
    for symlink in symlinks:
        symlink_path = ROOTDIR / symlink
        if os.path.lexists(symlink_path) and not symlink_path.exists():
            # remove broken symlink so it can be re-created
            symlink_path.unlink()
        if not symlink_path.exists():
            symlink_path.symlink_to(exec_path)
        if symlink == 'c++':
            var = 'CXX'
        else:
            var = symlink.upper()
        env[var] = symlink


def capture_compile(args):
    env = dict(os.environ)
    make_symlinks(env)
    env['PATH'] = str(ROOTDIR) + ':' + os.environ['PATH']

    result = subprocess.run(
        [Path(args.host) / 'bin' / 'python3',
         'setup.py',
         'install'], env=env)
    if result.returncode != 0:
        build_log_path = Path('build.log')
        if build_log_path.exists():
            build_log_path.unlink()
        sys.exit(result.returncode)


def f2c(args):
    new_args = []
    found_source = False
    for arg in args:
        if arg.endswith('.f'):
            filename = os.path.abspath(arg)
            subprocess.check_call(
                ['f2c', os.path.basename(filename)],
                cwd=os.path.dirname(filename))
            new_args.append(arg[:-2] + '.c')
            found_source = True
        else:
            new_args.append(arg)
    if not found_source:
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
       in particular containing ``args.cflags`` and ``args.ldflags``
    dryrun : bool, default=False
       if True do not run the resulting command, only return it

    Examples
    --------

    >>> from collections import namedtuple
    >>> Args = namedtuple('args', ['cflags', 'ldflags'])
    >>> args = Args(cflags='', ldflags='')
    >>> handle_command(['gcc', 'test.c'], args, dryrun=True)
    emcc test.c
    ['emcc', 'test.c']
    """
    # This is a special case to skip the compilation tests in numpy that aren't
    # actually part of the build
    for arg in line:
        if r'/file.c' in arg or '_configtest' in arg:
            return
        if re.match(r'/tmp/.*/source\.[bco]+', arg):
            return
        if arg == '-print-multiarch':
            return
        if arg.startswith('/tmp'):
            return

    if line[0] == 'gfortran':
        result = f2c(line)
        if result is None:
            return
        line = result
        new_args = ['emcc']
    elif line[0] == 'ar':
        new_args = ['emar']
    elif line[0] == 'c++':
        new_args = ['em++']
    else:
        new_args = ['emcc']
        # distutils doesn't use the c++ compiler when compiling c++ <sigh>
        if any(arg.endswith('.cpp') for arg in line):
            new_args = ['em++']
    shared = '-shared' in line

    if shared:
        new_args.extend(args.ldflags.split())
    elif new_args[0] in ('emcc', 'em++'):
        new_args.extend(args.cflags.split())
    if new_args[0] == 'em++':
        new_args.append('-std=c++98')

    # Go through and adjust arguments
    for arg in line[1:]:
        if arg.startswith('-I'):
            # Don't include any system directories
            if arg[2:].startswith('/usr'):
                continue
            if (str(Path(arg[2:]).resolve()).startswith(args.host) and
                    'site-packages' not in arg):
                arg = arg.replace('-I' + args.host, '-I' + args.target)
        # Don't include any system directories
        if arg.startswith('-L/usr'):
            continue
        # The native build is possibly multithreaded, but the emscripten one
        # definitely isn't
        arg = re.sub(r'/python([0-9]\.[0-9]+)m', r'/python\1', arg)
        if arg.endswith('.o'):
            arg = arg[:-2] + '.bc'
            output = arg
        elif shared and arg.endswith('.so'):
            arg = arg[:-3] + '.wasm'
            output = arg
        new_args.append(arg)

    if os.path.isfile(output):
        print('SKIPPING: ' + ' '.join(new_args))
        return

    print(' '.join(new_args))

    if not dryrun:
        result = subprocess.run(new_args)
        if result.returncode != 0:
            sys.exit(result.returncode)

    # Emscripten .so files shouldn't have the native platform slug
    if shared:
        renamed = output[:-5] + '.so'
        for ext in importlib.machinery.EXTENSION_SUFFIXES:
            if ext == '.so':
                continue
            if renamed.endswith(ext):
                renamed = renamed[:-len(ext)] + '.so'
                break
        if not dryrun:
            os.rename(output, renamed)
    return new_args


def replay_compile(args):
    # If pure Python, there will be no build.log file, which is fine -- just do
    # nothing
    build_log_path = Path('build.log')
    if build_log_path.is_file():
        with open(build_log_path, 'r') as fd:
            for line in fd:
                line = json.loads(line)
                handle_command(line, args)


def clean_out_native_artifacts():
    for root, dirs, files in os.walk('.'):
        for file in files:
            path = Path(root) / file
            if path.suffix in ('.o', '.so', '.a'):
                path.unlink()


def install_for_distribution(args):
    subprocess.check_call(
        [Path(args.host) / 'bin' / 'python3',
         'setup.py',
         'install',
         '--skip-build',
         '--prefix=install',
         '--old-and-unmanageable'])


def build_wrap(args):
    build_log_path = Path('build.log')
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
            'Cross compile a Python distutils package. '
            'Run from the root directory of the package\'s source')
        parser.add_argument(
            '--cflags', type=str, nargs='?', default=common.DEFAULTCFLAGS,
            help='Extra compiling flags')
        parser.add_argument(
            '--ldflags', type=str, nargs='?', default=common.DEFAULTLDFLAGS,
            help='Extra linking flags')
        parser.add_argument(
            '--host', type=str, nargs='?', default=common.HOSTPYTHON,
            help='The path to the host Python installation')
        parser.add_argument(
            '--target', type=str, nargs='?', default=common.TARGETPYTHON,
            help='The path to the target Python installation')
    return parser


def main(args):
    basename = Path(sys.argv[0]).name
    if basename in symlinks:
        collect_args(basename)
    else:
        build_wrap(args)


if __name__ == '__main__':
    basename = Path(sys.argv[0]).name
    if basename in symlinks:
        main(None)
    else:
        parser = make_parser(argparse.ArgumentParser())
        args = parser.parse_args()
        main(args)
