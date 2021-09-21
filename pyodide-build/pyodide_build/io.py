from pathlib import Path
from typing import Dict, Any, List, Optional


# TODO: support more complex types for validation

PACKAGE_CONFIG_SPEC: Dict[str, Dict[str, Any]] = {
    "package": {
        "name": str,
        "version": str,
    },
    "source": {
        "url": str,
        "extract_dir": str,
        "path": str,
        "patches": list,  # List[str]
        "md5": str,
        "sha256": str,
        "extras": list,  # List[Tuple[str, str]],
    },
    "build": {
        "skip_host": bool,
        "cflags": str,
        "cxxflags": str,
        "ldflags": str,
        "library": bool,
        "sharedlibrary": bool,
        "script": str,
        "post": str,
        "replace-libs": list,
        "unvendor-tests": bool,
    },
    "requirements": {
        "run": list,  # List[str],
    },
    "test": {
        "imports": list,  # List[str]
    },
    "about": {
        "home": str,
        "PyPi": str,
        "summary": str,
        "license": str,
    },
}


def check_package_config(
    config: Dict[str, Any], raise_errors: bool = True, file_path: Optional[Path] = None
) -> List[str]:
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
    errors_msg = []

    # Check top level sections
    wrong_keys = set(config.keys()).difference(PACKAGE_CONFIG_SPEC.keys())
    if wrong_keys:
        errors_msg.append(
            f"Found unknown sections {list(wrong_keys)}. Expected "
            f"sections are {list(PACKAGE_CONFIG_SPEC)}."
        )

    # Check subsections
    for section_key in config:
        if section_key not in PACKAGE_CONFIG_SPEC:
            # Don't check subsections is the main section is invalid
            continue
        actual_keys = set(config[section_key].keys())
        expected_keys = set(PACKAGE_CONFIG_SPEC[section_key].keys())

        wrong_keys = set(actual_keys).difference(expected_keys)
        if wrong_keys:
            errors_msg.append(
                f"Found unknown keys "
                f"{[section_key + '/' + key for key in wrong_keys]}. "
                f"Expected keys are "
                f"{[section_key + '/' + key for key in expected_keys]}."
            )

    # Check value types
    for section_key, section in config.items():
        for subsection_key, value in section.items():
            try:
                expected_type = PACKAGE_CONFIG_SPEC[section_key][subsection_key]
            except KeyError:
                # Unkown key, which was already reported previously, don't
                # check types
                continue
            if not isinstance(value, expected_type):
                errors_msg.append(
                    f"Wrong type for '{section_key}/{subsection_key}': "
                    f"expected {expected_type.__name__}, got {type(value).__name__}."
                )

    if raise_errors and errors_msg:
        if file_path is None:
            file_path = Path("meta.yaml")
        raise ValueError(
            f"{file_path} validation failed: \n  - " + "\n - ".join(errors_msg)
        )

    return errors_msg


def parse_package_config(path: Path, check: bool = True) -> Dict[str, Any]:
    """Load a meta.yaml file

    Parameters
    ----------
    path
       path to the meta.yaml file
    check
       check the consitency of the config file

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
