import pytest


@pytest.mark.xfail_browsers(firefox="no localstorage access", node="no idbfs")
def test_hook_indexedDB(selenium_standalone_noload):
    selenium = selenium_standalone_noload

    selenium.run_js(
        """
        indexedDBHook = {
            beforeFileSystemInitialized: (Module) => {
                Module.preRun.push(() => {
                    const mountDir = '/lib';
                    Module.FS.mkdirTree(mountDir);
                    Module.FS.mount(Module.IDBFS, {root : "."}, "/lib");

                    Module.addRunDependency("install-idbfs");
                    Module.FS.syncfs(true, () => {
                        Module.removeRunDependency("install-idbfs");
                    })

                    const hasCache = localStorage.getItem("PYODIDE_IDB_CACHE") === "true";
                    if(hasCache){
                        Module.fileSystemInitialized = true;
                    }
                });
            }
        }

        pyodide = await loadPyodide({
            hooks : [indexedDBHook],
        });

        pyodide.runPython('f = open("/lib/hello.txt", "w"); f.write("hello world"); f.close()');
        pyodide.runPython('assert open("/lib/hello.txt").read() == "hello world"');

        await new Promise((resolve, _) => pyodide.FS.syncfs(false, resolve));
        localStorage.setItem("PYODIDE_IDB_CACHE", "true");

        pyodide2 = await loadPyodide({
            hooks : [indexedDBHook],
        });

        pyodide2.runPython('assert open("/lib/hello.txt").read() == "hello world"');
        """
    )
