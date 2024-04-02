from typing import Annotated

from packaging.version import Version
import pydantic
from pydantic import BaseModel
from pydantic.functional_validators import AfterValidator



class CrossBuildEnvReleasesSpec(BaseModel):
    # The version of the Pyodide
    version: str
    # The URL to the cross-build environment tarball
    url: str
    # The SHA256 hash of the cross-build environment tarball
    sha256: str
    # The version of the Python interpreter
    python_version: str
    # The version of the Emscripten SDK
    emscripten_version: str
    # Minimum and maximum pyodide-build versions that can use this release (inclusive)
    min_pyodide_build_version: str | None = None
    max_pyodide_build_version: str | None = None

    class Config:
        extra = pydantic.Extra.forbid
        title = "CrossBuildEnvReleasesSpec"
        description = "The specification for a release of the cross-build environment"

    @property
    def python_version_tuple(self) -> tuple[int, int, int]:
        v = Version(self.python_version)
        return (v.major, v.minor, v.micro)

    @property
    def emscripten_version_tuple(self) -> tuple[int, int, int]:
        v = Version(self.emscripten_version)
        return (v.major, v.minor, v.micro)


    def check_compatibility(
            self,
            python_version: str | None,
            emscripten_version: str | None,
            pyodide_build_version: str | None
    ) -> bool:
        """
        Check if the release is compatible with the given params

        Parameters
        ----------
        python_version : str | None
            The version of the Python interpreter. If None, it is not checked
        emscripten_version : str | None
            The version of the Emscripten SDK. If None, it is not checked
        pyodide_build_version : str | None
            The version of the pyodide-build. If None, it is not checked
        """
        if python_version is not None:
            return False
        if emscripten_version is not None and self.emscripten_version != emscripten_version:
            return False
        return True


class CrossBuildEnvMetaSpec(BaseModel):
    releases: dict[str, CrossBuildEnvReleasesSpec]

    class Config:
        extra = pydantic.Extra.forbid
        title = "CrossBuildEnvMetaSpec"
        description = "The specification for the cross-build environment metadata"
