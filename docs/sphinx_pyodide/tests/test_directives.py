import pathlib
import sys
import json
import gzip

from docutils.utils import new_document
from docutils.frontend import OptionParser
from sphinx_js.jsdoc import Analyzer as JsAnalyzer
from sphinx_js.suffix_tree import SuffixTree

test_directory = pathlib.Path(__file__).resolve().parent
sys.path.append(str(test_directory.parent))

# jsdoc_dump.json.gz is the source file for the test docs.
# It can be updated as follows:
# jsdoc -c ./docs/jsdoc_conf.json -X ./src/js/ ./src/core/ | gzip > docs/sphinx_pyodide/tests/jsdoc_dump.json.gz
with gzip.open(test_directory / "jsdoc_dump.json.gz") as fh:
    jsdoc_json = json.load(fh)
settings_json = json.loads((test_directory / "app_settings.json").read_text())

from sphinx_pyodide.jsdoc import (
    PyodideAnalyzer,
    get_jsdoc_content_directive,
    get_jsdoc_summary_directive,
    flatten_suffix_tree,
)

inner_analyzer = JsAnalyzer(jsdoc_json, "/home/hood/pyodide/src")
settings = OptionParser().get_default_values()
settings.update(settings_json, OptionParser())

document = new_document("", settings)
pyodide_analyzer = PyodideAnalyzer(inner_analyzer)


def test_flatten_suffix_tree():
    t = SuffixTree()
    d = {
        ("a", "b", "c"): 1,
        ("a", "b", "d"): 2,
        ("a", "d", "d"): 3,
        ("a", "x", "y"): 4,
        ("b", "x", "c"): 5,
        ("b", "x", "d"): 6,
        ("b", "y", "d"): 7,
    }
    t.add_many(d.items())
    r = flatten_suffix_tree(t._tree)
    r = {k: v.value for (k, v) in r.items()}
    assert d == r


class dummy_app:
    _sphinxjs_analyzer = pyodide_analyzer
    document = document


class dummy_state:
    document = document


def test_pyodide_analyzer():
    function_names = {x.name for x in pyodide_analyzer.js_docs["pyodide"]["function"]}
    attribute_names = {x.name for x in pyodide_analyzer.js_docs["pyodide"]["attribute"]}
    assert function_names == {
        "runPython",
        "unregisterJsModule",
        "loadPackage",
        "runPythonAsync",
        "loadPackagesFromImports",
        "registerJsModule",
        "isPyProxy",
        "toPy",
        "setInterruptBuffer",
        "setStandardStreams",
        "checkInterrupt",
        "registerComlink",
    }
    assert attribute_names == {
        "FS",
        "loadedPackages",
        "globals",
        "version",
        "pyodide_py",
    }


def test_content():
    JsDocContent = get_jsdoc_content_directive(dummy_app)

    a = JsDocContent.__new__(JsDocContent)
    a.arguments = ["pyodide"]
    a.state = dummy_state

    def no_op_parse_rst(rst):
        return rst

    a.parse_rst = no_op_parse_rst

    results = {}
    for idx, entry in enumerate(a.run().split(".. js:")):
        [first_line, _, body] = entry.partition("\n")
        if "::" not in first_line:
            continue
        [directive, name] = first_line.split("::")
        directive = directive.strip()
        name = name.strip()
        if directive == "module":
            assert name == a.arguments[0]
            continue
        body = body.strip()
        d = dict(idx=idx, directive=directive, body=body, sig="")
        if "(" in name:
            [name, sig] = name.split("(")
            d["sig"] = sig
        results[name] = d

    rp = results["globals"]
    assert rp["directive"] == "attribute"
    assert rp["sig"] == ""
    assert "An alias to the global Python namespace." in rp["body"]

    rp = results["runPython"]
    assert rp["directive"] == "function"
    assert rp["sig"] == "code, globals)"
    assert "Runs a string of Python code from JavaScript." in rp["body"]


JsDocSummary = get_jsdoc_summary_directive(dummy_app)
jsdoc_summary = JsDocSummary.__new__(JsDocSummary)
jsdoc_summary.state = dummy_state
jsdoc_summary.options = {}


def test_extract_summary():
    assert (
        jsdoc_summary.extract_summary(
            "Registers the Js object ``module`` as a Js module with ``name``. This module can then be imported from Python using the standard Python\nimport system. :func:`some_func`"
        )
        == "Registers the Js object ``module`` as a Js module with ``name``."
    )


def test_summary():
    globals = jsdoc_summary.get_summary_table(
        "globalThis", dummy_app._sphinxjs_analyzer.js_docs["globalThis"]["function"]
    )
    attributes = jsdoc_summary.get_summary_table(
        "pyodide", dummy_app._sphinxjs_analyzer.js_docs["pyodide"]["attribute"]
    )
    functions = jsdoc_summary.get_summary_table(
        "pyodide", dummy_app._sphinxjs_analyzer.js_docs["pyodide"]["function"]
    )
    globals = {t[1]: t for t in globals}
    attributes = {t[1]: t for t in attributes}
    functions = {t[1]: t for t in functions}
    assert globals["loadPyodide"] == (
        "*async* ",
        "loadPyodide",
        "(config, )",
        "Load the main Pyodide wasm module and initialize it.",
        "globalThis.loadPyodide",
    )

    assert attributes["pyodide_py"] == (
        "",
        "pyodide_py",
        "",
        "An alias to the Python :py:mod:`pyodide` package.",
        "pyodide.pyodide_py",
    )
    assert attributes["version"] == (
        "",
        "version",
        "",
        "The Pyodide version.",
        "pyodide.version",
    )
    assert attributes["loadedPackages"] == (
        "",
        "loadedPackages",
        "",
        "The list of packages that Pyodide has loaded.",
        "pyodide.loadedPackages",
    )

    assert functions["loadPackagesFromImports"][:-2] == (
        "*async* ",
        "loadPackagesFromImports",
        "(code, messageCallback, errorCallback)",
    )
