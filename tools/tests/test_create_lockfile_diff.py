from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parents[1]))
from create_lockfile_diff import calculate_diff


def test_calculate_diff():
    old = Path(__file__).parent / "testdata" / "pyodide-lock-0.27.7.json"
    new = Path(__file__).parent / "testdata" / "pyodide-lock-0.28.0a3.json"

    added, removed, changed = calculate_diff(old, new)
    assert "platformdirs" in [pkg.name for pkg in added]
    assert "sharedlib-test-py" in [pkg.name for pkg in removed]
    assert "numpy" in [pkg.name for pkg in changed]
