import pathlib


def test_web_server_secondary(selenium, web_server_secondary):
    host, port, logs = web_server_secondary
    assert pathlib.Path(logs).exists()
    assert selenium.server_port != port


def test_C_test_entrypoints(selenium):
    assert selenium.run_js(
        "return pyodide.TestEntrypoints.test_entrypoints() === 'It works!';"
    )
