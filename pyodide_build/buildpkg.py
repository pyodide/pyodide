#!/usr/bin/env python3

"""
Builds a Pyodide package.
"""

import argparse
import cgi
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib import request
from datetime import datetime
from typing import Any, Dict


from . import common


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

        return buildpath / tarballname
    elif "path" in pkg["source"]:
        srcdir = Path(pkg["source"]["path"])

        if not srcdir.is_dir():
            raise ValueError("'path' must point to a path")

        if not srcpath.is_dir():
            shutil.copytree(srcdir, srcpath)

        return srcpath
    else:
        raise ValueError("Incorrect source provided")


def patch(path: Path, srcpath: Path, pkg: Dict[str, Any], args):
    if (srcpath / ".patched").is_file():
        return

    # Apply all of the patches
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


def compile(path: Path, srcpath: Path, pkg: Dict[str, Any], args):
    if (srcpath / ".built").is_file():
        return

    orig_dir = Path.cwd()
    os.chdir(srcpath)
    env = dict(os.environ)
    if pkg.get("build", {}).get("skip_host", True):
        env["SKIP_HOST"] = ""

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pyodide_build",
                "pywasmcross",
                "--cflags",
                args.cflags + " " + pkg.get("build", {}).get("cflags", ""),
                "--ldflags",
                args.ldflags + " " + pkg.get("build", {}).get("ldflags", ""),
                "--target",
                args.target,
                "--install-dir",
                args.install_dir,
            ],
            env=env,
            check=True,
        )
    finally:
        os.chdir(orig_dir)

    post = pkg.get("build", {}).get("post")
    if post is not None:
        site_packages_dir = srcpath / "install" / "lib" / "python3.8" / "site-packages"
        pkgdir = path.parent.resolve()
        env = {"SITEPACKAGES": str(site_packages_dir), "PKGDIR": str(pkgdir)}
        subprocess.run(["bash", "-c", post], env=env, check=True)

    with open(srcpath / ".built", "wb") as fd:
        fd.write(b"\n")


def package_files(buildpath: Path, srcpath: Path, pkg: Dict[str, Any], args):
    if (buildpath / ".packaged").is_file():
        return

    name = pkg["package"]["name"]
    install_prefix = (srcpath / "install").resolve()
    subprocess.run(
        [
            "python",
            common.ROOTDIR / "file_packager.py",
            name + ".data",
            "--abi={0}".format(args.package_abi),
            "--lz4",
            "--preload",
            "{}@/".format(install_prefix),
            "--js-output={}".format(name + ".js"),
            "--export-name=pyodide._module",
            "--exclude",
            "*.wasm.pre",
            "--exclude",
            "*__pycache__*",
            "--use-preload-plugins",
        ],
        cwd=buildpath,
        check=True,
    )
    subprocess.run(
        ["uglifyjs", buildpath / (name + ".js"), "-o", buildpath / (name + ".js")],
        check=True,
    )

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
    pkg = common.parse_package(path)
    name = pkg["package"]["name"]
    t0 = datetime.now()
    print("[{}] Building package {}...".format(t0.strftime("%Y-%m-%d %H:%M:%S"), name))
    packagedir = name + "-" + pkg["package"]["version"]
    dirpath = path.parent
    orig_path = Path.cwd()
    os.chdir(dirpath)
    buildpath = dirpath / "build"
    try:
        if not needs_rebuild(pkg, path, buildpath):
            return
        if "source" in pkg:
            if buildpath.resolve().is_dir():
                shutil.rmtree(buildpath)
            os.makedirs(buildpath)
        srcpath = download_and_extract(buildpath, packagedir, pkg, args)
        patch(path, srcpath, pkg, args)
        compile(path, srcpath, pkg, args)
        package_files(buildpath, srcpath, pkg, args)
    finally:
        os.chdir(orig_path)
        t1 = datetime.now()
        print(
            "[{}] done building package {} in {:.1f} s.".format(
                t1.strftime("%Y-%m-%d %H:%M:%S"), name, (t1 - t0).total_seconds()
            )
        )


def make_parser(parser: argparse.ArgumentParser):
    parser.description = "Build a pyodide package."
    parser.add_argument(
        "package", type=str, nargs=1, help="Path to meta.yaml package description"
    )
    parser.add_argument(
        "--package_abi",
        type=int,
        required=True,
        help="The ABI number for the package to be built",
    )
    parser.add_argument(
        "--cflags",
        type=str,
        nargs="?",
        default=common.DEFAULTCFLAGS,
        help="Extra compiling flags",
    )
    parser.add_argument(
        "--ldflags",
        type=str,
        nargs="?",
        default=common.DEFAULTLDFLAGS,
        help="Extra linking flags",
    )
    parser.add_argument(
        "--target",
        type=str,
        nargs="?",
        default=common.TARGETPYTHON,
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
    return parser


def main(args):
    path = Path(args.package[0]).resolve()
    build_package(path, args)


if __name__ == "__main__":
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
