import pytest


@pytest.mark.xfail_browsers(node="Scopes don't work as needed")
def test_syncify_not_supported(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    selenium.run_js(
        """
        // Ensure that it's not supported by deleting WebAssembly.Suspender
        delete WebAssembly.Suspender;
        let pyodide = await loadPyodide({});
        await assertThrowsAsync(
          async () => await pyodide.runPythonSyncifying("1+1"),
          "Error",
          "WebAssembly stack switching not supported in this JavaScript runtime"
        );
        await assertThrows(
          () => pyodide.runPython("from js import sleep; sleep().syncify()"),
          "PythonError",
          "RuntimeError: WebAssembly stack switching not supported in this JavaScript runtime"
        );
        """
    )


@pytest.mark.xfail_browsers(safari="No JSPI on Safari", firefox="No JSPI on firefox")
def test_syncify1(selenium):
    selenium.run_js(
        """
        await pyodide.runPythonSyncifying(`
            from pyodide.code import run_js

            test = run_js(
                '''
                (async function test() {
                    await sleep(1000);
                    return 7;
                })
                '''
            )
            assert test().syncify() == 7
            del test
        `);
        """
    )


@pytest.mark.xfail_browsers(safari="No JSPI on Safari", firefox="No JSPI on firefox")
def test_syncify2(selenium):
    selenium.run_js(
        """
        await pyodide.runPythonSyncifying(`
            from pyodide_js import loadPackage
            loadPackage("pytest").syncify()
            import pytest
            import importlib.metadata
            with pytest.raises(ModuleNotFoundError):
                importlib.metadata.version("micropip")

            from pyodide_js import loadPackage
            loadPackage("micropip").syncify()

            assert importlib.metadata.version("micropip")
        `);
        """
    )


@pytest.mark.xfail_browsers(safari="No JSPI on Safari", firefox="No JSPI on firefox")
def test_syncify_error(selenium):
    selenium.run_js(
        """
        await pyodide.loadPackage("pytest");
        await pyodide.runPythonSyncifying(`
            def temp():
                from pyodide.code import run_js

                asyncThrow = run_js(
                    '''
                    (async function asyncThrow(){
                        throw new Error("hi");
                    })
                    '''
                )
                from pyodide.ffi import JsException
                import pytest
                with pytest.raises(JsException, match="hi"):
                    asyncThrow().syncify()
            temp()
        `);
        """
    )


@pytest.mark.xfail_browsers(safari="No JSPI on Safari", firefox="No JSPI on firefox")
def test_syncify_no_suspender(selenium):
    selenium.run_js(
        """
        await pyodide.loadPackage("pytest");
        await pyodide.runPython(`
            from pyodide.code import run_js
            import pytest

            test = run_js(
                '''
                (async function test() {
                    await sleep(1000);
                    return 7;
                })
                '''
            )
            with pytest.raises(RuntimeError, match="No suspender"):
                test().syncify()
            del test
        `);
        """
    )


@pytest.mark.requires_dynamic_linking
@pytest.mark.xfail_browsers(safari="No JSPI on Safari", firefox="No JSPI on firefox")
def test_syncify_getset(selenium):
    selenium.run_js(
        """
        await pyodide.loadPackage("fpcast-test")
        await pyodide.runPythonSyncifying(`
            def temp():
                from pyodide.code import run_js

                test = run_js(
                    '''
                    (async function test() {
                        await sleep(1000);
                        return 7;
                    })
                    '''
                )
                x = []
                def wrapper():
                    x.append(test().syncify())

                import fpcast_test
                t = fpcast_test.TestType()
                t.getset_jspi_test = wrapper
                t.getset_jspi_test
                t.getset_jspi_test = None
                assert x == [7, 7]
            temp()
        `);
        """
    )


@pytest.mark.requires_dynamic_linking
@pytest.mark.xfail(reason="Will fix in a followup")
def test_syncify_ctypes():
    selenium.run_js(  # type: ignore[name-defined] # noqa: F821
        """
        await pyodide.runPythonSyncifying(`
            from pyodide.code import run_js

            test = run_js(
                '''
                (async function test() {
                    await sleep(1000);
                    return 7;
                })
                '''
            )

            def wrapper():
                return test().syncify()
            from ctypes import pythonapi, py_object
            pythonapi.PyObject_CallNoArgs.argtypes = [py_object]
            pythonapi.PyObject_CallNoArgs.restype = py_object
            assert pythonapi.PyObject_CallNoArgs(wrapper) == 7
        `);
        """
    )


@pytest.mark.requires_dynamic_linking
@pytest.mark.xfail_browsers(safari="No JSPI on Safari", firefox="No JSPI on firefox")
def test_cpp_exceptions_and_syncify(selenium):
    assert (
        selenium.run_js(
            """
            ptr = pyodide.runPython(`
                from pyodide.code import run_js
                temp = run_js(
                    '''
                    (async function temp() {
                        await sleep(100);
                        return 9;
                    })
                    '''
                )

                def f():
                    try:
                        return temp().syncify()
                    except Exception as e:
                        print(e)
                        return -1
                id(f)
            `);

            await pyodide.loadPackage("cpp-exceptions-test")
            const Module = pyodide._module;
            const catchlib = pyodide._module.LDSO.loadedLibsByName["/usr/lib/cpp-exceptions-test-catch.so"].exports;
            async function t(x){
                Module.validSuspender.value = true;
                const ptr = await Module.createPromising(catchlib.catch_call_pyobj)(x);
                Module.validSuspender.value = false;
                const res = Module.UTF8ToString(ptr);
                Module._free(ptr);
                return res;
            }
            return await t(ptr)
            """
        )
        == "result was: 9"
    )
