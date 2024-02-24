"""tests of using the emscripten filesystem API with pyodide

for a basic nodejs-based test, see src/js/test/filesystem.test.js
"""

import pytest
from pytest_pyodide import run_in_pyodide

from conftest import only_chrome


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_idbfs_persist_code(selenium_standalone):
    """can we persist files created by user python code?"""
    selenium = selenium_standalone
    if selenium.browser == "node":
        fstype = "NODEFS"
    else:
        fstype = "IDBFS"

    mount_dir = "/mount_test"
    # create mount
    selenium.run_js(
        f"""
        let mountDir = '{mount_dir}';
        pyodide.FS.mkdir(mountDir);
        pyodide.FS.mount(pyodide.FS.filesystems.{fstype}, {{root : "."}}, mountDir);
        """
    )
    # create file in mount
    selenium.run_js(
        f"""
        pyodide.runPython(`
            import pathlib
            p = pathlib.Path('{mount_dir}/test_idbfs/__init__.py')
            p.parent.mkdir(exist_ok=True, parents=True)
            p.write_text("def test(): return 7")
            from importlib import invalidate_caches
            invalidate_caches()
            import sys
            sys.path.append('{mount_dir}')
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
        self.pyodide = await loadPyodide({ fullStdLib: false });
        """
    )
    # idbfs isn't magically loaded
    selenium.run_js(
        f"""
        pyodide.runPython(`
            from importlib import invalidate_caches
            import sys
            invalidate_caches()
            err_type = None
            try:
                sys.path.append('{mount_dir}')
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
        pyodide.FS.mkdir('{mount_dir}');
        pyodide.FS.mount(pyodide.FS.filesystems.{fstype}, {{root : "."}}, "{mount_dir}");
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
        f"""
        pyodide.runPython(`
            from importlib import invalidate_caches
            invalidate_caches()
            import sys
            sys.path.append('{mount_dir}')
            from test_idbfs import test
            assert test() == 7
        `);
        """
    )
    # remove file
    selenium.run_js(f"""pyodide.FS.unlink("{mount_dir}/test_idbfs/__init__.py")""")


@pytest.mark.requires_dynamic_linking
@only_chrome
def test_nativefs_dir(request, selenium_standalone):
    # Note: Using *real* native file system requires
    # user interaction so it is not available in headless mode.
    # So in this test we use OPFS (Origin Private File System)
    # which is part of File System Access API but uses indexDB as a backend.

    if request.config.option.runner == "playwright":
        pytest.xfail("Playwright doesn't support file system access APIs")

    selenium = selenium_standalone

    selenium.run_js(
        """
        root = await navigator.storage.getDirectory();
        dirHandleMount = await root.getDirectoryHandle('testdir', { create: true });
        testFileHandle = await dirHandleMount.getFileHandle('test_read', { create: true });
        writable = await testFileHandle.createWritable();
        await writable.write("hello_read");
        await writable.close();
        fs = await pyodide.mountNativeFS("/mnt/nativefs", dirHandleMount);
        """
    )

    # Read

    selenium.run(
        """
        import os
        import pathlib
        assert len(os.listdir("/mnt/nativefs")) == 1, str(os.listdir("/mnt/nativefs"))
        assert os.listdir("/mnt/nativefs") == ["test_read"], str(os.listdir("/mnt/nativefs"))

        pathlib.Path("/mnt/nativefs/test_read").read_text() == "hello_read"
        """
    )

    # Write / Delete / Rename

    selenium.run(
        """
        import os
        import pathlib
        pathlib.Path("/mnt/nativefs/test_write").write_text("hello_write")
        pathlib.Path("/mnt/nativefs/test_write").read_text() == "hello_write"
        pathlib.Path("/mnt/nativefs/test_delete").write_text("This file will be deleted")
        pathlib.Path("/mnt/nativefs/test_rename").write_text("This file will be renamed")
        """
    )

    entries = selenium.run_js(
        """
        await fs.syncfs();
        entries = {};
        for await (const [key, value] of dirHandleMount.entries()) {
            entries[key] = value;
        }
        return entries;
        """
    )

    assert "test_read" in entries
    assert "test_write" in entries
    assert "test_delete" in entries
    assert "test_rename" in entries

    selenium.run(
        """
        import os
        os.remove("/mnt/nativefs/test_delete")
        os.rename("/mnt/nativefs/test_rename", "/mnt/nativefs/test_rename_renamed")
        """
    )

    entries = selenium.run_js(
        """
        await fs.syncfs();
        entries = {};
        for await (const [key, value] of dirHandleMount.entries()) {
            entries[key] = value;
        }
        return entries;
        """
    )

    assert "test_delete" not in entries
    assert "test_rename" not in entries
    assert "test_rename_renamed" in entries

    # unmount

    files = selenium.run(
        """
        import os
        os.listdir("/mnt/nativefs")
        """
    )

    assert "test_read" in entries
    assert "test_write" in entries
    assert "test_rename_renamed" in entries

    selenium.run_js(
        """
        await fs.syncfs();
        pyodide.FS.unmount("/mnt/nativefs");
        """
    )

    files = selenium.run(
        """
        import os
        os.listdir("/mnt/nativefs")
        """
    )

    assert not len(files)

    # Mount again

    selenium.run_js(
        """
        fs2 = await pyodide.mountNativeFS("/mnt/nativefs", dirHandleMount);
        """
    )

    # Read again

    selenium.run(
        """
        import os
        import pathlib
        assert len(os.listdir("/mnt/nativefs")) == 3, str(os.listdir("/mnt/nativefs"))
        pathlib.Path("/mnt/nativefs/test_read").read_text() == "hello_read"
        """
    )

    selenium.run_js(
        """
        await fs2.syncfs();
        pyodide.FS.unmount("/mnt/nativefs");
        """
    )


@pytest.fixture
def browser(selenium):
    return selenium.browser


@pytest.fixture
def runner(request):
    return request.config.option.runner


@run_in_pyodide
def test_fs_dup(selenium, browser):
    from os import close, dup
    from pathlib import Path

    from pyodide.code import run_js

    if browser == "node":
        fstype = "NODEFS"
    else:
        fstype = "IDBFS"

    mount_dir = Path("/mount_test")
    mount_dir.mkdir(exist_ok=True)
    run_js(
        """
        (fstype, mountDir) =>
            pyodide.FS.mount(pyodide.FS.filesystems[fstype], {root : "."}, mountDir);
        """
    )(fstype, str(mount_dir))

    file = open("/mount_test/a.txt", "w")
    fd2 = dup(file.fileno())
    close(fd2)
    file.write("abcd")
    file.close()


@pytest.mark.requires_dynamic_linking
@only_chrome
@run_in_pyodide
async def test_nativefs_dup(selenium, runner):
    from os import close, dup

    import pytest

    from pyodide.code import run_js

    # Note: Using *real* native file system requires
    # user interaction so it is not available in headless mode.
    # So in this test we use OPFS (Origin Private File System)
    # which is part of File System Access API but uses indexDB as a backend.

    if runner == "playwright":
        pytest.xfail("Playwright doesn't support file system access APIs")

    await run_js(
        """
        async () => {
            root = await navigator.storage.getDirectory();
            testFileHandle = await root.getFileHandle('test_read', { create: true });
            writable = await testFileHandle.createWritable();
            await writable.write("hello_read");
            await writable.close();
            await pyodide.mountNativeFS("/mnt/nativefs", root);
        }
        """
    )()
    file = open("/mnt/nativefs/test_read")
    fd2 = dup(file.fileno())
    close(fd2)
    assert file.read() == "hello_read"
    file.close()
