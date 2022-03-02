"""tests of using the emscripten filesystem API with pyodide

for a basic nodejs-based test, see src/js/test/filesystem.test.js
"""
import pytest

from pyodide_build.testing import PYVERSION


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_idbfs_persist_code(selenium_standalone):
    """can we persist files created by user python code?"""
    selenium = selenium_standalone
    if selenium.browser == "node":
        fstype = "NODEFS"
    else:
        fstype = "IDBFS"
    # create mount
    selenium.run_js(
        f"""
        pyodide.FS.mkdir('/lib/{PYVERSION}/site-packages/test_idbfs');
        pyodide.FS.mount(pyodide.FS.filesystems.{fstype}, {{root : "."}}, "/lib/{PYVERSION}/site-packages/test_idbfs");
        """
    )
    # create file in mount
    selenium.run_js(
        f"""
        pyodide.runPython(`
            import pathlib
            p = pathlib.Path('/lib/{PYVERSION}/site-packages/test_idbfs/__init__.py')
            p.write_text("def test(): return 7")
            from importlib import invalidate_caches
            invalidate_caches()
            from test_idbfs import test
            assert test() == 7
        `);
        """
    )
    # sync TO idbfs
    selenium.run_js(
        """
        const error = await new Promise(
            (resolve, reject) => pyodide.FS.syncfs(false, resolve)
        );
        assert(() => error == null);
        """
    )
    # refresh page and re-fixture
    selenium.refresh()
    selenium.run_js(
        """
        self.pyodide = await loadPyodide({ indexURL : './', fullStdLib: false });
        """
    )
    # idbfs isn't magically loaded
    selenium.run_js(
        """
        pyodide.runPython(`
            from importlib import invalidate_caches
            invalidate_caches()
            err_type = None
            try:
                from test_idbfs import test
            except Exception as err:
                err_type = type(err)
            assert err_type is ModuleNotFoundError, err_type
        `);
        """
    )
    # re-mount
    selenium.run_js(
        f"""
        pyodide.FS.mkdir('/lib/{PYVERSION}/site-packages/test_idbfs');
        pyodide.FS.mount(pyodide.FS.filesystems.{fstype}, {{root : "."}}, "/lib/{PYVERSION}/site-packages/test_idbfs");
        """
    )
    # sync FROM idbfs
    selenium.run_js(
        """
        const error = await new Promise(
            (resolve, reject) => pyodide.FS.syncfs(true, resolve)
        );
        assert(() => error == null);
        """
    )
    # import file persisted above
    selenium.run_js(
        """
        pyodide.runPython(`
            from importlib import invalidate_caches
            invalidate_caches()
            from test_idbfs import test
            assert test() == 7
        `);
        """
    )
    # remove file
    selenium.run_js(
        f"""pyodide.FS.unlink("/lib/{PYVERSION}/site-packages/test_idbfs/__init__.py")"""
    )
