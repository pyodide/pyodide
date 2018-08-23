

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
    assert "Invalid package name or URI" not in selenium_standalone.logs
    assert ("URI mismatch, attempting "
            "to load package pyparsing") in selenium_standalone.logs


def test_invalid_package_name(selenium):
    selenium.load_package('wrong name+$')
    assert "Invalid package name or URI" in selenium.logs
    selenium.clean_logs()
    selenium.load_package('tcp://some_url')
    assert "Invalid package name or URI" in selenium.logs
