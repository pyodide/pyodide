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
    with pytest.raises(WebDriverException,
                       match="URI mismatch, attempting "
                             "to load package pyparsing"):
        selenium_standalone.load_package('http://some_url/pyparsing.js')
    assert "Invalid package name or URI" not in selenium_standalone.logs


def test_invalid_package_name(selenium):
    with pytest.raises(WebDriverException,
                       match="Invalid package name or URI"):
        selenium.load_package('wrong name+$')
    selenium.clean_logs()

    with pytest.raises(WebDriverException,
                       match="Invalid package name or URI"):
        selenium.load_package('tcp://some_url')
