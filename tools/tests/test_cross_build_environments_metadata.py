from pathlib import Path

import pytest

from pyodide_build.xbuildenv_releases import CrossBuildEnvMetaSpec

REPO_ROOT = Path(__file__).parents[2]
METADATA_FILE_V1 = REPO_ROOT / "metadata" / "pyodide-cross-build-environments-v1.json"
METADATA_FILE_V2 = REPO_ROOT / "metadata" / "pyodide-cross-build-environments-v2.json"


@pytest.mark.parametrize("metadata_file", [METADATA_FILE_V1, METADATA_FILE_V2])
def test_load(metadata_file):
    model = CrossBuildEnvMetaSpec.from_json(metadata_file.read_text())
    assert model.releases


def test_v1_has_no_published_at():
    data = METADATA_FILE_V1.read_text()
    assert "published_at" not in data


def test_v2_has_published_at():
    model = CrossBuildEnvMetaSpec.from_json(METADATA_FILE_V2.read_text())
    assert all(r.published_at is not None for r in model.releases.values())
