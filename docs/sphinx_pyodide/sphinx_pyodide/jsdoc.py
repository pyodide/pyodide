from collections import OrderedDict
from typing import Any

from docutils import nodes
from docutils.parsers.rst import Directive
from docutils.parsers.rst import Parser as RstParser
from docutils.statemachine import StringList
from docutils.utils import new_document
from sphinx import addnodes
from sphinx.ext.autosummary import autosummary_table, extract_summary
from sphinx.util import rst
from sphinx.util.docutils import switch_source_input
from sphinx_js import ir, typedoc
from sphinx_js.ir import Class, Function, Interface
from sphinx_js.renderers import (
    AutoAttributeRenderer,
    AutoClassRenderer,
    AutoFunctionRenderer,
    JsRenderer,
)
from sphinx_js.typedoc import Analyzer as TsAnalyzer
from sphinx_js.typedoc import Base, Callable, Converter, ReflectionType

# Custom tags are a great way of conveniently passing information from the
# source code to this file. No custom tags will be seen by this code unless they
# are registered in src/js/tsdoc.json
#
# Modifier tags act like a flag, block tags have content.


def has_tag(doclet, tag):
    """Detects whether the doclet comes from a node that has the given modifier
    tag.
    """
    return ("@" + tag) in doclet.modifier_tags


def member_properties(self):
    return dict(
        is_abstract=self.flags.isAbstract,
        is_optional=self.flags.isOptional,
        is_static=self.flags.isStatic,
        is_private=self.flags.isPrivate or self.flags.isExternal,
    )


Base.member_properties = member_properties


def ts_should_destructure_arg(sig, param):
    return param.name == "options"


def ts_post_convert(converter, node, doclet):
    doclet.exported_from = None
    doclet.name = doclet.name.replace("Symbol․Symbol․", "Symbol․")

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


def fix_set_stdin(converter, node, doclet):
    assert isinstance(node, Callable)
    options = node.signatures[0].parameters[0]
    assert isinstance(options.type, ReflectionType)
    for param in options.type.declaration.children:
        if param.name == "stdin":
            break
    target = converter.index[param.type.target]
    for docparam in doclet.params:
        if docparam.name == "stdin":
            break
    docparam.type = target.type.render_name(converter)


def fix_native_fs(converter, node, doclet):
    assert isinstance(node, Callable)
    ty = node.signatures[0].type
    target = converter.index[ty.typeArguments[0].target]
    ty.typeArguments[0] = target.type
    doclet.returns[0].type = ty.render_name(converter)


orig_convert_all_nodes = Converter.convert_all_nodes


def locate_ffi_fields(root):
    for node in root.children:
        if node.name == "js/ffi":
            break
    for child in node.children:
        if child.name == "ffi":
            break
    fields = child.type.declaration.children
    FFI_FIELDS.update(x.name for x in fields)


# locate the ffi fields
FFI_FIELDS: set[str] = set()


def convert_all_nodes(self, root):
    locate_ffi_fields(root)
    return orig_convert_all_nodes(self, root)


Converter.convert_all_nodes = convert_all_nodes


def ts_xref_formatter(self, xref):
    from sphinx_pyodide.mdn_xrefs import JSDATA

    name = xref.name
    if name == "PyodideInterface":
        return ":ref:`PyodideInterface <js-api-pyodide>`"
    if name in JSDATA:
        result = f":js:data:`{name}`"
    elif name in FFI_FIELDS:
        result = f":js:class:`~pyodide.ffi.{name}`"
    else:
        result = f":js:class:`{name}`"
    return result


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

    def set_doclet_is_private(self, key, doclet):
        if getattr(doclet, "is_private", False):
            return
        doclet.is_private = False

        key = [x for x in key if "/" not in x]
        filename = key[0]
        toplevelname = key[1]
        if doclet.name == "PyodideAPI":
            doclet.is_private = True
            return

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

            key = [x for x in key if "/" not in x]
            filename = key[0]
            toplevelname = key[1]
            doclet.name = doclet.name.rpartition(".")[2]

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
                kind = obj.block_tags.get("dockind", [None])[0]
                if kind:
                    obj.kind = kind[0].text
                elif isinstance(obj, Class):
                    obj.kind = "class"
                elif isinstance(obj, Function):
                    obj.kind = "function"
                else:
                    obj.kind = "attribute"
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
            return rst

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
            prefix = "**async** " if getattr(obj, "is_async", False) else ""
            qualifier = "any"
            if obj.name == "ffi":
                qualifier = "js:mod"

            summary = self.extract_summary(
                JsRenderer.render_description(None, obj.description)
            )
            link_name = pkgname + "." + display_name
            return (prefix, qualifier, display_name, sig, summary, link_name)

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

            for prefix, qualifier, name, sig, summary, real_name in items:
                # The body of this loop is changed from copied code.
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
            new_items.append((prefix, "any", *item))
        return new_items

    Autosummary.get_items = get_items

    return JsDocSummary
