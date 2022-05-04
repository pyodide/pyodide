import re
from collections import UserDict
from dataclasses import astuple, dataclass
from typing import Iterable

__all__ = ["PackageDict"]


def _format_table(headers: list[str], table: list[Iterable]) -> str:
    """
    Returns a minimal formatted table

    >>> print(_format_table(["Header1", "Header2"], [["val1", "val2"], ["val3", "val4"]]))
    Header1 | Header2
    ------- | -------
    val1    | val2
    val3    | val4
    """

    def format_row(values, widths, filler=""):
        row = " | ".join(f"{x:{filler}<{w}}" for x, w in zip(values, widths))
        return row.rstrip()

    col_width = [max(len(x) for x in col) for col in zip(headers, *table)]
    rows = []

    rows.append(format_row(headers, col_width))
    rows.append(format_row([""] * len(col_width), col_width, filler="-"))
    for line in table:
        rows.append(format_row(line, col_width))

    return "\n".join(rows)


def normalize_package_name(pkgname: str):
    return re.sub(r"[^\w\d.]+", "_", pkgname, re.UNICODE).lower()


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


class PackageDict(UserDict):
    """
    A dictionary that holds list of metadata on packages.
    This class is used in micropip to keep the list of installed packages.
    """

    def __repr__(self):
        return self._tabularize()

    def __getitem__(self, key):
        normalized_key = normalize_package_name(key)
        return super().__getitem__(normalized_key)

    def __contains__(self, key):
        normalized_key = normalize_package_name(key)
        return super().__contains__(normalized_key)

    def _tabularize(self):
        headers = [key.capitalize() for key in PackageMetadata.keys()]
        table = list(self.values())
        return _format_table(headers, table)
