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


@pytest.mark.parametrize('name', registered_packages())
def test_meta(selenium, name):
    # check that we can parse the meta.yaml
    meta = common.parse_package(PKG_DIR / name / 'meta.yaml')

    # check imports
    for import_name in meta.get('test', {}).get('imports', []):
        selenium.load_package(import_name)
        selenium.run('import %s' % import_name)
