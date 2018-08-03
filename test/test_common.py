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
    packages = [name for name in os.listdir(PKG_DIR)
                if (PKG_DIR / name).is_dir()]
    return packages


@pytest.mark.parametrize('name', registered_packages())
def test_meta(selenium, name):
    # check that we can parse the meta.yaml
    meta = common.parse_package(PKG_DIR / name / 'meta.yaml')

    if 'test' in meta:
        if 'imports' in meta['test']:
            # check imports
            for import_name in meta['test']['imports']:
                selenium.load_package(import_name)
                selenium.run('import %s' % import_name)
