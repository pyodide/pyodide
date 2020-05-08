import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parents[2]))

from pyodide_build.common import _parse_package_subset # noqa: E402


def test_parse_package_subset():
    assert _parse_package_subset("") is None
    # micropip is always included
    assert _parse_package_subset("numpy,pandas") == [
        'micropip', 'numpy', 'pandas'
    ]
