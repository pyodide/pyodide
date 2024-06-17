import shutil
from pathlib import Path

import pytest

from conftest import DIST_PATH

HTML_TEAMPLTE_DIR = Path(__file__).parent / "html_templates"


@pytest.mark.xfail_browsers(node="No goto")
def test_commonjs_define(selenium_standalone_noload):
    """
    ErrorStackParser behaves differently when "define", and "define.amd" are defined in the global scope (CommonJS),
    Related issues: #4863 #4577
    """
    selenium = selenium_standalone_noload
    src_path = HTML_TEAMPLTE_DIR / "test_commonjs.html"
    target_path = DIST_PATH / "test_commonjs.html"
    try:
        shutil.copy(src_path, target_path)
        selenium.goto(f"{selenium.base_url}/test_commonjs.html")
        selenium.javascript_setup()
        selenium.load_pyodide()
    finally:
        target_path.unlink()
