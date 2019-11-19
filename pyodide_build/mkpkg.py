#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import urllib.request
import sys
from pathlib import Path


PACKAGES_ROOT = Path(__file__).parent.parent / 'packages'

SDIST_EXTENSIONS = []


def _get_sdist_extensions():
    if SDIST_EXTENSIONS:
        return SDIST_EXTENSIONS

    for format in shutil.get_unpack_formats():
        for ext in format[1]:
            SDIST_EXTENSIONS.append(ext)

    return SDIST_EXTENSIONS


def _extract_sdist(pypi_metadata):
    sdist_extensions = tuple(_get_sdist_extensions())

    # The first one we can use. Usually a .tar.gz
    for entry in pypi_metadata['urls']:
        if entry['filename'].endswith(sdist_extensions):
            return entry

    raise Exception('No sdist URL found for package %s (%s)' % (
        pypi_metadata['info'].get('name'),
        pypi_metadata['info'].get('package_url'),
    ))


def _get_metadata(package):
    url = f'https://pypi.org/pypi/{package}/json'

    with urllib.request.urlopen(url) as fd:
        pypi_metadata = json.load(fd)

    sdist_metadata = _extract_sdist(pypi_metadata)

    return sdist_metadata, pypi_metadata


def make_package(package):
    """
    Creates a template that will work for most pure Python packages,
    but will have to be edited for more complex things.
    """
    import yaml

    sdist_metadata, pypi_metadata = _get_metadata(package)
    url = sdist_metadata['url']
    sha256 = sdist_metadata['digests']['sha256']
    version = pypi_metadata['info']['version']

    yaml_content = {
        'package': {
            'name': package,
            'version': version
        },
        'source': {
            'url': url,
            'sha256': sha256
        },
        'test': {
            'imports': [
                package
            ]
        }
    }

    if not (PACKAGES_ROOT / package).is_dir():
        os.makedirs(PACKAGES_ROOT / package)
    with open(PACKAGES_ROOT / package / 'meta.yaml', 'w') as fd:
        yaml.dump(yaml_content, fd, default_flow_style=False)


def update_package(package):
    import yaml

    with open(PACKAGES_ROOT / package / 'meta.yaml', 'r') as fd:
        yaml_content = yaml.load(fd, Loader=yaml.FullLoader)

    if set(yaml_content.keys()) != set(('package', 'source', 'test')):
        raise ValueError(
            'Only pure-python packages can be updated automatically.')

    sdist_metadata, pypi_metadata = _get_metadata(package)
    pypi_ver = pypi_metadata['info']['version']
    local_ver = yaml_content['package']['version']
    if pypi_ver <= local_ver:
        print(f'Already up to date. Local: {local_ver} Pypi: {pypi_ver}')
        sys.exit(0)
    print(f'Updating {package} from {local_ver} to {pypi_ver}')

    if 'patches' in yaml_content['source']:
        import warnings
        warnings.warn(f"Pyodide applies patches to {package}. Update the "
                       "patches (if needed) to avoid build failing.")

    yaml_content['source']['url'] = sdist_metadata['url']
    yaml_content['source'].pop('md5', None)
    yaml_content['source']['sha256'] = sdist_metadata['digests']['sha256']
    yaml_content['package']['version'] = pypi_metadata['info']['version']
    with open(PACKAGES_ROOT / package / 'meta.yaml', 'w') as fd:
        yaml.dump(yaml_content, fd, default_flow_style=False)


def make_parser(parser):
    parser.description = '''Add or update a python package in pyodide.'''
    parser.add_argument(
        'package', type=str, nargs=1, help="The package name on PyPI")
    parser.add_argument(
        '--update', action='store_true', help='update existing package')
    return parser


def main(args):
    package = args.package[0]
    if args.update:
        return update_package(package)
    return make_package(package)


if __name__ == '__main__':
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
