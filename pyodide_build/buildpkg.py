#!/usr/bin/env python3

"""
Builds a Pyodide package.
"""

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess


from . import common


def check_checksum(path, pkg):
    """
    Checks that a tarball matches the checksum in the package metadata.
    """
    checksum_keys = {'md5', 'sha256'}.intersection(pkg['source'])
    if not checksum_keys:
        return
    elif len(checksum_keys) != 1:
        raise ValueError('Only one checksum should be included in a package '
                         'setup; found {}.'.format(checksum_keys))
    checksum_algorithm = checksum_keys.pop()
    checksum = pkg['source'][checksum_algorithm]
    CHUNK_SIZE = 1 << 16
    h = getattr(hashlib, checksum_algorithm)()
    with open(path, 'rb') as fd:
        while True:
            chunk = fd.read(CHUNK_SIZE)
            h.update(chunk)
            if len(chunk) < CHUNK_SIZE:
                break
    if h.hexdigest() != checksum:
        raise ValueError("Invalid {} checksum".format(checksum_algorithm))


def download_and_extract(buildpath, packagedir, pkg, args):
    tarballpath = buildpath / Path(pkg['source']['url']).name
    if not tarballpath.is_file():
        subprocess.run([
            'wget', '-q', '-O', str(tarballpath), pkg['source']['url']
        ], check=True)
        check_checksum(tarballpath, pkg)
    srcpath = buildpath / packagedir
    if not srcpath.is_dir():
        shutil.unpack_archive(str(tarballpath), str(buildpath))
    return srcpath


def patch(path, srcpath, pkg, args):
    if (srcpath / '.patched').is_file():
        return

    # Apply all of the patches
    orig_dir = Path.cwd()
    pkgdir = path.parent.resolve()
    os.chdir(srcpath)
    try:
        for patch in pkg['source'].get('patches', []):
            subprocess.run([
                'patch', '-p1', '--binary', '-i', pkgdir / patch
            ], check=True)
    finally:
        os.chdir(orig_dir)

    # Add any extra files
    for src, dst in pkg['source'].get('extras', []):
        shutil.copyfile(pkgdir / src, srcpath / dst)

    with open(srcpath / '.patched', 'wb') as fd:
        fd.write(b'\n')


def compile(path, srcpath, pkg, args):
    if (srcpath / '.built').is_file():
        return

    orig_dir = Path.cwd()
    os.chdir(srcpath)
    env = dict(os.environ)
    if pkg.get('build', {}).get('skip_host', True):
        env['SKIP_HOST'] = ''

    try:
        subprocess.run([
            str(Path(args.host) / 'bin' / 'python3'),
            '-m', 'pyodide_build', 'pywasmcross',
            '--cflags',
            args.cflags + ' ' +
            pkg.get('build', {}).get('cflags', ''),
            '--ldflags',
            args.ldflags + ' ' +
            pkg.get('build', {}).get('ldflags', ''),
            '--host', args.host,
            '--target', args.target], env=env, check=True)
    finally:
        os.chdir(orig_dir)

    post = pkg.get('build', {}).get('post')
    if post is not None:
        site_packages_dir = (
            srcpath / 'install' / 'lib' / 'python3.7' / 'site-packages')
        pkgdir = path.parent.resolve()
        env = {
            'SITEPACKAGES': site_packages_dir,
            'PKGDIR': pkgdir
        }
        subprocess.run([
            'bash', '-c', post], env=env, check=True)

    with open(srcpath / '.built', 'wb') as fd:
        fd.write(b'\n')


def package_files(buildpath, srcpath, pkg, args):
    if (buildpath / '.packaged').is_file():
        return

    name = pkg['package']['name']
    install_prefix = (srcpath / 'install').resolve()
    subprocess.run([
        'python',
        common.ROOTDIR / 'file_packager.py',
        name + '.data',
        '--abi={0}'.format(args.package_abi),
        '--lz4',
        '--preload',
        '{}@/'.format(install_prefix),
        '--js-output={}'.format(name + '.js'),
        '--export-name=pyodide._module',
        '--exclude', '*.wasm.pre',
        '--exclude', '*__pycache__*',
        '--use-preload-plugins'],
        cwd=buildpath, check=True)
    subprocess.run([
        'uglifyjs',
        buildpath / (name + '.js'),
        '-o',
        buildpath / (name + '.js')], check=True)

    with open(buildpath / '.packaged', 'wb') as fd:
        fd.write(b'\n')


def build_package(path, args):
    pkg = common.parse_package(path)
    packagedir = pkg['package']['name'] + '-' + pkg['package']['version']
    dirpath = path.parent
    orig_path = Path.cwd()
    os.chdir(dirpath)
    try:
        buildpath = dirpath / 'build'
        if not buildpath.resolve().is_dir():
            os.makedirs(buildpath)
        srcpath = download_and_extract(buildpath, packagedir, pkg, args)
        patch(path, srcpath, pkg, args)
        compile(path, srcpath, pkg, args)
        package_files(buildpath, srcpath, pkg, args)
    finally:
        os.chdir(orig_path)


def make_parser(parser):
    parser.description = 'Build a pyodide package.'
    parser.add_argument(
        'package', type=str, nargs=1,
        help="Path to meta.yaml package description")
    parser.add_argument(
        '--package_abi', type=int, required=True,
        help='The ABI number for the package to be built')
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
    path = Path(args.package[0]).resolve()
    build_package(path, args)


if __name__ == '__main__':
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
