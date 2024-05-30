from pathlib import Path
from typing import Literal, Self

import pydantic
from pydantic import BaseModel, ConfigDict, Field


class _PackageSpec(BaseModel):
    name: str
    version: str
    top_level: list[str] = Field([], alias="top-level")
    tag: list[str] = Field([])
    disabled: bool = Field(False, alias="_disabled")
    model_config = ConfigDict(extra="forbid")


class _SourceSpec(BaseModel):
    url: str | None = None
    extract_dir: str | None = None
    path: Path | None = None
    sha256: str | None = None
    patches: list[str] = []
    extras: list[tuple[str, str]] = []
    model_config = ConfigDict(extra="forbid")

    @pydantic.model_validator(mode="after")
    def _check_url_has_hash(self) -> Self:
        if self.url is not None and self.sha256 is None:
            raise ValueError(
                "If source is downloaded from url, it must have a 'source/sha256' hash."
            )

        return self

    @pydantic.model_validator(mode="after")
    def _check_in_tree_url(self) -> Self:
        in_tree = self.path is not None
        from_url = self.url is not None

        # cpython_modules is a special case, it is not in the tree
        # TODO: just copy the file into the tree?
        # if not (in_tree or from_url):
        #     raise ValueError("Source section should have a 'url' or 'path' key")

        if in_tree and from_url:
            raise ValueError(
                "Source section should not have both a 'url' and a 'path' key"
            )

        return self

    @pydantic.model_validator(mode="after")
    def _check_patches_extra(self) -> Self:
        in_tree = self.path is not None
        url_is_wheel = self.url and self.url.endswith(".whl")

        if in_tree and (self.patches or self.extras):
            raise ValueError(
                "If source is in tree, 'source/patches' and 'source/extras' keys "
                "are not allowed"
            )

        if url_is_wheel and (self.patches or self.extras):
            raise ValueError(
                "If source is a wheel, 'source/patches' and 'source/extras' "
                "keys are not allowed"
            )

        return self


_ExportTypes = Literal["pyinit", "requested", "whole_archive"]
_BuildSpecExports = _ExportTypes | list[str]
_BuildSpecTypes = Literal[
    "package", "static_library", "shared_library", "cpython_module"
]


class _BuildSpec(BaseModel):
    exports: _BuildSpecExports = "pyinit"
    backend_flags: str = Field("", alias="backend-flags")
    cflags: str = ""
    cxxflags: str = ""
    ldflags: str = ""
    package_type: _BuildSpecTypes = Field("package", alias="type")
    cross_script: str | None = Field(None, alias="cross-script")
    script: str | None = None
    post: str | None = None
    unvendor_tests: bool = Field(True, alias="unvendor-tests")
    retain_test_patterns: list[str] = Field([], alias="_retain-test-patterns")
    vendor_sharedlib: bool = Field(False, alias="vendor-sharedlib")
    cross_build_env: bool = Field(False, alias="cross-build-env")
    cross_build_files: list[str] = Field([], alias="cross-build-files")
    model_config = ConfigDict(extra="forbid")

    @pydantic.model_validator(mode="after")
    def _check_config(self) -> Self:
        static_library = self.package_type == "static_library"
        shared_library = self.package_type == "shared_library"
        cpython_module = self.package_type == "cpython_module"

        if not (static_library or shared_library or cpython_module):
            return self

        allowed_keys = {
            "package_type",
            "script",
            "exports",
            "unvendor_tests",
        }

        typ = self.package_type
        for key in self.model_fields_set:
            if key not in allowed_keys:
                raise ValueError(
                    f"If building a {typ}, 'build/{key}' key is not allowed."
                )

        return self


class _RequirementsSpec(BaseModel):
    run: list[str] = []
    host: list[str] = []
    executable: list[str] = []
    model_config = ConfigDict(extra="forbid")


class _TestSpec(BaseModel):
    imports: list[str] = []
    model_config = ConfigDict(extra="forbid")


class _AboutSpec(BaseModel):
    home: str | None = None
    PyPI: str | None = None
    summary: str | None = None
    license: str | None = None
    model_config = ConfigDict(extra="forbid")


class _ExtraSpec(BaseModel):
    recipe_maintainers: list[str] = Field([], alias="recipe-maintainers")


class MetaConfig(BaseModel):
    package: _PackageSpec
    source: _SourceSpec = _SourceSpec()
    build: _BuildSpec = _BuildSpec()
    requirements: _RequirementsSpec = _RequirementsSpec()
    test: _TestSpec = _TestSpec()
    about: _AboutSpec = _AboutSpec()
    extra: _ExtraSpec = _ExtraSpec()
    model_config = ConfigDict(extra="forbid")

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
        if config.source.path:
            config.source.path = path.parent / config.source.path
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
            yaml.dump(self.model_dump(by_alias=True, exclude_unset=True), f)

    @pydantic.model_validator(mode="after")
    def _check_wheel_host_requirements(self) -> Self:
        """Check that if sources is a wheel it shouldn't have host dependencies."""
        if self.source.path is None and self.source.url is None:
            raise ValueError(
                'either "path" or "url" must be provided in the "source" section'
            )

        source_url = self.source.url
        requirements_host = self.requirements.host

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
            for key in self.build.model_fields_set:
                if key not in allowed_keys:
                    raise ValueError(
                        f"If source is a wheel, 'build/{key}' key is not allowed"
                    )

        return self

    def is_rust_package(self) -> bool:
        """
        Check if a package requires rust toolchain to build.
        """
        return any(
            q in self.requirements.executable for q in ("rustc", "cargo", "rustup")
        )
