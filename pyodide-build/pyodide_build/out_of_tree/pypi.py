import json
import os
import shutil
import sys
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from email.message import EmailMessage
from email.parser import BytesParser
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
from . import build


@contextmanager
def stream_redirected(to=os.devnull, stream=None):
    if stream is None:
        stream = sys.stdout
    stream_fd = stream.fileno()
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


# cache of built sdists by url source to wheel file path
BUILD_CACHE: dict[str, dict[str, Any]] = {}


def get_cached_built_wheel(url):
    parsed_url = urlparse(url)
    gz_name = Path(parsed_url.path).name
    if url in BUILD_CACHE:
        return BUILD_CACHE[url]["path"]
    cache_entry: dict[str, Any] = {}
    build_dir = tempfile.TemporaryDirectory()
    cache_entry["build_dir"] = build_dir
    os.chdir(build_dir.name)
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
    print(f"Building wheel for {gz_name}: ", end="")
    with tempfile.TemporaryFile(mode="w+") as f:
        try:
            with (
                stream_redirected(to=f, stream=sys.stdout),
                stream_redirected(to=f, stream=sys.stderr),
            ):
                wheel_path = build.run(
                    PyPIProvider.BUILD_EXPORTS, PyPIProvider.BUILD_FLAGS
                )
        except BaseException as e:
            print(" Failed\n Error is:")
            f.seek(0)
            sys.stdout.write(f.read())
            raise e

    OKGREEN = "\033[92m"
    ENDC = "\033[0m"
    print(OKGREEN, "Success", ENDC)

    cache_entry["path"] = wheel_path
    BUILD_CACHE[url] = cache_entry
    return wheel_path


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


class ExtrasProvider(APBase):
    """A provider that handles extras."""

    def get_extras_for(self, requirement_or_candidate):
        """Given a requirement or candidate, return its extras.
        The extras should be a hashable value.
        """
        raise NotImplementedError

    def get_base_requirement(self, candidate):
        """Given a candidate, return a requirement that specifies that
        project/version.
        """
        raise NotImplementedError

    def identify(self, requirement_or_candidate):
        base = super().identify(requirement_or_candidate)
        return base

    def get_dependencies(self, candidate):
        deps = list(super().get_dependencies(candidate))
        if candidate.extras:
            req = self.get_base_requirement(candidate)
            deps.append(req)
        return deps


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
        index_urls=["https://pypi.org/simple/"], target_python=get_target_python()
    )
    matches = pf.find_all_packages(package_name)
    for i in matches:
        # TODO: ignore sourcedists if wheel for same version exists
        yield Candidate(i.name, i.version, url=i.link.url, extras=extras)


def download_or_build_wheel(url: str, target_directory: Path) -> None:
    parsed_url = urlparse(url)
    if parsed_url.path.endswith("gz"):
        wheel_file = get_cached_built_wheel(url)
        shutil.copy(wheel_file, target_directory)
    elif parsed_url.path.endswith(".whl"):
        with open(target_directory / Path(parsed_url.path).name, "wb") as f:
            f.write(requests.get(url).content)


def get_metadata_for_wheel(url):
    parsed_url = urlparse(url)
    if parsed_url.path.endswith("gz"):
        wheel_file = get_cached_built_wheel(url)
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


class PyPIProvider(ExtrasProvider):

    BUILD_FLAGS: list[str] = []
    BUILD_SKIP: list[str] = []
    BUILD_EXPORTS: str = ""

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
        for d in candidate.dependencies:
            if d.name not in PyPIProvider.BUILD_SKIP:
                deps.append(d)
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


def build_dependencies_for_wheel(
    wheel: Path,
    extras: list[str],
    skip_dependency: list[str],
    exports: str,
    build_flags: list[str],
) -> None:
    """Extract dependencies from this wheel and build pypi dependencies
    for each one in /dist/.

    n.b. because dependency resolution may need to backtrack, this
    is potentially quite slow in the case that one needs to build an
    sdist in order to discover dependencies of a candidate sub-dependency.
    """
    metadata = None
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
    requirements = []

    target_env = {
        "extra": ",".join(extras),
        "python_version": f'{common.get_make_flag("PYMAJOR")}.{common.get_make_flag("PYMINOR")}',
        "sys_platform": common.platform().split("_")[0],
    }

    for d in deps:
        # TODO: handle skip list
        r = Requirement(d)
        if (r.name not in PyPIProvider.BUILD_SKIP) and (
            (not r.marker) or r.marker.evaluate(target_env)
        ):
            requirements.append(r)

    # Create the (reusable) resolver.
    provider = PyPIProvider()
    reporter = BaseReporter()
    resolver: Resolver[Requirement, Candidate, str] = Resolver(provider, reporter)

    # Kick off the resolution process, and get the final result.
    result = resolver.resolve(requirements)
    for x in result.mapping.values():
        download_or_build_wheel(x.url, wheel.parent)


def fetch_pypi_package(package_spec, destdir):
    pf = PackageFinder(
        index_urls=["https://pypi.org/simple/"], target_python=get_target_python()
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
