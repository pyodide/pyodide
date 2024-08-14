import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parents[1]))
from create_xbuildenv import create


def test_xbuildenv_create(selenium, tmp_path):
    envpath = Path(tmp_path) / ".xbuildenv"
    root = Path(__file__).parents[2]

    create(envpath, root, skip_missing_files=True)

    assert (envpath / "xbuildenv").exists()
    assert (envpath / "xbuildenv" / "pyodide-root").is_dir()
    assert (envpath / "xbuildenv" / "site-packages-extras").is_dir()
    assert (envpath / "xbuildenv" / "requirements.txt").exists()
