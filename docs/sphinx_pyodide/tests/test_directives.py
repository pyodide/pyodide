import pathlib
import sys
import json

from docutils.utils import new_document
from docutils.frontend import OptionParser
from sphinx_js.jsdoc import Analyzer as JsAnalyzer


test_directory = pathlib.Path(__file__).resolve().parent
sys.path.append(str(test_directory.parent))

jsdoc_json = json.loads((test_directory / "jsdoc_dump.json").read_text())
settings_json = json.loads((test_directory / "app_settings.json").read_text())

from sphinx_pyodide.jsdoc import (
    PyodideAnalyzer,
    get_jsdoc_content_directive,
    get_jsdoc_summary_directive,
)

inner_analyzer = JsAnalyzer(jsdoc_json, "/home/hood/pyodide/src")
settings = OptionParser().get_default_values()
settings.update(settings_json, OptionParser())

document = new_document("", settings)
pyodide_analyzer = PyodideAnalyzer(inner_analyzer)


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
        "pyimport",
        "loadPackagesFromImports",
        "registerJsModule",
    }
    assert attribute_names == {"loadedPackages", "globals", "version", "pyodide_py"}


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
    assert rp["sig"] == "code)"
    assert "Runs a string of Python code from Javascript." in rp["body"]


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
        "globalThis", dummy_app._sphinxjs_analyzer.js_docs["globals"]["attribute"]
    )
    attributes = jsdoc_summary.get_summary_table(
        "pyodide", dummy_app._sphinxjs_analyzer.js_docs["pyodide"]["attribute"]
    )
    functions = jsdoc_summary.get_summary_table(
        "pyodide", dummy_app._sphinxjs_analyzer.js_docs["pyodide"]["function"]
    )
    assert set(globals) == {
        (
            "languagePluginLoader",
            "",
            "A promise that resolves to ``undefined`` when Pyodide is finished loading.",
            "globalThis.languagePluginLoader",
        )
    }
    assert set(attributes).issuperset(
        {
            (
                "loadedPackages",
                "",
                "The list of packages that Pyodide has loaded.",
                "pyodide.loadedPackages",
            ),
            (
                "pyodide_py",
                "",
                "An alias to the Python pyodide package.",
                "pyodide.pyodide_py",
            ),
        }
    )
    assert set(functions).issuperset(
        {
            (
                "loadPackagesFromImports",
                "(code, messageCallback, errorCallback)",
                "Inspect a Python code chunk and use :js:func:`pyodide.loadPackage` to load any known \npackages that the code chunk imports.",
                "pyodide.loadPackagesFromImports",
            ),
            (
                "registerJsModule",
                "(name, module)",
                "Registers the Js object ``module`` as a Js module with ``name``.",
                "pyodide.registerJsModule",
            ),
        }
    )
