from packaging.version import Version
from pydantic import BaseModel, ConfigDict


class CrossBuildEnvReleaseSpec(BaseModel):
    # The version of the Pyodide
    version: str
    # The URL to the cross-build environment tarball
    url: str
    # The SHA256 hash of the cross-build environment tarball
    sha256: str | None = None
    # The version of the Python interpreter
    python_version: str
    # The version of the Emscripten SDK
    emscripten_version: str
    # Minimum and maximum pyodide-build versions that is compatible with this release
    min_pyodide_build_version: str | None = None
    max_pyodide_build_version: str | None = None
    model_config = ConfigDict(extra="forbid", title="CrossBuildEnvReleasesSpec")

    @property
    def python_version_tuple(self) -> tuple[int, int, int]:
        v = Version(self.python_version)
        return (v.major, v.minor, v.micro)

    @property
    def emscripten_version_tuple(self) -> tuple[int, int, int]:
        v = Version(self.emscripten_version)
        return (v.major, v.minor, v.micro)

    def is_compatible(
        self,
        python_version: str | None = None,
        emscripten_version: str | None = None,
        pyodide_build_version: str | None = None,
    ) -> bool:
        """
        Check if the release is compatible with the given params

        Parameters
        ----------
        python_version
            The version of the Python interpreter. If None, it is not checked
        emscripten_version
            The version of the Emscripten SDK. If None, it is not checked
        pyodide_build_version
            The version of the pyodide-build. If None, it is not checked

        Returns
        -------
        bool
            True if the release is compatible with the given params, False otherwise
        """
        if python_version is not None:
            major, minor, _ = self.python_version_tuple
            v = Version(python_version)
            if major != v.major or minor != v.minor:
                return False

        if (
            emscripten_version is not None
            and self.emscripten_version != emscripten_version
        ):
            # TODO: relax the emscripten version check
            return False

        if pyodide_build_version is not None:
            if self.min_pyodide_build_version is not None:
                if Version(pyodide_build_version) < Version(
                    self.min_pyodide_build_version
                ):
                    return False
            if self.max_pyodide_build_version is not None:
                if Version(pyodide_build_version) > Version(
                    self.max_pyodide_build_version
                ):
                    return False

        return True


class CrossBuildEnvMetaSpec(BaseModel):
    """
    The specification for the Pyodide cross-build environment metadata
    """

    releases: dict[str, CrossBuildEnvReleaseSpec]
    model_config = ConfigDict(
        extra="forbid",
        title="CrossBuildEnvMetaSpec",
    )

    def list_compatible_releases(
        self,
        python_version: str | None = None,
        emscripten_version: str | None = None,
        pyodide_build_version: str | None = None,
    ) -> list[CrossBuildEnvReleaseSpec]:
        """
        Get the list of compatible releases

        Parameters
        ----------
        python_version
            The version of the Python interpreter. If None, it is not checked
        emscripten_version
            The version of the Emscripten SDK. If None, it is not checked
        pyodide_build_version
            The version of the pyodide-build. If None, it is not checked

        Returns
        -------
        The list of compatible releases, sorted by version number in descending order (latest first)
        """

        return sorted(
            [
                release
                for release in self.releases.values()
                if release.is_compatible(
                    python_version, emscripten_version, pyodide_build_version
                )
            ],
            key=lambda r: Version(r.version),
            reverse=True,
        )

    def get_latest_compatible_release(
        self,
        python_version: str | None = None,
        emscripten_version: str | None = None,
        pyodide_build_version: str | None = None,
    ) -> CrossBuildEnvReleaseSpec | None:
        """
        Get the latest compatible release

        Parameters
        ----------
        python_version
            The version of the Python interpreter. If None, it is not checked
        emscripten_version
            The version of the Emscripten SDK. If None, it is not checked
        pyodide_build_version
            The version of the pyodide-build. If None, it is not checked

        Returns
        -------
        The latest compatible release, or None if no compatible release is found
        """
        compatible_releases = self.list_compatible_releases(
            python_version, emscripten_version, pyodide_build_version
        )
        if not compatible_releases:
            return None

        return compatible_releases[0]
