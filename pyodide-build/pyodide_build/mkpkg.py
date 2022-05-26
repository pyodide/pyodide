#!/usr/bin/env python3

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import warnings
from pathlib import Path
from typing import Any, Callable, Literal, Sequence, TypedDict, cast, TypeVar, overload
from zipfile import ZipFile

import packaging.specifiers
import pkg_resources
import setuptools
from ruamel.yaml import YAML


class URLDict(TypedDict):
    comment_text: str
    digests: dict[str, Any]
    downloads: int
    filename: str
    has_sig: bool
    md5_digest: str
    packagetype: str
    python_version: str
    requires_python: str
    size: int
    upload_time: str
    upload_time_iso_8601: str
    url: str
    yanked: bool
    yanked_reason: str | None


class MetadataDict(TypedDict):
    info: dict[str, Any]
    last_serial: int
    releases: dict[str, list[dict[str, Any]]]
    urls: list[URLDict]
    vulnerabilities: list[Any]


class MkpkgFailedException(Exception):
    pass


SDIST_EXTENSIONS = tuple(
    extension
    for (name, extensions, description) in shutil.get_unpack_formats()
    for extension in extensions
)


def _find_sdist(pypi_metadata: MetadataDict) -> URLDict | None:
    """Get sdist file path from the metadata"""
    # The first one we can use. Usually a .tar.gz
    for entry in pypi_metadata["urls"]:
        if entry["packagetype"] == "sdist" and entry["filename"].endswith(
            SDIST_EXTENSIONS
        ):
            return entry
    return None


def _find_wheel(pypi_metadata: MetadataDict) -> URLDict | None:
    """Get wheel file path from the metadata"""
    for entry in pypi_metadata["urls"]:
        if entry["packagetype"] == "bdist_wheel" and entry["filename"].endswith(
            "py3-none-any.whl"
        ):
            return entry
    return None


def _find_dist(
    pypi_metadata: MetadataDict, source_types: list[Literal["wheel", "sdist"]]
) -> URLDict:
    """Find a wheel or sdist, as appropriate.

    source_types controls which types (wheel and/or sdist) are accepted and also
    the priority order.
    E.g., ["wheel", "sdist"] means accept either wheel or sdist but prefer wheel.
    ["sdist", "wheel"] means accept either wheel or sdist but prefer sdist.
    """
    result = None
    for source in source_types:
        if source == "wheel":
            result = _find_wheel(pypi_metadata)
        if source == "sdist":
            result = _find_sdist(pypi_metadata)
        if result:
            return result

    types_str = " or ".join(source_types)
    name = pypi_metadata["info"].get("name")
    url = pypi_metadata["info"].get("package_url")
    raise MkpkgFailedException(f"No {types_str} found for package {name} ({url})")


def _get_metadata(package: str, version: str | None = None) -> MetadataDict:
    """Download metadata for a package from PyPI"""

    if version is not None:
        # first download metadata for current version so we
        # can get the list of versions
        url = f"https://pypi.org/pypi/{package}/json"
        chosen_version = None
        try:
            with urllib.request.urlopen(url) as fd:
                main_metadata = json.load(fd)
                all_versions = main_metadata["releases"].keys()
                try:
                    spec = packaging.specifiers.SpecifierSet(version)
                except packaging.specifiers.InvalidSpecifier:
                    try:
                        spec = packaging.specifiers.SpecifierSet(f"=={version}")
                    except packaging.specifiers.InvalidSpecifier as e:
                        raise MkpkgFailedException(
                            f"Bad specifier for  {package}{version} from "
                            f"https://pypi.org/pypi/{package}{version}/json: {e}"
                        )

                filtered_versions = sorted(spec.filter(all_versions))
                if len(filtered_versions) != 0:
                    chosen_version = str(filtered_versions[-1])
                else:
                    raise MkpkgFailedException(
                        f"No matching version for  {package}{version} from "
                        f"https://pypi.org/pypi/{package}{version}/json:"
                    )

        except urllib.error.HTTPError as e:
            raise MkpkgFailedException(
                f"Failed to load metadata for {package}{version} from "
                f"https://pypi.org/pypi/{package}{version}/json: {e}"
            )
        if chosen_version is None:
            raise MkpkgFailedException(
                f"Failed to find pypi package for {package}{version} from "
                f"https://pypi.org/pypi/{package}{version}/json"
            )
        version = chosen_version

    # and set version to this to download specific metadata

    version = ("/" + version) if version is not None else ""
    url = f"https://pypi.org/pypi/{package}{version}/json"

    try:
        with urllib.request.urlopen(url) as fd:
            pypi_metadata = cast(MetadataDict, json.load(fd))
    except urllib.error.HTTPError as e:
        raise MkpkgFailedException(
            f"Failed to load metadata for {package}{version} from "
            f"https://pypi.org/pypi/{package}{version}/json: {e}"
        )

    return pypi_metadata


def run_prettier(meta_path: Path) -> None:
    subprocess.run(["npx", "prettier", "-w", meta_path])


def _download_package(
    url: str, project_name: str
) -> tuple[ZipFile | tarfile.TarFile, list[str], str | None]:
    all_files = []
    toplevel_text = None
    if url.endswith(".zip") or url.endswith(".whl"):
        filetype = ".zip"
    elif url.endswith(".tar.gz") or url.endswith(".tgz"):
        filetype = ".tar.gz"
    package: None | ZipFile | tarfile.TarFile = None
    tf = tempfile.NamedTemporaryFile(suffix=filetype)
    try:
        with urllib.request.urlopen(url) as fd:
            tf.write(fd.read())
        if filetype == ".zip":
            package = ZipFile(tf)
            all_files = package.namelist()
            open_fn: Callable[[Any], Any] = package.open
        elif filetype == ".tar.gz":
            package = tarfile.open(tf.name)
            all_files = package.getnames()
            open_fn = package.extractfile
        else:
            tf.close()
            raise MkpkgFailedException(
                f"Unknown archive type for {url}, can't determine imports"
            )
    except urllib.error.URLError as e:
        tf.close()
        raise MkpkgFailedException(
            f"Failed to load wheel or sdist for {project_name} from " f"{url} {e}"
        )
    for f in all_files:
        if f.endswith(".dist-info/top_level.txt") or f.endswith(
            ".egg-info/top_level.txt"
        ):
            with open_fn(f) as tl:
                toplevel_text = tl.read()
                toplevel_text = toplevel_text.decode(errors="ignore")
                break
    return package, all_files, toplevel_text


def _find_imports_from_package(url: str, project_name: str) -> list[str]:
    # first download the package and extract any top_level.txt
    compressed_package, all_files, toplevel_text = _download_package(url, project_name)

    # if there is a top_level.txt, just return the contents of that minus any blank lines
    if toplevel_text is not None:
        modules = list(filter(lambda s: len(s) > 0, toplevel_text.split("\n")))
        return modules
    else:
        # extract to a temp folder and run setuptools.find_package on it
        with tempfile.TemporaryDirectory() as temp_dir:
            compressed_package.extractall(temp_dir)
            all_imports = setuptools.find_packages(temp_dir)
            if len(all_imports) == 0:
                # check if it is a single file module
                # i.e. only has a single python file in root
                # with similar name to package
                # because find_packages doesn't find this type of module yet
                not_text = re.compile(r"\W|_")
                clean_name = not_text.sub("", project_name)
                for f in all_files:
                    if f.endswith(".py"):
                        clean_f = not_text.sub("", f[:-3])
                        if clean_f == clean_name:
                            all_imports = [f[:-3]]
                            break
                if len(all_imports) == 0:
                    raise MkpkgFailedException(
                        f"Couldn't find imports for {project_name} from "
                        f"{url} files:\n"
                        f"{all_files}"
                    )
    return all_imports


def make_package(
    packages_dir: Path,
    package: str,
    version: str | None = None,
    source_fmt: Literal["wheel", "sdist"] | None = None,
    extra: str | None = None,
    make_dependencies: bool = False,
    find_imports: bool = False,
) -> None:
    """
    Creates a template that will work for most pure Python packages,
    but will have to be edited for more complex things.
    """
    print(f"Creating meta.yaml package for {package}")

    yaml = YAML()

    pypi_metadata = _get_metadata(package, version)

    if source_fmt:
        sources = [source_fmt]
    else:
        # Prefer wheel unless sdist is specifically requested.
        sources = ["wheel", "sdist"]
    dist_metadata = _find_dist(pypi_metadata, sources)

    url = dist_metadata["url"]
    sha256 = dist_metadata["digests"]["sha256"]
    version = pypi_metadata["info"]["version"]

    homepage = pypi_metadata["info"]["home_page"]
    summary = pypi_metadata["info"]["summary"]
    license = pypi_metadata["info"]["license"]
    pypi = "https://pypi.org/project/" + package

    class YamlDistribution(pkg_resources.Distribution):
        def __init__(self, *args: Any, **argv: Any) -> None:
            super().__init__(*args, **argv)
            # filter python version etc. extras now

        #            self.__dep_map = self._filter_extras(self._build_dep_map())

        def requires(
            self, extras: tuple[str, ...] = ()
        ) -> list[pkg_resources.Requirement]:
            reqs = super().requires(extras)
            return reqs

        def _build_dep_map(self) -> dict[str | None, list[pkg_resources.Requirement]]:
            # read dependencies from pypi
            package_metadata = _get_metadata(self.project_name, self.version)
            dm: dict[str | None, list[pkg_resources.Requirement]] = {}
            if (
                "requires_dist" in package_metadata["info"]
                and package_metadata["info"]["requires_dist"] is not None
            ):
                # make a requirements parser and do this properly
                reqs = pkg_resources.parse_requirements(
                    package_metadata["info"]["requires_dist"]
                )
                for req in reqs:
                    m = req.marker
                    extra_name = None
                    if m is not None:
                        for m in m._markers:
                            if str(m[0]) == "extra" and len(m) == 3:
                                extra_name = str(m[2])
                    dm.setdefault(extra_name, []).append(req)

            return dm

    _T = TypeVar("_T")

    class EnvironmentHelper(pkg_resources.Environment):
        def __init__(self) -> None:
            super().__init__(search_path=[str(packages_dir)])

        def scan(self, search_path: Sequence[str] | None = None) -> None:
            pass

        def make_dist(self, proj_name: str, meta_path: Path) -> YamlDistribution:
            yaml = YAML()
            p_yaml = yaml.load(meta_path.read_bytes())
            p_version = p_yaml["package"]["version"]
            dist = YamlDistribution(
                meta_path.parents[0], project_name=proj_name, version=p_version
            )
            return dist

        @overload
        def best_match(
            self,
            req: pkg_resources.Requirement,
            working_set: pkg_resources.WorkingSet,
            *,
            replace_conflicting: bool = ...,
        ) -> pkg_resources.Distribution:
            ...

        @overload
        def best_match(
            self,
            req: pkg_resources.Requirement,
            working_set: pkg_resources.WorkingSet,
            installer: Callable[[pkg_resources.Requirement], _T],
            replace_conflicting: bool = ...,
        ) -> _T:
            ...

        def best_match(
            self, req, working_set, installer=None, replace_conflicting=False
        ):
            return self._best_match(
                req,
                working_set,
                installer=installer,
                replace_conflicting=replace_conflicting,
            )

        def _best_match(
            self,
            req: pkg_resources.Requirement,
            working_set: pkg_resources.WorkingSet,
            installer: None
            | (
                Callable[[pkg_resources.Requirement], pkg_resources.Distribution]
            ) = None,
            replace_conflicting: bool = False,
            from_install: bool = False,
        ) -> pkg_resources.Distribution:
            proj_name = req.project_name
            if os.path.isfile(packages_dir / proj_name / "meta.yaml"):
                return self.make_dist(
                    req.project_name, packages_dir / proj_name / "meta.yaml"
                )
            proj_name = proj_name.replace("-", "_")
            if os.path.isfile(packages_dir / proj_name / "meta.yaml"):
                return self.make_dist(
                    req.project_name, packages_dir / proj_name / "meta.yaml"
                )
            # no package installed - try to install it
            print("Installing dependency:", req.project_name, str(req.specs))
            self.from_install = True
            make_package(
                packages_dir,
                req.project_name,
                ",".join(["".join(x) for x in req.specs]),
                source_fmt=source_fmt,
                make_dependencies=make_dependencies,
                find_imports=find_imports,
            )
            return self._best_match(
                req,
                working_set,
                installer=installer,
                replace_conflicting=replace_conflicting,
                from_install=True,
            )

    if extra:
        our_extras = extra.split(",")
    else:
        our_extras = []
    requires_packages = []
    yaml_requires = []

    package_dir = packages_dir / package

    dist = YamlDistribution(package_dir, project_name=package, version=version)
    requires_packages = dist.requires(extras=tuple(our_extras))

    env = EnvironmentHelper()

    if make_dependencies:
        ws = pkg_resources.WorkingSet([])
        # bug in type specifications which are missing extras parameter
        ws.resolve(
            requires_packages, env=env, extras=our_extras
        )  # type:ignore[call-arg]

    for r in requires_packages:
        name = r.project_name
        if r.marker and not r.marker.evaluate(environment=env):
            continue
        if os.path.isfile(packages_dir / name / "meta.yaml"):
            yaml_requires.append(name)
        else:
            name = name.replace("-", "_")
            if os.path.isfile(packages_dir / name / "meta.yaml"):
                yaml_requires.append(name)
            else:
                print(f"Warning: Missing dependency of {package}: {name}")

    if find_imports:
        pkg_imports = _find_imports_from_package(url, package)
    else:
        pkg_imports = [package]

    yaml_content = {
        "package": {"name": package, "version": version},
        "source": {"url": url, "sha256": sha256},
        "test": {"imports": pkg_imports},
        "requirements": {"run": yaml_requires},
        "about": {
            "home": homepage,
            "PyPI": pypi,
            "summary": summary,
            "license": license,
        },
    }

    package_dir.mkdir(parents=True, exist_ok=True)

    meta_path = package_dir / "meta.yaml"
    if meta_path.exists():
        raise MkpkgFailedException(f"The package {package} already exists")

    yaml.dump(yaml_content, meta_path)
    try:
        run_prettier(meta_path)
    except FileNotFoundError:
        warnings.warn("'npx' executable missing, output has not been prettified.")

    success(f"Output written to {meta_path}")


# TODO: use rich for coloring outputs
class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def abort(msg):
    print(bcolors.FAIL + msg + bcolors.ENDC)
    sys.exit(1)


def warn(msg):
    warnings.warn(bcolors.WARNING + msg + bcolors.ENDC)


def success(msg):
    print(bcolors.OKBLUE + msg + bcolors.ENDC)


def update_package(
    root: Path,
    package: str,
    version: str | None = None,
    update_patched: bool = True,
    source_fmt: Literal["wheel", "sdist"] | None = None,
) -> None:

    yaml = YAML()

    meta_path = root / package / "meta.yaml"
    if not meta_path.exists():
        abort(f"{meta_path} does not exist")

    yaml_content = yaml.load(meta_path.read_bytes())

    if "url" not in yaml_content["source"]:
        raise MkpkgFailedException(f"Skipping: {package} is a local package!")

    build_info = yaml_content.get("build", {})
    if build_info.get("library", False) or build_info.get("sharedlibrary", False):
        raise MkpkgFailedException(f"Skipping: {package} is a library!")

    if yaml_content["source"]["url"].endswith("whl"):
        old_fmt = "wheel"
    else:
        old_fmt = "sdist"

    pypi_metadata = _get_metadata(package, version)
    pypi_ver = pypi_metadata["info"]["version"]
    local_ver = yaml_content["package"]["version"]
    already_up_to_date = pypi_ver <= local_ver and (
        source_fmt is None or source_fmt == old_fmt
    )
    if already_up_to_date:
        print(f"{package} already up to date. Local: {local_ver} PyPI: {pypi_ver}")
        return

    print(f"{package} is out of date: {local_ver} <= {pypi_ver}.")

    if "patches" in yaml_content["source"]:
        if update_patched:
            warn(
                f"Pyodide applies patches to {package}. Update the "
                "patches (if needed) to avoid build failing."
            )
        else:
            raise MkpkgFailedException(
                f"Pyodide applies patches to {package}. Skipping update."
            )

    if source_fmt:
        # require the type requested
        sources = [source_fmt]
    elif old_fmt == "wheel":
        # prefer wheel to sdist
        sources = ["wheel", "sdist"]
    else:
        # prefer sdist to wheel
        sources = ["sdist", "wheel"]

    dist_metadata = _find_dist(pypi_metadata, sources)

    yaml_content["source"]["url"] = dist_metadata["url"]
    yaml_content["source"].pop("md5", None)
    yaml_content["source"]["sha256"] = dist_metadata["digests"]["sha256"]
    yaml_content["package"]["version"] = pypi_metadata["info"]["version"]

    yaml.dump(yaml_content, meta_path)
    run_prettier(meta_path)

    success(f"Updated {package} from {local_ver} to {pypi_ver}.")


def make_parser(parser):
    parser.description = """
Make a new pyodide package. Creates a simple template that will work
for most pure Python packages, but will have to be edited for more
complex things.""".strip()
    parser.add_argument("package", type=str, nargs=1, help="The package name on PyPI")
    parser.add_argument("--update", action="store_true", help="Update existing package")
    parser.add_argument(
        "--update-if-not-patched",
        action="store_true",
        help="Update existing package if it has no patches",
    )
    parser.add_argument(
        "--make-dependencies",
        action="store_true",
        help="Make package dependencies if not installed",
    )
    parser.add_argument(
        "--source-format",
        help="Which source format is preferred. Options are wheel or sdist. "
        "If none is provided, then either a wheel or an sdist will be used. "
        "When updating a package, the type will be kept the same if possible.",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Package version string, "
        "e.g. v1.2.1 (defaults to latest stable release)",
    )
    parser.add_argument(
        "--extras",
        type=str,
        default=None,
        help="Package install extras" "e.g. extra1,extra2",
    )
    parser.add_argument(
        "--find-correct-imports",
        action="store_true",
        help="Find the correct imports for the package"
        "(e.g. if the package is called bob-jones, import might be bobjones, bob_jones, pybobjones etc.)"
        "This involves downloading the source wheel for the package, so could be slow.",
    )
    return parser


def main(args):
    PYODIDE_ROOT = os.environ.get("PYODIDE_ROOT")
    if PYODIDE_ROOT is None:
        raise ValueError("PYODIDE_ROOT is not set")

    PACKAGES_ROOT = Path(PYODIDE_ROOT) / "packages"

    try:
        package = args.package[0]
        if args.update:
            update_package(
                PACKAGES_ROOT,
                package,
                args.version,
                update_patched=True,
                source_fmt=args.source_format,
            )
            return
        if args.update_if_not_patched:
            update_package(
                PACKAGES_ROOT,
                package,
                args.version,
                update_patched=False,
                source_fmt=args.source_format,
            )
            return
        make_package(
            PACKAGES_ROOT,
            package,
            args.version,
            source_fmt=args.source_format,
            make_dependencies=args.make_dependencies,
            find_imports=args.find_correct_imports,
        )
    except MkpkgFailedException as e:
        # This produces two types of error messages:
        #
        # When the request to get the pypi json fails, it produces a message like:
        # "Failed to load metadata for libxslt from https://pypi.org/pypi/libxslt/json: HTTP Error 404: Not Found"
        #
        # If there is no sdist it prints an error message like:
        # "No sdist URL found for package swiglpk (https://pypi.org/project/swiglpk/)"
        abort(e.args[0])


if __name__ == "__main__":
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
