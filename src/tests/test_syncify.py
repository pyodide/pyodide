import pytest


@pytest.mark.xfail_browsers(safari="No JSPI on Safari", firefox="No JSPI on firefox")
def test_syncify1(selenium):
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
@pytest.mark.skip_refcount_check
def test_syncify2(selenium):
    selenium.run_js(
        """
        await pyodide.runPythonSyncifying(`
            def temp():
                from js import sleep
                print("a")
                from pyodide_js._module import validSuspender
                print("validSuspender.value:", validSuspender.value)
                sleep(1000).syncify()
                print("b")
            temp()
        `);
        """
    )
