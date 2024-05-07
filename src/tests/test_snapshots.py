import pytest


def test_make_snapshot_requires_arg(selenium):
    match = "Can only use pyodide.makeMemorySnapshot if the _makeSnapshot option is passed to loadPyodide"
    with pytest.raises(selenium.JavascriptException, match=match):
        selenium.run_js(
            """
            pyodide.makeMemorySnapshot();
            """
        )


def test_snapshot_bad_magic(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    match = "Snapshot has invalid magic number"
    with pytest.raises(selenium.JavascriptException, match=match):
        selenium.run_js(
            """
            const pyodide = await loadPyodide({_loadSnapshot: new Uint8Array(20 * (1<<20))});
            """
        )


def test_snapshot_simple(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    selenium.run_js(
        """
        const py1 = await loadPyodide({_makeSnapshot: true});
        py1.runPython(`
            from js import Headers, URL
            canParse = URL.canParse
        `);
        const snapshot = py1.makeMemorySnapshot();
        const py2 = await loadPyodide({_loadSnapshot: snapshot});
        assert(() => py2.globals.get("Headers") === Headers);
        assert(() => py2.globals.get("URL") === URL);
        assert(() => py2.globals.get("canParse") === URL.canParse);
        """
    )


def test_snapshot_cannot_serialize(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    match = "Can't serialize object at index"
    with pytest.raises(selenium.JavascriptException, match=match):
        selenium.run_js(
            """
            const py1 = await loadPyodide({_makeSnapshot: true});
            py1.runPython(`
                from js import Headers, URL

                a = Headers.new()
            `);
            py1.makeMemorySnapshot();
            """
        )


def test_snapshot_deleted_proxy(selenium_standalone_noload):
    """In previous test, we fail to make the snapshot because we have a proxy of
    a Headers which we don't know how to serialize.

    In this test, we delete the headers proxy and should be able to successfully
    create the snapshot.
    """
    selenium = selenium_standalone_noload
    selenium.run_js(
        """
        const py1 = await loadPyodide({_makeSnapshot: true});
        py1.runPython(`
            from js import Headers, URL
            from pyodide.code import run_js

            assert run_js("1+1") == 2
            assert run_js("(x) => x.get('a')")({'a': 7}) == 7

            a = Headers.new()
            del a # delete non-serializable JsProxy
        `);
        const snapshot = py1.makeMemorySnapshot();
        const py2 = await loadPyodide({_loadSnapshot: snapshot});
        py2.runPython(`
            assert run_js("1+1") == 2
            assert run_js("(x) => x.get('a')")({'a': 7}) == 7

            a = Headers.new()
        `);
        """
    )


def test_snapshot_stacked(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    selenium.run_js(
        """
        const py1 = await loadPyodide({_makeSnapshot: true});
        py1.runPython(`
            from js import Headers
            from pyodide.code import run_js

            assert run_js("1+1") == 2
            assert run_js("(x) => x.get('a')")({'a': 7}) == 7

            a = Headers.new()
            del a
        `);
        const snapshot = py1.makeMemorySnapshot();
        const py2 = await loadPyodide({_loadSnapshot: snapshot, _makeSnapshot: true});
        py2.runPython(`
            assert run_js("1+1") == 2
            assert run_js("(x) => x.get('a')")({'a': 7}) == 7
            from js import URL

            t = URL.new("http://a.com/z?t=2").searchParams["t"]
            assert t == "2"

            a = Headers.new()
            del a
        `);
        const snapshot2 = py2.makeMemorySnapshot();
        const py3 = await loadPyodide({_loadSnapshot: snapshot2, _makeSnapshot: true});
        py3.runPython(`
            assert run_js("1+1") == 2
            assert run_js("(x) => x.get('a')")({'a': 7}) == 7

            t = URL.new("http://a.com/z?t=2").searchParams["t"]
            assert t == "2"

            a = Headers.new()
        `);
        """
    )
