import pathlib


def test_pytest(selenium):
    selenium.load_package(['pytest', 'numpy', 'nose'])

    selenium.run(
        """
        from pathlib import Path
        import os
        import numpy
        import pytest

        base_dir = Path(numpy.__file__).parent / "core" / "tests"
        """)

    selenium.run("pytest.main([base_dir / 'test_api.py'])")

    logs = '\n'.join(selenium.logs)
    assert 'INTERNALERROR' not in logs


def test_web_server_secondary(selenium, web_server_secondary):
    host, port, logs = web_server_secondary
    assert pathlib.Path(logs).exists()
    assert selenium.server_port != port
