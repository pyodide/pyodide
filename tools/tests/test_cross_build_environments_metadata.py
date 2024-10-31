from pathlib import Path

from pyodide_build.xbuildenv_releases import CrossBuildEnvMetaSpec

METADATA_FILE = Path(__file__).parents[2] / "pyodide-cross-build-environments.json"


def test_load():
    model = CrossBuildEnvMetaSpec.parse_file(METADATA_FILE)
    assert model.releases
