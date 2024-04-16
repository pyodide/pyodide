
from pathlib import Path

from .build_env import _get_make_environment_vars


class ConfigManager:
    """
    Configuration manager for Package build process.

    The configuration manager is responsible for loading configuration from various sources.
    The configuration can be loaded from the following sources (in order of precedence):

        1. Command line arguments
        2. Environment variables
        3. Configuration file
        4. Makefile.envs
        5. Default values
    """
    
    def __init__(self, pyodide_root: Path | None = None):
        self.pyodide_root = pyodide_root
        self.config = self.load_default_config()

        self.config = {
            **self.config,
            **self.load_makefile_envs(),
        }

        self.load_env_config()
        self.load_file_config()
        self.load_cli_config()
    
    def load_default_config(self) -> dict[str, str]:
        return DEFAULT_CONFIG.copy()

    def load_makefile_envs(self) -> dict[str, str]:
        vars = _get_make_environment_vars(self.pyodide_root)
        return {BUILD_VAR_TO_KEY[k]: v for k, v in vars.items() if k in BUILD_VARS}

    def load_env_config(self):
        pass

    def load_file_config(self) -> dict[str, str]:
        # TODO: Implement this
        return {}

    def load_cli_config(self):
        pass

    def to_env(self):
        pass

# Configuration variables and corresponding environment variables.
BUILD_KEY_TO_VAR: dict[str, str] = {
    "cargo_build_target": "CARGO_BUILD_TARGET",
    "cargo_target_wasm32_unknown_emscripten_linker": "CARGO_TARGET_WASM32_UNKNOWN_EMSCRIPTEN_LINKER",
    "hostinstalldir": "HOSTINSTALLDIR",
    "hostsitepackages": "HOSTSITEPACKAGES",
    "numpy_lib": "NUMPY_LIB",
    "platform_triplet": "PLATFORM_TRIPLET",
    "pip_constraint": "PIP_CONSTRAINT",
    "pymajor": "PYMAJOR",
    "pymicro": "PYMICRO",
    "pyminor": "PYMINOR",
    "pyo3_cross_include_dir": "PYO3_CROSS_INCLUDE_DIR",
    "pyo3_cross_lib_dir": "PYO3_CROSS_LIB_DIR",
    "pyodide_emscripten_version": "PYODIDE_EMSCRIPTEN_VERSION",
    "pyodide_jobs": "PYODIDE_JOBS",
    "pyodide_root": "PYODIDE_ROOT",
    "python_archive_sha256": "PYTHON_ARCHIVE_SHA256",
    "python_archive_url": "PYTHON_ARCHIVE_URL",
    "pythoninclude": "PYTHONINCLUDE",
    "pythonpath": "PYTHONPATH",
    "pyversion": "PYVERSION",
    "rustflags": "RUSTFLAGS",
    "rust_toolchain": "RUST_TOOLCHAIN",
    "side_module_cflags": "SIDE_MODULE_CFLAGS",
    "side_module_cxxflags": "SIDE_MODULE_CXXFLAGS",
    "side_module_ldflags": "SIDE_MODULE_LDFLAGS",
    "stdlib_module_cflags": "STDLIB_MODULE_CFLAGS",
    "sysconfigdata_dir": "SYSCONFIGDATA_DIR",
    "sysconfig_name": "SYSCONFIG_NAME",
    "targetinstalldir": "TARGETINSTALLDIR",
    "wasm_library_dir": "WASM_LIBRARY_DIR",
    "cmake_toolchain_file": "CMAKE_TOOLCHAIN_FILE",
    "pyo3_config_file": "PYO3_CONFIG_FILE",
    "meson_cross_file": "MESON_CROSS_FILE",
    "pkg_config_libdir": "PKG_CONFIG_LIBDIR",
}

BUILD_VAR_TO_KEY = {v: k for k, v in BUILD_KEY_TO_VAR.items()}

# Some environment variables that are not configurable by the user but comes from Makefile.envs
NON_CONFIG_VARS: set[str] = {
    "HOME",
    "PATH",
    "PYODIDE_PACKAGE_API",
}

BUILD_VARS: set[str] = set(BUILD_KEY_TO_VAR.values()) | NON_CONFIG_VARS

# Default configuration values.
TOOLS_DIR = Path(__file__).parent / "tools"
DEFAULT_CONFIG: dict[str, str] = {
    # Paths to toolchain configuration files
    "cmake_toolchain_file": str(TOOLS_DIR / "cmake/Modules/Platform/Emscripten.cmake"),
    "pyo3_config_file": str(TOOLS_DIR / "pyo3_config.ini"),
    "meson_cross_file": str(TOOLS_DIR / "emscripten.meson.cross"),

    # Paths to build dependencies
    # This is relative to the build directory
    "host_site_packages": ".build_dependencies",  # TODO: rename
    "numpy_lib": ".build_dependencies/numpy/",

    # Rust-specific configuration
    "rustflags": "-C link-arg=-sSIDE_MODULE=2 -C link-arg=-sWASM_BIGINT -Z link-native-libraries=no",
    "cargo_build_target": "wasm32-unknown-emscripten",
    "cargo_target_wasm32_unknown_emscripten_linker": "emcc",
    "rust_toolchain": "nightly-2024-01-29",

    # Other configuration
    
    # The compression level used for wheels.
    # When distributing via a CDN it's more efficient to keep this value to 0,
    # and let the CDN perform the Brotli compression.
    "zip_compression_level": 6,
}

# Default configs that are computed from other values (often from Makefile.envs)
# TODO: Remove dependency on Makefile.envs
DEFAULT_CONFIG_COMPUTED: dict[str, str] = {
    # Compiler flags
    "cflags": "$(cflags_base) -I$(pythoninclude)",
    "cxxflags": "$(cxxflags_base)",
    "ldflags": "$(ldflags_base) -s SIDE_MODULE=1",
    
    # Rust-specific configuration
    "pyo3_cross_lib_dir": "$(cpythoninstall)/lib",
    "pyo3_cross_include_dir": "$(pythoninclude)",

    # Misc
    "stdlib_cflags": "$(cflags_base) -I Include/ -I. -IInclude/internal/",  # TODO: remove this
}