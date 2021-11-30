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


def check_checksum(path: Path, pkg: Dict[str, Any]):
    """
    Checks that a tarball matches the checksum in the package metadata.
    """
    checksum_keys = {"md5", "sha256"}.intersection(pkg["source"])
    if not checksum_keys:
        return
    elif len(checksum_keys) != 1:
        raise ValueError(
            "Only one checksum should be included in a package "
            "setup; found {}.".format(checksum_keys)
        )
    checksum_algorithm = checksum_keys.pop()
    checksum = pkg["source"][checksum_algorithm]
    CHUNK_SIZE = 1 << 16
    h = getattr(hashlib, checksum_algorithm)()
    with open(path, "rb") as fd:
        while True:
            chunk = fd.read(CHUNK_SIZE)
            h.update(chunk)
            if len(chunk) < CHUNK_SIZE:
                break
    if h.hexdigest() != checksum:
        raise ValueError("Invalid {} checksum".format(checksum_algorithm))


def download_and_extract(
    buildpath: Path, packagedir: Path, pkg: Dict[str, Any], args
) -> Path:
    srcpath = buildpath / packagedir

    if "source" not in pkg:
        return srcpath

    if "url" in pkg["source"]:
        response = request.urlopen(pkg["source"]["url"])
        _, parameters = cgi.parse_header(
            response.headers.get("Content-Disposition", "")
        )
        if "filename" in parameters:
            tarballname = parameters["filename"]
        else:
            tarballname = Path(response.geturl()).name

        tarballpath = buildpath / tarballname
        if not tarballpath.is_file():
            try:
                os.makedirs(os.path.dirname(tarballpath), exist_ok=True)
                with open(tarballpath, "wb") as f:
                    f.write(response.read())
                check_checksum(tarballpath, pkg)
            except Exception:
                tarballpath.unlink()
                raise

        if not srcpath.is_dir():
            shutil.unpack_archive(str(tarballpath), str(buildpath))

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
                tarballname = tarballname[: -len(extension)]
                break

        return buildpath / pkg["source"].get("extract_dir", tarballname)

    elif "path" in pkg["source"]:
        srcdir = Path(pkg["source"]["path"])

        if not srcdir.is_dir():
            raise ValueError(f"path={srcdir} must point to a directory that exists")

        if not srcpath.is_dir():
            shutil.copytree(srcdir, srcpath)

        return srcpath
    else:
        raise ValueError("Incorrect source provided")


def patch(path: Path, srcpath: Path, pkg: Dict[str, Any], args):
    if (srcpath / ".patched").is_file():
        return

    # Apply all the patches
    orig_dir = Path.cwd()
    pkgdir = path.parent.resolve()
    os.chdir(srcpath)
    try:
        for patch in pkg.get("source", {}).get("patches", []):
            subprocess.run(
                ["patch", "-p1", "--binary", "-i", pkgdir / patch], check=True
            )
    finally:
        os.chdir(orig_dir)

    # Add any extra files
    for src, dst in pkg.get("source", {}).get("extras", []):
        shutil.copyfile(pkgdir / src, srcpath / dst)

    with open(srcpath / ".patched", "wb") as fd:
        fd.write(b"\n")


def compile(path: Path, srcpath: Path, pkg: Dict[str, Any], args, bash_runner):
    if (srcpath / ".built").is_file():
        return

    orig_dir = Path.cwd()
    os.chdir(srcpath)
    if pkg.get("build", {}).get("skip_host", True):
        bash_runner.env["SKIP_HOST"] = ""

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pyodide_build",
                "pywasmcross",
                "--cflags",
                args.cflags + " " + pkg.get("build", {}).get("cflags", ""),
                "--cxxflags",
                args.cxxflags + " " + pkg.get("build", {}).get("cxxflags", ""),
                "--ldflags",
                args.ldflags + " " + pkg.get("build", {}).get("ldflags", ""),
                "--target",
                args.target,
                "--install-dir",
                args.install_dir,
                "--replace-libs",
                ";".join(pkg.get("build", {}).get("replace-libs", [])),
            ],
            check=True,
            env=bash_runner.env,
        )
    finally:
        os.chdir(orig_dir)

    post = pkg.get("build", {}).get("post")
    if post is not None:
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
        pkgdir = path.parent.resolve()
        bash_runner.env.update(
            {"SITEPACKAGES": str(site_packages_dir), "PKGDIR": str(pkgdir)}
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
    buildpath: Path, srcpath: Path, pkg: Dict[str, Any], compress: bool = False
) -> None:
    """Package the installation folder into .data and .js files

    Parameters
    ----------
    buildpath
        the package build path. Usually `packages/<name>/build`
    srcpath
        the package source path. Usually
        `packages/<name>/build/<name>-<version>`.
    pkg
        package JSON definition

    Notes
    -----
    The files to packages are located under the `install_prefix` corresponding
    to `srcpath / 'install'`.

    """
    if (buildpath / ".packaged").is_file():
        return

    name = pkg["package"]["name"]
    install_prefix = (srcpath / "install").resolve()
    test_install_prefix = (srcpath / "install-test").resolve()

    if pkg.get("build", {}).get("unvendor-tests", True):
        n_unvendored = unvendor_tests(install_prefix, test_install_prefix)
    else:
        n_unvendored = 0

    # Package the package except for tests
    subprocess.run(
        [
            str(common.file_packager_path()),
            f"{name}.data",
            f"--js-output={name}.js",
            "--preload",
            f"{install_prefix}@/",
        ],
        cwd=buildpath,
        check=True,
    )

    if compress:
        subprocess.run(
            [
                "npx",
                "--no-install",
                "terser",
                buildpath / (name + ".js"),
                "-o",
                buildpath / (name + ".js"),
            ],
            check=True,
        )

    # Package tests
    if n_unvendored > 0:
        subprocess.run(
            [
                str(common.file_packager_path()),
                f"{name}-tests.data",
                f"--js-output={name}-tests.js",
                "--preload",
                f"{test_install_prefix}@/",
            ],
            cwd=buildpath,
            check=True,
        )

        if compress:
            subprocess.run(
                [
                    "npx",
                    "--no-install",
                    "terser",
                    buildpath / (name + "-tests.js"),
                    "-o",
                    buildpath / (name + "-tests.js"),
                ],
                check=True,
            )

    with open(buildpath / ".packaged", "wb") as fd:
        fd.write(b"\n")


def run_script(buildpath: Path, srcpath: Path, pkg: Dict[str, Any], bash_runner):
    if pkg.get("build", {}).get("library"):
        # in libraries this  writes the packaged flag
        # We don't really do packaging, but needs_rebuild checks .packaged to
        # determine if it needs to rebuild
        if (buildpath / ".packaged").is_file():
            return

    orig_path = Path.cwd()
    os.chdir(srcpath)
    try:
        bash_runner.run(pkg["build"]["script"], check=True)
    finally:
        os.chdir(orig_path)

    # If library, we're done so create .packaged file
    if pkg["build"].get("library"):
        with open(buildpath / ".packaged", "wb") as fd:
            fd.write(b"\n")


def needs_rebuild(pkg: Dict[str, Any], path: Path, buildpath: Path) -> bool:
    """
    Determines if a package needs a rebuild because its meta.yaml, patches, or
    sources are newer than the `.packaged` thunk.
    """
    packaged_token = buildpath / ".packaged"
    if not packaged_token.is_file():
        return True

    package_time = packaged_token.stat().st_mtime

    def source_files():
        yield path
        yield from pkg.get("source", {}).get("patches", [])
        yield from (x[0] for x in pkg.get("source", {}).get("extras", []))

    for source_file in source_files():
        source_file = Path(source_file)
        if source_file.stat().st_mtime > package_time:
            return True
    return False


def build_package(path: Path, args):
    pkg = parse_package_config(path)
    name = pkg["package"]["name"]
    t0 = datetime.now()
    print("[{}] Building package {}...".format(t0.strftime("%Y-%m-%d %H:%M:%S"), name))
    packagedir = name + "-" + pkg["package"]["version"]
    dirpath = path.parent
    orig_path = Path.cwd()
    os.chdir(dirpath)
    buildpath = dirpath / "build"
    bash_runner = BashRunnerWithSharedEnvironment()
    try:
        if not needs_rebuild(pkg, path, buildpath):
            return
        if "source" in pkg:
            if buildpath.resolve().is_dir():
                shutil.rmtree(buildpath)
            os.makedirs(buildpath)
        srcpath = download_and_extract(buildpath, packagedir, pkg, args)
        patch(path, srcpath, pkg, args)
        if pkg.get("build", {}).get("script"):
            run_script(buildpath, srcpath, pkg, bash_runner)
        if not pkg.get("build", {}).get("library", False):
            # shared libraries get built by the script and put into install
            # subfolder, then packaged into a pyodide module
            # i.e. they need package running, but not compile
            if not pkg.get("build", {}).get("sharedlibrary"):
                compile(path, srcpath, pkg, args, bash_runner)
            package_files(buildpath, srcpath, pkg, compress=args.compress_package)
    finally:
        bash_runner.close()
        os.chdir(orig_path)
        t1 = datetime.now()
        print(
            "[{}] done building package {} in {:.1f} s.".format(
                t1.strftime("%Y-%m-%d %H:%M:%S"), name, (t1 - t0).total_seconds()
            )
        )


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
        "--target",
        type=str,
        nargs="?",
        default=common.get_make_flag("TARGETPYTHONROOT"),
        help="The path to the target Python installation",
    )
    parser.add_argument(
        "--install-dir",
        type=str,
        nargs="?",
        default="",
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
    path = Path(args.package[0]).resolve()
    if args.compress_package and not _have_terser():
        raise RuntimeError(
            "Terser is required to compress packages. Try `npm install -g terser` to install terser."
        )

    build_package(path, args)


if __name__ == "__main__":
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
