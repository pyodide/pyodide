from pyodide_build.common import (  # type: ignore[import]
    ALWAYS_PACKAGES,
    CORE_PACKAGES,
    CORE_SCIPY_PACKAGES,
    UNVENDORED_STDLIB_MODULES,
    _parse_package_subset,
    find_matching_wheels,
    get_make_environment_vars,
    get_make_flag,
)


def test_parse_package_subset():
    assert (
        _parse_package_subset("numpy,pandas")
        == {
            "numpy",
            "pandas",
        }
        | UNVENDORED_STDLIB_MODULES
        | ALWAYS_PACKAGES
    )

    # duplicates are removed
    assert (
        _parse_package_subset("numpy,numpy")
        == {
            "numpy",
        }
        | UNVENDORED_STDLIB_MODULES
        | ALWAYS_PACKAGES
    )

    # no empty package name included, spaces are handled
    assert (
        _parse_package_subset("x,  a, b, c   ,,, d,,")
        == {
            "x",
            "a",
            "b",
            "c",
            "d",
        }
        | UNVENDORED_STDLIB_MODULES
        | ALWAYS_PACKAGES
    )

    assert (
        _parse_package_subset("core")
        == CORE_PACKAGES | UNVENDORED_STDLIB_MODULES | ALWAYS_PACKAGES
    )
    # by default core packages are built
    assert _parse_package_subset(None) == _parse_package_subset("core")

    assert (
        _parse_package_subset("min-scipy-stack")
        == CORE_SCIPY_PACKAGES
        | CORE_PACKAGES
        | UNVENDORED_STDLIB_MODULES
        | ALWAYS_PACKAGES
    )
    # reserved key words can be combined with other packages
    assert _parse_package_subset("core, unknown") == _parse_package_subset("core") | {
        "unknown"
    }


def test_get_make_flag():
    assert len(get_make_flag("SIDE_MODULE_LDFLAGS")) > 0
    assert len(get_make_flag("SIDE_MODULE_CFLAGS")) > 0
    # n.b. right now CXXFLAGS is empty so don't check length here, just check it returns
    get_make_flag("SIDE_MODULE_CXXFLAGS")


def test_get_make_environment_vars():
    vars = get_make_environment_vars()
    assert "SIDE_MODULE_LDFLAGS" in vars
    assert "SIDE_MODULE_CFLAGS" in vars
    assert "SIDE_MODULE_CXXFLAGS" in vars
    assert "TOOLSDIR" in vars


def test_wheel_paths():
    from pathlib import Path

    old_version = "cp38"
    current_version = "cp39"
    future_version = "cp317"
    strings = []

    for interp in [
        old_version,
        current_version,
        future_version,
        "py3",
        "py2",
        "py2.py3",
    ]:
        for abi in [interp, "abi3", "none"]:
            for arch in ["emscripten_wasm32", "linux_x86_64", "any"]:
                strings.append(f"wrapt-1.13.3-{interp}-{abi}-{arch}.whl")

    paths = [Path(x) for x in strings]
    assert [x.stem.split("-", 2)[-1] for x in find_matching_wheels(paths)] == [
        "cp39-cp39-emscripten_wasm32",
        "cp39-abi3-emscripten_wasm32",
        "cp39-none-emscripten_wasm32",
        "cp38-abi3-emscripten_wasm32",
        "py3-none-emscripten_wasm32",
        "py2.py3-none-emscripten_wasm32",
        "py3-none-any",
        "py2.py3-none-any",
    ]
