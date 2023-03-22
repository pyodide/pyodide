import io
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from email.message import EmailMessage
from email.parser import BytesParser
from functools import cache
from io import BytesIO
from operator import attrgetter
from pathlib import Path
from platform import python_version
from typing import TYPE_CHECKING, Any, BinaryIO, cast
from urllib.parse import urlparse
from zipfile import ZipFile

import requests
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version
from resolvelib import BaseReporter, Resolver
from resolvelib.providers import AbstractProvider
from unearth.evaluator import TargetPython
from unearth.finder import PackageFinder

from .. import common
from ..common import chdir, repack_zip_archive
from ..logger import logger
from . import build

_PYPI_INDEX = ["https://pypi.org/simple/"]
_PYPI_TRUSTED_HOSTS = ["pypi.org"]


@contextmanager
def stream_redirected(to=os.devnull, stream=None):
    """
    Context manager to redirect stdout or stderr. It does it with filenos and things rather than
    just changing sys.stdout, so that output of subprocesses is also redirected.
    """
    if stream is None:
        stream = sys.stdout
    try:
        if not hasattr(stream, "fileno"):
            yield
            return
        stream_fd = stream.fileno()
    except io.UnsupportedOperation:
        # in case we're already capturing to something that isn't really a file
        # e.g. in pytest
        yield
        return
    if type(to) == str:
        to = open(to, "w")
    with os.fdopen(os.dup(stream_fd), "wb") as copied:
        stream.flush()
        os.dup2(to.fileno(), stream_fd)  # $ exec >&to
        try:
            yield stream  # allow code to be run with the redirected stream
        finally:
            # restore stream to its previous value
            # NOTE: dup2 makes stream_fd inheritable unconditionally
            stream.flush()
            os.dup2(copied.fileno(), stream_fd)  # $ exec >&copied
            to = None


def get_built_wheel(url):
    return _get_built_wheel_internal(url)["path"]


@cache
def _get_built_wheel_internal(url):
    parsed_url = urlparse(url)
    gz_name = Path(parsed_url.path).name

    cache_entry: dict[str, Any] = {}
    build_dir = tempfile.TemporaryDirectory()
    cache_entry["build_dir"] = build_dir
    with chdir(Path(build_dir.name)):
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as f:
            data = requests.get(url).content
            f.write(data)
            f.close()
            shutil.unpack_archive(f.name, build_dir.name)
            os.unlink(f.name)
            files = list(Path(build_dir.name).iterdir())
            if len(files) == 1 and files[0].is_dir():
                os.chdir(Path(build_dir.name, files[0]))
            else:
                os.chdir(build_dir.name)
        logger.info(f"Building wheel for {gz_name}...")
        with tempfile.NamedTemporaryFile(mode="w+") as f:
            try:
                with (
                    stream_redirected(to=f, stream=sys.stdout),
                    stream_redirected(to=f, stream=sys.stderr),
                ):
                    wheel_path = build.run(
                        PyPIProvider.BUILD_EXPORTS,
                        PyPIProvider.BUILD_FLAGS,
                        outdir=Path(build_dir.name) / "dist",
                    )
            except BaseException as e:
                logger.error(" Failed\n Error is:")
                f.seek(0)
                logger.stderr(f.read())
                raise e

    logger.success("Success")

    cache_entry["path"] = wheel_path
    return cache_entry


class Candidate:
    def __init__(self, name, version, url=None, extras=None):
        self.name = canonicalize_name(name)
        self.version = version
        self.url = url
        self.extras = extras

        self._metadata = None
        self._dependencies = None

    def __repr__(self):
        if not self.extras:
            return f"<{self.name}=={self.version}>"
        return f"<{self.name}[{','.join(self.extras)}]=={self.version}>"

    @property
    def metadata(self):
        if self._metadata is None:
            self._metadata = get_metadata_for_wheel(self.url)
        return self._metadata

    @property
    def requires_python(self):
        return self.metadata.get("Requires-Python")

    def _get_dependencies(self):
        deps = self.metadata.get_all("Requires-Dist", [])
        extras = self.extras if self.extras else [""]

        for d in deps:
            r = Requirement(d)
            if r.marker is None:
                yield r
            else:
                for e in extras:
                    if r.marker.evaluate({"extra": e}):
                        yield r
                        break

    @property
    def dependencies(self):
        if self._dependencies is None:
            self._dependencies = list(self._get_dependencies())
        return self._dependencies


if TYPE_CHECKING:
    APBase = AbstractProvider[Requirement, Candidate, str]
else:
    APBase = AbstractProvider

PYTHON_VERSION = Version(python_version())


def get_target_python():
    PYMAJOR = common.get_make_flag("PYMAJOR")
    PYMINOR = common.get_make_flag("PYMINOR")
    tp = TargetPython(
        py_ver=(int(PYMAJOR), int(PYMINOR)),
        platforms=[common.platform()],
        abis=[f"cp{PYMAJOR}{PYMINOR}"],
    )
    return tp


def get_project_from_pypi(package_name, extras):
    """Return candidates created from the project name and extras."""
    pf = PackageFinder(
        index_urls=_PYPI_INDEX,
        trusted_hosts=_PYPI_TRUSTED_HOSTS,
        target_python=get_target_python(),
    )
    matches = pf.find_all_packages(package_name)
    for i in matches:
        # TODO: ignore sourcedists if wheel for same version exists
        yield Candidate(i.name, i.version, url=i.link.url, extras=extras)


def download_or_build_wheel(
    url: str, target_directory: Path, compression_level: int = 6
) -> None:
    parsed_url = urlparse(url)
    if parsed_url.path.endswith("gz"):
        wheel_file = get_built_wheel(url)
        shutil.copy(wheel_file, target_directory)
        wheel_path = target_directory / wheel_file.name
    elif parsed_url.path.endswith(".whl"):
        wheel_path = target_directory / Path(parsed_url.path).name
        with open(wheel_path, "wb") as f:
            f.write(requests.get(url).content)

    repack_zip_archive(wheel_path, compression_level=compression_level)


def get_metadata_for_wheel(url):
    parsed_url = urlparse(url)
    if parsed_url.path.endswith("gz"):
        wheel_file = get_built_wheel(url)
        wheel_stream: BinaryIO = open(wheel_file, "rb")
    elif parsed_url.path.endswith(".whl"):
        data = requests.get(url).content
        wheel_stream = BytesIO(data)
    else:
        raise RuntimeError(f"Distributions of this type are unsupported:{url}")
    with ZipFile(wheel_stream) as z:
        for n in z.namelist():
            if n.endswith(".dist-info/METADATA"):
                p = BytesParser()
                return p.parse(cast(BinaryIO, z.open(n)), headersonly=True)

    # If we didn't find the metadata, return an empty dict
    return EmailMessage()


class PyPIProvider(APBase):
    BUILD_FLAGS: list[str] = []
    BUILD_SKIP: list[str] = []
    BUILD_EXPORTS: str = ""

    def __init__(self, build_dependencies: bool):
        self.build_dependencies = build_dependencies

    def identify(self, requirement_or_candidate):
        base = canonicalize_name(requirement_or_candidate.name)
        return base

    def get_extras_for(self, requirement_or_candidate):
        # Extras is a set, which is not hashable
        return tuple(sorted(requirement_or_candidate.extras))

    def get_base_requirement(self, candidate):
        return Requirement(f"{candidate.name}=={candidate.version}")

    def get_preference(
        self, identifier, resolutions, candidates, information, backtrack_causes
    ):
        return sum(1 for _ in candidates[identifier])

    def find_matches(self, identifier, requirements, incompatibilities):
        requirements = list(requirements[identifier])

        extra_requirements = {}
        for r in requirements:
            extra_requirements[tuple(r.extras)] = 1

        bad_versions = {c.version for c in incompatibilities[identifier]}

        # Need to pass the extras to the search, so they
        # are added to the candidate at creation - we
        # treat candidates as immutable once created.
        for extra_tuple in extra_requirements.keys():
            extras = set(extra_tuple)

            candidates = (
                candidate
                for candidate in get_project_from_pypi(identifier, extras)
                if candidate.version not in bad_versions
                and all(candidate.version in r.specifier for r in requirements)
            )

        return sorted(candidates, key=attrgetter("version"), reverse=True)

    def is_satisfied_by(self, requirement, candidate):
        if canonicalize_name(requirement.name) != candidate.name:
            return False
        return candidate.version in requirement.specifier

    def get_dependencies(self, candidate):
        deps = []
        if self.build_dependencies:
            for d in candidate.dependencies:
                if d.name not in PyPIProvider.BUILD_SKIP:
                    deps.append(d)
        if candidate.extras:
            # add the base package as a dependency too, so we can avoid conflicts between same package
            # but with different extras
            req = self.get_base_requirement(candidate)
            deps.append(req)
        return deps


def _get_json_package_list(fname: Path) -> Generator[str, None, None]:
    json_data = json.load(fname.open())
    if "packages" in json_data:
        # pyodide repodata.json format
        yield from json_data["packages"].keys()
    else:
        # jupyterlite all.json format
        for k in json_data.keys():
            if "releases" in json_data[k]:
                yield k


def _parse_skip_list(skip_dependency: list[str]) -> None:
    PyPIProvider.BUILD_SKIP = []
    for skip in skip_dependency:
        split_deps = skip.split(",")
        for dep in split_deps:
            if dep.endswith(".json"):
                # a pyodide json file
                # or a jupyterlite json file
                # skip all packages in it
                PyPIProvider.BUILD_SKIP.extend(_get_json_package_list(Path(dep)))
            else:
                PyPIProvider.BUILD_SKIP.append(dep)


def _resolve_and_build(
    deps: list[str],
    target_folder: Path,
    build_dependencies: bool,
    extras: list[str],
    output_lockfile: str | None,
    compression_level: int = 6,
) -> None:
    requirements = []

    target_env = {
        "python_version": f'{common.get_make_flag("PYMAJOR")}.{common.get_make_flag("PYMINOR")}',
        "sys_platform": common.platform().split("_")[0],
        "extra": ",".join(extras),
    }

    for d in deps:
        r = Requirement(d)
        if (r.name not in PyPIProvider.BUILD_SKIP) and (
            (not r.marker) or r.marker.evaluate(target_env)
        ):
            requirements.append(r)

    # Create the (reusable) resolver.
    provider = PyPIProvider(build_dependencies=build_dependencies)
    reporter = BaseReporter()
    resolver: Resolver[Requirement, Candidate, str] = Resolver(provider, reporter)

    # Kick off the resolution process, and get the final result.
    result = resolver.resolve(requirements)
    target_folder.mkdir(parents=True, exist_ok=True)
    version_file = None
    if output_lockfile is not None and len(output_lockfile) > 0:
        version_file = open(output_lockfile, "w")
    for x in result.mapping.values():
        download_or_build_wheel(x.url, target_folder)
        if len(x.extras) > 0:
            extratxt = "[" + ",".join(x.extras) + "]"
        else:
            extratxt = ""
        if version_file:
            version_file.write(f"{x.name}{extratxt}=={x.version}\n")
    if version_file:
        version_file.close()


def build_wheels_from_pypi_requirements(
    reqs: list[str],
    target_folder: Path,
    build_dependencies: bool,
    skip_dependency: list[str],
    exports: str,
    build_flags: list[str],
    output_lockfile: str | None,
) -> None:
    """
    Given a list of package requirements, build or fetch them. If build_dependencies is true, then
    package dependencies will be built or fetched also.
    """
    _parse_skip_list(skip_dependency)
    PyPIProvider.BUILD_EXPORTS = exports
    PyPIProvider.BUILD_FLAGS = build_flags
    _resolve_and_build(
        reqs,
        target_folder,
        build_dependencies,
        extras=[],
        output_lockfile=output_lockfile,
    )


def build_dependencies_for_wheel(
    wheel: Path,
    extras: list[str],
    skip_dependency: list[str],
    exports: str,
    build_flags: list[str],
    output_lockfile: str | None,
    compression_level: int = 6,
) -> None:
    """Extract dependencies from this wheel and build pypi dependencies
    for each one in ./dist/

    n.b. because dependency resolution may need to backtrack, this
    is potentially quite slow in the case that one needs to build an
    sdist in order to discover dependencies of a candidate sub-dependency.
    """
    metadata = None
    _parse_skip_list(skip_dependency)

    PyPIProvider.BUILD_EXPORTS = exports
    PyPIProvider.BUILD_FLAGS = build_flags
    with ZipFile(wheel) as z:
        for n in z.namelist():
            if n.endswith(".dist-info/METADATA"):
                p = BytesParser()
                metadata = p.parse(cast(BinaryIO, z.open(n)), headersonly=True)
    if metadata is None:
        raise RuntimeError(f"Can't find package metadata in {wheel}")

    deps: list[str] = metadata.get_all("Requires-Dist", [])
    metadata.get("version")
    _resolve_and_build(
        deps,
        wheel.parent,
        build_dependencies=True,
        extras=extras,
        output_lockfile=output_lockfile,
        compression_level=compression_level,
    )
    # add the current wheel to the package-versions.txt
    if output_lockfile is not None and len(output_lockfile) > 0:
        with open(output_lockfile, "a") as version_txt:
            name = metadata.get("Name")
            version = metadata.get("Version")
            if extras:
                extratxt = "[" + ",".join(extras) + "]"
            else:
                extratxt = ""
            version_txt.write(f"{name}{extratxt}=={version}\n")


def fetch_pypi_package(package_spec: str, destdir: Path) -> Path:
    pf = PackageFinder(
        index_urls=_PYPI_INDEX,
        trusted_hosts=_PYPI_TRUSTED_HOSTS,
        target_python=get_target_python(),
    )
    match = pf.find_best_match(package_spec)
    if match.best is None:
        if len(match.candidates) != 0:
            error = f"""Can't find version matching {package_spec}
versions found:
"""
            for c in match.candidates:
                error += "  " + str(c.version) + "\t"
            raise RuntimeError(error)
        else:
            raise RuntimeError(f"Can't find package: {package_spec}")
    with tempfile.TemporaryDirectory() as download_dir:
        return pf.download_and_unpack(
            link=match.best.link, location=destdir, download_dir=download_dir
        )
