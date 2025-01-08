import json
import pathlib
import re
import subprocess
from typing import Any
from urllib.request import urlopen

from docutils import nodes
from docutils.parsers.rst import Directive
from pyodide_lock import PackageSpec, PyodideLockSpec
from sphinx import addnodes

base_dir = pathlib.Path(__file__).resolve().parents[3]


# FIXME: Change to parse package lists from pyodide-lock.json
def get_packages_summary_directive(app):
    class PyodidePackagesSummary(Directive):
        """A directive that dumps the full list of packages included in Pyodide in place."""

        required_arguments = 1

        def run(self):
            url = self.parse_lockfile_url()
            resp = urlopen(url)
            lockfile_json = resp.read().decode("utf-8")

            lockfile = PyodideLockSpec(**json.loads(lockfile_json))
            lockfile_packages = lockfile.packages

            python_packages = {}
            for package in lockfile_packages.values():
                try:
                    name, version, is_package = self.parse_package_info(package)
                except Exception:
                    print(f"Warning: failed to parse package config for {package}")

                if not is_package or name.endswith("-tests"):
                    continue

                python_packages[name] = {
                    "name": name,
                    "version": version,
                }

            result = []
            columns = ("name", "version")
            table_markup = self.format_packages_table(python_packages, columns)
            result.extend(table_markup)

            return result

        def parse_lockfile_url(self) -> str:
            envs = subprocess.run(
                ["make", "-f", str(base_dir / "Makefile.envs"), ".output_vars"],
                capture_output=True,
                text=True,
                env={"PYODIDE_ROOT": str(base_dir)},
                check=False,
            )

            if envs.returncode != 0:
                raise RuntimeError("Failed to parse Makefile.envs")

            pattern = re.search(r"PYODIDE_PREBUILT_PACKAGES_LOCKFILE=(.*)", envs.stdout)
            if not pattern:
                raise RuntimeError("Failed to find lockfile URL in Makefile.envs")

            url = pattern.group(1)
            return url

        def parse_package_info(
            self,
            package: PackageSpec,
        ) -> tuple[str, str, bool]:
            name = package.name
            version = package.version
            is_package = package.package_type == "package"

            return name, version, is_package

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
