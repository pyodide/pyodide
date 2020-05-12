import pytest
import os
from pathlib import Path
from pyodide_build.common import parse_package, _parse_package_subset

BASE_DIR = Path(__file__).parent.parent
PKG_DIR = BASE_DIR / 'packages'


def registered_packages():
    """Returns a list of registered package names"""
    packages = [name for name in os.listdir(PKG_DIR)
                if (PKG_DIR / name).is_dir()]
    return packages


def registered_packages_meta():
    """Returns a dictionary with the contents of `meta.yaml`
    for each registered package
    """
    packages = registered_packages
    return {name: parse_package(PKG_DIR / name / 'meta.yaml')
            for name in packages}


UNSUPPORTED_PACKAGES = {'chrome': ['pandas', 'scipy', 'scikit-learn'],
                        'firefox': []}


@pytest.mark.parametrize('name', registered_packages())
def test_parse_package(name):
    # check that we can parse the meta.yaml
    meta = parse_package(PKG_DIR / name / 'meta.yaml')

    skip_host = meta.get('build', {}).get('skip_host', True)
    if name == 'numpy':
        assert skip_host is False
    elif name == 'pandas':
        assert skip_host is True


@pytest.mark.parametrize('name', registered_packages())
def test_import(name, selenium_standalone):
    # check that we can parse the meta.yaml
    meta = parse_package(PKG_DIR / name / 'meta.yaml')

    if name in UNSUPPORTED_PACKAGES[selenium_standalone.browser]:
        pytest.xfail(
                '{} fails to load and is not supported on {}.'
                .format(name, selenium_standalone.browser))

    built_packages = _parse_package_subset(os.environ.get('PYODIDE_PACKAGES'))
    # only a subset of packages were built
    if built_packages is not None and name not in built_packages:
        pytest.skip(f'{name} was skipped due to PYODIDE_PACKAGES')

    selenium_standalone.run("import glob, os")

    baseline_pyc = selenium_standalone.run(
        """
        len(list(glob.glob(
            '/lib/python3.7/site-packages/**/*.pyc',
            recursive=True)
        ))
        """
    )

    selenium_standalone.load_package(name)

    # Make sure there are no additional .pyc file
    assert selenium_standalone.run(
        """
        len(list(glob.glob(
            '/lib/python3.7/site-packages/**/*.pyc',
            recursive=True)
        ))
        """
    ) == baseline_pyc

    loaded_packages = []
    for import_name in meta.get('test', {}).get('imports', []):

        if name not in loaded_packages:
            selenium_standalone.load_package(name)
            loaded_packages.append(name)
        try:
            selenium_standalone.run('import %s' % import_name)
        except Exception:
            print(selenium_standalone.logs)
            raise

        # Make sure that even after importing, there are no additional .pyc
        # files
        assert selenium_standalone.run(
            """
            len(list(glob.glob(
                '/lib/python3.7/site-packages/**/*.pyc',
                recursive=True)
            ))
            """
        ) == baseline_pyc
