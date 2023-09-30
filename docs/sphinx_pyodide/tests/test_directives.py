import gzip
import inspect
import json
import sys
from pathlib import Path

from docutils.frontend import OptionParser
from docutils.utils import new_document

if not hasattr(inspect, "getargspec"):
    inspect.getargspec = inspect.getfullargspec  # type: ignore[assignment]


from sphinx_js.suffix_tree import SuffixTree
from sphinx_js.typedoc import Analyzer as TsAnalyzer
from sphinx_js.typedoc import Project

test_directory = Path(__file__).resolve().parent
sys.path.append(str(test_directory.parent))
src_dir = test_directory.parents[2] / "src"


# tsdoc_dump.json.gz is the source file for the test docs. It can be updated as follows:
#
# cp src/core/pyproxy.ts src/js/pyproxy.gen.ts
# typedoc src/js/*.ts --tsconfig src/js/tsconfig.json --json docs/sphinx_pyodide/tests/tsdoc_dump.json
# gzip docs/sphinx_pyodide/tests/tsdoc_dump.json
# rm src/js/pyproxy.gen.ts


from sphinx_pyodide.jsdoc import (
    PyodideAnalyzer,
    flatten_suffix_tree,
    get_jsdoc_content_directive,
    get_jsdoc_summary_directive,
    ts_post_convert,
    ts_should_destructure_arg,
    ts_xref_formatter,
)

with gzip.open(test_directory / "tsdoc_dump.json.gz") as fh:
    jsdoc_json = Project.parse_raw(fh.read())
settings_json = json.loads((test_directory / "app_settings.json").read_text())

inner_analyzer = TsAnalyzer(
    jsdoc_json,
    str(src_dir),
    post_convert=ts_post_convert,
    should_destructure_arg=ts_should_destructure_arg,
)
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
    assert d == r


class dummy_config:
    ts_type_xref_formatter = ts_xref_formatter


class dummy_app:
    _sphinxjs_analyzer = pyodide_analyzer
    document = document
    config = dummy_config


class dummy_state:
    document = document


def test_pyodide_analyzer():
    function_names = {x.name for x in pyodide_analyzer.js_docs["pyodide"]["function"]}
    attribute_names = {x.name for x in pyodide_analyzer.js_docs["pyodide"]["attribute"]}
    assert function_names == {
        "checkInterrupt",
        "isPyProxy",
        "loadPackage",
        "loadPackagesFromImports",
        "mountNativeFS",
        "pyimport",
        "registerComlink",
        "registerJsModule",
        "runPython",
        "runPythonAsync",
        "setDebug",
        "setInterruptBuffer",
        "setStderr",
        "setStdin",
        "setStdout",
        "toPy",
        "unpackArchive",
        "unregisterJsModule",
    }

    assert attribute_names == {
        "ERRNO_CODES",
        "FS",
        "PATH",
        "canvas",
        "ffi",
        "version",
        "globals",
        "loadedPackages",
        "pyodide_py",
        "version",
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
    assert rp["sig"] == "code, options)"
    assert "Runs a string of Python code from JavaScript" in rp["body"]


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
    globals = {t[2]: t for t in globals}
    attributes = {t[2]: t for t in attributes}
    functions = {t[2]: t for t in functions}
    assert globals["loadPyodide"] == (
        "**async** ",
        "any",
        "loadPyodide",
        "(options)",
        "Load the main Pyodide wasm module and initialize it.",
        "globalThis.loadPyodide",
    )

    assert attributes["pyodide_py"] == (
        "",
        "any",
        "pyodide_py",
        "",
        "An alias to the Python :ref:`pyodide <python-api>` package.",
        "pyodide.pyodide_py",
    )
    assert attributes["version"] == (
        "",
        "any",
        "version",
        "",
        "The Pyodide version.",
        "pyodide.version",
    )
    assert attributes["loadedPackages"] == (
        "",
        "any",
        "loadedPackages",
        "",
        "The list of packages that Pyodide has loaded.",
        "pyodide.loadedPackages",
    )

    assert functions["loadPackagesFromImports"][:-2] == (
        "**async** ",
        "any",
        "loadPackagesFromImports",
        "(code, options)",
    )
