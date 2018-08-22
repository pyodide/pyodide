import os
from pathlib import Path

from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

import pytest


@pytest.fixture
def static_web_server():
    # serve artefacts from a different port
    build_dir = Path(__file__).parent.parent / 'build'
    os.chdir(build_dir)
    try:
        url, port = ('127.0.0.1', 8888)
        server = HTTPServer((url, port), SimpleHTTPRequestHandler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        yield url, port
    finally:
        server.shutdown()


def test_load_from_url(selenium_standalone, static_web_server):

    url, port = static_web_server

    selenium_standalone.load_package(f"http://{url}:{port}/pyparsing.js")
    assert "Invalid package name or URI" not in selenium_standalone.logs

    selenium_standalone.run("from pyparsing import Word, alphas")
    selenium_standalone.run("Word(alphas).parseString('hello')")


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
