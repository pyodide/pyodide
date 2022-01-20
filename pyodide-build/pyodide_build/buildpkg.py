#!/usr/bin/env python3

"""
Builds a Pyodide package.
"""

import argparse
import cgi
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import fnmatch

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict
from urllib import request

from . import pywasmcross


@contextmanager
def chdir(new_dir: Path):
    orig_dir = Path.cwd()
    try:
        os.chdir(new_dir)
        yield
    finally:
        os.chdir(orig_dir)


from . import common
from .io import parse_package_config


def _make_whlfile(*args, owner=None, group=None, **kwargs):
    return shutil._make_zipfile(*args, **kwargs)  # type: ignore


shutil.register_archive_format("whl", _make_whlfile, description="Wheel file")
shutil.register_unpack_format(
    "whl", [".whl", ".wheel"], shutil._unpack_zipfile, description="Wheel file"  # type: ignore
)


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
        key: os.environ[key]
        for key in [
            "PATH",
            "PYTHONPATH",
            "PYODIDE_ROOT",
            "PYTHONINCLUDE",
            "NUMPY_LIB",
            "PYODIDE_PACKAGE_ABI",
        ]
    } | {"PYODIDE": "1"}
    if "PYODIDE_JOBS" in os.environ:
        env["PYODIDE_JOBS"] = os.environ["PYODIDE_JOBS"]
    b = BashRunnerWithSharedEnvironment(env=env)
    b.run(f"source {PYODIDE_ROOT}/emsdk/emsdk/emsdk_env.sh", stderr=subprocess.DEVNULL)
    try:
        yield b
    finally:
        b.close()


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
        ".whl",
    ]:
        if tarballname.endswith(extension):
            return tarballname[: -len(extension)]
    return tarballname


def download_and_extract(buildpath: Path, srcpath: Path, src_metadata: Dict[str, Any]):
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

    if tarballpath.suffix == ".whl":
        os.makedirs(srcpath / "dist")
        shutil.copy(tarballpath, srcpath / "dist")
        return

    if not srcpath.is_dir():
        shutil.unpack_archive(tarballpath, buildpath)

    extract_dir_name = src_metadata.get("extract_dir")
    if not extract_dir_name:
        extract_dir_name = trim_archive_extension(tarballname)

    shutil.move(buildpath / extract_dir_name, srcpath)


def prepare_source(
    pkg_root: Path, buildpath: Path, srcpath: Path, src_metadata: Dict[str, Any]
):
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
    if buildpath.resolve().is_dir():
        shutil.rmtree(buildpath)
    os.makedirs(buildpath)

    if "url" in src_metadata:
        download_and_extract(buildpath, srcpath, src_metadata)
        patch(pkg_root, srcpath, src_metadata)
        return
    if "path" not in src_metadata:
        raise ValueError(
            "Incorrect source provided. Either a url or a path must be provided."
        )

    srcdir = Path(src_metadata["path"]).resolve()

    if not srcdir.is_dir():
        raise ValueError(f"path={srcdir} must point to a directory that exists")

    shutil.copytree(srcdir, srcpath)


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


def unpack_wheel(path):
    with chdir(path.parent):
        subprocess.run([sys.executable, "-m", "wheel", "unpack", path.name], check=True)


def pack_wheel(path):
    with chdir(path.parent):
        subprocess.run([sys.executable, "-m", "wheel", "pack", path.name], check=True)


def install_for_distribution():
    commands = [
        sys.executable,
        "setup.py",
        "bdist_wheel",
        "--skip-build",
    ]
    env = dict(os.environ)
    env["_PYTHON_HOST_PLATFORM"] = "emscripten_wasm32"
    subprocess.check_call(commands, env=env)


def compile(
    srcpath: Path,
    build_metadata: Dict[str, Any],
    bash_runner: BashRunnerWithSharedEnvironment,
    *,
    target_install_dir: str,
    host_install_dir: str,
    should_capture_compile: bool,
    should_replay_compile: bool,
    replay_from: int = 0,
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
    # This function runs setup.py. library and sharedlibrary don't have setup.py
    if build_metadata.get("sharedlibrary"):
        return

    skip_host = build_metadata.get("skip_host", True)

    replace_libs = ";".join(build_metadata.get("replace-libs", []))
    bash_runner.env["_PYTHON_HOST_PLATFORM"] = "emscripten_wasm32"
    with chdir(srcpath):
        if should_capture_compile:
            pywasmcross.capture_compile(
                host_install_dir=host_install_dir,
                skip_host=skip_host,
                env=bash_runner.env,
            )
            prereplay = build_metadata.get("prereplay")
            if prereplay:
                bash_runner.run(prereplay)
        if should_replay_compile:
            pywasmcross.replay_compile(
                cflags=build_metadata["cflags"],
                cxxflags=build_metadata["cxxflags"],
                ldflags=build_metadata["ldflags"],
                target_install_dir=target_install_dir,
                host_install_dir=host_install_dir,
                replace_libs=replace_libs,
                replay_from=replay_from,
            )
        install_for_distribution()
    del bash_runner.env["_PYTHON_HOST_PLATFORM"]


def package_wheel(
    pkg_name: str,
    pkg_root: Path,
    srcpath: Path,
    build_metadata: Dict[str, Any],
    bash_runner: BashRunnerWithSharedEnvironment,
):
    """Package a wheel

    This unpacks the wheel, unvendors tests if necessary, runs and "build.post"
    script, and then repacks the wheel.

    Parameters
    ----------
    pkg_name
        The name of the package

    pkg_root
        The path to the root directory for the package. Generally
        $PYODIDE_ROOT/packages/<PACKAGES>

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
    if build_metadata.get("sharedlibrary"):
        return

    distdir = srcpath / "dist"
    wheel_paths = list(distdir.glob("*.whl"))
    assert len(wheel_paths) == 1
    unpack_wheel(wheel_paths[0])
    wheel_dir = Path(next(p for p in distdir.glob("*") if p.is_dir()))
    post = build_metadata.get("post")
    if post:
        bash_runner.env.update({"PKGDIR": str(pkg_root)})
        bash_runner.run(post, check=True)

    test_dir = distdir / "tests"
    nmoved = 0
    if build_metadata.get("unvendor-tests", True):
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


def create_packaged_token(buildpath: Path):
    (buildpath / ".packaged").write_text("\n")


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
    script = build_metadata.get("script")
    if not script:
        return

    with chdir(srcpath):
        bash_runner.run(script, check=True)


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
    pkg: Dict[str, Any],
    *,
    target_install_dir: str,
    host_install_dir: str,
    force_rebuild: bool,
    should_run_script: bool,
    should_prepare_source: bool,
    should_capture_compile: bool,
    should_replay_compile: bool,
    replay_from: int,
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
    """
    pkg_metadata = pkg["package"]
    source_metadata = pkg["source"]
    build_metadata = pkg["build"]
    name = pkg_metadata["name"]
    version = pkg_metadata["version"]
    build_dir = pkg_root / "build"
    src_dir_name: str = f"{name}-{version}"
    srcpath = build_dir / src_dir_name

    if not force_rebuild and not needs_rebuild(pkg_root, build_dir, source_metadata):
        return

    if not should_prepare_source and not srcpath.exists():
        raise IOError(
            "Cannot find source for rebuild. Expected to find the source "
            f"directory at the path {srcpath}, but that path does not exist."
        )

    with chdir(pkg_root), get_bash_runner() as bash_runner:
        if should_prepare_source:
            prepare_source(pkg_root, build_dir, srcpath, source_metadata)

        if should_run_script:
            run_script(build_dir, srcpath, build_metadata, bash_runner)

        if build_metadata.get("library"):
            create_packaged_token(build_dir)
            return

        url = source_metadata.get("url")
        finished_wheel = url and url.endswith(".whl")
        if not build_metadata.get("sharedlibrary") and not finished_wheel:
            compile(
                srcpath,
                build_metadata,
                bash_runner,
                target_install_dir=target_install_dir,
                host_install_dir=host_install_dir,
                should_capture_compile=should_capture_compile,
                should_replay_compile=should_replay_compile,
                replay_from=replay_from,
            )
        if not build_metadata.get("sharedlibrary"):
            package_wheel(
                name,
                pkg_root,
                srcpath,
                build_metadata,
                bash_runner,
            )

        shutil.rmtree(pkg_root / "dist", ignore_errors=True)
        shutil.copytree(srcpath / "dist", pkg_root / "dist")

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
        "--force-rebuild",
        action="store_true",
        help=(
            "Force rebuild of package regardless of whether it appears to have been updated"
        ),
    )
    parser.add_argument(
        "--continue",
        type=str,
        nargs="?",
        dest="continue_from",
        default="None",
        const="script",
        help=(
            dedent(
                """
                Continue a build from the middle. For debugging. Implies
                "--force-rebuild". Possible arguments:

                    'script' : Don't prepare source, start with running script. `--continue` with no argument has the same effect.

                    'capture' : Start with capture step

                    'replay' : Start with replay step

                    'replay:15' : Replay the capture step starting with the 15th compile command (any integer works)
                """
            ).strip()
        ),
    )
    return parser


def parse_continue_arg(continue_from: str) -> Dict[str, Any]:
    from itertools import accumulate

    is_none = continue_from == "None"
    is_script = continue_from == "script"
    is_capture = continue_from == "capture"
    is_replay = continue_from == "replay" or re.fullmatch(
        r"replay(:[0-9]+)?", continue_from
    )

    [
        should_prepare_source,
        should_run_script,
        should_capture_compile,
        should_replay_compile,
    ] = accumulate([is_none, is_script, is_capture, is_replay], lambda a, b: a or b)

    if not should_replay_compile:
        raise IOError(
            f"Unexpected --continue argument '{continue_from}', should have been 'script', 'capture', 'replay', or 'replay:##'"
        )

    result: Dict[str, Any] = {}
    result["should_prepare_source"] = should_prepare_source
    result["should_run_script"] = should_run_script
    result["should_capture_compile"] = should_capture_compile
    result["should_replay_compile"] = should_replay_compile
    result["replay_from"] = 1
    if continue_from.startswith("replay:"):
        result["replay_from"] = int(continue_from.removeprefix("replay:"))
    return result


def main(args):
    step_controls = parse_continue_arg(args.continue_from)
    # --continue implies --force-rebuild
    force_rebuild = args.force_rebuild or not not args.continue_from

    meta_file = Path(args.package[0]).resolve()

    pkg_root = meta_file.parent
    pkg = parse_package_config(meta_file)

    pkg["source"] = pkg.get("source", {})
    pkg["build"] = pkg.get("build", {})
    build_metadata = pkg["build"]
    build_metadata["cflags"] = build_metadata.get("cflags", "")
    build_metadata["cxxflags"] = build_metadata.get("cxxflags", "")
    build_metadata["ldflags"] = build_metadata.get("ldflags", "")

    build_metadata["cflags"] += f" {args.cflags}"
    build_metadata["cxxflags"] += f" {args.cxxflags}"
    build_metadata["ldflags"] += f" {args.ldflags}"

    name = pkg["package"]["name"]
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
            **step_controls,
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
