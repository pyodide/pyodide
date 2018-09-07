import pytest
import os
from pathlib import Path
import sys

BASE_DIR = Path(__file__).parent.parent
PKG_DIR = BASE_DIR / 'packages'

# TODO: remove once we have a proper Python package for common functions
sys.path.append(str(BASE_DIR / 'tools'))
import common  # noqa


def registered_packages():
    """Returns a list of registred package names"""
    packages = [name for name in os.listdir(PKG_DIR)
                if (PKG_DIR / name).is_dir()]
    return packages


def registered_packages_meta():
    """Returns a dictionary with the contents of `meta.yaml`
    for each registed package
    """
    packages = registered_packages
    return {name: common.parse_package(PKG_DIR / name / 'meta.yaml')
            for name in packages}


UNSUPPORTED_PACKAGES = {'chrome': ['pandas'],
                        'firefox': []}


@pytest.mark.parametrize('name', registered_packages())
def test_import(name, selenium_standalone):
    # check that we can parse the meta.yaml
    meta = common.parse_package(PKG_DIR / name / 'meta.yaml')

    if name in UNSUPPORTED_PACKAGES[selenium_standalone.browser]:
        pytest.xfail(
                '{} fails to load and is not supported on {}.'
                .format(name, selenium_standalone.browser))

    for import_name in meta.get('test', {}).get('imports', []):
        selenium_standalone.load_package(name)
        try:
            selenium_standalone.run('import %s' % import_name)
        except Exception as e:
            print(selenium_standalone.logs)
