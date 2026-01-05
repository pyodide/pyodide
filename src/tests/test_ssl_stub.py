# type: ignore

from pytest_pyodide import run_in_pyodide


@run_in_pyodide
def test_ssl_import(selenium):
    import sys

    # See src/py/{ssl.py, _ssl.py} for details.

    # Test all public attributes of the ssl module can be accessed
    # https://docs.python.org/3.13/library/ssl.html

    # If you are not sure, you can generate this list by running:
    """
import ssl
public_attrs = [attr for attr in dir(ssl) if not attr.startswith('_')]
print("from ssl import (\n{})".format(",\n    ".join(public_attrs)))
    """

    # Guardrail to ensure we don't forget to update this test when Python version changes
    assert sys.version_info.minor == 13
