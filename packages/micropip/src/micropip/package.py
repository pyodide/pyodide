from collections.abc import Collection
from dataclasses import dataclass, field, astuple
from pathlib import Path
from typing import List, Dict, Iterable

__all__: List[str] = []


def _format_table(headers: List[str], table: List[Iterable]) -> str:
    def format_row(values, widths, filler=""):
        columns = " | ".join(f"{x:{filler}<{w}}" for x, w in zip(values, widths))
        return f"| {columns} |"

    col_width = [max(len(x) for x in col) for col in zip(headers, *table)]
    rows = []

    rows.append(format_row(headers, col_width))
    rows.append(format_row([""] * len(col_width), col_width, filler="-"))
    for line in table:
        rows.append(format_row(line, col_width))

    return "\n".join(rows)


@dataclass
class PackageMetadata:
    name: str
    version: str = ""
    source: str = ""

    def __iter__(self):
        return iter(astuple(self))

    @staticmethod
    def keys():
        return PackageMetadata.__dataclass_fields__.keys()


class PackageList(Collection):
    def __init__(self):
        self.packages: Dict[str, PackageMetadata] = {}

    def __repr__(self):
        return self._tabularize()

    def __len__(self):
        return len(self.packages)

    def __iter__(self):
        return iter(self.packages.values())

    def __contains__(self, pkg_name: str):  # type: ignore
        return pkg_name in self.package_names

    def __setitem__(self, key: str, item: PackageMetadata):
        self.packages[key] = item

    def __getitem__(self, key: str):
        return self.packages[key]

    @property
    def package_names(self):
        return [pkg.name for pkg in self]

    def update(self, pkg: Dict[str, PackageMetadata]):
        self.packages.update(pkg)

    def _tabularize(self):
        headers = PackageMetadata.keys()
        table = list(self.packages.values())
        return _format_table(headers, table)
