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

test_directory = Path(__file__).resolve().parent
sys.path.append(str(test_directory.parent))
src_dir = test_directory.parents[2] / "src"


# tsdoc_dump.json.gz is the source file for the test docs. It can be updated as follows:
#
# cp src/core/pyproxy.ts src/js/pyproxy.gen.ts
# typedoc src/js/*.ts --tsconfig src/js/tsconfig.json --json docs/sphinx_pyodide/tests/tsdoc_dump.json
# gzip docs/sphinx_pyodide/tests/tsdoc_dump.json
# rm src/js/pyproxy.gen.ts
with gzip.open(test_directory / "tsdoc_dump.json.gz") as fh:
    jsdoc_json = json.load(fh)
settings_json = json.loads((test_directory / "app_settings.json").read_text())

from sphinx_pyodide.jsdoc import (
    PyodideAnalyzer,
    flatten_suffix_tree,
    get_jsdoc_content_directive,
    get_jsdoc_summary_directive,
)

inner_analyzer = TsAnalyzer(jsdoc_json, str(src_dir))
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


class dummy_app:
    _sphinxjs_analyzer = pyodide_analyzer
    document = document


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
        "setDefaultStdout",
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
    globals = {t[1]: t for t in globals}
    attributes = {t[1]: t for t in attributes}
    functions = {t[1]: t for t in functions}
    assert globals["loadPyodide"] == (
        "**async** ",
        "loadPyodide",
        "(options)",
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
        "**async** ",
        "loadPackagesFromImports",
        "(code, options)",
    )


def test_type_name():
    tn = inner_analyzer._type_name
    assert tn({"name": "void", "type": "intrinsic"}) == ":js:data:`void`"
    assert tn({"value": None, "type": "literal"}) == ":js:data:`null`"
    assert (
        tn(
            {
                "name": "Promise",
                "type": "reference",
                "typeArguments": [{"name": "string", "type": "intrinsic"}],
            }
        ).strip()
        == r":js:class:`Promise`\ **<**\ :js:data:`string`\ **>**"
    )

    assert (
        tn(
            {
                "asserts": False,
                "name": "jsobj",
                "targetType": {"name": "PyProxy", "type": "reference"},
                "type": "predicate",
            }
        ).strip()
        == ":js:data:`boolean` (typeguard for :js:class:`PyProxy`)"
    )

    assert (
        tn(
            {
                "declaration": {
                    "kindString": "Method",
                    "name": "messageCallback",
                    "signatures": [
                        {
                            "kindString": "Call signature",
                            "name": "messageCallback",
                            "parameters": [
                                {
                                    "flags": {},
                                    "kindString": "Parameter",
                                    "name": "message",
                                    "type": {"name": "string", "type": "intrinsic"},
                                }
                            ],
                            "type": {"name": "void", "type": "intrinsic"},
                        }
                    ],
                },
                "type": "reflection",
            }
        ).strip()
        == r"\ **(**\ \ **message:** :js:data:`string`\ **) =>** :js:data:`void`"
    )

    assert (
        tn(
            {
                "name": "Iterable",
                "type": "reference",
                "typeArguments": [
                    {
                        "elements": [
                            {
                                "element": {"name": "string", "type": "intrinsic"},
                                "isOptional": False,
                                "name": "key",
                                "type": "named-tuple-member",
                            },
                            {
                                "element": {"name": "any", "type": "intrinsic"},
                                "isOptional": False,
                                "name": "value",
                                "type": "named-tuple-member",
                            },
                        ],
                        "type": "tuple",
                    }
                ],
            }
        ).strip()
        == r":js:data:`Iterable`\ **<**\ \ **[**\ \ **key:** :js:data:`string`\ **,** \ **value:** :js:data:`any`\ **]** \ **>**"
    )

    assert (
        tn(
            {
                "declaration": {
                    "flags": {},
                    "indexSignature": {
                        "flags": {},
                        "kindString": "Index signature",
                        "parameters": [
                            {
                                "flags": {},
                                "name": "key",
                                "type": {"name": "string", "type": "intrinsic"},
                            }
                        ],
                        "type": {"name": "string", "type": "intrinsic"},
                    },
                    "kindString": "Type literal",
                },
                "type": "reflection",
            }
        ).strip()
        == r"""\ **{**\ \ **[key:** :js:data:`string`\ **]:** :js:data:`string`\ **}**\ """.strip()
    )

    assert (
        tn(
            {
                "declaration": {
                    "children": [
                        {
                            "flags": {},
                            "kindString": "Property",
                            "name": "cache",
                            "type": {"name": "PyProxyCache", "type": "reference"},
                        },
                        {
                            "flags": {"isOptional": True},
                            "kindString": "Property",
                            "name": "destroyed_msg",
                            "type": {"name": "string", "type": "intrinsic"},
                        },
                        {
                            "flags": {},
                            "kindString": "Property",
                            "name": "ptr",
                            "type": {"name": "number", "type": "intrinsic"},
                        },
                    ],
                    "flags": {},
                    "kindString": "Type literal",
                },
                "type": "reflection",
            }
        ).strip()
        == r"""\ **{**\ \ **cache:** :js:class:`PyProxyCache`\ **,** \ **destroyed_msg?:** :js:data:`string`\ **,** \ **ptr:** :js:data:`number`\ **}**\ """.strip()
    )
