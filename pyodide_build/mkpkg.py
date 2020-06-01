#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import urllib.request
from pathlib import Path

PACKAGES_ROOT = Path(__file__).parent.parent / 'packages'

SDIST_EXTENSIONS = []


def get_sdist_extensions():
    if SDIST_EXTENSIONS:
        return SDIST_EXTENSIONS

    for format in shutil.get_unpack_formats():
        for ext in format[1]:
            SDIST_EXTENSIONS.append(ext)

    return SDIST_EXTENSIONS


def get_sdist_url_entry(json_content):
    sdist_extensions_tuple = tuple(get_sdist_extensions())

    for entry in json_content['urls']:
        if entry['filename'].endswith(sdist_extensions_tuple):
            return entry

    raise Exception('No sdist URL found for package %s (%s)' % (
        json_content['info'].get('name'),
        json_content['info'].get('package_url'),
    ))


def make_package(package, version=None):
    import yaml

    version = ('/' + version) if version is not None else ''
    url = f"https://pypi.org/pypi/{package}{version}/json"

    with urllib.request.urlopen(url) as fd:
        json_content = json.load(fd)

    entry = get_sdist_url_entry(json_content)
    download_url = entry['url']
    sha256 = entry['digests']['sha256']
    version = json_content['info']['version']

    yaml_content = {
        'package': {
            'name': package,
            'version': version
        },
        'source': {
            'url': download_url,
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


def make_parser(parser):
    parser.description = '''
Make a new pyodide package. Creates a simple template that will work
for most pure Python packages, but will have to be edited for more wv
complex things.'''.strip()
    parser.add_argument(
        'package', type=str, nargs=1,
        help="The package name on PyPI")
    parser.add_argument(
        '--version', type=str, default=None,
        help="Package version string, "
             "e.g. v1.2.1 (defaults to latest stable release)")
    return parser


def main(args):
    package = args.package[0]
    make_package(package, args.version)


if __name__ == '__main__':
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
