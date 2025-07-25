from collections.abc import Iterator

from sphinx_js import ir
from sphinx_js.ir import Class, TypeXRefInternal
from sphinx_js.typedoc import Analyzer as TsAnalyzer

__all__ = ["ts_xref_formatter", "patch_sphinx_js"]


def patch_sphinx_js():
    TsAnalyzer._get_toplevel_objects = _get_toplevel_objects


def ts_xref_formatter(_config, xref):
    """Format cross references info sphinx roles"""
    from sphinx_pyodide.mdn_xrefs import JSDATA

    name = xref.name
    if name == "Lockfile":
        name = "~globalThis.Lockfile"
    if name == "TypedArray":
        name = "~pyodide.TypedArray"
    if name == "PyodideAPI":
        return ":ref:`PyodideAPI <js-api-pyodide>`"
    if name in JSDATA:
        return f":js:data:`{name}`"
    if name in FFI_FIELDS:
        return f":js:class:`~pyodide.ffi.{name}`"
    if name in ["ConcatArray", "IterableIterator", "unknown", "U"]:
        return f"``{name}``"
    if isinstance(xref, TypeXRefInternal):
        return f":js:{xref.kind}:`{name}`"
    return f":js:class:`{name}`"


# Custom tags are a great way of passing information from the source code to
# this file. No custom tags will be seen by this code unless they are registered
# in src/js/tsdoc.json
#
# Modifier tags act like a flag, block tags have content.


def has_tag(doclet, tag):
    """Detects whether the doclet comes from a node that has the given modifier
    tag.
    """
    return ("@" + tag) in doclet.modifier_tags


# We hide the PyXXXMethods from the documentation and add their children to the
# documented PyXXX class. We'll stick them here in ts_post_convert and read them
# out later
PYPROXY_METHODS = {}


# locate the ffi fields. We use this to redirect the documentation items to be
# documented under pyodide.ffi and to adjust the xrefs to point appropriately to
# `pyodide.ffi.xxx`
FFI_FIELDS: set[str] = set()


def _get_toplevel_objects(
    self: TsAnalyzer, ir_objects: list[ir.TopLevel]
) -> Iterator[tuple[ir.TopLevel, str | None, str | None]]:
    """Monkeypatch: yield object, module, kind for each triple we want to
    document.
    """
    FFI_FIELDS.update(self._extra_data["ffiFields"])
    from sphinx_js.ir import Attribute, Function, converter

    methodPairs = converter.structure(
        self._extra_data["pyproxyMethods"], list[tuple[str, list[Function | Attribute]]]
    )
    PYPROXY_METHODS.update(methodPairs)
    for obj in ir_objects:
        if obj.name == "PyodideAPI":
            for member in obj.members:
                member.documentation_root = True
            yield from _get_toplevel_objects(self, obj.members)
            continue
        if not obj.documentation_root:
            continue
        if doclet_is_private(obj):
            continue
        mod = get_obj_mod(obj)
        set_kind(obj)
        if obj.deppath == "./core/pyproxy" and isinstance(obj, Class):
            fix_pyproxy_class(obj)

        yield obj, mod, obj.kind


def doclet_is_private(doclet: ir.TopLevel) -> bool:
    """Should we render this object?"""
    if getattr(doclet, "is_private", False):
        return True
    key = doclet.path.segments
    key = [x for x in key if "/" not in x]
    filename = key[0]
    toplevelname = key[1]
    if key[-1].startswith("$"):
        return True
    if key[-1] == "constructor":
        # For whatever reason, sphinx-js does not properly record
        # whether constructors are private or not. For now, all
        # constructors are private so leave them all off. TODO: handle
        # this via a @private decorator in the documentation comment.
        return True

    if filename in ["module.", "compat."]:
        return True

    if filename == "pyproxy." and toplevelname.endswith("Methods"):
        # Don't document methods classes. We moved them to the
        # corresponding PyProxy subclass.
        return True
    return False


def get_obj_mod(doclet: ir.TopLevel) -> str:
    """Categorize objects by what section they should go into"""
    key = doclet.path.segments
    key = [x for x in key if "/" not in x]
    filename = key[0]
    doclet.name = doclet.name.rpartition(".")[2]

    if kind := doclet.block_tags.get("docgroup"):
        return kind[0][0].text

    if filename == "pyodide.":
        return "globalThis"

    if filename == "canvas.":
        return "pyodide.canvas"

    if doclet.name in FFI_FIELDS and not has_tag(doclet, "alias"):
        return "pyodide.ffi"
    doclet.is_static = False
    return "pyodide"


def set_kind(obj: ir.TopLevel) -> None:
    """If there is a @dockind tag, change obj.kind to reflect this"""
    k = obj.block_tags.get("dockind", [None])[0]
    if not k:
        return
    obj.kind = k[0].text.strip()


def fix_pyproxy_class(cls: ir.Class) -> None:
    """
    1. Filter supers to remove PyXxxMethods
    2. For each PyXxxMethods in supers, add PyXxxMethods.children to
       cls.children
    """
    methods_supers = [x for x in cls.supers if x[0].name in PYPROXY_METHODS]
    cls.supers = [x for x in cls.supers if x[0].name not in PYPROXY_METHODS]
    for x in methods_supers:
        cls.members.extend(PYPROXY_METHODS[x[0].name])
