from pathlib import Path
from typing import Any, Literal

import pydantic
from pydantic import BaseModel, Field


class _PackageSpec(BaseModel):
    name: str
    version: str
    top_level: list[str] = Field([], alias="top-level")
    tag: str = Field("", alias="_tag")
    disabled: bool = Field(False, alias="_disabled")

    class Config:
        extra = pydantic.Extra.forbid


class _SourceSpec(BaseModel):
    url: str | None = None
    extract_dir: str | None = None
    path: Path | None = None
    sha256: str | None = None
    patches: list[str] = []
    extras: list[tuple[str, str]] = []

    class Config:
        extra = pydantic.Extra.forbid

    @pydantic.root_validator
    def _check_url_has_hash(cls, values: dict[str, Any]) -> dict[str, Any]:
        if values["url"] is not None and values["sha256"] is None:
            raise ValueError(
                "If source is downloaded from url, it must have a 'source/sha256' hash."
            )
        return values

    @pydantic.root_validator
    def _check_in_tree_url(cls, values: dict[str, Any]) -> dict[str, Any]:
        in_tree = values["path"] is not None
        from_url = values["url"] is not None

        # cpython_modules is a special case, it is not in the tree
        # TODO: just copy the file into the tree?
        # if not (in_tree or from_url):
        #     raise ValueError("Source section should have a 'url' or 'path' key")

        if in_tree and from_url:
            raise ValueError(
                "Source section should not have both a 'url' and a 'path' key"
            )
        return values

    @pydantic.root_validator
    def _check_patches_extra(cls, values: dict[str, Any]) -> dict[str, Any]:
        patches = values["patches"]
        extras = values["extras"]
        in_tree = values["path"] is not None
        from_url = values["url"] is not None

        url_is_wheel = from_url and values["url"].endswith(".whl")

        if in_tree and (patches or extras):
            raise ValueError(
                "If source is in tree, 'source/patches' and 'source/extras' keys "
                "are not allowed"
            )

        if url_is_wheel and (patches or extras):
            raise ValueError(
                "If source is a wheel, 'source/patches' and 'source/extras' "
                "keys are not allowed"
            )

        return values


_BuildSpecExports = Literal["pyinit", "requested", "whole_archive"]
_BuildSpecTypes = Literal[
    "package", "static_library", "shared_library", "cpython_module"
]


class _BuildSpec(BaseModel):
    exports: _BuildSpecExports | list[_BuildSpecExports] = "pyinit"
    backend_flags: str = Field("", alias="backend-flags")
    cflags: str = ""
    cxxflags: str = ""
    ldflags: str = ""
    package_type: _BuildSpecTypes = Field("package", alias="type")
    cross_script: str | None = Field(None, alias="cross-script")
    script: str | None = None
    post: str | None = None
    unvendor_tests: bool = Field(True, alias="unvendor-tests")
    vendor_sharedlib: bool = Field(False, alias="vendor-sharedlib")
    cross_build_env: bool = Field(False, alias="cross-build-env")
    cross_build_files: list[str] = Field([], alias="cross-build-files")

    class Config:
        extra = pydantic.Extra.forbid

    @pydantic.root_validator
    def _check_config(cls, values: dict[str, Any]) -> dict[str, Any]:
        static_library = values["package_type"] == "static_library"
        shared_library = values["package_type"] == "shared_library"
        cpython_module = values["package_type"] == "cpython_module"

        if not (static_library or shared_library or cpython_module):
            return values

        allowed_keys = {
            "package_type",
            "script",
            "exports",
            "unvendor_tests",
        }

        typ = values["package_type"]
        for key, val in values.items():
            if val and key not in allowed_keys:
                raise ValueError(
                    f"If building a {typ}, 'build/{key}' key is not allowed."
                )
        return values


class _RequirementsSpec(BaseModel):
    run: list[str] = []
    host: list[str] = []

    class Config:
        extra = pydantic.Extra.forbid


class _TestSpec(BaseModel):
    imports: list[str] = []

    class Config:
        extra = pydantic.Extra.forbid


class _AboutSpec(BaseModel):
    home: str | None = None
    PyPI: str | None = None
    summary: str | None = None
    license: str | None = None

    class Config:
        extra = pydantic.Extra.forbid


class MetaConfig(BaseModel):
    package: _PackageSpec
    source: _SourceSpec = _SourceSpec()
    build: _BuildSpec = _BuildSpec()
    requirements: _RequirementsSpec = _RequirementsSpec()
    test: _TestSpec = _TestSpec()
    about: _AboutSpec = _AboutSpec()

    class Config:
        extra = pydantic.Extra.forbid

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

    @pydantic.root_validator
    def _check_wheel_host_requirements(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Check that if sources is a wheel it shouldn't have host dependencies."""
        if "source" not in values:
            raise ValueError(
                'either "path" or "url" must be provided in the "source" section'
            )

        source_url = values["source"].url
        requirements_host = values["requirements"].host

        if source_url is not None and source_url.endswith(".whl"):
            if len(requirements_host):
                raise ValueError(
                    f"When source -> url is a wheel ({source_url}) the package cannot have host "
                    f"dependencies. Found {requirements_host}"
                )

            allowed_keys = {
                "post",
                "unvendor-tests",
                # Note here names are with "_", after alias conversion
                "cross_build_env",
                "cross_build_files",
                "exports",
                "unvendor_tests",
                "package_type",
            }
            for key, val in values["build"].dict().items():
                if val and key not in allowed_keys:
                    raise ValueError(
                        f"If source is a wheel, 'build/{key}' key is not allowed"
                    )
        return values
