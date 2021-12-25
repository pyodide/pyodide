#!/usr/bin/env python3

"""
Builds a Pyodide package.
"""

import argparse
import cgi
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict
from urllib import request
import fnmatch
from contextlib import contextmanager

from . import pywasmcross


@contextmanager
def chdir(new_dir: "os.PathLike[str]"):
    orig_dir = Path.cwd()
    try:
        os.chdir(new_dir)
        yield
    finally:
        os.chdir(orig_dir)


from . import common
from .io import parse_package_config


class BashRunnerWithSharedEnvironment:
    """Run multiple bash scripts with persisent environment.

    Environment is stored to "env" member between runs. This can be updated
    directly to adjust the environment, or read to get variables.
    """

    def __init__(self, env=None):
        if env is None:
            env = dict(os.environ)
        self.env: Dict[str, str] = env
        self._fd_read, self._fd_write = os.pipe()
        self._reader = os.fdopen(self._fd_read, "r")

    def run(self, cmd, **opts):
        """Run a bash script. Any keyword arguments are passed on to subprocess.run."""
        write_env_pycode = ";".join(
            [
                "import os",
                "import json",
                f'os.write({self._fd_write}, json.dumps(dict(os.environ)).encode() + b"\\n")',
            ]
        )
        write_env_shell_cmd = f"{sys.executable} -c '{write_env_pycode}'"
        cmd += "\n" + write_env_shell_cmd
        result = subprocess.run(
            ["bash", "-ce", cmd], pass_fds=[self._fd_write], env=self.env, **opts
        )
        self.env = json.loads(self._reader.readline())
        return result

    def close(self):
        """Free the file descriptors."""
        if self._fd_read:
            os.close(self._fd_read)
            os.close(self._fd_write)
            self._fd_read = None
            self._fd_write = None


@contextmanager
def get_bash_runner():
    PYODIDE_ROOT = os.environ["PYODIDE_ROOT"]
    env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": os.environ["PYTHONPATH"],
        "PYODIDE_ROOT": PYODIDE_ROOT,
        "PYTHONINCLUDE": os.environ["PYTHONINCLUDE"],
        "NUMPY_LIB": os.environ["NUMPY_LIB"],
    }
    if "PYODIDE_JOBS" in os.environ:
        env["PYODIDE_JOBS"] = os.environ["PYODIDE_JOBS"]
    b = BashRunnerWithSharedEnvironment(env=env)
    b.run(f"source {PYODIDE_ROOT}/emsdk/emsdk/emsdk_env.sh")
    try:
        yield b
    finally:
        b.close()


def _have_terser():
    try:
        # Check npm exists and terser is installed locally
        subprocess.run(
            [
                "npm",
                "list",
                "terser",
            ],
            stdout=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return False

    return True


def check_checksum(archive: Path, source_metadata: Dict[str, Any]):
    """
    Checks that an archive matches the checksum in the package metadata.


    Parameters
    ----------
    archive
        the path to the archive we wish to checksum
    source_metadata
        The source section from meta.yaml.
    """
    checksum_keys = {"md5", "sha256"}.intersection(source_metadata)
    if not checksum_keys:
        return
    elif len(checksum_keys) != 1:
        raise ValueError(
            "Only one checksum should be included in a package "
            "setup; found {}.".format(checksum_keys)
        )
    checksum_algorithm = checksum_keys.pop()
    checksum = source_metadata[checksum_algorithm]
    CHUNK_SIZE = 1 << 16
    h = getattr(hashlib, checksum_algorithm)()
    with open(archive, "rb") as fd:
        while True:
            chunk = fd.read(CHUNK_SIZE)
            h.update(chunk)
            if len(chunk) < CHUNK_SIZE:
                break
    if h.hexdigest() != checksum:
        raise ValueError("Invalid {} checksum".format(checksum_algorithm))


def trim_archive_extension(tarballname):
    for extension in [
        ".tar.gz",
        ".tgz",
        ".tar",
        ".tar.bz2",
        ".tbz2",
        ".tar.xz",
        ".txz",
        ".zip",
    ]:
        if tarballname.endswith(extension):
            return tarballname[: -len(extension)]
    return tarballname


def download_and_extract(
    buildpath: Path, srcpath: Path, src_metadata: Dict[str, Any]
) -> Path:
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
    response = request.urlopen(src_metadata["url"])
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

    if not srcpath.is_dir():
        shutil.unpack_archive(str(tarballpath), str(buildpath))

    extract_dir_name = src_metadata.get("extract_dir")
    if not extract_dir_name:
        extract_dir_name = trim_archive_extension(tarballname)
    return buildpath / extract_dir_name


def prepare_source(
    pkg_root: Path, buildpath: Path, srcpath: Path, src_metadata: Dict[str, Any]
) -> Path:
    """
    Figure out from the "source" key in the package metadata where to get the source
    from, then get the source into srcpath (or somewhere else, if it goes somewhere
    else, returns where it ended up).

    Parameters
    ----------
    pkg_root
        The path to the root directory for the package. Generally
        $PYODIDE_ROOT/packages/<PACKAGES>

    buildpath
        The path to the build directory. Generally will be
        $(PYOIDE_ROOT)/packages/<PACKAGE>/build/.

    srcpath
        The default place we want the source to end up. Will generally be
        $(PYOIDE_ROOT)/packages/<package-name>/build/<package-name>-<package-version>.

    src_metadata
        The source section from meta.yaml.

    Returns
    -------
        The location where the source ended up.
    """
    if "url" in src_metadata:
        srcpath = download_and_extract(buildpath, srcpath, src_metadata)
        patch(pkg_root, srcpath, src_metadata)
        return srcpath

    if "path" not in src_metadata:
        raise ValueError(
            "Incorrect source provided. Either a url or a path must be provided."
        )

    srcdir = Path(src_metadata["path"])

    if not srcdir.is_dir():
        raise ValueError(f"path={srcdir} must point to a directory that exists")

    if not srcpath.is_dir():
        shutil.copytree(srcdir, srcpath)

    return srcpath


def patch(pkg_root: Path, srcpath: Path, src_metadata: Dict[str, Any]):
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

    patches = src_metadata.get("patches", [])
    extras = src_metadata.get("extras", [])
    if not patches and not extras:
        return

    # Apply all the patches
    with chdir(srcpath):
        for patch in patches:
            subprocess.run(
                ["patch", "-p1", "--binary", "-i", pkg_root / patch], check=True
            )

    # Add any extra files
    for src, dst in extras:
        shutil.copyfile(pkg_root / src, srcpath / dst)

    with open(srcpath / ".patched", "wb") as fd:
        fd.write(b"\n")


def install_for_distribution():
    commands = [
        sys.executable,
        "setup.py",
        "install",
        "--skip-build",
        "--prefix=install",
        "--old-and-unmanageable",
    ]
    try:
        subprocess.check_call(commands)
    except Exception:
        print(
            f'Warning: {" ".join(str(arg) for arg in commands)} failed '
            f"with distutils, possibly due to the use of distutils "
            f"that does not support the --old-and-unmanageable "
            "argument. Re-trying the install without this argument."
        )
        subprocess.check_call(commands[:-1])


def compile(
    pkg_root: Path,
    srcpath: Path,
    build_metadata: Dict[str, Any],
    bash_runner: BashRunnerWithSharedEnvironment,
    *,
    target_install_dir: str,
    host_install_dir: str,
):
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
    pkg_root
        The path to the root directory for the package. Generally
        $PYODIDE_ROOT/packages/<PACKAGES>

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

    host_install_dir
        Directory for installing built host packages. Defaults to setup.py
        default. Set to 'skip' to skip installation. Installation is
        needed if you want to build other packages that depend on this one.
    """
    if (srcpath / ".built").is_file():
        return

    skip_host = build_metadata.get("skip_host", True)

    replace_libs = ";".join(build_metadata.get("replace-libs", []))

    with chdir(srcpath):
        pywasmcross.capture_compile(
            host_install_dir=host_install_dir,
            skip_host=skip_host,
            env=bash_runner.env,
        )
        pywasmcross.replay_compile(
            cflags=build_metadata["cflags"],
            cxxflags=build_metadata["cxxflags"],
            ldflags=build_metadata["ldflags"],
            target_install_dir=target_install_dir,
            host_install_dir=host_install_dir,
            replace_libs=replace_libs,
        )
        install_for_distribution()

    post = build_metadata.get("post")
    if post:
        # use Python, 3.9 by default
        pyfolder = "".join(
            [
                "python",
                os.environ.get("PYMAJOR", "3"),
                ".",
                os.environ.get("PYMINOR", "9"),
            ]
        )
        site_packages_dir = srcpath / "install" / "lib" / pyfolder / "site-packages"
        bash_runner.env.update(
            {"SITEPACKAGES": str(site_packages_dir), "PKGDIR": str(pkg_root)}
        )
        bash_runner.run(post, check=True)

    with open(srcpath / ".built", "wb") as fd:
        fd.write(b"\n")


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
    for root, dirs, files in os.walk(install_prefix):
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


def package_files(
    pkg_name: str,
    buildpath: Path,
    srcpath: Path,
    *,
    should_unvendor_tests: bool = True,
    compress: bool = False,
) -> None:
    """Package the installation folder into .data and .js files

    Parameters
    ----------
    pkg_name
        the name of the package

    buildpath
        the package build path. Usually `packages/<name>/build`

    srcpath
        the package source path. Usually
        `packages/<name>/build/<name>-<version>`.

    should_unvendor_tests
        should we unvendor tests

    compress
        should we compress the output

    Notes
    -----
    The files to packages are located under the `install_prefix` corresponding
    to `srcpath / 'install'`.

    """
    if (buildpath / ".packaged").is_file():
        return

    install_prefix = (srcpath / "install").resolve()
    test_install_prefix = (srcpath / "install-test").resolve()

    if should_unvendor_tests:
        n_unvendored = unvendor_tests(install_prefix, test_install_prefix)
    else:
        n_unvendored = 0

    # Package the package except for tests
    common.invoke_file_packager(
        name=pkg_name,
        root_dir=buildpath,
        base_dir=install_prefix,
        pyodidedir="/",
        compress=compress,
    )

    # Package tests
    if n_unvendored > 0:
        common.invoke_file_packager(
            name=f"{pkg_name}-tests",
            root_dir=buildpath,
            base_dir=test_install_prefix,
            pyodidedir="/",
            compress=compress,
        )


def create_packaged_token(buildpath: Path):
    with open(buildpath / ".packaged", "wb") as fd:
        fd.write(b"\n")


def run_script(
    buildpath: Path,
    srcpath: Path,
    build_metadata: Dict[str, Any],
    bash_runner: BashRunnerWithSharedEnvironment,
):
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
    if build_metadata.get("library"):
        # in libraries this  writes the packaged flag
        # We don't really do packaging, but needs_rebuild checks .packaged to
        # determine if it needs to rebuild
        if (buildpath / ".packaged").is_file():
            return

    with chdir(srcpath):
        bash_runner.run(build_metadata["script"], check=True)


def needs_rebuild(
    pkg_root: Path, buildpath: Path, source_metadata: Dict[str, Any]
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

    def source_files():
        yield pkg_root / "meta.yaml"
        yield from source_metadata.get("patches", [])
        yield from (x[0] for x in source_metadata.get("extras", []))
        src_path = source_metadata.get("path")
        if src_path:
            yield from Path(src_path).glob("**/*")

    for source_file in source_files():
        source_file = Path(source_file)
        if source_file.stat().st_mtime > package_time:
            return True
    return False


def build_package(
    pkg_root: Path,
    pkg: Dict,
    *,
    target_install_dir: str,
    host_install_dir: str,
    compress_package: bool,
):
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

    compress_package
        Should we compress the package?
    """
    name = pkg["package"]["name"]
    build_dir = pkg_root / "build"
    src_dir_name: str = name + "-" + pkg["package"]["version"]
    src_path = build_dir / src_dir_name
    source_metadata = pkg["source"]
    build_metadata = pkg["build"]
    with chdir(pkg_root), get_bash_runner() as bash_runner:
        if not needs_rebuild(pkg_root, build_dir, source_metadata):
            return
        if source_metadata:
            if build_dir.resolve().is_dir():
                shutil.rmtree(build_dir)
            os.makedirs(build_dir)

        srcpath = prepare_source(pkg_root, build_dir, src_path, source_metadata)
        if build_metadata.get("script"):
            run_script(build_dir, srcpath, build_metadata, bash_runner)
        if build_metadata.get("library"):
            create_packaged_token(build_dir)
            return
        # shared libraries get built by the script and put into install
        # subfolder, then packaged into a pyodide module
        # i.e. they need package running, but not compile
        if not build_metadata.get("sharedlibrary"):
            compile(
                pkg_root,
                srcpath,
                build_metadata,
                bash_runner,
                target_install_dir=target_install_dir,
                host_install_dir=host_install_dir,
            )
        should_unvendor_tests = build_metadata.get("unvendor-tests", True)
        package_files(
            name,
            build_dir,
            srcpath,
            should_unvendor_tests=should_unvendor_tests,
            compress=compress_package,
        )
        create_packaged_token(build_dir)


def make_parser(parser: argparse.ArgumentParser):
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
        "--no-compress-package",
        action="store_false",
        default=True,
        dest="compress_package",
        help="Do not compress built packages.",
    )
    return parser


def main(args):
    meta_file = Path(args.package[0]).resolve()
    if args.compress_package and not _have_terser():
        raise RuntimeError(
            "Terser is required to compress packages. Try `npm install -g terser` to install terser."
        )

    pkg_root = meta_file.parent
    pkg = parse_package_config(meta_file)
    name = pkg["package"]["name"]
    t0 = datetime.now()
    print("[{}] Building package {}...".format(t0.strftime("%Y-%m-%d %H:%M:%S"), name))
    success = True
    try:
        pkg["source"] = pkg.get("source", {})
        pkg["build"] = pkg.get("build", {})
        build_metadata = pkg["build"]
        build_metadata["cflags"] = build_metadata.get("cflags", "")
        build_metadata["cxxflags"] = build_metadata.get("cxxflags", "")
        build_metadata["ldflags"] = build_metadata.get("ldflags", "")

        build_metadata["cflags"] += f" {args.cflags}"
        build_metadata["cxxflags"] += f" {args.cxxflags}"
        build_metadata["ldflags"] += f" {args.ldflags}"
        build_package(
            pkg_root,
            pkg,
            target_install_dir=args.target_install_dir,
            host_install_dir=args.host_install_dir,
            compress_package=args.compress_package,
        )
    except:
        success = False
        raise
    finally:
        t1 = datetime.now()
        datestamp = "[{}]".format(t1.strftime("%Y-%m-%d %H:%M:%S"))
        total_seconds = "{:.1f}".format((t1 - t0).total_seconds())
        status = "Succeeded" if success else "Failed"
        print(
            f"{datestamp} {status} building package {name} in {total_seconds} seconds."
        )


if __name__ == "__main__":
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
