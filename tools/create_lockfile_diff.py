import argparse
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from pyodide_lock import PackageSpec, PyodideLockSpec


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare two Pyodide lockfiles and output the differences. This tool is for creating a diff for changelog."
    )
    parser.add_argument(
        "old_lockfile",
        type=str,
        nargs="?",
        help="Path to the old lockfile. If not provided, will fetch from upstream/main branch.",
    )
    parser.add_argument(
        "new_lockfile",
        type=str,
        nargs="?",
        help="Path to the new lockfile. If not provided, will use current branch's lockfile.",
    )
    return parser.parse_args()


@dataclass
class PackageDiff:
    name: str
    old_version: str | None
    new_version: str | None


def is_normal_python_package(pkg: PackageSpec) -> bool:
    return pkg.package_type == "package" and pkg.file_name.endswith(".whl")


def get_lockfile_url_from_makefile(branch: str | None = None) -> str:
    """
    Get the PYODIDE_PREBUILT_PACKAGES_LOCKFILE URL from the Makefile.

    Args:
        branch: If provided, get the URL from this git branch. If None, use the current branch.

    Returns:
        The URL to the lockfile.
    """
    if branch:
        # Get the Makefile.envs content from the specified branch
        result = subprocess.run(
            ["git", "show", f"{branch}:Makefile.envs"],
            capture_output=True,
            text=True,
            check=True,
        )
        makefile_content = result.stdout

        # First pass: collect all variable definitions
        variables = {}
        for line in makefile_content.split("\n"):
            line = line.strip()
            if line.startswith("export ") and "=" in line:
                # Remove 'export ' prefix and split on first '='
                var_line = line[7:]  # Remove 'export '
                var_name, var_value = var_line.split("=", 1)
                variables[var_name.strip()] = var_value.strip()

        # Second pass: resolve variable references
        import re

        max_iterations = 10  # Prevent infinite loops
        for _ in range(max_iterations):
            changed = False
            for var_name, var_value in list(variables.items()):
                for match in re.finditer(r"\$\(([^)]+)\)", var_value):
                    ref_var = match.group(1)
                    if ref_var in variables:
                        new_value = var_value.replace(
                            match.group(0), variables[ref_var]
                        )
                        if new_value != var_value:
                            variables[var_name] = new_value
                            changed = True
            if not changed:
                break

        if "PYODIDE_PREBUILT_PACKAGES_LOCKFILE" not in variables:
            raise ValueError(
                f"Could not find PYODIDE_PREBUILT_PACKAGES_LOCKFILE in {branch} branch"
            )

        return variables["PYODIDE_PREBUILT_PACKAGES_LOCKFILE"]
    else:
        # Get the URL from the current branch using make env
        result = subprocess.run(
            ["make", "env"],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.split("\n"):
            if line.startswith("PYODIDE_PREBUILT_PACKAGES_LOCKFILE="):
                return line.split("=", 1)[1].strip()
        raise ValueError(
            "Could not find PYODIDE_PREBUILT_PACKAGES_LOCKFILE in current branch"
        )


def download_lockfile(url: str, temp_dir: Path) -> Path:
    """
    Download a lockfile from a URL to a temporary directory.

    Args:
        url: The URL to download from.
        temp_dir: The temporary directory to save the file in.

    Returns:
        Path to the downloaded file.
    """
    temp_dir.mkdir(parents=True, exist_ok=True)
    filename = temp_dir / "lockfile.json"
    print(f"Downloading lockfile from {url}...", file=sys.stderr)
    urllib.request.urlretrieve(url, filename)
    return filename


def get_lockfile_path(path_or_url: str | None, is_old: bool, temp_dir: Path) -> Path:
    """
    Get the path to a lockfile, downloading it if necessary.

    Args:
        path_or_url: Path or URL to the lockfile, or None to auto-detect.
        is_old: Whether this is the old lockfile (True) or new lockfile (False).
        temp_dir: Temporary directory for downloads.

    Returns:
        Path to the lockfile.
    """
    if path_or_url is None:
        # Auto-detect based on whether it's old or new
        if is_old:
            print(
                "Auto-detecting old lockfile from upstream/main branch...",
                file=sys.stderr,
            )
            url = get_lockfile_url_from_makefile("upstream/main")
        else:
            print("Auto-detecting new lockfile from current branch...", file=sys.stderr)
            url = get_lockfile_url_from_makefile(None)
        return download_lockfile(url, temp_dir / ("old" if is_old else "new"))
    elif path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        # It's a URL, download it
        return download_lockfile(path_or_url, temp_dir / ("old" if is_old else "new"))
    else:
        # It's a local path
        return Path(path_or_url)


def calculate_diff(
    old_lockfile_path: Path, new_lockfile_path: Path
) -> tuple[list[PackageDiff], list[PackageDiff], list[PackageDiff]]:
    """
    Calculate the differences between two Pyodide lockfiles.

    Returns a tuple of three lists:
    - Added packages
    - Removed packages
    - Changed packages (with old and new versions)
    """
    old_lockfile = PyodideLockSpec.from_json(Path(old_lockfile_path))
    new_lockfile = PyodideLockSpec.from_json(Path(new_lockfile_path))

    old_packages = {
        pkg.name: pkg
        for pkg in old_lockfile.packages.values()
        if is_normal_python_package(pkg)
    }
    new_packages = {
        pkg.name: pkg
        for pkg in new_lockfile.packages.values()
        if is_normal_python_package(pkg)
    }

    added = [
        PackageDiff(name=pkg.name, old_version=None, new_version=pkg.version)
        for name, pkg in new_packages.items()
        if name not in old_packages
    ]

    removed = [
        PackageDiff(name=pkg.name, old_version=pkg.version, new_version=None)
        for name, pkg in old_packages.items()
        if name not in new_packages
    ]

    changed = [
        PackageDiff(
            name=name,
            old_version=old_packages[name].version,
            new_version=new_packages[name].version,
        )
        for name in set(old_packages) & set(new_packages)
        if old_packages[name].version != new_packages[name].version
    ]

    return added, removed, changed


def main():
    args = parse_args()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Get lockfile paths, downloading if necessary
        old_lockfile_path = get_lockfile_path(
            args.old_lockfile, is_old=True, temp_dir=temp_path
        )
        new_lockfile_path = get_lockfile_path(
            args.new_lockfile, is_old=False, temp_dir=temp_path
        )

        added, removed, changed = calculate_diff(old_lockfile_path, new_lockfile_path)

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
