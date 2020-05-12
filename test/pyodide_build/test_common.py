import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parents[2]))

from pyodide_build.common import _parse_package_subset  # noqa


def test_parse_package_subset():
    assert _parse_package_subset(None) is None
    # micropip is always included
    assert _parse_package_subset("numpy,pandas") == {
        'micropip', 'distlib', 'numpy', 'pandas'
    }

    # duplicates are removed
    assert _parse_package_subset("numpy,numpy") == {
        'micropip', 'distlib', 'numpy'
    }
