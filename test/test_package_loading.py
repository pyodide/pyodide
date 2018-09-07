import pytest
from selenium.common.exceptions import WebDriverException


def test_load_from_url(selenium_standalone, web_server):

    url, port = web_server

    selenium_standalone.load_package(f"http://{url}:{port}/pyparsing.js")
    assert "Invalid package name or URI" not in selenium_standalone.logs

    selenium_standalone.run("from pyparsing import Word, alphas")
    selenium_standalone.run("Word(alphas).parseString('hello')")

    selenium_standalone.load_package(f"http://{url}:{port}/numpy.js")
    selenium_standalone.run("import numpy as np")


def test_uri_mismatch(selenium_standalone):
    selenium_standalone.load_package('pyparsing')
    selenium_standalone.load_package('http://some_url/pyparsing.js')
    assert ("URI mismatch, attempting to load package pyparsing" in
            selenium_standalone.logs)
    assert "Invalid package name or URI" not in selenium_standalone.logs


def test_invalid_package_name(selenium):
    selenium.load_package('wrong name+$')
    assert "Invalid package name or URI" in selenium.logs
    selenium.clean_logs()

    selenium.load_package('tcp://some_url')
    assert "Invalid package name or URI" in selenium.logs


@pytest.mark.parametrize('packages', [['pyparsing', 'pytz'],
                                      ['pyparsing', 'matplotlib']],
                         ids='-'.join)
def test_load_packages_multiple(selenium_standalone, packages):
    selenium = selenium_standalone
    selenium.load_package(packages)
    selenium.run(f'import {packages[0]}')
    selenium.run(f'import {packages[1]}')
    # The log must show that each package is loaded exactly once,
    # including when one package is a dependency of the other
    # ('pyparsing' and 'matplotlib')
    assert selenium.logs.count(f'Loading {packages[0]}') == 1
    assert selenium.logs.count(f'Loading {packages[1]}') == 1


@pytest.mark.parametrize('packages', [['pyparsing', 'pytz'],
                                      ['pyparsing', 'matplotlib']],
                         ids='-'.join)
def test_load_packages_sequential(selenium_standalone, packages):
    selenium = selenium_standalone
    promises = ','.join(
        'pyodide.loadPackage("{}")'.format(x) for x in packages
    )
    selenium.run_js(
        'window.done = false\n' +
        'Promise.all([{}])'.format(promises) +
        '.finally(function() { window.done = true; })')
    selenium.wait_until_packages_loaded()
    selenium.run(f'import {packages[0]}')
    selenium.run(f'import {packages[1]}')
    # The log must show that each package is loaded exactly once,
    # including when one package is a dependency of the other
    # ('pyparsing' and 'matplotlib')
    assert selenium.logs.count(f'Loading {packages[0]}') == 1
    assert selenium.logs.count(f'Loading {packages[1]}') == 1
