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


def test_snapshot_bad_build_id(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    match = r"\s*".join(
        [
            "Snapshot build id mismatch",
            "expected: [0-9a-f]*",
            "got     : 404142435051525360616263707172738081828390919293a0a1a2a3b0b1b2b3",
        ]
    )
    with pytest.raises(selenium.JavascriptException, match=match):
        selenium.run_js(
            """
            const snp = new Uint8Array(20 * (1<<20));
            const snp32 = new Uint32Array(snp.buffer);
            snp32[0] =  0x706e7300; // snapshot magic

            snp32[4] =  0x40414243;
            snp32[5] =  0x50515253;
            snp32[6] =  0x60616263;
            snp32[7] =  0x70717273;
            snp32[8] =  0x80818283;
            snp32[9] =  0x90919293;
            snp32[10] = 0xa0a1a2a3;
            snp32[11] = 0xb0b1b2b3;
            snp32[12] = 0xc0c1c2c3;
            const pyodide = await loadPyodide({_loadSnapshot: snp});
            """
        )


def test_snapshot_simple(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    selenium.run_js(
        """
        const py1 = await loadPyodide({_makeSnapshot: true});
        py1.runPython(`
            from js import Headers, URL
            createObjectURL = URL.createObjectURL
        `);
        const snapshot = py1.makeMemorySnapshot();
        const py2 = await loadPyodide({_loadSnapshot: snapshot});
        assert(() => py2.globals.get("Headers") === Headers);
        assert(() => py2.globals.get("URL") === URL);
        assert(() => py2.globals.get("createObjectURL") === URL.createObjectURL);
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


def test_snapshot_serializer1(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    selenium.run_js(
        """
        const py1 = await loadPyodide({_makeSnapshot: true});
        py1.runPython(`
            from js import Headers, URL

            a = Headers.new([["X", "1"], ["Y", "2"]])
        `);
        const snapshot = py1.makeMemorySnapshot({serializer(obj) {
            if (obj.constructor.name === "Headers") {
                return {type: "Headers", value: Array.from(obj)};
            }
            throw new Error("Not implemented");
        }});
        const py2 = await loadPyodide({_loadSnapshot: snapshot, _snapshotDeserializer(obj) {
            if (obj.type === "Headers") {
                return new Headers(obj.value);
            }
        }});
        py2.runPython(`
            assert a.constructor.name == "Headers"
            assert a["X"] == "1"
            assert a["Y"] == "2"
        `);
        """
    )


def test_snapshot_serializer_not_serializable(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    match = "Serializer returned result that cannot be JSON.stringify'd at index"
    with pytest.raises(selenium.JavascriptException, match=match):
        selenium.run_js(
            """
            const py1 = await loadPyodide({_makeSnapshot: true});
            py1.runPython(`
                from pyodide.code import run_js

                a = run_js("(o = {}, o.o = o)")
            `);
            const snapshot = py1.makeMemorySnapshot({serializer: (obj) => obj});
            """
        )


def test_snapshot_serializer_need_deserializer(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    match = "You must pass an appropriate deserializer as _snapshotDeserializer"
    with pytest.raises(selenium.JavascriptException, match=match):
        selenium.run_js(
            """
            const py1 = await loadPyodide({_makeSnapshot: true});
            py1.runPython(`
                from js import Headers, URL

                a = Headers.new([["X", "1"], ["Y", "2"]])
            `);
            const snapshot = py1.makeMemorySnapshot({serializer(obj) {
                if (obj.constructor.name === "Headers") {
                    return {type: "Headers", value: Array.from(obj)};
                }
                throw new Error("Not implemented");
            }});
            const py2 = await loadPyodide({_loadSnapshot: snapshot });
            """
        )
