import re
from collections import OrderedDict
from typing import Any

import docutils.parsers.rst.directives as directives
from docutils import nodes
from docutils.parsers.rst import Directive
from docutils.parsers.rst import Parser as RstParser
from docutils.statemachine import StringList
from docutils.utils import new_document
from sphinx import addnodes
from sphinx.domains.javascript import JavaScriptDomain, JSCallable
from sphinx.ext.autosummary import autosummary_table, extract_summary
from sphinx.util import rst
from sphinx.util.docutils import switch_source_input
from sphinx_js.ir import Class, Function, Interface, Pathname
from sphinx_js.parsers import PathVisitor, path_and_formal_params
from sphinx_js.renderers import (
    AutoAttributeRenderer,
    AutoClassRenderer,
    AutoFunctionRenderer,
    JsRenderer,
)
from sphinx_js.typedoc import Analyzer as TsAnalyzer
from sphinx_js.typedoc import make_path_segments

_orig_convert_node = TsAnalyzer._convert_node
_orig_constructor_and_members = TsAnalyzer._constructor_and_members
_orig_top_level_properties = TsAnalyzer._top_level_properties
_orig_convert_all_nodes = TsAnalyzer._convert_all_nodes


def _constructor_and_members(self, cls):
    result = _orig_constructor_and_members(self, cls)
    for tag in cls.get("comment", {}).get("tags", []):
        if tag["tag"] == "hideconstructor":
            return (None, result[1])
    return result


TsAnalyzer._constructor_and_members = _constructor_and_members

commentdict = {}

FFI_FIELDS: set[str] = set()


def _convert_all_nodes(self, root):
    for node in root.get("children", []):
        if node["name"] == "ffi":
            FFI_FIELDS.update(x["name"] for x in node["children"])
            FFI_FIELDS.remove("ffi")
            break
    return _orig_convert_all_nodes(self, root)


TsAnalyzer._convert_all_nodes = _convert_all_nodes


def _top_level_properties(self, node):
    if "comment" not in node:
        sig = {}
        if "getSignature" in node:
            sig = node["getSignature"][0]
        elif "signatures" in node:
            sig = node["signatures"][0]
        node["comment"] = sig.get("comment", {})
    path = str(Pathname(make_path_segments(node, self._base_dir)))
    commentdict[path] = node.get("comment") or {}
    result = _orig_top_level_properties(self, node)
    return result


def get_tag(doclet, tag):
    tags = commentdict[str(doclet.path)].get("tags", [])
    for t in tags:
        if t["tag"] == tag:
            return True, t["text"]
    return False, None


def has_tag(doclet, tag):
    return get_tag(doclet, tag)[0]


TsAnalyzer._top_level_properties = _top_level_properties

orig_JsRenderer_rst_ = JsRenderer.rst


def JsRenderer_rst(self, partial_path, obj, use_short_name=False):
    match get_tag(obj, "deprecated"):
        case (True, text):
            # This is definitely not unreachable...
            if not text.strip():  # type: ignore[unreachable]
                obj.deprecated = True
            else:
                obj.deprecated = text
    if has_tag(obj, "hidetype"):
        obj.type = ""
    return orig_JsRenderer_rst_(self, partial_path, obj, use_short_name)


for cls in [AutoAttributeRenderer, AutoFunctionRenderer, AutoClassRenderer]:
    cls.rst = JsRenderer_rst


def destructure_param(param: dict[str, Any]) -> list[dict[str, Any]]:
    """We want to document a destructured argument as if it were several
    separate arguments. This finds complex inline object types in the arguments
    list of a function and "destructures" them into separately documented arguments.

    E.g., a function

        /**
        * @param options
        */
        function f({x , y } : {
            /** The x value */
            x : number,
            /** The y value */
            y : string
        }){ ... }

    should be documented like:

        options.x (number) The x value
        options.y (number) The y value
    """
    decl = param["type"]["declaration"]
    result = []
    for child in decl["children"]:
        child = dict(child)
        if "type" not in child:
            if "signatures" in child:
                try:
                    child["comment"] = child["signatures"][0]["comment"]
                except KeyError:
                    # TODO: handle no comment case
                    pass
                child["type"] = {
                    "type": "reflection",
                    "declaration": dict(child),
                }
            else:
                raise AssertionError("Didn't expect to get here...")
        child["name"] = param["name"] + "." + child["name"]
        result.append(child)
    return result


def fix_up_inline_object_signature(self: TsAnalyzer, node: dict[str, Any]) -> None:
    """Calls get_destructured_children on inline object types"""
    kind = node.get("kindString")
    if kind not in ["Call signature", "Constructor signature"]:
        return
    params = node.get("parameters", [])
    new_params = []
    for param in params:
        if "@ignore" in param.get("comment", {}).get("shortText", ""):
            if not param.get("flags", {}).get("isOptional"):
                print("sphinx-pyodide warning: Hiding mandatory argument!")
            continue
        param_type = param["type"]
        if (
            param_type["type"] != "reflection"
            or "children" not in param_type["declaration"]
        ):
            new_params.append(param)
        else:
            new_params.extend(destructure_param(param))
    node["parameters"] = new_params


def _convert_node(self: TsAnalyzer, node: dict[str, Any]) -> Any:
    """Monkey patch for TsAnalyzer._convert_node.

    Fixes two crashes and separates documentation for destructured object
    arguments into a series of separate argument entries.
    """
    kind = node.get("kindString")
    # if a class has no documented constructor, don't crash
    if kind in ["Function", "Constructor", "Method"] and not node.get("sources"):
        return None, []
    # This fixes a crash, not really sure what it means.
    node["extendedTypes"] = [t for t in node.get("extendedTypes", []) if "id" in t]
    # See docstring for destructure_param
    fix_up_inline_object_signature(self, node)
    converted, more_todo = _orig_convert_node(self, node)
    if not converted:
        return converted, more_todo
    converted.is_private = node.get("flags", {}).get("isPrivate", False)
    if kind in ["Call signature", "Constructor signature"]:
        tags = node.get("comment", {}).get("tags", [])
        converted.examples = [tag["text"] for tag in tags if tag["tag"] == "example"]
    return converted, more_todo


TsAnalyzer._convert_node = _convert_node

from os.path import relpath


def _containing_deppath(self, node):
    """Return the path pointing to the module containing the given node.
    The path is absolute or relative to `root_for_relative_js_paths`.
    Raises ValueError if one isn't found.

    """
    from pathlib import Path

    filename = node["sources"][0]["fileName"].replace(".gen", "")
    deppath = next(Path(self._base_dir).glob("**/" + filename), None)
    if deppath:
        return relpath(deppath, self._base_dir)
    return ""


TsAnalyzer._containing_deppath = _containing_deppath


def _add_type_role(self, name):
    from sphinx_pyodide.mdn_xrefs import JSDATA

    if name in JSDATA:
        return f":js:data:`{name}`"
    if name in FFI_FIELDS:
        return f":js:class:`~pyodide.ffi.{name}`"
    return f":js:class:`{name}`"


def object_literal_type_name(self, decl):
    """This renders the names of object literal types.

    They have zero or more "children" and zero or one "indexSignatures".
    For example:

        {
            [key: string]: string,
            name : string,
            id : string
        }

    has children "name" and "id" and an indexSignature "[key: string]: string"
    """
    children = []
    if "indexSignature" in decl:
        index_sig = decl["indexSignature"]
        assert len(index_sig["parameters"]) == 1
        key = index_sig["parameters"][0]
        keyname = key["name"]
        keytype = self._type_name(key["type"])
        valuetype = self._type_name(index_sig["type"])
        children.append(rf"\ **[{keyname}:** {keytype}\ **]:** {valuetype}")
    if "children" in decl:
        for child in decl["children"]:
            maybe_optional = ""
            if child["flags"].get("isOptional"):
                maybe_optional = "?"
            if child["kindString"] == "Method":
                child_type_name = self.function_type_name(child)
            else:
                child_type_name = self._type_name(child["type"])
            children.append(
                r"\ **" + child["name"] + maybe_optional + ":** " + child_type_name
            )

    return r"\ **{**\ " + r"\ **,** ".join(children) + r"\ **}**\ "


def function_type_name(self, decl):
    decl_sig = None
    if "signatures" in decl:
        decl_sig = decl["signatures"][0]
    elif decl["kindString"] == "Call signature":
        decl_sig = decl
    assert decl_sig
    params = [
        rf'\ **{ty["name"]}:** {self._type_name(ty["type"])}'
        for ty in decl_sig.get("parameters", [])
    ]
    params_str = r"\ **,** ".join(params)
    ret_str = self._type_name(decl_sig["type"])
    return rf"\ **(**\ {params_str}\ **) =>** {ret_str}"


def reflection_type_name(self, type):
    """Fill in the type names for type_of_type == "reflection"

    This is left as a TODO in sphinx-js.

    There are a couple of options: if

        decl["kindString"] == "Type Literal"

    then this is a literal object type. At least we assume it's a literal object
    type, maybe there are other ways for that to happen.

    Otherwise, we assume that it's a function type, which we want to format
    like:

        (a : string, b : number) => string
    """
    decl = type["declaration"]
    if decl["kindString"] == "Type literal" and "signatures" not in decl:
        return self.object_literal_type_name(decl)
    return self.function_type_name(decl)


def _type_name_root(self, type):
    type_of_type = type.get("type")

    if type_of_type == "reference" and type.get("id"):
        node = self._index[type["id"]]
        name = node["name"]
        if node.get("flags", {}).get("isPrivate") and "type" in node:
            return self._type_name(node["type"])
        return self._add_type_role(name)
    if type_of_type == "unknown":
        if re.match(r"-?\d*(\.\d+)?", type["name"]):  # It's a number.
            # TypeDoc apparently sticks numeric constants' values into
            # the type name. String constants? Nope. Function ones? Nope.
            return "number"
        return self._add_type_role(type["name"])
    if type_of_type in ["intrinsic", "reference"]:
        return self._add_type_role(type["name"])
    if type_of_type == "stringLiteral":
        return '"' + type["value"] + '"'
    if type_of_type == "array":
        return self._type_name(type["elementType"]) + r"\ **[]**"
    if type_of_type == "tuple" and type.get("elements"):
        types = [self._type_name(t) for t in type["elements"]]
        return r"\ **[**\ " + r"\ **,** ".join(types) + r"\ **]** "
    if type_of_type == "union":
        return r" **|** ".join(self._type_name(t) for t in type["types"])
    if type_of_type == "intersection":
        return " **&** ".join(self._type_name(t) for t in type["types"])
    if type_of_type == "typeOperator":
        return type["operator"] + " " + self._type_name(type["target"])
        # e.g. "keyof T"
    if type_of_type == "typeParameter":
        name = type["name"]
        constraint = type.get("constraint")
        if constraint is not None:
            name += " extends " + self._type_name(constraint)
            # e.g. K += extends + keyof T
        return name
    if type_of_type == "reflection":
        return self.reflection_type_name(type)
    if type_of_type == "named-tuple-member":
        name = type["name"]
        type = self._type_name(type["element"])
        return rf"\ **{name}:** {type}"
    if type_of_type == "predicate":
        return (
            f":js:data:`boolean` (typeguard for {self._type_name(type['targetType'])})"
        )
    if type_of_type == "literal" and type["value"] is None:
        return ":js:data:`null`"
    if type_of_type == "query":
        return f"``typeof {type['queryType']['name']}``"
    return "<TODO: other type>"


def _type_name(self, type):
    """Return a string description of a type.

    :arg type: A TypeDoc-emitted type node

    """
    name = self._type_name_root(type)

    type_args = type.get("typeArguments")
    if type_args:
        arg_names = ", ".join(self._type_name(arg) for arg in type_args)
        name += rf"\ **<**\ {arg_names}\ **>** "
    return name


for obj in [
    _add_type_role,
    object_literal_type_name,
    reflection_type_name,
    _type_name_root,
    _type_name,
    function_type_name,
]:
    setattr(TsAnalyzer, obj.__name__, obj)


def _param_type_formatter(param):
    """Generate types for function parameters specified in field."""
    if not param.type:
        return None
    heads = ["type", param.name]
    tail = param.type
    return heads, tail


def _return_formatter(return_):
    """Derive heads and tail from ``@returns`` blocks."""
    tail = ("%s -- " % return_.type) if return_.type else ""
    tail += return_.description
    return ["returns"], tail


import sphinx_js.renderers

for obj in [_param_type_formatter, _return_formatter]:  # type:ignore[assignment]
    setattr(sphinx_js.renderers, obj.__name__, obj)


class JSFuncMaybeAsync(JSCallable):
    option_spec = {
        **JSCallable.option_spec,
        "async": directives.flag,
    }

    def get_display_prefix(
        self,
    ):
        if "async" in self.options:
            return [
                addnodes.desc_sig_keyword("async", "async"),
                addnodes.desc_sig_space(),
            ]
        return []


JavaScriptDomain.directives["function"] = JSFuncMaybeAsync


def flatten_suffix_tree(tree):
    """Flatten suffix tree into a dictionary.

    self._doclets_by_class already has stuff in the correct layout but it
    does not contain top level file attributes. They are contained in the
    suffix tree, but the suffix tree is inconveniently shaped. So we flatten
    it...
    """
    result: dict[tuple[str, ...], Any] = {}
    path: list[str] = []
    iters: list[Any] = []
    cur_iter = iter(tree.get("subtree", {}).items())
    while True:
        try:
            [key, val] = next(cur_iter)
        except StopIteration:
            if not iters:
                return result
            cur_iter = iters.pop()
            path.pop()
            continue
        if "subtree" in val:
            iters.append(cur_iter)
            path.append(key)
            cur_iter = iter(val["subtree"].items())
        if "value" in val:
            path.append(key)
            result[tuple(reversed(path))] = val["value"]
            path.pop()


class PyodideAnalyzer:
    """JsDoc automatically instantiates the JsAnalyzer. Rather than subclassing
    or monkey patching it, we use composition (see getattr impl).

    The main extra thing we do is reorganize the doclets based on our globals /
    functions / attributes scheme. This we use to subdivide the sections in our
    summary. We store these in the "js_docs" field which is the only field that
    we access later.
    """

    def __init__(self, analyzer: TsAnalyzer) -> None:
        self.inner = analyzer
        self.create_js_doclets()

    def __getattr__(self, key):
        return getattr(self.inner, key)

    def longname_to_path(self, name):
        """Convert the longname field produced by jsdoc to a path appropriate to use
        with _sphinxjs_analyzer.get_object. Based on:
        https://github.com/mozilla/sphinx-js/blob/3.1/sphinx_js/jsdoc.py#L181
        """
        return PathVisitor().visit(path_and_formal_params["path"].parse(name))

    def set_doclet_is_private(self, key, doclet):
        if getattr(doclet, "is_private", False):
            return
        doclet.is_private = False

        key = [x for x in key if "/" not in x]
        filename = key[0]
        toplevelname = key[1]
        if key[-1].startswith("$"):
            doclet.is_private = True
            return
        if key[-1] == "constructor":
            # For whatever reason, sphinx-js does not properly record
            # whether constructors are private or not. For now, all
            # constructors are private so leave them all off. TODO: handle
            # this via a @private decorator in the documentation comment.
            doclet.is_private = True
            return

        if filename in ["module.", "compat."]:
            doclet.is_private = True
            return

        if filename == "pyproxy.gen." and toplevelname.endswith("Methods"):
            # Don't document methods classes. We moved them to the
            # corresponding PyProxy subclass.
            doclet.is_private = True
            return

    def create_js_doclets(self):
        """Search through the doclets generated by JsDoc and categorize them by
        summary section. Skip docs labeled as "@private".
        """
        self.doclets = flatten_suffix_tree(self._objects_by_path._tree)

        def get_val():
            return OrderedDict([("attribute", []), ("function", []), ("class", [])])

        modules = ["globalThis", "pyodide", "pyodide.ffi", "pyodide.canvas"]
        self.js_docs = {key: get_val() for key in modules}
        items = {key: list[Any]() for key in modules}
        pyproxy_subclasses = []
        pyproxy_methods: dict[str, list[Any]] = {}

        for key, doclet in self.doclets.items():
            self.set_doclet_is_private(key, doclet)

        for key, doclet in self.doclets.items():
            if doclet.is_private:
                continue

            filename = key[0]
            toplevelname = key[1]
            doclet.name = doclet.name.rpartition(".")[2]
            if doclet.name.startswith("["):
                # a symbol.
                # \u2024 looks like a period but is not a period.
                # This isn't ideal, but otherwise the coloring is weird.
                doclet.name = "[Symbol\u2024" + doclet.name[1:]

            if filename == "pyodide.":
                items["globalThis"].append(doclet)
                continue

            if filename == "pyproxy.gen." and toplevelname.endswith("Methods#"):
                l = pyproxy_methods.setdefault(toplevelname.removesuffix("#"), [])
                l.append(doclet)
                continue

            if toplevelname.endswith("#"):
                # This is a class method. If it's not part of a PyProxyXMethods
                # class (which we already dealt with), the method will be
                # documented as part of the class.
                #
                # This doesn't filter static methods! Currently this actually
                # ends up working out on our favor. If we did want to filter
                # them, we could probably test for:
                # isinstance(doclet, Function) and doclet.is_static.
                continue

            if filename == "canvas.":
                items["pyodide.canvas"].append(doclet)
                continue

            if filename == "pyproxy.gen." and isinstance(doclet, Class):
                pyproxy_subclasses.append(doclet)

            if doclet.name in FFI_FIELDS and not has_tag(doclet, "alias"):
                items["pyodide.ffi"].append(doclet)
            else:
                doclet.is_static = False
                items["pyodide"].append(doclet)

        for cls in pyproxy_subclasses:
            methods_supers = [
                x for x in cls.supers if x.segments[-1] in pyproxy_methods
            ]
            cls.supers = [
                x for x in cls.supers if x.segments[-1] not in pyproxy_methods
            ]
            for x in cls.supers:
                x.segments = [x.segments[-1]]
            for x in methods_supers:
                cls.members.extend(pyproxy_methods[x.segments[-1]])

        from operator import attrgetter

        for key, value in items.items():
            for obj in sorted(value, key=attrgetter("name")):
                _, kind = get_tag(obj, "doc_kind")
                if kind:
                    obj.kind = kind
                elif isinstance(obj, Class):
                    obj.kind = "class"
                elif isinstance(obj, Function):
                    obj.kind = "function"
                else:
                    obj.kind = "attribute"

                obj.async_ = False
                if isinstance(obj, Function):
                    obj.async_ = obj.returns and obj.returns[0].type.startswith(
                        ":js:class:`Promise`"
                    )
                self.js_docs[key][obj.kind].append(obj)


def get_jsdoc_content_directive(app):
    """These directives need to close over app"""

    class JsDocContent(Directive):
        """A directive that just dumps a summary table in place. There are no
        options, it only prints the one thing, we control the behavior from
        here
        """

        required_arguments = 1

        def get_rst(self, obj):
            """Grab the appropriate renderer and render us to rst."""
            if isinstance(obj, Function):
                cls = AutoFunctionRenderer
            elif isinstance(obj, Class):
                cls = AutoClassRenderer
            elif isinstance(obj, Interface):
                cls = AutoClassRenderer
            else:
                cls = AutoAttributeRenderer
            renderer = cls(self, app, arguments=["dummy"], options={"members": ["*"]})
            rst = renderer.rst([obj.name], obj, use_short_name=False)
            if obj.async_:
                rst = self.add_async_option_to_rst(rst)
            return rst

        def add_async_option_to_rst(self, rst: str) -> str:
            rst_lines = rst.split("\n")
            try:
                index = next(i for i, ln in enumerate(rst_lines) if ln.startswith(".."))
            except StopIteration:
                index = len(rst_lines) - 1
            rst_lines.insert(index + 1, "   :async:")
            return "\n".join(rst_lines)

        def get_rst_for_group(self, objects):
            return [self.get_rst(obj) for obj in objects]

        def parse_rst(self, rst):
            """We produce a bunch of rst but directives are supposed to output
            docutils trees. This is a helper that converts the rst to docutils.
            """
            settings = self.state.document.settings
            doc = new_document("", settings)
            RstParser().parse(rst, doc)
            return doc.children

        def run(self):
            module = self.arguments[0]
            values = app._sphinxjs_analyzer.js_docs[module]
            rst = []
            if module != "PyProxy":
                rst.append([f".. js:module:: {module}"])
            for group in values.values():
                rst.append(self.get_rst_for_group(group))
            joined_rst = "\n\n".join(["\n\n".join(r) for r in rst])
            return self.parse_rst(joined_rst)

    return JsDocContent


def get_jsdoc_summary_directive(app):
    class JsDocSummary(Directive):
        """A directive that just dumps the Js API docs in place. There are no
        options, it only prints the one thing, we control the behavior from
        here
        """

        required_arguments = 1

        def run(self):
            result = []
            module = self.arguments[0]
            value = app._sphinxjs_analyzer.js_docs[module]
            for group_name, group_objects in value.items():
                if not group_objects:
                    continue
                if group_name == "class":
                    # Plural of class is "classes" not "classs"
                    group_name += "e"
                result.append(self.format_heading(group_name.title() + "s:"))
                table_items = self.get_summary_table(module, group_objects)
                table_markup = self.format_table(table_items)
                result.extend(table_markup)
            return result

        def format_heading(self, text):
            """Make a section heading. This corresponds to the rst: "**Heading:**"
            autodocsumm uses headings like that, so this will match that style.
            """
            heading = nodes.paragraph("")
            strong = nodes.strong("")
            strong.append(nodes.Text(text))
            heading.append(strong)
            return heading

        def extract_summary(self, descr):
            """Wrapper around autosummary extract_summary that is easier to use.
            It seems like colons need escaping for some reason.
            """
            colon_esc = "esccolon\\\xafhoa:"
            # extract_summary seems to have trouble if there are Sphinx
            # directives in descr
            descr, _, _ = descr.partition("\n..")
            return extract_summary(
                [descr.replace(":", colon_esc)], self.state.document
            ).replace(colon_esc, ":")

        def get_sig(self, obj):
            """If the object is a function, get its signature (as figured by JsDoc)"""
            if isinstance(obj, Function):
                return AutoFunctionRenderer(
                    self, app, arguments=["dummy"]
                )._formal_params(obj)
            else:
                return ""

        def get_summary_row(self, pkgname, obj):
            """Get the summary table row for obj.

            The output is designed to be input to format_table. The link name
            needs to be set up so that :any:`link_name` makes a link to the
            actual API docs for this object.
            """
            sig = self.get_sig(obj)
            display_name = obj.name
            prefix = "**async** " if obj.async_ else ""
            summary = self.extract_summary(obj.description)
            link_name = pkgname + "." + display_name
            return (prefix, display_name, sig, summary, link_name)

        def get_summary_table(self, pkgname, group):
            """Get the data for a summary tget_summary_tableable. Return value
            is set up to be an argument of format_table.
            """
            return [self.get_summary_row(pkgname, obj) for obj in group]

        # This following method is copied almost verbatim from autosummary
        # (where it is called get_table).
        #
        # We have to change the value of one string: qualifier = 'obj   ==>
        # qualifier = 'any'
        # https://github.com/sphinx-doc/sphinx/blob/6.0.x/sphinx/ext/autosummary/__init__.py#L375
        def format_table(self, items):
            """Generate a proper list of table nodes for autosummary:: directive.

            *items* is a list produced by :meth:`get_items`.
            """
            table_spec = addnodes.tabular_col_spec()
            table_spec["spec"] = r"\X{1}{2}\X{1}{2}"

            table = autosummary_table("")
            real_table = nodes.table("", classes=["longtable"])
            table.append(real_table)
            group = nodes.tgroup("", cols=2)
            real_table.append(group)
            group.append(nodes.colspec("", colwidth=10))
            group.append(nodes.colspec("", colwidth=90))
            body = nodes.tbody("")
            group.append(body)

            def append_row(*column_texts: str) -> None:
                row = nodes.row("")
                source, line = self.state_machine.get_source_and_line()
                for text in column_texts:
                    node = nodes.paragraph("")
                    vl = StringList()
                    vl.append(text, "%s:%d:<autosummary>" % (source, line))
                    with switch_source_input(self.state, vl):
                        self.state.nested_parse(vl, 0, node)
                        try:
                            if isinstance(node[0], nodes.paragraph):
                                node = node[0]
                        except IndexError:
                            pass
                        row.append(nodes.entry("", node))
                body.append(row)

            for prefix, name, sig, summary, real_name in items:
                # The body of this loop is changed from copied code.
                qualifier = "any"
                sig = rst.escape(sig)
                if sig:
                    sig = f"**{sig}**"
                if "nosignatures" not in self.options:
                    col1 = f"{prefix}:{qualifier}:`{name} <{real_name}>`\\ {sig}"
                else:
                    col1 = f"{prefix}:{qualifier}:`{name} <{real_name}>`"
                col2 = summary
                append_row(col1, col2)

            return [table_spec, table]

    from inspect import iscoroutinefunction

    from sphinx.ext.autosummary import Autosummary, get_import_prefixes_from_env

    # Monkey patch Autosummary to:
    # 1. include "async" prefix in the summary table for async functions.
    # 2. Render signature in bold (for better consistency with rest of docs)
    Autosummary.get_table = JsDocSummary.format_table
    orig_get_items = Autosummary.get_items

    def get_items(self, names):
        prefixes = get_import_prefixes_from_env(self.env)
        items = orig_get_items(self, names)
        new_items = []
        for name, item in zip(names, items, strict=True):
            name = name.removeprefix("~")
            _, obj, *_ = self.import_by_name(name, prefixes=prefixes)
            prefix = "**async** " if iscoroutinefunction(obj) else ""
            new_items.append((prefix, *item))
        return new_items

    Autosummary.get_items = get_items

    return JsDocSummary
