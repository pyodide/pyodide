import json
import sys
from pathlib import Path

from pyodide_build.xbuildenv_releases import CrossBuildEnvMetaSpec

sys.path.append(str(Path(__file__).parents[1]))
from update_cross_build_releases import add_version, parse_env_var


def test_add_version():
    metadata = CrossBuildEnvMetaSpec.parse_raw(
        """
{
    "releases": {
        "0.17.0": {
            "version": "0.17.0",
            "url": "https://example.com/xbuildenv-0.17.0.tar.bz2",
            "sha256": "1234567890abcdef",
            "python_version": "3.8.10",
            "emscripten_version": "2.0.10",
            "min_pyodide_build_version": "0.17.0",
            "max_pyodide_build_version": "0.17.0"
        },
        "0.16.0": {
            "version": "0.16.0",
            "url": "https://example.com/xbuildenv-0.16.0.tar.bz2",
            "sha256": "abcdef1234567890",
            "python_version": "3.8.10",
            "emscripten_version": "2.0.10",
            "min_pyodide_build_version": "0.16.0",
            "max_pyodide_build_version": "0.16.0"
        }
    }
}
        """.strip()
    )

    new_metadata_raw = add_version(
        metadata.json(),
        "0.18.0",
        "https://example.com/xbuildenv-0.18.0.tar.bz2",
        "abcdef1234567890",
    )

    new_metadata = CrossBuildEnvMetaSpec.parse_raw(new_metadata_raw)
    assert new_metadata.releases["0.18.0"].version == "0.18.0"
    assert (
        new_metadata.releases["0.18.0"].url
        == "https://example.com/xbuildenv-0.18.0.tar.bz2"
    )
    assert new_metadata.releases["0.18.0"].sha256 == "abcdef1234567890"

    # Check that the new release is first in the list
    assert list(new_metadata.releases.keys())[0] == "0.18.0"
    assert list(new_metadata.releases.keys())[1] == "0.17.0"
    assert list(new_metadata.releases.keys())[2] == "0.16.0"

    new_metadata_raw = add_version(
        metadata.json(),
        "0.16.1",
        "https://example.com/xbuildenv-0.16.1.tar.bz2",
        "abcdef1234567890",
    )

    new_metadata = CrossBuildEnvMetaSpec.parse_raw(new_metadata_raw)
    assert new_metadata.releases["0.16.1"].version == "0.16.1"
    assert (
        new_metadata.releases["0.16.1"].url
        == "https://example.com/xbuildenv-0.16.1.tar.bz2"
    )
    assert new_metadata.releases["0.16.1"].sha256 == "abcdef1234567890"

    assert list(new_metadata.releases.keys())[0] == "0.17.0"
    assert list(new_metadata.releases.keys())[1] == "0.16.1"
    assert list(new_metadata.releases.keys())[2] == "0.16.0"

    new_metadata_raw = add_version(
        metadata.json(),
        "0.17.0a1",
        "https://example.com/xbuildenv-0.17.0a1.tar.bz2",
        "abcdef1234567890",
    )

    new_metadata = CrossBuildEnvMetaSpec.parse_raw(new_metadata_raw)
    assert new_metadata.releases["0.17.0a1"].version == "0.17.0a1"
    assert (
        new_metadata.releases["0.17.0a1"].url
        == "https://example.com/xbuildenv-0.17.0a1.tar.bz2"
    )
    assert new_metadata.releases["0.17.0a1"].sha256 == "abcdef1234567890"

    assert list(new_metadata.releases.keys())[0] == "0.17.0"
    assert list(new_metadata.releases.keys())[1] == "0.17.0a1"
    assert list(new_metadata.releases.keys())[2] == "0.16.0"


def test_add_version_full():
    metadata = CrossBuildEnvMetaSpec.parse_raw(
        """
{
    "releases": {
        "0.17.0": {
            "version": "0.17.0",
            "url": "https://example.com/xbuildenv-0.17.0.tar.bz2",
            "sha256": "1234567890abcdef",
            "python_version": "3.8.10",
            "emscripten_version": "2.0.10",
            "min_pyodide_build_version": "0.17.0",
            "max_pyodide_build_version": "0.17.0"
        },
        "0.16.0": {
            "version": "0.16.0",
            "url": "https://example.com/xbuildenv-0.16.0.tar.bz2",
            "sha256": "abcdef1234567890",
            "python_version": "3.8.10",
            "emscripten_version": "2.0.10",
            "min_pyodide_build_version": "0.16.0",
            "max_pyodide_build_version": "0.16.0"
        }
    }
}
        """.strip()
    )

    new_metadata_raw = add_version(
        metadata.json(),
        "0.18.0",
        "https://example.com/xbuildenv-0.18.0.tar.bz2",
        "abcdef1234567890",
        python_version="3.8.11",
        emscripten_version="2.0.11",
        min_pyodide_build_version="0.18.0",
        max_pyodide_build_version="0.18.0",
    )

    new_metadata = CrossBuildEnvMetaSpec.parse_raw(new_metadata_raw)
    assert new_metadata.releases["0.18.0"].version == "0.18.0"
    assert (
        new_metadata.releases["0.18.0"].url
        == "https://example.com/xbuildenv-0.18.0.tar.bz2"
    )
    assert new_metadata.releases["0.18.0"].sha256 == "abcdef1234567890"
    assert new_metadata.releases["0.18.0"].python_version == "3.8.11"
    assert new_metadata.releases["0.18.0"].emscripten_version == "2.0.11"
    assert new_metadata.releases["0.18.0"].min_pyodide_build_version == "0.18.0"
    assert new_metadata.releases["0.18.0"].max_pyodide_build_version == "0.18.0"


def test_exclude_none():
    metadata = CrossBuildEnvMetaSpec.parse_raw(
        """
{
    "releases": {
        "0.17.0": {
            "version": "0.17.0",
            "url": "https://example.com/xbuildenv-0.17.0.tar.bz2",
            "sha256": "1234567890abcdef",
            "python_version": "3.8.10",
            "emscripten_version": "2.0.10"
        }
    }
}
        """.strip()
    )

    new_metadata_raw = add_version(
        metadata.json(),
        "0.18.0",
        "https://example.com/xbuildenv-0.18.0.tar.bz2",
        "abcdef1234567890",
    )

    metadata = json.loads(new_metadata_raw)
    assert "releases" in metadata
    assert "0.17.0" in metadata["releases"]
    assert "python_version" in metadata["releases"]["0.17.0"]
    # unspecified fields should be excluded
    assert "min_pyodide_build_version" not in metadata["releases"]["0.17.0"]


def test_parse_env_var():
    testdata = """
export PYVERSION ?= 3.45.67
export PYODIDE_EMSCRIPTEN_VERSION ?= 1.23.45
export SOMETHING_ELSE ?= hello
"""

    assert parse_env_var(testdata, "PYVERSION") == "3.45.67"
    assert parse_env_var(testdata, "PYODIDE_EMSCRIPTEN_VERSION") == "1.23.45"
    assert parse_env_var(testdata, "SOMETHING_ELSE") == "hello"
