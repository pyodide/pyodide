#!/usr/bin/env python3

import argparse
import json
import os
from pathlib import Path
import urllib.request


PACKAGES_ROOT = Path(__file__).parent.parent / 'packages'


def make_package(package):
    import yaml

    url = f'https://pypi.org/pypi/{package}/json'

    with urllib.request.urlopen(url) as fd:
        json_content = json.load(fd)

    entry = json_content['urls'][0]
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
    return parser


def main(args):
    package = args.package[0]
    make_package(package)


if __name__ == '__main__':
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
