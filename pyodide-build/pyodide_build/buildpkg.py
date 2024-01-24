#!/usr/bin/env python3

"""
Builds a Pyodide package.
"""

import cgi
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import textwrap
import urllib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any, TextIO, cast
from urllib import request

from . import pypabuild
from .build_env import (
    RUST_BUILD_PRELUDE,
    get_build_environment_vars,
    get_build_flag,
    get_pyodide_root,
    pyodide_tags,
    replace_so_abi_tags,
)
from .common import (
    _environment_substitute_str,
    _get_sha256_checksum,
    chdir,
    exit_with_stdio,
    find_matching_wheels,
    find_missing_executables,
    make_zip_archive,
    modify_wheel,
)
from .io import MetaConfig, _BuildSpec, _SourceSpec
from .logger import logger
from .pywasmcross import BuildArgs


def _make_whlfile(
    *args: Any, owner: int | None = None, group: int | None = None, **kwargs: Any
) -> str:
    return shutil._make_zipfile(*args, **kwargs)  # type: ignore[attr-defined]


shutil.register_archive_format("whl", _make_whlfile, description="Wheel file")
shutil.register_unpack_format(
    "whl", [".whl", ".wheel"], shutil._unpack_zipfile, description="Wheel file"  # type: ignore[attr-defined]
)


class BashRunnerWithSharedEnvironment:
    """Run multiple bash scripts with persistent environment.

    Environment is stored to "env" member between runs. This can be updated
    directly to adjust the environment, or read to get variables.
    """

    def __init__(self, env: dict[str, str] | None = None) -> None:
        if env is None:
            env = dict(os.environ)

        self._reader: TextIO | None
        self._fd_write: int | None
        self.env: dict[str, str] = env

    def __enter__(self) -> "BashRunnerWithSharedEnvironment":
        fd_read, self._fd_write = os.pipe()
        self._reader = os.fdopen(fd_read, "r")
        return self

    def run_unchecked(self, cmd: str, **opts: Any) -> subprocess.CompletedProcess[str]:
        assert self._fd_write is not None
        assert self._reader is not None

        write_env_pycode = ";".join(
            [
                "import os",
                "import json",
                f'os.write({self._fd_write}, json.dumps(dict(os.environ)).encode() + b"\\n")',
            ]
        )
        write_env_shell_cmd = f"{sys.executable} -c '{write_env_pycode}'"
        full_cmd = f"{cmd}\n{write_env_shell_cmd}"
        result = subprocess.run(
            ["bash", "-ce", full_cmd],
            pass_fds=[self._fd_write],
            env=self.env,
            encoding="utf8",
            **opts,
        )
        if result.returncode == 0:
            self.env = json.loads(self._reader.readline())
        return result

    def run(
        self,
        cmd: str | None,
        *,
        script_name: str,
        cwd: Path | str | None = None,
        **opts: Any,
    ) -> subprocess.CompletedProcess[str] | None:
        """Run a bash script. Any keyword arguments are passed on to subprocess.run."""
        if not cmd:
            return None
        if cwd is None:
            cwd = Path.cwd()
        cwd = Path(cwd).absolute()
        logger.info(f"Running {script_name} in {str(cwd)}")
        opts["cwd"] = cwd
        result = self.run_unchecked(cmd, **opts)
        if result.returncode != 0:
            logger.error(f"ERROR: {script_name} failed")
            logger.error(textwrap.indent(cmd, "    "))
            exit_with_stdio(result)
        return result

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Free the file descriptors."""

        if self._fd_write:
            os.close(self._fd_write)
            self._fd_write = None
        if self._reader:
            self._reader.close()
            self._reader = None


@contextmanager
def get_bash_runner(extra_envs: dict[str, str]) -> Iterator[BashRunnerWithSharedEnvironment]:
    PYODIDE_ROOT = get_pyodide_root()
    env = get_build_environment_vars()
    env.update(extra_envs)

    with BashRunnerWithSharedEnvironment(env=env) as b:
        # Working in-tree, add emscripten toolchain into PATH and set ccache
        if Path(PYODIDE_ROOT, "pyodide_env.sh").exists():
            b.run(
                f"source {PYODIDE_ROOT}/pyodide_env.sh",
                script_name="source pyodide_env",
                stderr=subprocess.DEVNULL,
            )

        yield b


class RecipeBuilder:
    """
    A class to build a Pyodide meta.yaml recipe.
    """

    def __init__(self,
        recipe: str | Path,
        build_args: BuildArgs,
        build_dir: str | Path | None,
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
        self.pkg_root, self.recipe = _load_package_config(meta_file)

        self.name = self.recipe.package.name
        self.version = self.recipe.package.version
        self.fullname = f"{self.name}-{self.version}"

        self.build_dir = Path(build_dir).resolve() if build_dir else self.pkg_root / "build"
        self.src_extract_dir = self.build_dir / self.fullname # where we extract the source

        # where the built artifacts are put.
        # For wheels, this is the default location where the built wheels are put by pypa/build.
        # For shared libraries, users should use this directory to put the built shared libraries (can be accessed by DISTDIR env var)
        self.src_dist_dir = self.src_extract_dir / "dist" 

        # where Pyodide will look for the built artifacts when building pyodide-lock.json.
        # after building packages, artifacts in src_dist_dir will be copied to dist_dir
        self.dist_dir = self.pkg_root / "dist" 

        self.source_metadata = self.recipe.source
        self.build_metadata = self.recipe.build
        self.build_metadata.cflags += f" {build_args.cflags}"
        self.build_metadata.cxxflags += f" {build_args.cxxflags}"
        self.build_metadata.ldflags += f" {build_args.ldflags}"

        self.force_rebuild = force_rebuild or continue_
        self.continue_ = continue_

    def build(self) -> None:
        """
        Build the package. This is the only public method of this class.
        """
        _check_executables(pkg)

        t0 = datetime.now()
        timestamp = t0.strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[{timestamp}] Building package {self.name}...")
        success = True
        try:
            self._build()

            (self.build_dir / ".packaged").touch()
        except Exception:
            success = False
            raise
        finally:
            t1 = datetime.now()
            datestamp = "[{}]".format(t1.strftime("%Y-%m-%d %H:%M:%S"))
            total_seconds = f"{(t1 - t0).total_seconds():.1f}"
            status = "Succeeded" if success else "Failed"
            msg = (
                f"{datestamp} {status} building package {name} in {total_seconds} seconds."
            )
            if success:
                logger.success(msg)
            else:
                logger.error(msg)

    def _build(self) -> None:
        if not self.force_rebuild and not needs_rebuild(self.pkg_root, self.build_dir, self.source_metadata):
            return

        if self.continue_ and not self.src_extract_dir.exists():
            raise OSError(
                "Cannot find source for rebuild. Expected to find the source "
                f"directory at the path {self.src_extract_dir}, but that path does not exist."
            )

        self._redirect_stdout_stderr_to_logfile()

        with chdir(pkg_root), get_bash_runner(self._get_helper_vars()) as bash_runner:
            if not self.continue_:
                self._prepare_source()
                self._patch()

            if pkg.is_rust_package():
                bash_runner.run(
                    RUST_BUILD_PRELUDE,
                    script_name="rust build prelude",
                    cwd=self.src_extract_dir,
                )
            
            bash_runner.run(self.build_metadata.script, script_name="build script", cwd=self.src_extract_dir)

            self._finish()

    def _check_executables(self) -> None:
        """
        Check that the executables required to build the package are available.
        """
        missing_executables = find_missing_executables(self.recipe.requirements.executable)
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

        shutil.copytree(srcdir, srcpath)

    def _download_and_extract(self) -> None:
        """
        Download the source from specified in the package metadata,
        then checksum it, then extract the archive into the build directory.
        """

        build_env = get_build_environment_vars()
        url = cast(str, self.source_metadata.url)  # we know it's not None
        url = _environment_substitute_str(url, build_env)

        max_retry = 3
        for retry_cnt in range(max_retry):
            try:
                response = request.urlopen(url)
            except urllib.error.URLError as e:
                if retry_cnt == max_retry - 1:
                    raise RuntimeError(
                        f"Failed to download {url} after {max_retry} trials"
                    ) from e

                continue

            break

        # TODO: replace cgi with something else (will be removed in Python 3.13)
        _, parameters = cgi.parse_header(response.headers.get("Content-Disposition", ""))
        if "filename" in parameters:
            tarballname = parameters["filename"]
        else:
            tarballname = Path(response.geturl()).name

        self.build_dir.mkdir(parents=True, exist_ok=True)
        tarballpath = self.build_dir / tarballname
        tarballpath.write_bytes(response.read())

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
            self.src_extract_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(tarballpath, self.src_extract_dir)
            return


        shutil.unpack_archive(tarballpath, self.build_dir)

        extract_dir_name = self.source_metadata.extract_dir
        if extract_dir_name is None:
            extract_dir_name = trim_archive_extension(tarballname)

        shutil.move(self.build_dir / extract_dir_name, self.src_extract_dir)

    def _patch(self) -> None:
        """
        Apply patches to the source.
        """
        token_path = self.src_extract_dir / ".patched"
        if token_path.is_file():
            return

        patches = self.source_metadata.patches
        extras = self.source_metadata.extras
        url = cast(str, self.source_metadata.url)

        if not patches and not extras:
            return

        # We checked these in check_package_config.
        assert not src_metadata.url.endswith(".whl")

        # Apply all the patches
        for patch in patches:
            result = subprocess.run(
                ["patch", "-p1", "--binary", "--verbose", "-i", pkg_root / patch],
                check=False,
                encoding="utf-8",
                cwd=srcpath,
            )
            if result.returncode != 0:
                logger.error(f"ERROR: Patch {pkg_root/patch} failed")
                exit_with_stdio(result)

        # Add any extra files
        for src, dst in extras:
            shutil.copyfile(pkg_root / src, srcpath / dst)

        token_path.touch()

    def _redirect_stdout_stderr_to_logfile(self) -> None:
        """
        Redirect stdout and stderr to a log file.
        """
        try:
            stdout_fileno = sys.stdout.fileno()
            stderr_fileno = sys.stderr.fileno()

            tee = subprocess.Popen(["tee", self.pkg_root / "build.log"], stdin=subprocess.PIPE)

            # Cause tee's stdin to get a copy of our stdin/stdout (as well as that
            # of any child processes we spawn)
            os.dup2(tee.stdin.fileno(), stdout_fileno)  # type: ignore[union-attr]
            os.dup2(tee.stdin.fileno(), stderr_fileno)  # type: ignore[union-attr]
        except OSError:
            # This normally happens when testing
            logger.warning("stdout/stderr does not have a fileno, not logging to file")

    @cache
    def _get_helper_vars(self) -> dict[str, str]:
        """
        Get the helper variables for the build script.
        """
        return {
            "PKGDIR": str(self.pkg_root),
            "PKG_VERSION": self.version,
            "PKG_BUILD_DIR": str(self.srcpath),
            "DISTDIR": str(self.src_dist_dir),
        }

    # TODO: subclass this for different package types?
    def _finish(self) -> None:
        """
        Finish building the package:
            - Make an archive of the built files
            - Remove old build files
        """
        package_type = self.build_metadata.package_type

        if package_type == "static_library":
            # Nothing needs to be done for a static library
            pass

        elif package_type in ("shared_library", "cpython_module"):
            # If shared library, we copy .so files to dist_dir
            # and create a zip archive of the .so files
            shutil.rmtree(dist_dir, ignore_errors=True)
            dist_dir.mkdir(parents=True)
            make_zip_archive(dist_dir / f"{src_dir_name}.zip", src_dist_dir)

        else:  # wheel
            url = self.source_metadata.url
            finished_wheel = url and url.endswith(".whl")
            if not finished_wheel:
                compile(
                    name,
                    srcpath,
                    build_metadata,
                    bash_runner,
                    target_install_dir=build_args.target_install_dir,
                )

            package_wheel(
                self.name, srcpath, build_metadata, bash_runner, build_args.host_install_dir
            )
            shutil.rmtree(dist_dir, ignore_errors=True)
            shutil.copytree(src_dist_dir, dist_dir)



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


def compile(
    name: str,
    srcpath: Path,
    build_metadata: _BuildSpec,
    bash_runner: BashRunnerWithSharedEnvironment,
    *,
    target_install_dir: str,
) -> None:
    """
    Runs pywasmcross for the package. The effect of this is to first run setup.py
    with compiler wrappers subbed in, which don't actually build the package but
    write the compile commands to build.log. Then we walk over build log and invoke
    the same set of commands but with some flags munged around or removed to make it
    work with emcc.

    In any case, only works for Python packages, not libraries or shared libraries
    which don't have a setup.py.

    Parameters
    ----------
    srcpath
        The path to the source. We extract the source into the build directory, so it
        will be something like
        $(PYOIDE_ROOT)/packages/<PACKAGE>/build/<PACKAGE>-<VERSION>.

    build_metadata
        The build section from meta.yaml.

    bash_runner
        The runner we will use to execute our bash commands. Preserves environment
        variables from one invocation to the next.

    target_install_dir
        The path to the target Python installation

    """
    # This function runs pypa/build. libraries don't need to do this.
    if build_metadata.package_type != "package":
        return

    build_env_ctx = pypabuild.get_build_env(
        env=bash_runner.env,
        pkgname=name,
        cflags=build_metadata.cflags,
        cxxflags=build_metadata.cxxflags,
        ldflags=build_metadata.ldflags,
        target_install_dir=target_install_dir,
        exports=build_metadata.exports,
    )
    config_settings = pypabuild.parse_backend_flags(build_metadata.backend_flags)

    with build_env_ctx as build_env:
        if build_metadata.cross_script is not None:
            with BashRunnerWithSharedEnvironment(build_env) as runner:
                runner.run(
                    build_metadata.cross_script, script_name="cross script", cwd=srcpath
                )
                build_env = runner.env

        from .pypabuild import build

        outpath = srcpath / "dist"
        build(srcpath, outpath, build_env, config_settings)


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


def package_wheel(
    pkg_name: str,
    srcpath: Path,
    build_metadata: _BuildSpec,
    bash_runner: BashRunnerWithSharedEnvironment,
    host_install_dir: str,
) -> None:
    """Package a wheel

    This unpacks the wheel, unvendors tests if necessary, runs and "build.post"
    script, and then repacks the wheel.

    Parameters
    ----------
    pkg_name
        The name of the package

    srcpath
        The path to the source. We extract the source into the build directory,
        so it will be something like
        $(PYOIDE_ROOT)/packages/<PACKAGE>/build/<PACKAGE>-<VERSION>.

    build_metadata
        The build section from meta.yaml.

    bash_runner
        The runner we will use to execute our bash commands. Preserves
        environment variables from one invocation to the next.
    """
    if build_metadata.package_type != "package":
        return

    distdir = srcpath / "dist"
    wheel, *rest = find_matching_wheels(distdir.glob("*.whl"), pyodide_tags())
    if rest:
        raise Exception(
            f"Unexpected number of wheels {len(rest) + 1} when building {pkg_name}"
        )
    logger.info(f"Unpacking wheel to {str(wheel)}")

    name, ver, _ = wheel.name.split("-", 2)

    with modify_wheel(wheel) as wheel_dir:
        # update so abi tags after build is complete but before running post script
        # to maximize sanity.
        replace_so_abi_tags(wheel_dir)

        bash_runner.env.update({"WHEELDIR": str(wheel_dir)})
        post = build_metadata.post
        bash_runner.run(post, script_name="post script")

        vendor_sharedlib = build_metadata.vendor_sharedlib
        if vendor_sharedlib:
            lib_dir = Path(get_build_flag("WASM_LIBRARY_DIR"))
            copy_sharedlibs(wheel, wheel_dir, lib_dir)

        python_dir = f"python{sys.version_info.major}.{sys.version_info.minor}"
        host_site_packages = Path(host_install_dir) / f"lib/{python_dir}/site-packages"
        if build_metadata.cross_build_env:
            subprocess.run(
                ["pip", "install", "-t", str(host_site_packages), f"{name}=={ver}"],
                check=True,
            )

        cross_build_files = build_metadata.cross_build_files
        if cross_build_files:
            for file_ in cross_build_files:
                shutil.copy((wheel_dir / file_), host_site_packages / file_)

        try:
            test_dir = distdir / "tests"
            nmoved = 0
            if build_metadata.unvendor_tests:
                nmoved = unvendor_tests(wheel_dir, test_dir)
            if nmoved:
                with chdir(distdir):
                    shutil.make_archive(f"{pkg_name}-tests", "tar", test_dir)
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)


def unvendor_tests(install_prefix: Path, test_install_prefix: Path) -> int:
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
                (test_install_prefix / root_rel).mkdir(exist_ok=True, parents=True)
                shutil.move(
                    install_prefix / root_rel / fpath,
                    test_install_prefix / root_rel / fpath,
                )
                n_moved += 1

    return n_moved


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


def _load_package_config(package_dir: Path) -> tuple[Path, MetaConfig]:
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
