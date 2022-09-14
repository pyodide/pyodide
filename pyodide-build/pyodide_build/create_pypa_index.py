from pathlib import Path
from textwrap import dedent
from typing import TypedDict


class PackageInfo(TypedDict):
    file_name: str
    sha256: str


def create_pypa_index(
    packages: dict[str, PackageInfo], target_dir: Path, dist_url: str
) -> None:
    """Create a pip-compatible Python package (pypa) index to be used with a Pyodide virtual
    environment.

    To use, pass as an `--index-url` or `--extra-index-url` parameter to pip.
    The argument should be a `file:` url pointing to the `pypa_index` folder (or
    if you serve `pypa_index` it can be a normal url). It is also used
    automatically by Pyodide virtual environments created from a release version
    of Pyodide.

    Parameters
    ----------
    packages:
        A dictionary of packages that we want to index. This should be the
        "packages" field from repodata.json.

    target_dir:
        Where to put the  index. It will be placed in a subfolder of
        target_dir called `pypa_index`. `target_dir` should exist but
        `target_dir/pypa_index` should not exist.

    dist_url:
        The CDN url to download packages from. This will be hard coded into the
        generated index. If you wish to install from local files, then prefix
        with `file:` e.g., `f"file:{pyodide_root}/dist"`.
    """
    # We only want to index the wheels
    packages = {
        pkgname: pkginfo
        for (pkgname, pkginfo) in packages.items()
        if pkginfo["file_name"].endswith(".whl")
    }
    if not target_dir.exists():
        raise RuntimeError(f"target_dir={target_dir} does not exist")

    index_dir = target_dir / "pypa_index"
    if index_dir.exists():
        raise RuntimeError(f"{index_dir} already exists")
    index_dir.mkdir()

    # Create top level index
    packages_str = "\n".join(f'<a href="{x}/">{x}</a>' for x in packages.keys())
    index_html = dedent(
        f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta name="pypi:repository-version" content="1.0">
        <title>Simple index</title>
        </head>
        <body>
        {packages_str}
        </body>
        </html>
        """
    ).strip()

    (index_dir / "index.html").write_text(index_html)

    files_template = dedent(
        """
        <!DOCTYPE html>
        <html>
        <head>
        <meta name="pypi:repository-version" content="1.0">
        <title>Links for {pkgname}</title>
        </head>
        <body>
        <h1>Links for {pkgname}</h1>
        {links}
        </body>
        </html>
        """
    ).strip()

    for pkgname, pkginfo in packages.items():
        pkgdir = index_dir / pkgname
        filename = pkginfo["file_name"]
        shasum = pkginfo["sha256"]
        href = f"{dist_url}{filename}#sha256={shasum}"
        links_str = f'<a href="{href}">{pkgname}</a>\n'
        files_html = files_template.format(pkgname=pkgname, links=links_str)

        pkgdir.mkdir()
        (pkgdir / "index.html").write_text(files_html)
