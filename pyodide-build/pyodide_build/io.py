from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Extra, Field


class _PackageSpec(BaseModel):
    name: str
    version: str
    top_level: list[str] = Field([], alias="top-level")
    tag: str = Field("", alias="_tag")
    disabled: bool = Field(False, alias="_disabled")
    cpython_dynlib: bool = Field(False, alias="_cpython_dynlib")

    class Config:
        extra = Extra.forbid


class _SourceSpec(BaseModel):
    url: str | None = None
    extract_dir: str | None = None
    path: Path | None = None
    sha256: str | None = None
    patches: list[str] = []
    extras: list[tuple[str, str]] = []

    class Config:
        extra = Extra.forbid


class _BuildSpec(BaseModel):
    exports: str | list[str] = "pyinit"
    backend_flags: str = Field("", alias="backend-flags")
    cflags: str = ""
    cxxflags: str = ""
    ldflags: str = ""
    library: bool = False
    sharedlibrary: bool = False
    cross_script: str | None = Field(None, alias="cross-script")
    script: str | None = None
    post: str | None = None
    unvendor_tests: bool = Field(True, alias="unvendor-tests")
    cross_build_env: bool = Field(False, alias="cross-build-env")
    cross_build_files: list[str] = Field([], alias="cross-build-files")

    class Config:
        extra = Extra.forbid


class _RequirementsSpec(BaseModel):
    run: list[str] = []
    host: list[str] = []

    class Config:
        extra = Extra.forbid


class _TestSpec(BaseModel):
    imports: list[str] = []

    class Config:
        extra = Extra.forbid


class _AboutSpec(BaseModel):
    home: str | None = None
    PyPI: str | None = None
    summary: str | None = None
    license: str | None = None

    class Config:
        extra = Extra.forbid


class MetaConfig(BaseModel):
    package: _PackageSpec
    source: _SourceSpec
    build: _BuildSpec = _BuildSpec()
    requirements: _RequirementsSpec = _RequirementsSpec()
    test: _TestSpec = _TestSpec()
    about: _AboutSpec = _AboutSpec()

    class Config:
        extra = Extra.forbid

    @classmethod
    def from_yaml(cls, path: Path) -> "MetaConfig":
        """Load the meta.yaml from a path

        Parameters
        ----------
        path
            path to the meta.yaml file
        """
        import yaml

        stream = path.read_bytes()
        config_raw = yaml.safe_load(stream)

        config = cls(**config_raw)
        return config

    def to_yaml(self, path: Path) -> None:
        """Serialize the configuration to meta.yaml file

        Parameters
        ----------
        path
            path to the meta.yaml file
        """
        import yaml

        with open(path, "w") as f:
            yaml.dump(self.dict(by_alias=True, exclude_unset=True), f)


PACKAGE_CONFIG_SPEC: dict[Any, Any] = {}


def _check_config_types(config: dict[str, Any]) -> Iterator[str]:
    # Check that if sources is a wheel it shouldn't have host dependencies.
    source_url = config.get("source", {}).get("url", "")
    requirements_host = config.get("requirements", {}).get("host", [])

    if source_url.endswith(".whl") and len(requirements_host):
        yield (
            f"When source -> url is a wheel ({source_url}) the package cannot have host "
            f"dependencies. Found {requirements_host}'"
        )


def _check_config_source(config: dict[str, Any]) -> Iterator[str]:

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
    exports = build_metadata.get("exports", "pyinit")
    if isinstance(exports, str) and exports not in [
        "pyinit",
        "requested",
        "whole_archive",
    ]:
        yield f"build/exports must be 'pyinit', 'requested', or 'whole_archive' not {build_metadata['exports']}"
    if not library and not sharedlibrary:
        return
    if library and sharedlibrary:
        yield "build/library and build/sharedlibrary cannot both be true."

    allowed_keys = {"library", "sharedlibrary", "script", "cross-script"}
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
    yield from _check_config_types(config)
    yield from _check_config_source(config)
    yield from _check_config_build(config)
    yield from _check_config_wheel_build(config)


def check_package_config(
    config: dict[str, Any],
    file_path: Path | str | None = None,
    raise_errors: bool = True,
) -> list[str]:
    errors_msg = list(check_package_config_generate_errors(config))

    if errors_msg:
        if file_path is None:
            file_path = Path("meta.yaml")
        if raise_errors:
            raise ValueError(
                f"{file_path} validation failed: \n  - " + "\n - ".join(errors_msg)
            )
    return errors_msg
