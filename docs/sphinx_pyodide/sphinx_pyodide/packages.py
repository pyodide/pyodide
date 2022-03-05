import pathlib
import sys
from typing import Any

from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx import addnodes

base_dir = pathlib.Path(__file__).resolve().parents[3]
sys.path.append(str(base_dir / "pyodide-build"))

from pyodide_build.io import parse_package_config


def get_packages_summary_directive(app):
    class PyodidePackagesSummary(Directive):
        """A directive that dumps the full list of packages included in Pyodide in place."""

        required_arguments = 1

        def run(self):
            packages_root = base_dir / self.arguments[0]
            packages_list = self.get_package_metadata_list(packages_root)

            packages = {}
            for package in packages_list:
                name, version, is_library = self.parse_package_info(package)

                # skip libraries (e.g. libxml, libyaml, ...)
                if is_library:
                    continue

                packages[name] = {
                    "name": name,
                    "version": version,
                }

            result = []
            columns = ("name", "version")
            table_markup = self.format_packages_table(packages, columns)
            result.extend(table_markup)

            return result

        def parse_package_info(self, config: pathlib.Path) -> tuple[str, str, bool]:
            yaml_data = parse_package_config(config)

            name = yaml_data["package"]["name"]
            version = yaml_data["package"]["version"]
            is_library = yaml_data.get("build", {}).get("library", False)

            return name, version, is_library

        def get_package_metadata_list(
            self, directory: pathlib.Path
        ) -> list[pathlib.Path]:
            """Return metadata files of packages in alphabetical order (case insensitive)"""
            return sorted(
                directory.glob("**/meta.yaml"),
                key=lambda path: path.parent.name.lower(),
            )

        def format_packages_table(
            self, packages: dict[str, Any], columns: tuple[str, ...]
        ) -> list[Any]:
            table_spec = addnodes.tabular_col_spec()
            table_spec["spec"] = r"\X{1}{2}\X{1}{2}"

            table = nodes.table("", classes=["longtable"])

            group = nodes.tgroup("", cols=len(columns))
            group.extend([nodes.colspec("", colwidth=100) for _ in columns])
            table.append(group)

            thead = nodes.thead()
            row = nodes.row()
            for column in columns:
                entry = nodes.entry()
                entry += nodes.paragraph(text=column.capitalize())
                row += entry

            thead.append(row)
            group += thead

            rows = []
            for pkg_info in packages.values():
                row = nodes.row()
                rows.append(row)
                for column in columns:
                    value = pkg_info[column]
                    entry = nodes.entry()
                    entry += nodes.paragraph(text=value)
                    row += entry

            tbody = nodes.tbody()
            tbody.extend(rows)
            group += tbody

            return [table_spec, table]

    return PyodidePackagesSummary
