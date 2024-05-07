from collections.abc import Iterator

from sphinx_js import ir, typedoc
from sphinx_js.ir import Class
from sphinx_js.typedoc import Analyzer as TsAnalyzer
from sphinx_js.typedoc import Base, Callable, Converter, Interface, ReflectionType

# Custom tags are a great way of conveniently passing information from the
# source code to this file. No custom tags will be seen by this code unless they
# are registered in src/js/tsdoc.json
#
# Modifier tags act like a flag, block tags have content.


def patch_sphinx_js():
    Base.member_properties = member_properties
    Converter.convert_all_nodes = convert_all_nodes
    TsAnalyzer._get_toplevel_objects = _get_toplevel_objects
    Interface.to_ir = Interface_to_ir


def ts_should_destructure_arg(sig, param):
    """Destructure all parameters named 'options'"""
    return param.name == "options"


def ts_xref_formatter(_config, xref):
    """Format cross references info sphinx roles"""
    from sphinx_pyodide.mdn_xrefs import JSDATA

    name = xref.name
    if name == "PyodideInterface":
        return ":ref:`PyodideInterface <js-api-pyodide>`"
    if name in JSDATA:
        return f":js:data:`{name}`"
    if name in FFI_FIELDS:
        return f":js:class:`~pyodide.ffi.{name}`"
    if name in ["ConcatArray", "IterableIterator", "unknown", "U"]:
        return f"``{name}``"
    return f":js:class:`{name}`"


def member_properties(self):
    """Monkey patch for node.member_properties that hides all external nodes by
    marking them as private."""
    return dict(
        is_abstract=self.flags.isAbstract,
        is_optional=self.flags.isOptional,
        is_static=self.flags.isStatic,
        is_private=self.flags.isPrivate or self.flags.isExternal,
    )


def has_tag(doclet, tag):
    """Detects whether the doclet comes from a node that has the given modifier
    tag.
    """
    return ("@" + tag) in doclet.modifier_tags


# We hide the PyXXXMethods from the documentation and add their children to the
# documented PyXXX class. We'll stick them here in ts_post_convert and read them
# out later
PYPROXY_METHODS = {}


def ts_post_convert(converter, node, doclet):
    # hide exported_from
    doclet.exported_from = None

    if has_tag(doclet, "hidetype"):
        doclet.type = ""
        if isinstance(node, typedoc.Callable):
            node.signatures[0].type = ""

    if isinstance(doclet, ir.Class) and has_tag(doclet, "hideconstructor"):
        doclet.constructor = None

    if node.name == "setStdin":
        fix_set_stdin(converter, node, doclet)

    if node.name == "mountNativeFS":
        fix_native_fs(converter, node, doclet)

    if doclet.deppath == "./core/pyproxy" and doclet.path.segments[-1].endswith(
        "Methods"
    ):
        PYPROXY_METHODS[doclet.name] = doclet.members


def fix_set_stdin(converter, node, doclet):
    """The type of stdin is given as StdinFunc which is opaque. Replace it with
    the definition of StdinFunc.

    TODO: Find a better way!
    """
    assert isinstance(node, Callable)
    options = node.signatures[0].parameters[0]
    assert isinstance(options.type, ReflectionType)
    for param in options.type.declaration.children:
        if param.name == "stdin":
            break
    else:
        raise RuntimeError("Stdin param not found")
    target = converter.index[param.type.target]
    for docparam in doclet.params:
        if docparam.name == "options.stdin":
            break
    else:
        raise RuntimeError("Stdin param not found")
    docparam.type = target.type.render_name(converter)


NATIVE_FS_DOCLET = None


def fix_native_fs(converter, node, doclet):
    """mountNativeFS has NativeFS as it's return type. This is a bit opaque, so
    we resolve the reference to the reference target which is
    Promise<{ syncfs: () => Promise<void>; }>

    TODO: find a better way.
    """
    assert isinstance(node, Callable)
    ty = node.signatures[0].type
    if not ty.typeArguments[0].type == "reference":
        return
    target = converter.index[ty.typeArguments[0].target]
    ty.typeArguments[0] = target.type
    return_type = ty.render_name(converter)
    doclet.returns[0].type = return_type


# locate the ffi fields. We use this to redirect the documentation items to be
# documented under pyodide.ffi and to adjust the xrefs to point appropriately to
# `pyodide.ffi.xxx`
FFI_FIELDS: set[str] = set()

orig_convert_all_nodes = Converter.convert_all_nodes


def convert_all_nodes(self, root):
    children = children_dict(root)
    locate_ffi_fields(children["js/ffi"])
    return orig_convert_all_nodes(self, root)


def children_dict(root):
    return {node.name: node for node in root.children}


def locate_ffi_fields(ffi_module):
    for child in ffi_module.children:
        if child.name == "ffi":
            break
    fields = child.type.declaration.children
    FFI_FIELDS.update(x.name for x in fields)


def _get_toplevel_objects(
    self: TsAnalyzer, ir_objects: list[ir.TopLevel]
) -> Iterator[tuple[ir.TopLevel, str | None, str | None]]:
    """Monkeypatch: yield object, module, kind for each triple we want to
    document.
    """
    for obj in ir_objects:
        if obj.name == "PyodideAPI":
            yield from _get_toplevel_objects(self, obj.members)
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

    if filename in ["module.", "compat.", "types."]:
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
    kind = k[0].text.strip()
    if kind == "class":
        kind += "es"
    else:
        kind += "s"
    obj.kind = kind


def fix_pyproxy_class(cls: ir.Class) -> None:
    """
    1. Filter supers to remove PyXxxMethods
    2. For each PyXxxMethods in supers, add PyXxxMethods.children to
       cls.children
    """
    methods_supers = [x for x in cls.supers if x.segments[-1] in PYPROXY_METHODS]
    cls.supers = [x for x in cls.supers if x.segments[-1] not in PYPROXY_METHODS]
    for x in cls.supers:
        x.segments = [x.segments[-1]]
    for x in methods_supers:
        cls.members.extend(PYPROXY_METHODS[x.segments[-1]])


orig_Interface_to_ir = Interface.to_ir

# sphinx_js incorrectly handles is_private for classes and interfaces.
# TODO: fix sphinx_js


def Interface_to_ir(self, converter):
    orig = orig_Interface_to_ir(self, converter)
    orig[0].is_private = self.flags.isPrivate
    return orig
