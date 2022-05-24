"""
Monkey patch autodoc to recursively include submodules as well. We have to
import the submodules for it to find them.
"""

from typing import Any

from sphinx.ext.autodoc import ModuleDocumenter, ObjectMember
from sphinx.util.inspect import safe_getattr

__all__ = ["monkeypatch_module_documenter"]


def get_module_members(module: Any) -> list[tuple[str, Any]]:
    members: dict[str, tuple[str, Any]] = {}
    for name in dir(module):
        try:
            value = safe_getattr(module, name, None)
            # Before patch this used to always do
            # members[name] = (name, value)
            # We want to also recursively look up names on submodules.
            if type(value).__name__ != "module":
                members[name] = (name, value)
                continue
            if name.startswith("_"):
                continue
            submodule = value  # Rename for clarity
            [base, _, rest] = submodule.__name__.partition(".")
            if not base == module.__name__:
                # Not part of package, don't document
                continue

            for (sub_name, sub_val) in get_module_members(submodule):
                # Skip names not in __all__
                if hasattr(submodule, "__all__") and sub_name not in submodule.__all__:
                    continue
                qual_name = rest + "." + sub_name
                members[qual_name] = (qual_name, sub_val)
            continue
        except AttributeError:
            continue

    return sorted(list(members.values()))


def get_object_members(
    self: ModuleDocumenter, want_all: bool
) -> tuple[bool, list[tuple[str, Any]] | list[ObjectMember]]:
    """
    For some reason I was unable to monkey patch get_module_members so we monkey
    patch get_object_members to call our updated `get_module_members`.

    This is similar to the original function but I dropped the `want_all` branch
    for brevity because we don't use it.
    """
    members = get_module_members(self.object)
    if not self.__all__:
        # for implicit module members, check __module__ to avoid
        # documenting imported objects
        return True, members
    else:
        ret = []
        for name, value in members:
            if name in self.__all__ or "." in name:
                ret.append(ObjectMember(name, value))
            else:
                ret.append(ObjectMember(name, value, skipped=True))

        return False, ret


def monkeypatch_module_documenter():
    ModuleDocumenter.get_object_members = get_object_members
