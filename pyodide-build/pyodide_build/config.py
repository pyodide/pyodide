import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from .common import _environment_substitute_str, exit_with_stdio
from .logger import logger


class ConfigManager:
    """
    Configuration manager for Package build process.

    The configuration manager is responsible for loading configuration from various sources.
    The configuration can be loaded from the following sources (in order of precedence):

        1. Command line arguments (TODO)
        2. Environment variables
        3. Configuration file (TODO)
        4. Makefile.envs
        5. Default values
    """

    def __init__(self, pyodide_root: Path):
        self.pyodide_root = pyodide_root
        self._config = {
            **self._load_default_config(),
            **self._load_makefile_envs(),
            **self._load_config_file(),
            **self._load_config_from_env(os.environ),
        }

    def _load_default_config(self) -> Mapping[str, str]:
        return {
            k: _environment_substitute_str(
                v, env={"PYODIDE_ROOT": str(self.pyodide_root)}
            )
            for k, v in DEFAULT_CONFIG.items()
        }

    def _load_makefile_envs(self) -> Mapping[str, str]:
        makefile_vars = self._get_make_environment_vars()
        computed_vars = {
            k: _environment_substitute_str(v, env=makefile_vars)
            for k, v in DEFAULT_CONFIG_COMPUTED.items()
        }

        return {
            BUILD_VAR_TO_KEY[k]: v
            for k, v in makefile_vars.items()
            if k in BUILD_VAR_TO_KEY
        } | computed_vars

    def _get_make_environment_vars(self) -> Mapping[str, str]:
        """
        Load environment variables from Makefile.envs
        """
        environment = {}
        result = subprocess.run(
            ["make", "-f", str(self.pyodide_root / "Makefile.envs"), ".output_vars"],
            capture_output=True,
            text=True,
            env={"PYODIDE_ROOT": str(self.pyodide_root)},
        )

        if result.returncode != 0:
            logger.error(
                "ERROR: Failed to load environment variables from Makefile.envs"
            )
            exit_with_stdio(result)

        for line in result.stdout.splitlines():
            equalPos = line.find("=")
            if equalPos != -1:
                varname = line[0:equalPos]

                if varname not in BUILD_VAR_TO_KEY:
                    continue

                value = line[equalPos + 1 :]
                value = value.strip("'").strip()
                environment[varname] = value

        return environment

    def _load_config_from_env(self, env: Mapping[str, str]) -> Mapping[str, str]:
        return {
            BUILD_VAR_TO_KEY[key]: env[key] for key in env if key in BUILD_VAR_TO_KEY
        }

    def _load_config_file(self) -> Mapping[str, str]:
        # TODO: Implement this
        return {}

    @property
    def config(self) -> Mapping[str, str]:
        return MappingProxyType(self._config)

    def to_env(self) -> dict[str, str]:
        """
        Export the configuration to environment variables.
        """
        return {BUILD_KEY_TO_VAR[k]: v for k, v in self.config.items()}


# Configuration variables and corresponding environment variables.
# TODO: distinguish between variables that are overridable by the user and those that are not.
BUILD_KEY_TO_VAR: dict[str, str] = {
    "pyodide_version": "PYODIDE_VERSION",
    "pyodide_abi_version": "PYODIDE_ABI_VERSION",
    "cargo_build_target": "CARGO_BUILD_TARGET",
    "cargo_target_wasm32_unknown_emscripten_linker": "CARGO_TARGET_WASM32_UNKNOWN_EMSCRIPTEN_LINKER",
    "host_install_dir": "HOSTINSTALLDIR",
    "host_site_packages": "HOSTSITEPACKAGES",
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
    "pyversion": "PYVERSION",
    "cpythoninstall": "CPYTHONINSTALL",
    "rustflags": "RUSTFLAGS",
    "rust_toolchain": "RUST_TOOLCHAIN",
    "side_module_cflags": "SIDE_MODULE_CFLAGS",
    "side_module_cxxflags": "SIDE_MODULE_CXXFLAGS",
    "side_module_ldflags": "SIDE_MODULE_LDFLAGS",
    "stdlib_module_cflags": "STDLIB_MODULE_CFLAGS",
    "sysconfigdata_dir": "SYSCONFIGDATA_DIR",
    "sysconfig_name": "SYSCONFIG_NAME",
    "targetinstalldir": "TARGETINSTALLDIR",
    "cmake_toolchain_file": "CMAKE_TOOLCHAIN_FILE",
    "pyo3_config_file": "PYO3_CONFIG_FILE",
    "meson_cross_file": "MESON_CROSS_FILE",
    "cflags_base": "CFLAGS_BASE",
    "cxxflags_base": "CXXFLAGS_BASE",
    "ldflags_base": "LDFLAGS_BASE",
    "home": "HOME",
    "path": "PATH",
    "zip_compression_level": "PYODIDE_ZIP_COMPRESSION_LEVEL",
}

BUILD_VAR_TO_KEY = {v: k for k, v in BUILD_KEY_TO_VAR.items()}

# Default configuration values.
TOOLS_DIR = Path(__file__).parent / "tools"
DEFAULT_CONFIG: dict[str, str] = {
    # Paths to toolchain configuration files
    "cmake_toolchain_file": str(TOOLS_DIR / "cmake/Modules/Platform/Emscripten.cmake"),
    "pyo3_config_file": str(TOOLS_DIR / "pyo3_config.ini"),
    "meson_cross_file": str(TOOLS_DIR / "emscripten.meson.cross"),
    # Rust-specific configuration
    "rustflags": "-C link-arg=-sSIDE_MODULE=2 -C link-arg=-sWASM_BIGINT -Z link-native-libraries=no",
    "cargo_build_target": "wasm32-unknown-emscripten",
    "cargo_target_wasm32_unknown_emscripten_linker": "emcc",
    "rust_toolchain": "nightly-2024-01-29",
    # Other configuration
    "pyodide_jobs": "1",
}

# Default configs that are computed from other values (often from Makefile.envs)
# TODO: Remove dependency on Makefile.envs
DEFAULT_CONFIG_COMPUTED: dict[str, str] = {
    # Compiler flags
    "side_module_cflags": "$(CFLAGS_BASE) -I$(PYTHONINCLUDE)",
    "side_module_cxxflags": "$(CXXFLAGS_BASE)",
    "side_module_ldflags": "$(LDFLAGS_BASE) -s SIDE_MODULE=1",
    # Rust-specific configuration
    "pyo3_cross_lib_dir": "$(CPYTHONINSTALL)/lib",
    "pyo3_cross_include_dir": "$(PYTHONINCLUDE)",
    # Misc
    "stdlib_module_cflags": "$(CFLAGS_BASE) -I$(PYTHONINCLUDE) -I Include/ -I. -IInclude/internal/",  # TODO: remove this
    # Paths to build dependencies
    "host_install_dir": "$(PYODIDE_ROOT)/packages/.artifacts",
    "host_site_packages": "$(PYODIDE_ROOT)/packages/.artifacts/lib/python$(PYMAJOR).$(PYMINOR)/site-packages",
    "numpy_lib": "$(PYODIDE_ROOT)/packages/.artifacts/lib/python$(PYMAJOR).$(PYMINOR)/site-packages/numpy/",
}
