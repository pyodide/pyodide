#!/usr/bin/env python3

"""
Builds a Pyodide package.
"""

import argparse
import cgi
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import textwrap
import urllib
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from types import TracebackType
from typing import Any, TextIO, cast
from urllib import request

from . import common, pywasmcross
from .common import (
    BUILD_VARS,
    exit_with_stdio,
    find_matching_wheels,
    find_missing_executables,
)
from .io import MetaConfig, _BuildSpec, _SourceSpec


@contextmanager
def chdir(new_dir: Path) -> Generator[None, None, None]:
    orig_dir = Path.cwd()
    try:
        os.chdir(new_dir)
        yield
    finally:
        os.chdir(orig_dir)


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

    def run(self, cmd: str, **opts: Any) -> subprocess.CompletedProcess[str]:
        """Run a bash script. Any keyword arguments are passed on to subprocess.run."""
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
        if result.returncode != 0:
            print("ERROR: bash command failed")
            print(textwrap.indent(cmd, "    "))
            exit_with_stdio(result)

        self.env = json.loads(self._reader.readline())
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
def get_bash_runner() -> Iterator[BashRunnerWithSharedEnvironment]:
    PYODIDE_ROOT = os.environ["PYODIDE_ROOT"]
    env = {key: os.environ[key] for key in BUILD_VARS} | {"PYODIDE": "1"}
    if "PYODIDE_JOBS" in os.environ:
        env["PYODIDE_JOBS"] = os.environ["PYODIDE_JOBS"]

    env["PKG_CONFIG_PATH"] = env["WASM_PKG_CONFIG_PATH"]
    if "PKG_CONFIG_PATH" in os.environ:
        env["PKG_CONFIG_PATH"] += f":{os.environ['PKG_CONFIG_PATH']}"

    tools_dir = Path(__file__).parent / "tools"

    env["CMAKE_TOOLCHAIN_FILE"] = str(
        tools_dir / "cmake/Modules/Platform/Emscripten.cmake"
    )
    env["PYO3_CONFIG_FILE"] = str(tools_dir / "pyo3_config.ini")

    with BashRunnerWithSharedEnvironment(env=env) as b:
        b.run(f"source {PYODIDE_ROOT}/pyodide_env.sh", stderr=subprocess.DEVNULL)
        yield b


def check_checksum(archive: Path, source_metadata: _SourceSpec) -> None:
    """
    Checks that an archive matches the checksum in the package metadata.


    Parameters
    ----------
    archive
        the path to the archive we wish to checksum
    source_metadata
        The source section from meta.yaml.
    """
    if source_metadata.sha256 is None:
        return
    checksum = source_metadata.sha256
    CHUNK_SIZE = 1 << 16
    h = hashlib.sha256()
    with open(archive, "rb") as fd:
        while True:
            chunk = fd.read(CHUNK_SIZE)
            h.update(chunk)
            if len(chunk) < CHUNK_SIZE:
                break
    if h.hexdigest() != checksum:
        raise ValueError(f"Invalid sha256 checksum: {h.hexdigest()}")


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


def download_and_extract(
    buildpath: Path, srcpath: Path, src_metadata: _SourceSpec
) -> None:
    """
    Download the source from specified in the meta data, then checksum it, then
    extract the archive into srcpath.

    Parameters
    ----------

    buildpath
        The path to the build directory. Generally will be
        $(PYOIDE_ROOT)/packages/<package-name>/build/.

    srcpath
        The place we want the source to end up. Will generally be
        $(PYOIDE_ROOT)/packages/<package-name>/build/<package-name>-<package-version>.

    src_metadata
        The source section from meta.yaml.
    """
    # We only call this function when the URL is defined
    url = cast(str, src_metadata.url)
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

    _, parameters = cgi.parse_header(response.headers.get("Content-Disposition", ""))
    if "filename" in parameters:
        tarballname = parameters["filename"]
    else:
        tarballname = Path(response.geturl()).name

    tarballpath = buildpath / tarballname
    if not tarballpath.is_file():
        os.makedirs(tarballpath.parent, exist_ok=True)
        with open(tarballpath, "wb") as f:
            f.write(response.read())
        try:
            check_checksum(tarballpath, src_metadata)
        except Exception:
            tarballpath.unlink()
            raise

    if tarballpath.suffix == ".whl":
        os.makedirs(srcpath / "dist")
        shutil.copy(tarballpath, srcpath / "dist")
        return

    if not srcpath.is_dir():
        shutil.unpack_archive(tarballpath, buildpath)

    extract_dir_name = src_metadata.extract_dir
    if extract_dir_name is None:
        extract_dir_name = trim_archive_extension(tarballname)

    shutil.move(buildpath / extract_dir_name, srcpath)


def prepare_source(
    buildpath: Path, srcpath: Path, src_metadata: _SourceSpec, clear_only: bool = False
) -> None:
    """
    Figure out from the "source" key in the package metadata where to get the source
    from, then get the source into srcpath (or somewhere else, if it goes somewhere
    else, returns where it ended up).

    Parameters
    ----------
    buildpath
        The path to the build directory. Generally will be
        $(PYOIDE_ROOT)/packages/<PACKAGE>/build/.

    srcpath
        The default place we want the source to end up. Will generally be
        $(PYOIDE_ROOT)/packages/<package-name>/build/<package-name>-<package-version>.

    src_metadata
        The source section from meta.yaml.

    clear_only
        Clear the source directory only, do not download or extract the source.
        Set this to True if the source collected from external source.

    Returns
    -------
        The location where the source ended up. TODO: None, actually?
    """
    if buildpath.resolve().is_dir():
        shutil.rmtree(buildpath)
    os.makedirs(buildpath)

    if clear_only:
        srcpath.mkdir(parents=True, exist_ok=True)
        return

    if src_metadata.url is not None:
        download_and_extract(buildpath, srcpath, src_metadata)
        return

    if src_metadata.path is None:
        raise ValueError(
            "Incorrect source provided. Either a url or a path must be provided."
        )

    srcdir = src_metadata.path.resolve()

    if not srcdir.is_dir():
        raise ValueError(f"path={srcdir} must point to a directory that exists")

    shutil.copytree(srcdir, srcpath)


def patch(pkg_root: Path, srcpath: Path, src_metadata: _SourceSpec) -> None:
    """
    Apply patches to the source.

    Parameters
    ----------
    pkg_root
        The path to the root directory for the package. Generally
        $PYODIDE_ROOT/packages/<PACKAGES>

    srcpath
        The path to the source. We extract the source into the build directory, so it
        will be something like
        $(PYOIDE_ROOT)/packages/<PACKAGE>/build/<PACKAGE>-<VERSION>.

    src_metadata
        The "source" key from meta.yaml.
    """
    if (srcpath / ".patched").is_file():
        return

    patches = src_metadata.patches
    extras = src_metadata.extras
    if not patches and not extras:
        return

    # We checked these in check_package_config.
    assert src_metadata.url is not None
    assert not src_metadata.url.endswith(".whl")

    # Apply all the patches
    with chdir(srcpath):
        for patch in patches:
            result = subprocess.run(
                ["patch", "-p1", "--binary", "--verbose", "-i", pkg_root / patch],
                check=False,
                encoding="utf-8",
            )
            if result.returncode != 0:
                print(f"ERROR: Patch {pkg_root/patch} failed")
                exit_with_stdio(result)

    # Add any extra files
    for src, dst in extras:
        shutil.copyfile(pkg_root / src, srcpath / dst)

    with open(srcpath / ".patched", "wb") as fd:
        fd.write(b"\n")


def unpack_wheel(path: Path) -> None:
    with chdir(path.parent):
        result = subprocess.run(
            [sys.executable, "-m", "wheel", "unpack", path.name],
            check=False,
            encoding="utf-8",
        )
        if result.returncode != 0:
            print(f"ERROR: Unpacking wheel {path.name} failed")
            exit_with_stdio(result)


def pack_wheel(path: Path) -> None:
    with chdir(path.parent):
        result = subprocess.run(
            [sys.executable, "-m", "wheel", "pack", path.name],
            check=False,
            encoding="utf-8",
        )
        if result.returncode != 0:
            print(f"ERROR: Packing wheel {path} failed")
            exit_with_stdio(result)


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

    build_env_ctx = pywasmcross.get_build_env(
        env=bash_runner.env,
        pkgname=name,
        cflags=build_metadata.cflags,
        cxxflags=build_metadata.cxxflags,
        ldflags=build_metadata.ldflags,
        target_install_dir=target_install_dir,
        exports=build_metadata.exports,
    )
    backend_flags = build_metadata.backend_flags

    with chdir(srcpath), build_env_ctx as build_env:
        if build_metadata.cross_script is not None:
            with BashRunnerWithSharedEnvironment(build_env) as runner:
                runner.run(build_metadata.cross_script)
                build_env = runner.env

        from .pypabuild import build

        try:
            build(build_env, backend_flags)
        except BaseException:
            build_log_path = Path("build.log")
            if build_log_path.exists():
                build_log_path.unlink()
            raise


def replace_so_abi_tags(wheel_dir: Path) -> None:
    """Replace native abi tag with emscripten abi tag in .so file names"""
    build_soabi = sysconfig.get_config_var("SOABI")
    assert build_soabi
    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX")
    assert ext_suffix
    build_triplet = "-".join(build_soabi.split("-")[2:])
    host_triplet = common.get_make_flag("PLATFORM_TRIPLET")
    for file in wheel_dir.glob(f"**/*{ext_suffix}"):
        file.rename(file.with_name(file.name.replace(build_triplet, host_triplet)))


def copy_sharedlibs(
    wheel_file: Path, wheel_dir: Path, lib_dir: Path
) -> dict[str, Path]:
    from auditwheel_emscripten import copylib, resolve_sharedlib  # type: ignore[import]
    from auditwheel_emscripten.wheel_utils import WHEEL_INFO_RE  # type: ignore[import]

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
        print("Copied shared libraries:")
        for lib, path in dep_map_new.items():
            original_path = dep_map[lib]
            print(f"  {original_path} -> {path}")

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
    wheel, *rest = find_matching_wheels(distdir.glob("*.whl"))
    if rest:
        raise Exception(
            f"Unexpected number of wheels {len(rest) + 1} when building {pkg_name}"
        )
    print(f"Unpacking wheel to {str(wheel)}")
    unpack_wheel(wheel)
    wheel.unlink()
    name, ver, _ = wheel.name.split("-", 2)
    wheel_dir_name = f"{name}-{ver}"
    wheel_dir = distdir / wheel_dir_name

    # update so abi tags after build is complete but before running post script
    # to maximize sanity.
    replace_so_abi_tags(wheel_dir)

    post = build_metadata.post
    if post:
        print("Running post script in ", str(Path.cwd().absolute()))
        bash_runner.env.update({"WHEELDIR": str(wheel_dir)})
        result = bash_runner.run(post)
        if result.returncode != 0:
            print("ERROR: post failed")
            exit_with_stdio(result)

    vendor_sharedlib = build_metadata.vendor_sharedlib
    if vendor_sharedlib:
        lib_dir = Path(common.get_make_flag("WASM_LIBRARY_DIR"))
        copy_sharedlibs(wheel, wheel_dir, lib_dir)

    python_dir = f"python{sys.version_info.major}.{sys.version_info.minor}"
    host_site_packages = Path(host_install_dir) / f"lib/{python_dir}/site-packages"
    if build_metadata.cross_build_env:
        subprocess.check_call(
            ["pip", "install", "-t", str(host_site_packages), f"{name}=={ver}"]
        )

    cross_build_files = build_metadata.cross_build_files
    if cross_build_files:
        for file_ in cross_build_files:
            shutil.copy((wheel_dir / file_), host_site_packages / file_)

    test_dir = distdir / "tests"
    nmoved = 0
    if build_metadata.unvendor_tests:
        nmoved = unvendor_tests(wheel_dir, test_dir)
    if nmoved:
        with chdir(distdir):
            shutil.make_archive(f"{pkg_name}-tests", "tar", test_dir)
    pack_wheel(wheel_dir)
    # wheel_dir causes pytest collection failures for in-tree packages like
    # micropip. To prevent these, we get rid of wheel_dir after repacking the
    # wheel.
    shutil.rmtree(wheel_dir)
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


def create_packaged_token(buildpath: Path) -> None:
    (buildpath / ".packaged").write_text("\n")


def run_script(
    buildpath: Path,
    srcpath: Path,
    build_metadata: _BuildSpec,
    bash_runner: BashRunnerWithSharedEnvironment,
) -> None:
    """
    Run the build script indicated in meta.yaml

    Parameters
    ----------
    buildpath
        the package build path. Usually `packages/<name>/build`

    srcpath
        the package source path. Usually
        `packages/<name>/build/<name>-<version>`.

    build_metadata
        The build section from meta.yaml.

    bash_runner
        The runner we will use to execute our bash commands. Preserves environment
        variables from one invocation to the next.
    """
    script = build_metadata.script
    if not script:
        return

    with chdir(srcpath):
        result = bash_runner.run(script)
        if result.returncode != 0:
            print("ERROR: script failed")
            exit_with_stdio(result)


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
        The path to the build directory. Generally will be
        $(PYOIDE_ROOT)/packages/<PACKAGE>/build/.

    src_metadata
        The source section from meta.yaml.
    """
    packaged_token = buildpath / ".packaged"
    if not packaged_token.is_file():
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


def build_package(
    pkg_root: Path,
    pkg: MetaConfig,
    *,
    target_install_dir: str,
    host_install_dir: str,
    force_rebuild: bool,
    continue_: bool,
) -> None:
    """
    Build the package. The main entrypoint in this module.

    pkg_root
        The path to the root directory for the package. Generally
        $PYODIDE_ROOT/packages/<PACKAGES>

    pkg
        The package metadata parsed from the meta.yaml file in pkg_root

    target_install_dir
        The path to the target Python installation

    host_install_dir
        Directory for installing built host packages.
    """
    source_metadata = pkg.source
    build_metadata = pkg.build
    name = pkg.package.name
    version = pkg.package.version
    build_dir = pkg_root / "build"
    dist_dir = pkg_root / "dist"
    src_dir_name: str = f"{name}-{version}"
    srcpath = build_dir / src_dir_name
    src_dist_dir = srcpath / "dist"
    # Python produces output .whl or .so files in src_dist_dir.
    # We copy them to dist_dir later

    url = source_metadata.url
    finished_wheel = url and url.endswith(".whl")
    post = build_metadata.post
    package_type = build_metadata.package_type

    # These are validated in io.check_package_config
    # If any of these assertions fail, the code path through here might get a
    # bit weird
    if finished_wheel:
        assert not build_metadata.script
        assert package_type == "package"
    if post:
        assert package_type == "package"

    if not force_rebuild and not needs_rebuild(pkg_root, build_dir, source_metadata):
        return

    if continue_ and not srcpath.exists():
        raise OSError(
            "Cannot find source for rebuild. Expected to find the source "
            f"directory at the path {srcpath}, but that path does not exist."
        )

    import os
    import subprocess
    import sys

    tee = subprocess.Popen(["tee", pkg_root / "build.log"], stdin=subprocess.PIPE)
    # Cause tee's stdin to get a copy of our stdin/stdout (as well as that
    # of any child processes we spawn)
    os.dup2(tee.stdin.fileno(), sys.stdout.fileno())  # type: ignore[union-attr]
    os.dup2(tee.stdin.fileno(), sys.stderr.fileno())  # type: ignore[union-attr]

    with chdir(pkg_root), get_bash_runner() as bash_runner:
        bash_runner.env["PKGDIR"] = str(pkg_root)
        bash_runner.env["PKG_VERSION"] = version
        bash_runner.env["PKG_BUILD_DIR"] = str(srcpath)
        if not continue_:
            clear_only = package_type == "cpython_module"
            prepare_source(build_dir, srcpath, source_metadata, clear_only=clear_only)
            patch(pkg_root, srcpath, source_metadata)

        run_script(build_dir, srcpath, build_metadata, bash_runner)

        if package_type == "static_library":
            # Nothing needs to be done for a static library
            pass
        elif package_type in ("shared_library", "cpython_module"):
            # If shared library, we copy .so files to dist_dir
            # and create a zip archive of the .so files
            shutil.rmtree(dist_dir, ignore_errors=True)
            dist_dir.mkdir(parents=True)
            shutil.make_archive(str(dist_dir / src_dir_name), "zip", src_dist_dir)
        else:  # wheel
            if not finished_wheel:
                compile(
                    name,
                    srcpath,
                    build_metadata,
                    bash_runner,
                    target_install_dir=target_install_dir,
                )

            package_wheel(name, srcpath, build_metadata, bash_runner, host_install_dir)
            shutil.rmtree(dist_dir, ignore_errors=True)
            shutil.copytree(src_dist_dir, dist_dir)

        create_packaged_token(build_dir)


def make_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.description = (
        "Build a pyodide package.\n\n"
        "Note: this is a private endpoint that should not be used "
        "outside of the Pyodide Makefile."
    )
    parser.add_argument(
        "package", type=str, nargs=1, help="Path to meta.yaml package description"
    )
    parser.add_argument(
        "--cflags",
        type=str,
        nargs="?",
        default=common.get_make_flag("SIDE_MODULE_CFLAGS"),
        help="Extra compiling flags",
    )
    parser.add_argument(
        "--cxxflags",
        type=str,
        nargs="?",
        default=common.get_make_flag("SIDE_MODULE_CXXFLAGS"),
        help="Extra C++ specific compiling flags",
    )
    parser.add_argument(
        "--ldflags",
        type=str,
        nargs="?",
        default=common.get_make_flag("SIDE_MODULE_LDFLAGS"),
        help="Extra linking flags",
    )
    parser.add_argument(
        "--target-install-dir",
        type=str,
        nargs="?",
        default=common.get_make_flag("TARGETINSTALLDIR"),
        help="The path to the target Python installation",
    )
    parser.add_argument(
        "--host-install-dir",
        type=str,
        nargs="?",
        default=common.get_make_flag("HOSTINSTALLDIR"),
        help=(
            "Directory for installing built host packages. Defaults to setup.py "
            "default. Set to 'skip' to skip installation. Installation is "
            "needed if you want to build other packages that depend on this one."
        ),
    )
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help=(
            "Force rebuild of package regardless of whether it appears to have been updated"
        ),
    )
    parser.add_argument(
        "--continue",
        dest="continue_",
        action="store_true",
        help=(
            dedent(
                """
                Continue a build from the middle. For debugging. Implies "--force-rebuild".
                """
            ).strip()
        ),
    )
    return parser


def main(args: argparse.Namespace) -> None:
    continue_ = not not args.continue_
    # --continue implies --force-rebuild
    force_rebuild = args.force_rebuild or continue_

    meta_file = Path(args.package[0]).resolve()

    pkg_root = meta_file.parent
    pkg = MetaConfig.from_yaml(meta_file)

    pkg.build.cflags += f" {args.cflags}"
    pkg.build.cxxflags += f" {args.cxxflags}"
    pkg.build.ldflags += f" {args.ldflags}"

    missing_executables = find_missing_executables(pkg.requirements.executable)
    if missing_executables:
        missing_string = ", ".join(missing_executables)
        error_msg = (
            "The following executables are required but missing in the host system: "
            + missing_string
        )
        raise RuntimeError(error_msg)

    name = pkg.package.name
    t0 = datetime.now()
    print("[{}] Building package {}...".format(t0.strftime("%Y-%m-%d %H:%M:%S"), name))
    success = True
    try:
        build_package(
            pkg_root,
            pkg,
            target_install_dir=args.target_install_dir,
            host_install_dir=args.host_install_dir,
            force_rebuild=force_rebuild,
            continue_=continue_,
        )

    except Exception:
        success = False
        raise
    finally:
        t1 = datetime.now()
        datestamp = "[{}]".format(t1.strftime("%Y-%m-%d %H:%M:%S"))
        total_seconds = f"{(t1 - t0).total_seconds():.1f}"
        status = "Succeeded" if success else "Failed"
        print(
            f"{datestamp} {status} building package {name} in {total_seconds} seconds."
        )


if __name__ == "__main__":
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
