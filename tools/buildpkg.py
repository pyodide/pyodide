#!/usr/bin/env python3

"""
Builds a Pyodide package.
"""

import argparse
import hashlib
import os
import shutil
import subprocess


import common


ROOTDIR = os.path.abspath(os.path.dirname(__file__))


def check_checksum(path, pkg):
    """
    Checks that a tarball matches the checksum in the package metadata.
    """
    if 'md5' not in pkg['source']:
        return
    checksum = pkg['source']['md5']
    CHUNK_SIZE = 1 << 16
    h = hashlib.md5()
    with open(path, 'rb') as fd:
        while True:
            chunk = fd.read(CHUNK_SIZE)
            h.update(chunk)
            if len(chunk) < CHUNK_SIZE:
                break
    if h.hexdigest() != checksum:
        raise ValueError("Invalid checksum")


def download_and_extract(buildpath, packagedir, pkg, args):
    tarballpath = os.path.join(
        buildpath, os.path.basename(pkg['source']['url']))
    if not os.path.isfile(tarballpath):
        subprocess.run([
            'wget', '-q', '-O', tarballpath, pkg['source']['url']
        ], check=True)
        check_checksum(tarballpath, pkg)
    srcpath = os.path.join(buildpath, packagedir)
    if not os.path.isdir(srcpath):
        shutil.unpack_archive(tarballpath, buildpath)
    return srcpath


def patch(path, srcpath, pkg, args):
    if os.path.isfile(os.path.join(srcpath, '.patched')):
        return

    # Apply all of the patches
    orig_dir = os.getcwd()
    pkgdir = os.path.abspath(os.path.dirname(path))
    os.chdir(srcpath)
    try:
        for patch in pkg['source'].get('patches', []):
            subprocess.run([
                'patch', '-p1', '--binary', '-i', os.path.join(pkgdir, patch)
            ], check=True)
    finally:
        os.chdir(orig_dir)

    # Add any extra files
    for src, dst in pkg['source'].get('extras', []):
        shutil.copyfile(os.path.join(pkgdir, src), os.path.join(srcpath, dst))

    with open(os.path.join(srcpath, '.patched'), 'wb') as fd:
        fd.write(b'\n')


def get_libdir(srcpath, args):
    # Get the name of the build/lib.XXX directory that distutils wrote its
    # output to
    slug = subprocess.check_output([
        os.path.join(args.host, 'bin', 'python3'),
        '-c',
        'import sysconfig, sys; '
        'print("{}-{}.{}".format('
        'sysconfig.get_platform(), '
        'sys.version_info[0], '
        'sys.version_info[1]))']).decode('ascii').strip()
    purelib = os.path.join(srcpath, 'build', 'lib')
    if os.path.isdir(purelib):
        libdir = purelib
    else:
        libdir = os.path.join(srcpath, 'build', 'lib.' + slug)
    return libdir


def compile(path, srcpath, pkg, args):
    if os.path.isfile(os.path.join(srcpath, '.built')):
        return

    orig_dir = os.getcwd()
    os.chdir(srcpath)
    try:
        subprocess.run([
            os.path.join(args.host, 'bin', 'python3'),
            os.path.join(ROOTDIR, 'pywasmcross'),
            '--cflags',
            args.cflags + ' ' +
            pkg.get('build', {}).get('cflags', ''),
            '--ldflags',
            args.ldflags + ' ' +
            pkg.get('build', {}).get('ldflags', ''),
            '--host', args.host,
            '--target', args.target], check=True)
    finally:
        os.chdir(orig_dir)

    post = pkg.get('build', {}).get('post')
    if post is not None:
        libdir = get_libdir(srcpath, args)
        pkgdir = os.path.abspath(os.path.dirname(path))
        env = {
            'BUILD': libdir,
            'PKGDIR': pkgdir
        }
        subprocess.run([
            'bash', '-c', post], env=env, check=True)

    with open(os.path.join(srcpath, '.built'), 'wb') as fd:
        fd.write(b'\n')


def package_files(buildpath, srcpath, pkg, args):
    if os.path.isfile(os.path.join(buildpath, '.packaged')):
        return

    name = pkg['package']['name']
    libdir = get_libdir(srcpath, args)
    subprocess.run([
        'python2',
        os.path.join(os.environ['EMSCRIPTEN'], 'tools', 'file_packager.py'),
        os.path.join(buildpath, name + '.data'),
        '--preload',
        '{}@/lib/python3.6/site-packages'.format(libdir),
        '--js-output={}'.format(os.path.join(buildpath, name + '.js')),
        '--export-name=pyodide',
        '--exclude', '*.wasm.pre',
        '--exclude', '__pycache__',
        '--use-preload-plugins'], check=True)
    subprocess.run([
        'uglifyjs',
        os.path.join(buildpath, name + '.js'),
        '-o',
        os.path.join(buildpath, name + '.js')], check=True)

    with open(os.path.join(buildpath, '.packaged'), 'wb') as fd:
        fd.write(b'\n')


def build_package(path, args):
    pkg = common.parse_package(path)
    packagedir = pkg['package']['name'] + '-' + pkg['package']['version']
    dirpath = os.path.dirname(path)
    orig_path = os.getcwd()
    os.chdir(dirpath)
    try:
        buildpath = os.path.join(dirpath, 'build')
        if not os.path.exists(buildpath):
            os.makedirs(buildpath)
        srcpath = download_and_extract(buildpath, packagedir, pkg, args)
        patch(path, srcpath, pkg, args)
        compile(path, srcpath, pkg, args)
        package_files(buildpath, srcpath, pkg, args)
    finally:
        os.chdir(orig_path)


def parse_args():
    parser = argparse.ArgumentParser('Build a pyodide package.')
    parser.add_argument(
        'package', type=str, nargs=1,
        help="Path to meta.yaml package description")
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
    return parser.parse_args()


def main(args):
    path = os.path.abspath(args.package[0])
    build_package(path, args)


if __name__ == '__main__':
    args = parse_args()
    main(args)
