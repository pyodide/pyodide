
import pydantic
from pydantic import BaseModel, Field

class CrossBuildEnvMetaSpec(BaseModel):
    releases: dict[str, CrossBuildEnvReleasesSpec]

    class Config:
        extra = pydantic.Extra.forbid
        title = "CrossBuildEnvMetaSpec"
        description = "The specification for the cross-build environment metadata"


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

    def check_compatibility(self, python_version: str | None, emscripten_version: str | None, pyodide_build_version: str | None) -> bool:
        if python_version is not None:
            
            return False
        if emscripten_version is not None and self.emscripten_version != emscripten_version:
            return False
        return True