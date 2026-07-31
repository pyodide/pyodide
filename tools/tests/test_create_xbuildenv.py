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

    # Test that the pins in requirements.txt exactly match the versions of the
    # xbuild packages in our recipes.
    from pyodide_build.recipe.loader import load_all_recipes

    expected = {
        name: config.package.version
        for name, config in load_all_recipes(root / "packages").items()
        if config.build.cross_build_env
    }
    requirements = (envpath / "xbuildenv" / "requirements.txt").read_text()
    pins = dict(line.split("==", 1) for line in requirements.split() if "==" in line)
    assert pins == expected
