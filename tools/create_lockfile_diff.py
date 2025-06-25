import argparse
from dataclasses import dataclass
from pathlib import Path
from pyodide_lock import PyodideLockSpec, PackageSpec


def parse_args():
    parser = argparse.ArgumentParser(description="Compare two Pyodide lockfiles and output the differences. This tool is for creating a diff for changelog.")
    parser.add_argument("old_lockfile", type=str, help="Path to the old lockfile.")
    parser.add_argument("new_lockfile", type=str, help="Path to the new lockfile.")
    return parser.parse_args()


@dataclass
class PackageDiff:
    name: str
    old_version: str | None
    new_version: str | None


def is_normal_python_package(pkg: PackageSpec) -> bool:
    return pkg.package_type == "package" and pkg.file_name.endswith(".whl")


def calculate_diff(old_lockfile_path: Path, new_lockfile_path: Path) -> tuple[list[PackageDiff], list[PackageDiff], list[PackageDiff]]:
    """
    Calculate the differences between two Pyodide lockfiles.

    Returns a tuple of three lists:
    - Added packages
    - Removed packages
    - Changed packages (with old and new versions)
    """
    old_lockfile = PyodideLockSpec.from_json(Path(old_lockfile_path))
    new_lockfile = PyodideLockSpec.from_json(Path(new_lockfile_path))

    old_packages = {pkg.name: pkg for pkg in old_lockfile.packages.values() if is_normal_python_package(pkg)}
    new_packages = {pkg.name: pkg for pkg in new_lockfile.packages.values() if is_normal_python_package(pkg)}

    added = [PackageDiff(name=pkg.name, old_version=None, new_version=pkg.version) 
             for name, pkg in new_packages.items() if name not in old_packages]
    
    removed = [PackageDiff(name=pkg.name, old_version=pkg.version, new_version=None) 
               for name, pkg in old_packages.items() if name not in new_packages]
    
    changed = [PackageDiff(name=name, old_version=old_packages[name].version, new_version=new_packages[name].version)
               for name in set(old_packages) & set(new_packages)
               if old_packages[name].version != new_packages[name].version]
    
    return added, removed, changed


def main():
    args = parse_args()

    added, removed, changed = calculate_diff(args.old_lockfile, args.new_lockfile)

    print("Added packages:")
    for pkg in added:
        print(f"  - {pkg.name} ({pkg.new_version})")

    print("\nRemoved packages:")
    for pkg in removed:
        print(f"  - {pkg.name} ({pkg.old_version})")

    print("\nChanged packages:")
    for pkg in changed:
        print(f"  - {pkg.name}: {pkg.old_version} -> {pkg.new_version}")


if __name__ == "__main__":
    main()