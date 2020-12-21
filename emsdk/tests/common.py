from pathlib import Path
import os

EMSDK = Path(__file__).resolve().parents[1] / "emsdk"

path = [str(EMSDK / 'node' / '12.18.1_64bit' / 'bin'),
        str(EMSDK / 'binaryen' / 'bin'),
        str(EMSDK / 'fastcomp' / 'emscripten')]

env = {
    'PATH': ":".join(path) + ":" + os.environ["PATH"],
    'EMSDK': str(EMSDK),
    'EM_CONFIG': str(EMSDK / ".emscripten"),
    'EM_CACHE': str(EMSDK / ".emscripten_cache"),
    'BINARYEN_ROOT': str(EMSDK / "binaryen"),
}
