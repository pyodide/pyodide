from docutils import nodes
from docutils.parsers.rst import Directive, Parser as RstParser, directives
from docutils.statemachine import StringList
from docutils.utils import new_document

from collections import OrderedDict
import re

from sphinx import addnodes
from sphinx.util import rst
from sphinx.util.docutils import switch_source_input
from sphinx.ext.autosummary import autosummary_table, extract_summary
from sphinx.domains.javascript import JSCallable, JavaScriptDomain

from sphinx_js.typedoc import Analyzer as TsAnalyzer
from sphinx_js.ir import Class, Function
from sphinx_js.parsers import path_and_formal_params, PathVisitor
from sphinx_js.renderers import (
    AutoFunctionRenderer,
    AutoAttributeRenderer,
    AutoClassRenderer,
)

_orig_convert_node = TsAnalyzer._convert_node

def _convert_node(self, node):
    kind = node.get("kindString")
    if kind in ["Function", "Constructor", "Method"] and not node.get("sources"):
        return None, []
    if kind in ['Call signature', 'Constructor signature']:
        params = node.get('parameters', [])
        new_params = []
        for param in params:
            new_params.append(param)
            param_type = param["type"]
            if param_type["type"] != "reflection":
                continue
            param_type["skip"] = True
            decl = param_type["declaration"]
            if "children" not in decl:
                continue
            for child in decl["children"]:
                child = dict(child)
                if not "type" in child:
                    if "signatures" in child:
                        child["comment"] = child["signatures"][0]["comment"]
                        child["type"] = {"type" : "reflection", "declaration" : dict(child)}
                    # child["type"]["type"] = "reflection"
                child["name"] = param["name"] + "." + child["name"]
                new_params.append(child)
        node["parameters"] = new_params
    node["extendedTypes"] = [t for t in node.get("extendedTypes", []) if "id" in t]
    return _orig_convert_node(self, node)


TsAnalyzer._convert_node = _convert_node

_orig_type_name = TsAnalyzer._type_name

def type_literal_name(self, decl):
    children = []
    if "indexSignature" in decl:
        index_sig = decl["indexSignature"]
        assert len(index_sig["parameters"]) == 1
        key = index_sig["parameters"][0]
        keyname = key["name"]
        keytype = self._type_name(key["type"])
        valuetype = self._type_name(index_sig["type"])
        children.append(f"[{keyname}: {keytype}]: {valuetype}")
    if 'children' in decl:
        children.extend(child["name"] + ": " + self._type_name(child["type"]) for child in decl["children"])

    return "{" + ", ".join(children) + "}"

def _type_name(self, type):
    res = _orig_type_name(self, type)
    if "TODO" not in res:
        return res
    if "skip" in type:
        return ""
    type_of_type = type.get("type")
    if type_of_type == "predicate":
        return f"boolean (typeguard for {self._type_name(type['targetType'])})"
    if type_of_type != "reflection":
        return res
    decl = type["declaration"]
    if decl["kindString"] == 'Type literal':
        return type_literal_name(self, decl)
    decl_sig = None
    if "signatures" in decl:
        decl_sig = decl["signatures"][0]
    if decl["kindString"] == "Call signature":
        decl_sig = decl
    if decl_sig:
        params = [
            f'{ty["name"]}: {self._type_name(ty["type"])}'
            for ty in decl_sig.get("parameters", [])
        ]
        params_str = ", ".join(params)
        ret_str = self._type_name(decl_sig["type"])
        return f"({params_str}) => {ret_str}"
    assert False


TsAnalyzer._type_name = _type_name


class JSFuncMaybeAsync(JSCallable):
    option_spec = {
        **JSCallable.option_spec,
        "async": directives.flag,
    }

    def handle_signature(self, sig, signode):
        if "async" in self.options:
            self.display_prefix = "async"
        return super().handle_signature(sig, signode)


JavaScriptDomain.directives["function"] = JSFuncMaybeAsync


def flatten_suffix_tree(tree):
    """Flatten suffix tree into a dictionary.

    self._doclets_by_class already has stuff in the correct layout but it
    does not contain top level file attributes. They are contained in the
    suffix tree, but the suffix tree is inconveniently shaped. So we flatten
    it...
    """
    result = {}
    path = []
    iters = []
    cur_iter = iter(tree.items())
    while True:
        try:
            [key, val] = next(cur_iter)
        except StopIteration:
            if not iters:
                return result
            cur_iter = iters.pop()
            path.pop()
            continue
        if isinstance(val, dict):
            iters.append(cur_iter)
            path.append(key)
            cur_iter = iter(val.items())
        else:
            path.append(key)
            result[tuple(reversed(path))] = val
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

    def create_js_doclets(self):
        """Search through the doclets generated by JsDoc and categorize them by
        summary section. Skip docs labeled as "@private".
        """
        self.doclets = flatten_suffix_tree(self._objects_by_path._tree)

        def get_val():
            return OrderedDict([["attribute", []], ["function", []], ["class", []]])

        modules = ["globalThis", "pyodide", "PyProxy"]
        self.js_docs = {key: get_val() for key in modules}
        items = {key: [] for key in modules}
        for (key, doclet) in self.doclets.items():
            if getattr(doclet.value, "is_private", False):
                continue
            # Remove the part of the key corresponding to the file
            key = [x for x in key if "/" not in x]
            filename = key[0]
            toplevelname = key[1]
            if key[-1].startswith("$"):
                doclet.value.is_private = True
                continue
            doclet.value.name = doclet.value.name.rpartition(".")[2]
            if filename == "pyodide.":
                # Might be named globalThis.something or exports.something.
                # Trim off the prefix.
                items["globalThis"] += doclet
                continue
            pyproxy_class_endings = ("Methods", "Class")
            if toplevelname.endswith("#"):
                # This is a class method.
                if filename == "pyproxy.gen." and toplevelname[:-1].endswith(
                    pyproxy_class_endings
                ):
                    # Merge all of the PyProxy methods into one API
                    items["PyProxy"] += doclet
                # If it's not part of a PyProxy class, the method will be
                # documented as part of the class.
                continue
            if filename == "pyproxy.gen." and toplevelname.endswith(
                pyproxy_class_endings
            ):
                continue
            if filename.startswith("PyProxy"):
                # Skip all PyProxy classes, they are documented as one merged
                # API.
                continue
            items["pyodide"] += doclet

        from operator import attrgetter

        for key, value in items.items():
            for obj in sorted(value, key=attrgetter("name")):
                obj.async_ = False
                if isinstance(obj, Class):
                    obj.kind = "class"
                    # sphinx-jsdoc messes up array types. Fix them.
                    for x in obj.members:
                        if hasattr(x, "type") and x.type:
                            x.type = re.sub("Array\.<([a-zA-Z_0-9]*)>", r"\1[]", x.type)
                elif isinstance(obj, Function):
                    obj.kind = "function"
                    obj.async_ = obj.returns and obj.returns[0].type.startswith(
                        "Promise<"
                    )
                else:
                    obj.kind = "attribute"
                if obj.name == "iterator":
                    # sphinx-jsdoc messes up Symbol attributes. Fix them.
                    obj.name = "[Symbol.iterator]"
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
            """Grab the appropriate renderer and render us to rst.
            JsDoc also has an AutoClassRenderer which may be useful in the future."""
            if isinstance(obj, Function):
                renderer = AutoFunctionRenderer
            elif isinstance(obj, Class):
                renderer = AutoClassRenderer
            else:
                renderer = AutoAttributeRenderer
            rst = renderer(
                self, app, arguments=["dummy"], options={"members": ["*"]}
            ).rst([obj.name], obj, use_short_name=False)
            if obj.async_:
                rst = self.add_async_option_to_rst(rst)
            return rst

        def add_async_option_to_rst(self, rst):
            rst_lines = rst.split("\n")
            for i, line in enumerate(rst_lines):
                if line.startswith(".."):
                    break
            rst_lines.insert(i + 1, "   :async:")
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
            prefix = "*async* " if obj.async_ else ""
            summary = self.extract_summary(obj.description)
            link_name = pkgname + "." + display_name
            return (prefix, display_name, sig, summary, link_name)

        def get_summary_table(self, pkgname, group):
            """Get the data for a summary table. Return value is set up to be an
            argument of format_table.
            """
            return [self.get_summary_row(pkgname, obj) for obj in group]

        # This following method is copied almost verbatim from autosummary
        # (where it is called get_table).
        #
        # We have to change the value of one string: qualifier = 'obj   ==>
        # qualifier = 'any'
        # https://github.com/sphinx-doc/sphinx/blob/3.x/sphinx/ext/autosummary/__init__.py#L392
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
                qualifier = "any"  # <== Only thing changed from autosummary version
                if "nosignatures" not in self.options:
                    col1 = "%s:%s:`%s <%s>`\\ %s" % (
                        prefix,
                        qualifier,
                        name,
                        real_name,
                        rst.escape(sig),
                    )
                else:
                    col1 = "%s:%s:`%s <%s>`" % (prefix, qualifier, name, real_name)
                col2 = summary
                append_row(col1, col2)

            return [table_spec, table]

    return JsDocSummary
