#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import warnings
from pathlib import Path,PurePath
from typing import Any, Literal, TypedDict
import pkg_resources
import packaging.specifiers

from ruamel.yaml import YAML
from zipfile import ZipFile
import tarfile
import tempfile

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
        chosen_version=None
        try:
            with urllib.request.urlopen(url) as fd:
                main_metadata = json.load(fd)
                all_versions=main_metadata["releases"].keys()
                all_versions=sorted(map(pkg_resources.parse_version,all_versions))
                this_ver=pkg_resources.parse_version(version)
                if this_ver in all_versions:
                    chosen_version=str(this_ver)
                else:
                    try:
                        spec=packaging.specifiers.SpecifierSet(version)
                        chosen_version=None
                        for v in reversed(all_versions):
                            if spec.contains(str(v)):
                                chosen_version=str(v)
                                break
                    except packaging.specifiers.InvalidSpecifier as e:
                        raise MkpkgFailedException(
                            f"Bad specifier for  {package}{version} from "
                            f"https://pypi.org/pypi/{package}{version}/json: {e}"
                        )
                    
        except urllib.error.HTTPError as e:
            raise MkpkgFailedException(
                f"Failed to load metadata for {package}{version} from "
                f"https://pypi.org/pypi/{package}{version}/json: {e}"
            )
        if chosen_version is None:
            raise MkpkgFailedException(
                f"Failed to find pypi package for {package}{version} from "
                f"https://pypi.org/pypi/{package}{version}/json: {e}"
            )
        version=chosen_version
                
    # and set version to this to download specific metadata

    version = ("/" + version) if version is not None else ""
    url = f"https://pypi.org/pypi/{package}{version}/json"

    try:
        with urllib.request.urlopen(url) as fd:
            pypi_metadata = json.load(fd)
    except urllib.error.HTTPError as e:
        raise MkpkgFailedException(
            f"Failed to load metadata for {package}{version} from "
            f"https://pypi.org/pypi/{package}{version}/json: {e}"
        )

    return pypi_metadata


def run_prettier(meta_path):
    subprocess.run(["npx", "prettier", "-w", meta_path])


def _make_project_compare_name(project_name):
    project_name_cleaned=project_name.replace("_","").replace("-","").lower()
    if project_name_cleaned.startswith("py"):
        project_name_cleaned=project_name[2:]
    return project_name_cleaned

# download a package from pypi and guess what modules are provided by it
def _find_imports_from_package(url,project_name):
    project_name_cleaned=_make_project_compare_name(project_name)
    all_imports=[]
    try:
        if url.endswith(".zip") or url.endswith(".whl"):
            filetype=".zip"
        elif url.endswith(".tar.gz") or url.endswith(".tgz"):
            filetype=".tar.gz"
        else:
            print("Unknown archive type for {url}, can't determine imports")
            return []
        with tempfile.NamedTemporaryFile(suffix=filetype) as tf:
            with urllib.request.urlopen(url) as fd:
                tf.write(fd.read())
            all_files=[]
            if url.endswith(".zip") or url.endswith(".whl"):
                # wheel is zip
                with ZipFile(tf) as package:
                    all_files=package.namelist()
            elif url.endswith(".tar.gz") or url.endswith(".tgz"):
                # wheel is tar gz
                with tarfile.open(tf.name) as package:
                    all_files=package.getnames()
                    all_modules=[]
            all_modules=[]
            for f in all_files:
                # find module folders
                if f.endswith("__init__.py") and f.find("/test/")==-1:
                    all_modules.append(PurePath("/"+f).parents[0])
            if len(all_modules)==0:
                # is this maybe a single file module with a file called 'modulename.py'?
                for f in all_files:
                    p=PurePath("/"+f)
                    if p.suffix==".py":
                        cleaned=_make_project_compare_name(p.stem)
                        if cleaned==project_name:
                            return [p.stem]
            if len(all_modules)==0:
                print(f"WARNING: COuldn't find any imports in package {url}")
                return []
            main_prefix=None
            main_prefix_level=None
            # check for first bit of the path that looks like the package name
            # without any _ or -
            for mod in all_modules:
                level=len(mod.parts)
                path_part=mod.parts[-1]
                cleaned=_make_project_compare_name(path_part)
                if cleaned==project_name_cleaned:
                    if main_prefix_level==None or level<=main_prefix_level :
                        main_prefix_level=level
                        main_prefix=PurePath(*mod.parts[0:level+1])
            if main_prefix==None:
                # not found a correctly named top level prefix, just find the highest up path
                # that contains all modules and assume that is the base
                test_prefix=all_modules[0]
                found_prefix=False
                while main_prefix==None:
                    found_prefix=True
                    for mod in all_modules:
                        if not str(all_modules).startswith(str(test_prefix)):
                            found_prefix=False
                            break
                    if not found_prefix and len(test_prefix.parents)>1:
                        test_prefix=test_prefix.parents[0]
                    else:
                        main_prefix=test_prefix

            main_prefix=str(main_prefix.parents[0])
            if not main_prefix.endswith("/"):
                main_prefix+="/"
            for mod in all_modules:
                if str(mod).startswith(str(main_prefix)):
                    import_name=str(mod).replace("/",".")
                    import_name=import_name[len(str(main_prefix)):]
                    all_imports.append(import_name)
    except urllib.error.HTTPError as e:
        raise MkpkgFailedException(
            f"Failed to load wheel or sdist for {project_name} from "
            f"{url} {e}"
        )
    print(f"Package {project_name}, imports = {','.join(all_imports)}")
    return all_imports

    


def make_package(
    packages_dir: Path,
    package: str,
    version: str | None = None,
    source_fmt: Literal["wheel", "sdist"] | None = None,
    extra: str | None = None,
    make_dependencies: bool = False,
    find_imports : bool= False
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
        def __init__(self,*args,**argv):
            super().__init__(*args,**argv)
            # filter python version etc. extras now
            self.__dep_map= self._filter_extras(self._build_dep_map())

        def requires(self,extras=()):
            reqs=super().requires(extras)
            return reqs

        def _build_dep_map(self):
            # read dependencies from pypi
            package_metadata=_get_metadata(self.project_name,self._version)
            dm={}
            if "requires_dist" in package_metadata["info"] and package_metadata["info"]["requires_dist"]!=None:
                # make a requirements parser and do this properly
                reqs=pkg_resources.parse_requirements(package_metadata["info"]["requires_dist"])
                for req in reqs:
                    m=req.marker
                    extra_name=None
                    if m!=None:
                        for m in m._markers:
                            if str(m[0])=="extra" and len(m)==3:
                                extra_name=str(m[2])
                    dm.setdefault(extra_name, []).append(req)

            return dm

    class EnvironmentHelper(pkg_resources.Environment):
        def __init__(self):
            super().__init__(search_path=[packages_dir])

        def scan(self, search_path=None):
            pass

        def make_dist(self,proj_name,meta_path):
            yaml=YAML()
            p_yaml=yaml.load(meta_path.read_bytes())
            p_version=p_yaml["package"]["version"]
            dist=YamlDistribution( meta_path.parents[0],project_name=proj_name,version=p_version)
            return dist

        def best_match(self,req,working_set,installer=None,replace_conflicting=False,from_install=False):
            proj_name=req.project_name
            if os.path.isfile(packages_dir / proj_name / "meta.yaml"):
                return self.make_dist(req.project_name,packages_dir / proj_name / "meta.yaml")
            proj_name=proj_name.replace("-","_")
            if os.path.isfile(packages_dir / proj_name / "meta.yaml"):
                return self.make_dist(req.project_name,packages_dir / proj_name / "meta.yaml")
            # no package installed - try to install it
            if from_install:
                return None
            parser = make_parser(argparse.ArgumentParser())            
            print("Installing dependency:",req.project_name,str(req.specs))
            make_package(
                packages_dir,req.project_name,str(req.specifier),source_fmt=source_fmt,make_dependencies=make_dependencies,find_imports=find_imports)
            return self.best_match(req,working_set,installer,replace_conflicting,True)
            
    if extra:
        our_extras=extra.split(",")
    else:
        our_extras=[]
    requires_packages=[]
    yaml_requires=[]

    package_dir = packages_dir / package

    dist=YamlDistribution(package_dir,project_name=package,version=version)
    requires_packages=dist.requires(extras=our_extras)

    env=EnvironmentHelper()

    if make_dependencies:
        ws= pkg_resources.WorkingSet([])
        ws.resolve(requires_packages,env=env,extras=our_extras)

    for r in requires_packages:
        name=r.name
        if r.marker and not r.marker.evaluate(environment=env):
            continue
        if os.path.isfile(packages_dir / name / "meta.yaml"):
            yaml_requires.append(name)
        else:
            name=name.replace("-","_")
            if os.path.isfile(packages_dir / name / "meta.yaml"):
                yaml_requires.append(name)
            else:
                print(f"Warning: Missing dependency of {package}: {name}")

    if find_imports:
        pkg_imports=_find_imports_from_package(url,package)
    else:
        pkg_imports=[package]

    yaml_content = {
        "package": {"name": package, "version": version},
        "source": {"url": url, "sha256": sha256},
        "test": {"imports": pkg_imports},
        "requirements": {"run":yaml_requires},
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
        help="Package install extras"
        "e.g. extra1,extra2",
    )
    parser.add_argument(
        "--find-correct-imports",
        action="store_true",
        help="Find the correct imports for the package"
        "(e.g. if the package is called bob-jones, import might be bobjones, bob_jones, pybobjones etc.)"
        "This involves downloading the source wheel for the package, so could be slow."
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
            PACKAGES_ROOT, package, args.version, source_fmt=args.source_format,make_dependencies=args.make_dependencies,find_imports=args.find_correct_imports
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
