from docutils import nodes
from docutils.parsers.rst import Directive, Parser as RstParser
from docutils.statemachine import StringList
from docutils.utils import new_document

from sphinx import addnodes
from sphinx.util import rst
from sphinx.util.docutils import switch_source_input
from sphinx.ext.autosummary import autosummary_table, extract_summary

from sphinx_js.jsdoc import Analyzer as JsAnalyzer
from sphinx_js.ir import Function
from sphinx_js.parsers import path_and_formal_params, PathVisitor
from sphinx_js.renderers import AutoFunctionRenderer, AutoAttributeRenderer


def longname_to_path(name):
    """Convert the longname field produced by jsdoc to a path appropriate to use
    with _sphinxjs_analyzer.get_object. Based on:
    https://github.com/mozilla/sphinx-js/blob/3.1/sphinx_js/jsdoc.py#L181
    """
    return PathVisitor().visit(path_and_formal_params["path"].parse(name))


# old__init__ = JsAnalyzer.__init__
# def patch__init__(self, arg, basename):
#     import json
#     import pathlib
#     pathlib.Path("blah.json").write_text(json.dumps(arg))
#     old__init__(self, arg, basename)
# JsAnalyzer.__init__ = patch__init__


class PyodideAnalyzer:
    """JsDoc automatically instantiates the JsAnalyzer. Rather than subclassing
    or monkey patching it, we use composition (see getattr impl).
    """

    def __init__(self, analyzer: JsAnalyzer) -> None:
        self.inner = analyzer
        self.create_js_doclets()

    def __getattr__(self, key):
        return getattr(self.inner, key)

    def get_object_from_json(self, json):
        path = longname_to_path(json["longname"])
        kind = "function" if json["kind"] == "function" else "attribute"
        obj = self.get_object(path, kind)
        obj.kind = kind
        return obj

    def create_js_doclets(self):
        globals = []
        pyodide = []
        self.js_docs = {"function": [], "attribute": [], "global": []}
        for (key, group) in self._doclets_by_class.items():
            if key[-1] == "globalThis":
                globals = group
            if key[-1] == "Module":
                pyodide = group
        for json in globals:
            if json.get("access", None) == "private":
                continue
            obj = self.get_object_from_json(json)
            self.js_docs["global"].append(obj)
        for json in pyodide:
            if json.get("access", None) == "private":
                continue
            obj = self.get_object_from_json(json)
            self.js_docs[obj.kind].append(obj)


def get_jsdoc_content_directive(app):
    """These directives need to close over app """

    class JsDocContent(Directive):
        """A directive that just dumps a summary table in place. There are no
        options, it only prints the one thing, we control the behavior from
        here
        """

        def get_rst(self, obj):
            if isinstance(obj, Function):
                renderer = AutoFunctionRenderer
            else:
                renderer = AutoAttributeRenderer
            return renderer(self, app, arguments=["dummy"]).rst(
                [obj.name], obj, use_short_name=False
            )

        def parse_rst(self, rst):
            settings = self.state.document.settings
            doc = new_document("", settings)
            RstParser().parse(rst, doc)
            return doc.children

        def get_rst_for_group(self, group):
            result = []
            for obj in app._sphinxjs_analyzer.js_docs[group]:
                result.append(self.get_rst(obj))
            return result

        def run(self):
            rst = []
            rst.append([".. js:module:: globalThis"])
            rst.append(self.get_rst_for_group("global"))
            rst.append([".. js:module:: pyodide"])
            rst.append(self.get_rst_for_group("attribute"))
            rst.append(self.get_rst_for_group("function"))
            joined_rst = "\n\n".join(["\n\n".join(r) for r in rst])
            return self.parse_rst(joined_rst)

    return JsDocContent


def get_jsdoc_summary_directive(app):
    class JsDocSummary(Directive):
        """A directive that just dumps the Js API docs in place. There are no
        options, it only prints the one thing, we control the behavior from
        here
        """

        def run(self):
            result = []
            for name, entries in self.get_items():
                result.append(self.make_heading(name + ":"))
                table = self.get_table(entries)
                result.extend(table)
            return result

        def make_heading(self, text):
            heading = nodes.paragraph("")
            strong = nodes.strong("")
            strong.append(nodes.Text(text))
            heading.append(strong)
            return heading

        def get_items(self):
            result = []
            for group in ["global", "attribute", "function"]:
                pkgname = "globalThis." if group == "global" else "pyodide."
                items = []
                for obj in app._sphinxjs_analyzer.js_docs[group]:
                    sig = self.get_sig(obj)
                    display_name = obj.name
                    summary = extract_summary([obj.description], self.state.document)
                    link_name = pkgname + display_name
                    items.append((display_name, sig, summary, link_name))
                result.append([group.title() + "s", items])
            return result

        def get_sig(self, obj):
            if isinstance(obj, Function):
                return AutoFunctionRenderer(
                    self, app, arguments=["dummy"]
                )._formal_params(obj)
            else:
                return ""

        # This following method is copied almost verbatim from autosummary.
        # We have to change the value of one string:
        # qualifier = 'obj   ==>   qualifier = 'any'
        # https://github.com/sphinx-doc/sphinx/blob/3.x/sphinx/ext/autosummary/__init__.py#L392
        def get_table(self, items):
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

            for name, sig, summary, real_name in items:
                qualifier = "any"  # <== Only thing changed from autosummary version
                if "nosignatures" not in self.options:
                    col1 = ":%s:`%s <%s>`\\ %s" % (
                        qualifier,
                        name,
                        real_name,
                        rst.escape(sig),
                    )
                else:
                    col1 = ":%s:`%s <%s>`" % (qualifier, name, real_name)
                col2 = summary
                append_row(col1, col2)

            return [table_spec, table]

    return JsDocSummary
