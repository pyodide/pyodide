from pathlib import Path
from typing import Any, Iterator

# TODO: support more complex types for validation

PACKAGE_CONFIG_SPEC: dict[str, dict[str, Any]] = {
    "package": {
        "name": str,
        "version": str,
        "_tag": str,
        "_disabled": bool,
        "_cpython_dynlib": bool,
    },
    "source": {
        "url": str,
        "extract_dir": str,
        "path": str,
        "sha256": str,
        "patches": list,  # List[str]
        "extras": list,  # List[Tuple[str, str]],
    },
    "build": {
        "backend-flags": str,
        "cflags": str,
        "cxxflags": str,
        "ldflags": str,
        "library": bool,
        "sharedlibrary": bool,
        "script": str,
        "post": str,
        "replace-libs": list,
        "unvendor-tests": bool,
        "cross-build-env": bool,
        "cross-build-files": list,  # list[str]
    },
    "requirements": {
        "run": list,  # List[str],
    },
    "test": {
        "imports": list,  # List[str]
    },
    "about": {
        "home": str,
        "PyPI": str,
        "summary": str,
        "license": str,
    },
}


def _check_config_keys(config: dict[str, Any]) -> Iterator[str]:
    # Check top level sections
    wrong_keys = set(config.keys()).difference(PACKAGE_CONFIG_SPEC.keys())
    if wrong_keys:
        yield (
            f"Found unknown sections {list(wrong_keys)}. Expected "
            f"sections are {list(PACKAGE_CONFIG_SPEC)}."
        )

    # Check subsections
    for section_key in config:
        if section_key not in PACKAGE_CONFIG_SPEC:
            # Don't check subsections if the main section is invalid
            continue
        actual_keys = set(config[section_key].keys())
        expected_keys = set(PACKAGE_CONFIG_SPEC[section_key].keys())

        wrong_keys = set(actual_keys).difference(expected_keys)
        if wrong_keys:
            yield (
                f"Found unknown keys "
                f"{[section_key + '/' + key for key in wrong_keys]}. "
                f"Expected keys are "
                f"{[section_key + '/' + key for key in expected_keys]}."
            )


def _check_config_types(config: dict[str, Any]) -> Iterator[str]:
    # Check value types
    for section_key, section in config.items():
        for subsection_key, value in section.items():
            try:
                expected_type = PACKAGE_CONFIG_SPEC[section_key][subsection_key]
            except KeyError:
                # Unknown key, which was already reported previously, don't
                # check types
                continue
            if not isinstance(value, expected_type):
                yield (
                    f"Wrong type for '{section_key}/{subsection_key}': "
                    f"expected {expected_type.__name__}, got {type(value).__name__}."
                )


def _check_config_source(config: dict[str, Any]) -> Iterator[str]:
    if "source" not in config:
        yield "Missing source section"
        return

    src_metadata = config["source"]
    patches = src_metadata.get("patches", [])
    extras = src_metadata.get("extras", [])

    in_tree = "path" in src_metadata
    from_url = "url" in src_metadata

    if not (in_tree or from_url):
        yield "Source section should have a 'url' or 'path' key"
        return

    if in_tree and from_url:
        yield "Source section should not have both a 'url' and a 'path' key"
        return

    if in_tree and (patches or extras):
        yield "If source is in tree, 'source/patches' and 'source/extras' keys are not allowed"

    if from_url:
        if "sha256" not in src_metadata:
            yield "If source is downloaded from url, it must have a 'source/sha256' hash."


def _check_config_build(config: dict[str, Any]) -> Iterator[str]:
    if "build" not in config:
        return
    build_metadata = config["build"]
    library = build_metadata.get("library", False)
    sharedlibrary = build_metadata.get("sharedlibrary", False)
    if not library and not sharedlibrary:
        return
    if library and sharedlibrary:
        yield "build/library and build/sharedlibrary cannot both be true."

    allowed_keys = {"library", "sharedlibrary", "script"}
    typ = "library" if library else "sharedlibrary"
    for key in build_metadata.keys():
        if key not in PACKAGE_CONFIG_SPEC["build"]:
            continue
        if key not in allowed_keys:
            yield f"If building a {typ}, 'build/{key}' key is not allowed."


def _check_config_wheel_build(config: dict[str, Any]) -> Iterator[str]:
    if "source" not in config:
        return
    src_metadata = config["source"]
    if "url" not in src_metadata:
        return
    if not src_metadata["url"].endswith(".whl"):
        return
    patches = src_metadata.get("patches", [])
    extras = src_metadata.get("extras", [])
    if patches or extras:
        yield "If source is a wheel, 'source/patches' and 'source/extras' keys are not allowed"
    if "build" not in config:
        return
    build_metadata = config["build"]
    allowed_keys = {"post", "unvendor-tests", "cross-build-env", "cross-build-files"}
    for key in build_metadata.keys():
        if key not in PACKAGE_CONFIG_SPEC["build"]:
            continue
        if key not in allowed_keys:
            yield f"If source is a wheel, 'build/{key}' key is not allowed"


def check_package_config_generate_errors(
    config: dict[str, Any],
) -> Iterator[str]:
    """Check the validity of a loaded meta.yaml file

    Currently the following checks are applied:
     -

    TODO:
     - check for mandatory fields

    Parameter
    ---------
    config
        loaded meta.yaml as a dict
    raise_errors
        if true raise errors, otherwise return the list of error messages.
    file_path
        optional meta.yaml file path. Only used for more explicit error output,
        when raise_errors = True.
    """
    yield from _check_config_keys(config)
    yield from _check_config_types(config)
    yield from _check_config_source(config)
    yield from _check_config_build(config)
    yield from _check_config_wheel_build(config)


def check_package_config(
    config: dict[str, Any], file_path: Path | str | None = None
) -> None:
    errors_msg = list(check_package_config_generate_errors(config))

    if errors_msg:
        if file_path is None:
            file_path = Path("meta.yaml")
        raise ValueError(
            f"{file_path} validation failed: \n  - " + "\n - ".join(errors_msg)
        )


def parse_package_config(path: Path | str, *, check: bool = True) -> dict[str, Any]:
    """Load a meta.yaml file

    Parameters
    ----------
    path
       path to the meta.yaml file
    check
       check the consistency of the config file

    Returns
    -------
    the loaded config as a Dict
    """
    # Import yaml here because pywasmcross needs to run in the built native
    # Python, which won't have PyYAML
    import yaml

    with open(path, "rb") as fd:
        config = yaml.safe_load(fd)

    if check:
        check_package_config(config, file_path=path)

    return config
