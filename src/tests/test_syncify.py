import pytest


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
        await pyodide.loadPackage("pytest")
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
