from collections import UserDict
from dataclasses import dataclass, field, astuple
from pathlib import Path
from typing import List, Dict, Iterable

__all__ = ["PackageDict"]


def _format_table(headers: List[str], table: List[Iterable]) -> str:
    def format_row(values, widths, filler=""):
        row = " | ".join(f"{x:{filler}<{w}}" for x, w in zip(values, widths))
        return row

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


class PackageDict(UserDict):
    
    def __repr__(self):
        return self._tabularize()

    def _tabularize(self):
        headers = [key.capitalize() for key in PackageMetadata.keys()]
        table = list(self.values())
        return _format_table(headers, table)
