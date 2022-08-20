import argparse
from pathlib import Path
from textwrap import dedent

from packaging.utils import parse_wheel_filename


def make_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.description = (
        "Create simple index of dist packages.\n\n" "Note: this is a private endpoint."
    )
    return parser


def create_index(dist_dir):
    g = dist_dir.glob("*.whl")
    m: dict[str, list[Path]] = {}
    for p in g:
        file_name = p.name
        wheel_name = parse_wheel_filename(file_name)[0]
        m[wheel_name] = m.get(wheel_name, [])
        m[wheel_name].append(p)

    index_dir = dist_dir / "pypi_index"
    index_dir.mkdir()

    packages_str = "\n".join(f'<a href="/pypi_index/{x}/">{x}</a>' for x in m.keys())
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

    for k, v in m.items():
        pkgdir = index_dir / k
        pkgdir.mkdir()
        links_str = "\n".join(
            f'<a href="/{x.relative_to(Path.cwd())}">{x.name}</a>' for x in v
        )
        files_html = files_template.format(pkgname=k, links=links_str)
        (pkgdir / "index.html").write_text(files_html)
