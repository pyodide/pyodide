"""tests of using the emscripten filesystem API with pyodide

for a basic nodejs-based test, see src/js/test/filesystem.test.js
"""

import pytest
from pytest_pyodide import run_in_pyodide

from conftest import only_chrome, only_node


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_idbfs_persist_code(selenium_standalone_refresh):
    """can we persist files created by user python code?"""
    selenium = selenium_standalone_refresh
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

    @run_in_pyodide
    def create_test_file(selenium_module, mount_dir):
        import sys
        from importlib import invalidate_caches
        from pathlib import Path

        p = Path(f"{mount_dir}/test_idbfs/__init__.py")
        p.parent.mkdir(exist_ok=True, parents=True)
        p.write_text("def test(): return 7")
        invalidate_caches()
        sys.path.append(mount_dir)
        from test_idbfs import test

        assert test() == 7

    create_test_file(selenium, mount_dir)
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
        self.pyodide = await loadPyodide();
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
def test_nativefs_dir(request, selenium_standalone_refresh):
    # Note: Using *real* native file system requires
    # user interaction so it is not available in headless mode.
    # So in this test we use OPFS (Origin Private File System)
    # which is part of File System Access API but uses indexDB as a backend.

    if request.config.option.runner == "playwright":
        pytest.xfail("Playwright doesn't support file system access APIs")

    selenium = selenium_standalone_refresh

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


@pytest.mark.requires_dynamic_linking
@only_chrome
def test_opfs_basic(request, selenium_webworker_standalone):
    # OPFS is only accessible in dedicated Web Worker contexts so we use
    # selenium_webworker_standalone. FileSystemSyncAccessHandle is only
    # available in workers.

    if request.config.option.runner == "playwright":
        pytest.xfail("Playwright doesn't support file system access APIs")

    selenium = selenium_webworker_standalone

    # SetUp: create tet files in OPFS from the main thread.
    # OPFS is origin-scoped so the worker will see these files.
    selenium.run_js(
        """
        const root = await navigator.storage.getDirectory();
        const testDir = await root.getDirectoryHandle('opfs_test', {create: true });
        const fileHandle = await testDir.getFileHandle('test_read', {create: true});
        const writable = await fileHandle.createWritable();
        await writable.write("hello_read");
        await writable.close();
        """
    )

    # Mount OPFS in the worker and read the file
    result = selenium.run_webworker(
        """
        from js import pyodide
        await pyodide.mountOPFS("/mnt/opfs")

        import os
        import pathlib

        # Read
        assert "opfs_test" in os.listdir("/mnt/opfs"), str(os.listdir("/mnt/opfs"))
        assert "test_read" in os.listdir("/mnt/opfs/opfs_test")

        content = pathlib.Path("/mnt/opfs/opfs_test/test_read").read_text()
        assert content == "hello_read", content

        # Size check
        size = os.path.getsize("/mnt/opfs/opfs_test/test_read")
        assert size == len("hello_read"), size

        "ok"
        """
    )

    assert result == "ok"

    # Verify from main thread: file should still exist in OPFS
    entries = selenium.run_js(
        """
        const root = await navigator.storage.getDirectory();
        const testDir = await root.getDirectoryHandle('opfs_test');
        const result = {};
        for await (const [key, value] of testDir.entries()) {
            result[key] = value;
        }
        return result;
        """
    )
    assert "test_read" in entries


@pytest.mark.requires_dynamic_linking
@only_chrome
def test_opfs_readdir(request, selenium_webworker_standalone):
    if request.config.option.runner == "playwright":
        pytest.xfail("Playwright doesn't support file system access APIs")

    selenium = selenium_webworker_standalone

    # Setup: create nested directory structure in OPFS
    # /opfs_readdir_test/
    #   ├── a.txt
    #   ├── b.txt
    #   └── nested/
    #       └── c.txt
    selenium.run_js(
        """
        const root = await navigator.storage.getDirectory();
        const testDir = await root.getDirectoryHandle('opfs_readdir_test', {create: true});

        for (const name of ['a.txt', 'b.txt']) {
            const fileHandle = await testDir.getFileHandle(name, {create: true});
            const writable = await fileHandle.createWritable();
            await writable.write(`content of ${name}`);
            await writable.close();
        }

        const nestedDir = await testDir.getDirectoryHandle('nested', {create: true});
        const nestedFileHandle = await nestedDir.getFileHandle('c.txt', {create: true});
        const nestedWritable = await nestedFileHandle.createWritable();
        await nestedWritable.write("content of c.txt");
        await nestedWritable.close();
        """
    )

    result = selenium.run_webworker(
        """
        from js import pyodide
        await pyodide.mountOPFS("/mnt/opfs")

        import os

        # readdir - top level
        top = sorted(os.listdir("/mnt/opfs/opfs_readdir_test"))
        assert top == ["a.txt", "b.txt", "nested"], top

        # readdir - nested
        nested = sorted(os.listdir("/mnt/opfs/opfs_readdir_test/nested"))
        assert nested == ["c.txt"], nested

        # os.walk
        walked = []
        for dirpath, dirnames, filenames in os.walk("/mnt/opfs/opfs_readdir_test"):
            walked.append((dirpath, sorted(dirnames), sorted(filenames)))

        # os.path.isfile / isdir
        assert os.path.isfile("/mnt/opfs/opfs_readdir_test/a.txt")
        assert os.path.isfile("/mnt/opfs/opfs_readdir_test/b.txt")
        assert os.path.isfile("/mnt/opfs/opfs_readdir_test/nested/c.txt")
        assert not os.path.isfile("/mnt/opfs/opfs_readdir_test/nested")
        assert os.path.isdir("/mnt/opfs/opfs_readdir_test/nested")
        assert os.path.isdir("/mnt/opfs/opfs_readdir_test")
        assert not os.path.isdir("/mnt/opfs/opfs_readdir_test/a.txt")

        # Non-existent paths
        assert not os.path.exists("/mnt/opfs/opfs_readdir_test/nonexistent.txt")
        assert not os.path.isfile("/mnt/opfs/opfs_readdir_test/nonexistent.txt")
        assert not os.path.isdir("/mnt/opfs/opfs_readdir_test/nonexistent.txt")

        "ok"
        """
    )
    assert result == "ok"


@pytest.mark.requires_dynamic_linking
@only_chrome
def test_opfs_large_file(request, selenium_webworker_standalone):
    # Verify that reading a large file from OPFS does not consume
    # memory proportional to the file size, unlike MEMFS-based approaches.
    # This is the key property that OPFS_WORKER_FS is designed to provide.

    if request.config.option.runner == "playwright":
        pytest.xfail("Playwright doesn't support file system access APIs")

    selenium = selenium_webworker_standalone

    # Setup: create a 10MB file in OPFS with a known pattern
    selenium.run_js(
        """
        const root = await navigator.storage.getDirectory();
        const testDir = await root.getDirectoryHandle('opfs_large_file_test', {create: true});
        const fileHandle = await testDir.getFileHandle('large_file.bin', {create: true});
        const writable = await fileHandle.createWritable();

        const chunk = new Uint8Array(1024 * 1024); // 1MB chunk
        for (let i = 0; i < chunk.length; i++) {
            chunk[i] = i % 256; // Fill with a known pattern
        }
        for (let i = 0; i < 10; i++) {
            await writable.write(chunk);
        }
        await writable.close();
        """
    )

    result = selenium.run_webworker(
        """
        from js import pyodide

        # Measure WASM heap size before mounting OPFS
        initial_heap_size = pyodide._module.HEAPU8.length

        await pyodide.mountOPFS("/mnt/opfs")

        import os
        FILE_SIZE = 10 * 1024 * 1024  # 10MB
        path = "/mnt/opfs/opfs_large_file_test/large_file.bin"

        # Verify file size is reported correctly (from OPFS, not MEMFS buffer)
        size = os.path.getsize(path)
        assert size == FILE_SIZE, f"Expected file size {FILE_SIZE}, got {size}"

        # Random access - read a small chunk from the middle of the file.
        # Should succeed without loading the whole file into memory.
        with open(path, "rb") as f:
            f.seek(5 * 1024 * 1024)  # Seek to the middle of the file
            chunk = f.read(1024)  # Read 1KB
            assert len(chunk) == 1024, f"Expected to read 1024 bytes, got {len(chunk)}"
            # Verify pattern: byte at position N should be (N % 256)
            for i in range(len(chunk)):
                expected_byte = ((5 * 1024 * 1024) + i) % 256
                assert chunk[i] == expected_byte, (
                    f"Byte {i} mismatch: expected {expected_byte}, got {chunk[i]}"
                )

        # Measure WASM heap size after reading from OPFS
        final_heap_size = pyodide._module.HEAPU8.length
        growth = final_heap_size - initial_heap_size

        # A MEMFS-based implementation would grow by the full file size.
        # With direct OPFS I/O via FileSystemSyncAccessHandle, file contents
        # never enter WASM memory, so growth should be bounded by:
        #   - WASM memory page granularity (64 KiB)
        #   - Python/runtime incidental allocations
        #   - The 1024-byte read buffer
        # 512 KiB gives headroom for these while still detecting regressions
        # where file data leaks into MEMFS (which would be ~10 MB here).
        assert growth < 512 * 1024, (
            f"Memory grew by {growth} bytes for a {FILE_SIZE} byte file; "
            f"expected << {FILE_SIZE}. A MEMFS-based implementation would "
            f"have grown by ~{FILE_SIZE} bytes."
        )

        from pyodide.ffi import to_js
        from js import Object
        to_js({"size": size, "growth": growth}, dict_converter=Object.fromEntries)
        """
    )
    assert result["size"] == 10 * 1024 * 1024


@pytest.mark.requires_dynamic_linking
@only_chrome
def test_opfs_pandas_compatibility(request, selenium_webworker_standalone):
    # Integration test : verify that pandas can read a CSV file from an
    # OPFS-mounted directory via the standard Python file APIs.
    # This confirms our custom stream_ops work through Python's io layer and the C fopen/fread path used by pandas.
    #
    # Note : this is a compatibility test only. The memory-efficiency property of OPFS (file contents not entering WASM memory)
    # is covered separately by test_opfs_large_file. A small CSV is sufficient for this test.

    if request.config.option.runner == "playwright":
        pytest.xfail("Playwright doesn't support file system access APIs")

    selenium = selenium_webworker_standalone

    # Setup: write a CSV file in OPFS from the main thread.
    selenium.run_js(
        """
        const root = await navigator.storage.getDirectory();
        const testDir = await root.getDirectoryHandle('opfs_pandas_test', {create: true});
        const fileHandle = await testDir.getFileHandle('test.csv', {create: true});
        const writable = await fileHandle.createWritable();

        let csv = "id,name,value\\n";
        for (let i = 0; i < 1000; i++) {
            csv += `${i},name${i},${i * 10}\\n`;
        }
        await writable.write(csv);
        await writable.close();
        """
    )

    result = selenium.run_webworker(
        """
        from js import pyodide
        await pyodide.loadPackage("pandas")

        await pyodide.mountOPFS("/mnt/opfs")

        import pandas as pd
        df = pd.read_csv("/mnt/opfs/opfs_pandas_test/test.csv")

        # Verify end-to-end : header, row count, numeric parsing, string parsing
        assert df.shape == (1000, 3), f"Expected 1000 rows and 3 columns, got {df.shape}"
        assert list(df.columns) == ["id", "name", "value"], f"Unexpected columns: {df.columns}"
        assert df.iloc[0]["name"] == "name0", f"Unexpected value in first row: {df.iloc[0]['name']}"
        assert df.iloc[999]["value"] == 9990, f"Unexpected value in last row: {df.iloc[999]['value']}"
        assert df["value"].sum() == sum(i * 10 for i in range(1000)), f"Unexpected sum of 'value' column: {df['value'].sum()}"

        from pyodide.ffi import to_js
        from js import Object
        to_js({"rows": len(df)}, dict_converter=Object.fromEntries)
        """
    )
    assert result["rows"] == 1000


@pytest.mark.requires_dynamic_linking
@only_chrome
def test_opfs_parquet_partial_read(request, selenium_webworker_standalone):
    # Parquet files are columnar: readers first fetch the footer metadata
    # from the end of the file, then seek to individual column chunks.
    # This exercises our llseek + read path with non-sequential access
    # patterns, which is where FileSystemSyncAccessHandle shines — the
    # reader only needs the bytes for the requested columns, not the
    # full file materialized in memory.

    if request.config.option.runner == "playwright":
        pytest.xfail("Playwright doesn't support file system access APIs")

    selenium = selenium_webworker_standalone

    result = selenium.run_webworker(
        """
        from js import pyodide, navigator
        from pyodide.ffi import to_js

        await pyodide.loadPackage("pyarrow")

        # Step 1: generate a parquet file in memory with pyarrow
        import pyarrow as pa
        import pyarrow.parquet as pq
        import io

        table = pa.table({
            "id": list(range(10000)),
            "name": [f"row_{i}" for i in range(10000)],
            "value": [i * 1.5 for i in range(10000)],
        })
        buf = io.BytesIO()
        pq.write_table(table, buf)
        parquet_bytes = buf.getvalue()

        # Step 2: write bytes to OPFS via the raw API from this worker
        # (FileSystemSyncAccessHandle is available in dedicated workers).
        # We can't use our mounted FS to create a new file because sync
        # handles are only pre-created at mount time (see opfs.ts TODO).
        root = await navigator.storage.getDirectory()
        test_dir = await root.getDirectoryHandle("opfs_parquet_test", create=True)
        file_handle = await test_dir.getFileHandle("data.parquet", create=True)
        sync_handle = await file_handle.createSyncAccessHandle()
        sync_handle.write(to_js(parquet_bytes))
        sync_handle.flush()
        sync_handle.close()

        # Step 3: mount OPFS so our filesystem picks up the file
        await pyodide.mountOPFS("/mnt/opfs")

        # Step 4: partial read — only the "name" column.
        # The reader will:
        #   - seek to the end of file to read the footer
        #   - seek to the "name" column chunk
        #   - skip "id" and "value" column chunks entirely
        # This demonstrates random access via our llseek + read.
        initial_heap = pyodide._module.HEAPU8.length

        name_col = pq.read_table(
            "/mnt/opfs/opfs_parquet_test/data.parquet",
            columns=["name"],
        )

        final_heap = pyodide._module.HEAPU8.length
        growth = final_heap - initial_heap

        # Verify
        assert name_col.num_rows == 10000, name_col.num_rows
        assert name_col.column_names == ["name"], name_col.column_names
        assert name_col["name"][0].as_py() == "row_0"
        assert name_col["name"][9999].as_py() == "row_9999"

        from pyodide.ffi import to_js
        from js import Object
        to_js(
            {
                "rows": name_col.num_rows,
                "growth": growth,
                "file_size": len(parquet_bytes),
            },
            dict_converter=Object.fromEntries,
        )
        """
    )
    assert result["rows"] == 10000


@only_chrome
def test_nativefs_errors(selenium):
    selenium.run_js(
        """
        const root = await navigator.storage.getDirectory();
        const handle = await root.getDirectoryHandle("dir", { create: true });

        await pyodide.mountNativeFS("/mnt1/nativefs", handle);
        await assertThrowsAsync(
          async () => await pyodide.mountNativeFS("/mnt1/nativefs", handle),
          "Error",
          "path '/mnt1/nativefs' is already a file system mount point",
        );

        pyodide.FS.mkdirTree("/mnt2");
        pyodide.FS.writeFile("/mnt2/some_file", "contents");
        await assertThrowsAsync(
          async () => await pyodide.mountNativeFS("/mnt2/some_file", handle),
          "Error",
          "path '/mnt2/some_file' points to a file not a directory",
        );
        // Check we didn't overwrite the file.
        assert(
          () =>
            pyodide.FS.readFile("/mnt2/some_file", { encoding: "utf8" }) === "contents",
        );

        pyodide.FS.mkdirTree("/mnt3/nativefs");
        pyodide.FS.writeFile("/mnt3/nativefs/a.txt", "contents");
        await assertThrowsAsync(
          async () => await pyodide.mountNativeFS("/mnt3/nativefs", handle),
          "Error",
          "directory '/mnt3/nativefs' is not empty",
        );
        // Check directory wasn't changed
        const { node } = pyodide.FS.lookupPath("/mnt3/nativefs/");
        assert(() => Object.entries(node.contents).length === 1);
        assert(
          () =>
            pyodide.FS.readFile("/mnt3/nativefs/a.txt", { encoding: "utf8" }) ===
            "contents",
        );

        const [r1, r2] = await Promise.allSettled([
          pyodide.mountNativeFS("/mnt4/nativefs", handle),
          pyodide.mountNativeFS("/mnt4/nativefs", handle),
        ]);
        assert(() => r1.status === "fulfilled");
        assert(() => r2.status === "rejected");
        assert(
          () =>
            r2.reason.message === "path '/mnt4/nativefs' is already a file system mount point",
        );
        """
    )


@only_node
def test_mount_nodefs(selenium):
    selenium.run_js(
        """
        pyodide.mountNodeFS("/mnt1/nodefs", ".");
        assertThrows(
          () => pyodide.mountNodeFS("/mnt1/nodefs", "."),
          "Error",
          "path '/mnt1/nodefs' is already a file system mount point"
        );

        assertThrows(
          () =>
            pyodide.mountNodeFS(
              "/mnt2/nodefs",
              "/thispath/does-not/exist/ihope"
            ),
          "Error",
          "hostPath '/thispath/does-not/exist/ihope' does not exist"
        );

        const os = require("os");
        const fs = require("fs");
        const path = require("path");
        const crypto = require("crypto");
        const tmpdir = path.join(os.tmpdir(), crypto.randomUUID());
        fs.mkdirSync(tmpdir);
        const apath = path.join(tmpdir, "a");
        fs.writeFileSync(apath, "xyz");
        pyodide.mountNodeFS("/mnt3/nodefs", tmpdir);
        assert(
          () =>
            pyodide.FS.readFile("/mnt3/nodefs/a", { encoding: "utf8" }) ===
            "xyz"
        );

        assertThrows(
          () => pyodide.mountNodeFS("/mnt4/nodefs", apath),
          "Error",
          `hostPath '${apath}' is not a directory`
        );
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


def test_trackingDelegate(selenium_standalone_refresh):
    selenium = selenium_standalone_refresh

    selenium.run_js(
        """
        assert (() => typeof pyodide.FS.trackingDelegate !== "undefined")

        if (typeof window !== "undefined") {
            global = window
        } else {
            global = globalThis
        }

        global.trackingLog = ""
        pyodide.FS.trackingDelegate["onCloseFile"] = (path) => { global.trackingLog = `CALLED ${path}` }
        """
    )

    selenium.run(
        """
        f = open("/hello", "w")
        f.write("helloworld")
        f.close()

        import js

        assert "CALLED /hello" in js.trackingLog
        """
    )

    # logs = selenium.logs
    # assert "CALLED /hello" in logs
