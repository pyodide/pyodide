"""tests of the OPFS_WORKER_FS filesystem, which is only available in Web Workers

These tests are kept separate from test_filesystem.py because webworker tests
cannot be mixed with non-webworker tests in Safari.
"""

import pytest

from conftest import only_chrome


@pytest.mark.requires_dynamic_linking
@only_chrome
def test_opfs_basic(request, selenium_webworker_standalone):
    # OPFS is only accessible in dedicated Web Worker contexts so we use
    # selenium_webworker_standalone. FileSystemSyncAccessHandle is only
    # available in workers.

    if request.config.option.runner == "playwright":
        pytest.xfail("Playwright doesn't support file system access APIs")

    selenium = selenium_webworker_standalone

    # SetUp: create test files in OPFS from the main thread.
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

        "ok"
        """
    )
    assert result == "ok"


@pytest.mark.requires_dynamic_linking
@only_chrome
def test_opfs_write(request, selenium_webworker_standalone):
    if request.config.option.runner == "playwright":
        pytest.xfail("Playwright doesn't support file system access APIs")

    selenium = selenium_webworker_standalone

    # Setup: create files in OPFS from the main thread. Sync handles are only
    # pre-created for files that exist at mount time (see src/js/fs/opfs.ts),
    # so every file written below must already exist in OPFS.
    selenium.run_js(
        """
        const root = await navigator.storage.getDirectory();
        const testDir = await root.getDirectoryHandle('opfs_write_test', {create: true});
        const files = {
            'overwrite.txt': 'original content',
            'append.txt': 'hello',
            'truncate.txt': '0123456789',
            'seek_write.bin': '0123456789',
        };
        for (const [name, content] of Object.entries(files)) {
            const fileHandle = await testDir.getFileHandle(name, {create: true});
            const writable = await fileHandle.createWritable();
            await writable.write(content);
            await writable.close();
        }
        """
    )

    result = selenium.run_webworker(
        """
        from js import pyodide
        await pyodide.mountOPFS("/mnt/opfs")

        import os
        from pathlib import Path

        base = Path("/mnt/opfs/opfs_write_test")

        # Overwrite: opening with "w" truncates the existing contents
        p = base / "overwrite.txt"
        p.write_text("new")
        assert p.read_text() == "new", p.read_text()
        assert os.path.getsize(p) == len("new"), os.path.getsize(p)

        # Append
        p = base / "append.txt"
        with open(p, "a") as f:
            f.write(" world")
        assert p.read_text() == "hello world", p.read_text()
        assert os.path.getsize(p) == len("hello world"), os.path.getsize(p)

        # Truncate by path and by file descriptor
        p = base / "truncate.txt"
        os.truncate(p, 4)
        assert p.read_text() == "0123", p.read_text()
        with open(p, "r+") as f:
            f.truncate(2)
        assert p.read_text() == "01", p.read_text()
        assert os.path.getsize(p) == 2, os.path.getsize(p)

        # Write in place at an offset without changing the rest of the file
        p = base / "seek_write.bin"
        with open(p, "r+b") as f:
            f.seek(4)
            f.write(b"XY")
        assert p.read_bytes() == b"0123XY6789", p.read_bytes()
        assert os.path.getsize(p) == 10, os.path.getsize(p)

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
