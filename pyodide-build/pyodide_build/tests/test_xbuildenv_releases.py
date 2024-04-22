from pyodide_build.xbuildenv_releases import (
    CrossBuildEnvMetaSpec,
    CrossBuildEnvReleaseSpec,
)

FAKE_METADATA = {
    "releases": {
        "0.1.0": {
            "version": "0.1.0",
            "url": "https://example.com/0.1.0.tar.gz",
            "sha256": "1234567890abcdef",
            "python_version": "3.8.0",
            "emscripten_version": "1.39.8",
            "min_pyodide_build_version": "0.1.0",
            "max_pyodide_build_version": "0.2.0",
        },
        "0.2.0": {
            "version": "0.2.0",
            "url": "https://example.com/0.2.0.tar.gz",
            "sha256": "1234567890abcdef",
            "python_version": "3.9.0",
            "emscripten_version": "1.39.8",
            "min_pyodide_build_version": "0.2.0",
            "max_pyodide_build_version": "0.3.0",
        },
        "0.3.0": {
            "version": "0.3.0",
            "url": "https://example.com/0.3.0.tar.gz",
            "sha256": "1234567890abcdef",
            "python_version": "3.10.0",
            "emscripten_version": "1.39.8",
            "min_pyodide_build_version": "0.3.0",
            "max_pyodide_build_version": "0.4.0",
        },
        "0.4.0": {
            "version": "0.4.0",
            "url": "https://example.com/0.4.0.tar.gz",
            "sha256": "1234567890abcdef",
            "python_version": "3.10.1",
            "emscripten_version": "1.39.8",
            "min_pyodide_build_version": "0.4.0",
            "max_pyodide_build_version": "0.5.0",
        },
        "0.5.0": {
            "version": "0.5.0",
            "url": "https://example.com/0.5.0.tar.gz",
            "sha256": "1234567890abcdef",
            "python_version": "3.10.2",
            "emscripten_version": "1.40.0",
            "min_pyodide_build_version": "0.5.0",
            "max_pyodide_build_version": "0.6.0",
        },
    },
}


def test_model():
    model = CrossBuildEnvMetaSpec(**FAKE_METADATA)
    assert "0.1.0" in model.releases
    assert "0.2.0" in model.releases
    assert "0.3.0" in model.releases
    assert "0.4.0" in model.releases
    assert model.releases["0.1.0"].python_version == "3.8.0"
    assert model.releases["0.1.0"].emscripten_version == "1.39.8"
    assert model.releases["0.1.0"].min_pyodide_build_version == "0.1.0"
    assert model.releases["0.1.0"].max_pyodide_build_version == "0.2.0"


def test_list_compatible_releases():
    model = CrossBuildEnvMetaSpec(**FAKE_METADATA)

    releases = model.list_compatible_releases(
        python_version="3.10.5",
        emscripten_version="1.39.8",
    )

    assert len(releases) == 2
    assert releases[0].version == "0.4.0"
    assert releases[1].version == "0.3.0"

    releases = model.list_compatible_releases(
        python_version="3.10.5",
    )

    assert len(releases) == 3
    assert releases[0].version == "0.5.0"

    releases = model.list_compatible_releases(
        python_version="3.7.0",
    )

    assert not releases


def test_get_latest_compatible_release():
    model = CrossBuildEnvMetaSpec(**FAKE_METADATA)

    release = model.get_latest_compatible_release(
        python_version="3.10.5",
        emscripten_version="1.39.8",
    )

    assert release and release.version == "0.4.0"

    release = model.get_latest_compatible_release(
        python_version="3.10.5",
    )

    assert release and release.version == "0.5.0"

    release = model.get_latest_compatible_release(
        python_version="3.7.0",
    )

    assert release is None


def test_is_compatible_full():
    release = CrossBuildEnvReleaseSpec(
        version="0.1.0",
        url="https://example.com/0.1.0.tar.gz",
        sha256="1234567890abcdef",
        python_version="3.8.0",
        emscripten_version="1.39.8",
        min_pyodide_build_version="0.1.0",
        max_pyodide_build_version="0.2.0",
    )

    assert release.is_compatible(
        python_version="3.8.0",
        emscripten_version="1.39.8",
        pyodide_build_version="0.1.0",
    )

    # Major Python version does not match
    assert not release.is_compatible(
        python_version="4.8.0",
        emscripten_version="1.39.8",
        pyodide_build_version="0.1.0",
    )

    # Minor Python version does not match
    assert not release.is_compatible(
        python_version="3.9.0",
        emscripten_version="1.39.8",
        pyodide_build_version="0.1.0",
    )

    # Patch Python version does not match (should pass)
    assert release.is_compatible(
        python_version="3.8.1",
        emscripten_version="1.39.8",
        pyodide_build_version="0.1.0",
    )

    # Emscripten version does not match
    assert not release.is_compatible(
        python_version="3.8.0",
        emscripten_version="1.39.9",
        pyodide_build_version="0.1.0",
    )

    # Pyodide build version is too low
    assert not release.is_compatible(
        python_version="3.8.0",
        emscripten_version="1.39.8",
        pyodide_build_version="0.0.1",
    )

    # Pyodide build version is too high
    assert not release.is_compatible(
        python_version="3.8.0",
        emscripten_version="1.39.8",
        pyodide_build_version="0.3.0",
    )

    # Python version is not checked
    assert release.is_compatible(
        python_version=None,
        emscripten_version="1.39.8",
        pyodide_build_version="0.1.0",
    )

    # Emscripten version is not checked
    assert release.is_compatible(
        python_version="3.8.0",
        emscripten_version=None,
        pyodide_build_version="0.1.0",
    )

    # Pyodide build version is not checked
    assert release.is_compatible(
        python_version="3.8.0",
        emscripten_version="1.39.8",
        pyodide_build_version=None,
    )


def test_is_compatible_without_pyodide_build_range():
    release = CrossBuildEnvReleaseSpec(
        version="0.1.0",
        url="https://example.com/0.1.0.tar.gz",
        sha256="1234567890abcdef",
        python_version="3.8.0",
        emscripten_version="1.39.8",
    )

    assert release.is_compatible(
        python_version="3.8.0",
        emscripten_version="1.39.8",
        pyodide_build_version="0.1.0",
    )
