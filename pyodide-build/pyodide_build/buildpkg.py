#!/usr/bin/env python3

"""
Builds a Pyodide package.
"""

import fnmatch
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import requests

from . import common, pypabuild
from .bash_runner import BashRunnerWithSharedEnvironment, get_bash_runner
from .build_env import (
    RUST_BUILD_PRELUDE,
    BuildArgs,
    get_build_environment_vars,
    get_pyodide_root,
    pyodide_tags,
    replace_so_abi_tags,
    wheel_platform,
)
from .common import (
    _environment_substitute_str,
    _get_sha256_checksum,
    chdir,
    exit_with_stdio,
    find_matching_wheels,
    make_zip_archive,
    modify_wheel,
    retag_wheel,
)
from .io import MetaConfig, _SourceSpec
from .logger import logger


def _make_whlfile(
    *args: Any, owner: int | None = None, group: int | None = None, **kwargs: Any
) -> str:
    return shutil._make_zipfile(*args, **kwargs)  # type: ignore[attr-defined]


shutil.register_archive_format("whl", _make_whlfile, description="Wheel file")
shutil.register_unpack_format(
    "whl",
    [".whl", ".wheel"],
    shutil._unpack_zipfile,  # type: ignore[attr-defined]
    description="Wheel file",
)


class RecipeBuilder:
    """
    A class to build a Pyodide meta.yaml recipe.
    """

    def __init__(
        self,
        recipe: str | Path,
        build_args: BuildArgs,
        build_dir: str | Path | None = None,
        force_rebuild: bool = False,
        continue_: bool = False,
    ):
        """
        Parameters
        ----------
        recipe
            The path to the meta.yaml file or the directory containing
            the meta.yaml file.
        build_args
            The extra build arguments passed to the build script.
        build_dir
            The path to the build directory. By default, it will be
            <the directory containing the meta.yaml file> / build
        force_rebuild
            If True, the package will be rebuilt even if it is already up-to-date.
        continue_
            If True, continue a build from the middle. For debugging. Implies "force_rebuild".
        """
        recipe = Path(recipe).resolve()
        self.pkg_root, self.recipe = self._load_recipe(recipe)

        self.name = self.recipe.package.name
        self.version = self.recipe.package.version
        self.fullname = f"{self.name}-{self.version}"
        self.build_args = build_args

        self.build_dir = (
            Path(build_dir).resolve() if build_dir else self.pkg_root / "build"
        )

        self.library_install_prefix = self.build_dir.parent.parent / ".libs"

        self.src_extract_dir = (
            self.build_dir / self.fullname
        )  # where we extract the source

        # where the built artifacts are put.
        # For wheels, this is the default location where the built wheels are put by pypa/build.
        # For shared libraries, users should use this directory to put the built shared libraries (can be accessed by DISTDIR env var)
        self.src_dist_dir = self.src_extract_dir / "dist"

        # where Pyodide will look for the built artifacts when building pyodide-lock.json.
        # after building packages, artifacts in src_dist_dir will be copied to dist_dir
        self.dist_dir = self.pkg_root / "dist"

        self.source_metadata = self.recipe.source
        self.build_metadata = self.recipe.build
        self.package_type = self.build_metadata.package_type

        self.force_rebuild = force_rebuild or continue_
        self.continue_ = continue_

    def build(self) -> None:
        """
        Build the package. This is the only public method of this class.
        """
        self._check_executables()

        t0 = datetime.now()
        timestamp = t0.strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[{timestamp}] Building package {self.name}...")
        success = True
        try:
            self._build()

            (self.build_dir / ".packaged").touch()
        except (Exception, KeyboardInterrupt):
            success = False
            raise
        except SystemExit as e:
            success = e.code == 0
            raise
        finally:
            t1 = datetime.now()
            datestamp = "[{}]".format(t1.strftime("%Y-%m-%d %H:%M:%S"))
            total_seconds = f"{(t1 - t0).total_seconds():.1f}"
            status = "Succeeded" if success else "Failed"
            msg = f"{datestamp} {status} building package {self.name} in {total_seconds} seconds."
            if success:
                logger.success(msg)
            else:
                logger.error(msg)

    def _build(self) -> None:
        if not self.force_rebuild and not needs_rebuild(
            self.pkg_root, self.build_dir, self.source_metadata
        ):
            return

        if self.continue_ and not self.src_extract_dir.exists():
            raise OSError(
                "Cannot find source for rebuild. Expected to find the source "
                f"directory at the path {self.src_extract_dir}, but that path does not exist."
            )

        self._redirect_stdout_stderr_to_logfile()

        if not self.continue_:
            self._prepare_source()
            self._patch()

        with (
            chdir(self.pkg_root),
            get_bash_runner(self._get_helper_vars()) as bash_runner,
        ):
            if self.recipe.is_rust_package():
                bash_runner.run(
                    RUST_BUILD_PRELUDE,
                    script_name="rust build prelude",
                    cwd=self.src_extract_dir,
                )

            bash_runner.run(
                self.build_metadata.script,
                script_name="build script",
                cwd=self.src_extract_dir,
            )

            # TODO: maybe subclass this for different package types?
            if self.package_type == "static_library":
                # Nothing needs to be done for a static library
                pass

            elif self.package_type in ("shared_library", "cpython_module"):
                # If shared library, we copy .so files to dist_dir
                # and create a zip archive of the .so files
                shutil.rmtree(self.dist_dir, ignore_errors=True)
                self.dist_dir.mkdir(parents=True)
                make_zip_archive(
                    self.dist_dir / f"{self.fullname}.zip", self.src_dist_dir
                )

            else:  # wheel
                url = self.source_metadata.url
                prebuilt_wheel = url and url.endswith(".whl")
                if not prebuilt_wheel:
                    self._compile(bash_runner)

                self._package_wheel(bash_runner)
                shutil.rmtree(self.dist_dir, ignore_errors=True)
                shutil.copytree(self.src_dist_dir, self.dist_dir)

    def _load_recipe(self, package_dir: Path) -> tuple[Path, MetaConfig]:
        """
        Load the package configuration from the given directory.

        Parameters
        ----------
        package_dir
            The directory containing the package configuration, or the path to the
            package configuration file.

        Returns
        -------
        pkg_dir
            The directory containing the package configuration.
        pkg
            The package configuration.
        """
        if not package_dir.exists():
            raise FileNotFoundError(f"Package directory {package_dir} does not exist")

        if package_dir.is_dir():
            meta_file = package_dir / "meta.yaml"
        else:
            meta_file = package_dir
            package_dir = meta_file.parent

        return package_dir, MetaConfig.from_yaml(meta_file)

    def _check_executables(self) -> None:
        """
        Check that the executables required to build the package are available.
        """
        missing_executables = common.find_missing_executables(
            self.recipe.requirements.executable
        )
        if missing_executables:
            missing_string = ", ".join(missing_executables)
            error_msg = (
                f"The following executables are required to build {self.name}, but missing in the host system: "
                + missing_string
            )
            raise RuntimeError(error_msg)

    def _prepare_source(self) -> None:
        """
        Figure out from the "source" key in the package metadata where to get the source
        from, then get the source into the build directory.
        """

        # clear the build directory
        if self.build_dir.resolve().is_dir():
            shutil.rmtree(self.build_dir)

        self.build_dir.mkdir(parents=True, exist_ok=True)

        if self.source_metadata.url is not None:
            self._download_and_extract()
            return

        # Build from local source, mostly for testing purposes.
        if self.source_metadata.path is None:
            raise ValueError(
                "Incorrect source provided. Either a url or a path must be provided."
            )

        srcdir = self.source_metadata.path.resolve()
        if not srcdir.is_dir():
            raise ValueError(f"path={srcdir} must point to a directory that exists")

        def ignore(path: str, names: list[str]) -> list[str]:
            ignored: list[str] = []

            if fnmatch.fnmatch(path, "*/dist"):
                # Do not copy dist/*.whl files from a dirty source tree;
                # this can lead to "Exception: Unexpected number of wheels" later.
                ignored.extend(name for name in names if name.endswith(".whl"))
            return ignored

        shutil.copytree(srcdir, self.src_extract_dir, ignore=ignore)

        self.src_dist_dir.mkdir(parents=True, exist_ok=True)

    def _download_and_extract(self) -> None:
        """
        Download the source from specified in the package metadata,
        then checksum it, then extract the archive into the build directory.
        """
        build_env = get_build_environment_vars(get_pyodide_root())
        url = cast(str, self.source_metadata.url)  # we know it's not None
        url = _environment_substitute_str(url, build_env)

        max_retry = 3
        for retry_cnt in range(max_retry):
            try:
                response = requests.get(url)
                response.raise_for_status()
            except requests.HTTPError as e:
                if retry_cnt == max_retry - 1:
                    raise RuntimeError(
                        f"Failed to download {url} after {max_retry} trials"
                    ) from e

                continue

            break

        self.build_dir.mkdir(parents=True, exist_ok=True)

        tarballname = url.split("/")[-1]
        if "Content-Disposition" in response.headers:
            filenames = re.findall(
                "filename=(.+)", response.headers["Content-Disposition"]
            )
            if filenames:
                tarballname = filenames[0]

        tarballpath = self.build_dir / tarballname
        tarballpath.write_bytes(response.content)

        checksum = self.source_metadata.sha256
        if checksum is not None:
            try:
                checksum = _environment_substitute_str(checksum, build_env)
                check_checksum(tarballpath, checksum)
            except Exception:
                tarballpath.unlink()
                raise

        # already built
        if tarballpath.suffix == ".whl":
            self.src_dist_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(tarballpath, self.src_dist_dir)
            return

        shutil.unpack_archive(tarballpath, self.build_dir)

        extract_dir_name = self.source_metadata.extract_dir
        if extract_dir_name is None:
            extract_dir_name = trim_archive_extension(tarballname)

        shutil.move(self.build_dir / extract_dir_name, self.src_extract_dir)
        self.src_dist_dir.mkdir(parents=True, exist_ok=True)

    def _compile(
        self,
        bash_runner: BashRunnerWithSharedEnvironment,
    ) -> None:
        """
        Runs pypa/build for the package.

        Parameters
        ----------
        bash_runner
            The runner we will use to execute our bash commands. Preserves environment
            variables from one invocation to the next.

        target_install_dir
            The path to the target Python installation

        """

        cflags = self.build_metadata.cflags + " " + self.build_args.cflags
        cxxflags = self.build_metadata.cxxflags + " " + self.build_args.cxxflags
        ldflags = self.build_metadata.ldflags + " " + self.build_args.ldflags

        build_env_ctx = pypabuild.get_build_env(
            env=bash_runner.env,
            pkgname=self.name,
            cflags=cflags,
            cxxflags=cxxflags,
            ldflags=ldflags,
            target_install_dir=self.build_args.target_install_dir,
            exports=self.build_metadata.exports,
        )
        config_settings = pypabuild.parse_backend_flags(
            self.build_metadata.backend_flags
        )

        with build_env_ctx as build_env:
            if self.build_metadata.cross_script is not None:
                with BashRunnerWithSharedEnvironment(build_env) as runner:
                    runner.run(
                        self.build_metadata.cross_script,
                        script_name="cross script",
                        cwd=self.src_extract_dir,
                    )
                    build_env = runner.env

            pypabuild.build(
                self.src_extract_dir, self.src_dist_dir, build_env, config_settings
            )

    def _package_wheel(
        self,
        bash_runner: BashRunnerWithSharedEnvironment,
    ) -> None:
        """Package a wheel

        This unpacks the wheel, unvendors tests if necessary, runs and "build.post"
        script, and then repacks the wheel.

        Parameters
        ----------
        bash_runner
            The runner we will use to execute our bash commands. Preserves
            environment variables from one invocation to the next.
        """
        wheel, *rest = find_matching_wheels(
            self.src_dist_dir.glob("*.whl"), pyodide_tags()
        )
        if rest:
            raise Exception(
                f"Unexpected number of wheels {len(rest) + 1} when building {self.name}"
            )

        if "emscripten" in wheel.name:
            # Retag platformed wheels to pyodide
            wheel = retag_wheel(wheel, wheel_platform())

        logger.info(f"Unpacking wheel to {str(wheel)}")

        name, ver, _ = wheel.name.split("-", 2)

        with modify_wheel(wheel) as wheel_dir:
            # update so abi tags after build is complete but before running post script
            # to maximize sanity.
            replace_so_abi_tags(wheel_dir)
            bash_runner.run(
                self.build_metadata.post, script_name="post script", cwd=wheel_dir
            )

            if self.build_metadata.vendor_sharedlib:
                lib_dir = self.library_install_prefix
                copy_sharedlibs(wheel, wheel_dir, lib_dir)

            python_dir = f"python{sys.version_info.major}.{sys.version_info.minor}"
            host_site_packages = (
                Path(self.build_args.host_install_dir)
                / f"lib/{python_dir}/site-packages"
            )
            if self.build_metadata.cross_build_env:
                subprocess.run(
                    ["pip", "install", "-t", str(host_site_packages), f"{name}=={ver}"],
                    check=True,
                )

            for cross_build_file in self.build_metadata.cross_build_files:
                shutil.copy(
                    (wheel_dir / cross_build_file),
                    host_site_packages / cross_build_file,
                )

            try:
                test_dir = self.src_dist_dir / "tests"
                if self.build_metadata.unvendor_tests:
                    nmoved = unvendor_tests(
                        wheel_dir, test_dir, self.build_metadata.retain_test_patterns
                    )
                    if nmoved:
                        with chdir(self.src_dist_dir):
                            shutil.make_archive(f"{self.name}-tests", "tar", test_dir)
            finally:
                shutil.rmtree(test_dir, ignore_errors=True)

    def _patch(self) -> None:
        """
        Apply patches to the source.
        """
        token_path = self.src_extract_dir / ".patched"
        if token_path.is_file():
            return

        patches = self.source_metadata.patches
        extras = self.source_metadata.extras
        cast(str, self.source_metadata.url)

        if not patches and not extras:
            return

        # Apply all the patches
        for patch in patches:
            patch_abspath = self.pkg_root / patch
            result = subprocess.run(
                ["patch", "-p1", "--binary", "--verbose", "-i", patch_abspath],
                check=False,
                encoding="utf-8",
                cwd=self.src_extract_dir,
            )
            if result.returncode != 0:
                logger.error(f"ERROR: Patch {patch_abspath} failed")
                exit_with_stdio(result)

        # Add any extra files
        for src, dst in extras:
            shutil.copyfile(self.pkg_root / src, self.src_extract_dir / dst)

        token_path.touch()

    def _redirect_stdout_stderr_to_logfile(self) -> None:
        """
        Redirect stdout and stderr to a log file.
        """
        try:
            stdout_fileno = sys.stdout.fileno()
            stderr_fileno = sys.stderr.fileno()

            tee = subprocess.Popen(
                ["tee", self.pkg_root / "build.log"], stdin=subprocess.PIPE
            )

            # Cause tee's stdin to get a copy of our stdin/stdout (as well as that
            # of any child processes we spawn)
            os.dup2(tee.stdin.fileno(), stdout_fileno)  # type: ignore[union-attr]
            os.dup2(tee.stdin.fileno(), stderr_fileno)  # type: ignore[union-attr]
        except OSError:
            # This normally happens when testing
            logger.warning("stdout/stderr does not have a fileno, not logging to file")

    def _get_helper_vars(self) -> dict[str, str]:
        """
        Get the helper variables for the build script.
        """
        return {
            "PKGDIR": str(self.pkg_root),
            "PKG_VERSION": self.version,
            "PKG_BUILD_DIR": str(self.src_extract_dir),
            "DISTDIR": str(self.src_dist_dir),
            # TODO: rename this to something more compatible with Makefile or CMake conventions
            "WASM_LIBRARY_DIR": str(self.library_install_prefix),
            # Using PKG_CONFIG_LIBDIR instead of PKG_CONFIG_PATH,
            # so pkg-config will not look in the default system directories
            "PKG_CONFIG_LIBDIR": str(self.library_install_prefix / "lib/pkgconfig"),
        }


def check_checksum(archive: Path, checksum: str) -> None:
    """
    Checks that an archive matches the checksum in the package metadata.


    Parameters
    ----------
    archive
        the path to the archive we wish to checksum
    checksum
        the checksum we expect the archive to have
    """
    real_checksum = _get_sha256_checksum(archive)
    if real_checksum != checksum:
        raise ValueError(
            f"Invalid sha256 checksum: {real_checksum} != {checksum} (expected)"
        )


def trim_archive_extension(tarballname: str) -> str:
    for extension in [
        ".tar.gz",
        ".tgz",
        ".tar",
        ".tar.bz2",
        ".tbz2",
        ".tar.xz",
        ".txz",
        ".zip",
        ".whl",
    ]:
        if tarballname.endswith(extension):
            return tarballname[: -len(extension)]
    return tarballname


def copy_sharedlibs(
    wheel_file: Path, wheel_dir: Path, lib_dir: Path
) -> dict[str, Path]:
    from auditwheel_emscripten import copylib, resolve_sharedlib
    from auditwheel_emscripten.wheel_utils import WHEEL_INFO_RE

    match = WHEEL_INFO_RE.match(wheel_file.name)
    if match is None:
        raise RuntimeError(f"Failed to parse wheel file name: {wheel_file.name}")

    dep_map: dict[str, Path] = resolve_sharedlib(
        wheel_dir,
        lib_dir,
    )
    lib_sdir: str = match.group("name") + ".libs"

    if dep_map:
        dep_map_new = copylib(wheel_dir, dep_map, lib_sdir)
        logger.info("Copied shared libraries:")
        for lib, path in dep_map_new.items():
            original_path = dep_map[lib]
            logger.info(f"  {original_path} -> {path}")

        return dep_map_new

    return {}


def unvendor_tests(
    install_prefix: Path, test_install_prefix: Path, retain_test_patterns: list[str]
) -> int:
    """Unvendor test files and folders

    This function recursively walks through install_prefix and moves anything
    that looks like a test folder under test_install_prefix.


    Parameters
    ----------
    install_prefix
        the folder where the package was installed
    test_install_prefix
        the folder where to move the tests. If it doesn't exist, it will be
        created.

    Returns
    -------
    n_moved
        number of files or folders moved
    """
    n_moved = 0
    out_files = []
    shutil.rmtree(test_install_prefix, ignore_errors=True)
    for root, _dirs, files in os.walk(install_prefix):
        root_rel = Path(root).relative_to(install_prefix)
        if root_rel.name == "__pycache__" or root_rel.name.endswith(".egg_info"):
            continue
        if root_rel.name in ["test", "tests"]:
            # This is a test folder
            (test_install_prefix / root_rel).parent.mkdir(exist_ok=True, parents=True)
            shutil.move(install_prefix / root_rel, test_install_prefix / root_rel)
            n_moved += 1
            continue
        out_files.append(root)
        for fpath in files:
            if (
                fnmatch.fnmatchcase(fpath, "test_*.py")
                or fnmatch.fnmatchcase(fpath, "*_test.py")
                or fpath == "conftest.py"
            ):
                if any(fnmatch.fnmatchcase(fpath, pat) for pat in retain_test_patterns):
                    continue
                (test_install_prefix / root_rel).mkdir(exist_ok=True, parents=True)
                shutil.move(
                    install_prefix / root_rel / fpath,
                    test_install_prefix / root_rel / fpath,
                )
                n_moved += 1

    return n_moved


# TODO: move this to common.py or somewhere else
def needs_rebuild(
    pkg_root: Path, buildpath: Path, source_metadata: _SourceSpec
) -> bool:
    """
    Determines if a package needs a rebuild because its meta.yaml, patches, or
    sources are newer than the `.packaged` thunk.

    pkg_root
        The path to the root directory for the package. Generally
        $PYODIDE_ROOT/packages/<PACKAGES>

    buildpath
        The path to the build directory. By default, it will be
        $(PYOIDE_ROOT)/packages/<PACKAGE>/build/.

    src_metadata
        The source section from meta.yaml.
    """
    packaged_token = buildpath / ".packaged"
    if not packaged_token.is_file():
        logger.debug(
            f"{pkg_root} needs rebuild because {packaged_token} does not exist"
        )
        return True

    package_time = packaged_token.stat().st_mtime

    def source_files() -> Iterator[Path]:
        yield pkg_root / "meta.yaml"
        yield from (pkg_root / patch_path for patch_path in source_metadata.patches)
        yield from (pkg_root / patch_path for [patch_path, _] in source_metadata.extras)
        src_path = source_metadata.path
        if src_path:
            yield from (pkg_root / src_path).resolve().glob("**/*")

    for source_file in source_files():
        source_file = Path(source_file)
        if source_file.stat().st_mtime > package_time:
            return True
    return False
