from inspect import getsource


def test_filesystem_mounting(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    selenium.run_js(
        f"""
        let pyodide1 = await loadPyodide();
        let pyodide2 = await loadPyodide();

        {js_set_test_environment_source()}

        pyodide1.runPython(`{py_write_file_source(1)}`);
        pyodide2.runPython(`{py_write_file_source(2)}`);

        pyodide1.runPython(`{py_assert_created_files_source(1)}`);
        pyodide2.runPython(`{py_assert_created_files_source(2)}`);

        {js_remove_files_source()}

        pyodide1.runPython(`{py_assert_removed_files_source(1)}`);
        pyodide2.runPython(`{py_assert_removed_files_source(2)}`);
        """
    )


def js_set_test_environment_source():
    return """
        await pyodide1.FS.mkdir("/pyodide1");
        await pyodide2.FS.mkdir("/pyodide2");

        await pyodide2.FS.mount(
            pyodide2.FS.filesystems.PROXYFS,
            {
                root: "/pyodide1",
                fs: pyodide1.FS,
            },
            "/pyodide2"
        );
    """


def js_remove_files_source():
    return """
        await pyodide2.FS.unmount("/pyodide2");
        await pyodide2.FS.rmdir("/pyodide2");
        await pyodide1.FS.unlink("/pyodide1/file_from_1.txt");
        await pyodide1.FS.unlink("/pyodide1/file_from_2.txt");
        await pyodide1.FS.rmdir("/pyodide1");
    """


def py_write_file_source(index: int) -> str:
    def write_file():
        with open("/pyodide{index}/file_from_{index}.txt", "w", encoding="utf-8") as f:
            f.write("pyodide{index}")

    return (
        getsource(write_file).format(index=index).lstrip() + f"{write_file.__name__}()"
    )


def py_assert_created_files_source(index: int) -> str:
    def assert_created_files():
        import os

        assert os.path.exists("/pyodide{index}/file_from_1.txt")
        assert os.path.exists("/pyodide{index}/file_from_2.txt")
        assert not os.path.exists("/pyodide{index}/file_from_nowhere.txt")

        assert os.path.isfile("/pyodide{index}/file_from_1.txt")
        assert os.path.isfile("/pyodide{index}/file_from_2.txt")
        assert not os.path.isfile("/pyodide{index}/file_from_nowhere.txt")

        assert not os.path.isdir("/pyodide{index}/file_from_1.txt")
        assert not os.path.isdir("/pyodide{index}/file_from_2.txt")
        assert not os.path.isdir("/pyodide{index}/file_from_nowhere.txt")

        assert os.path.isdir("/pyodide{index}")
        assert not os.path.isfile("/pyodide{index}")

        # Test os.listdir
        assert sorted(os.listdir("/pyodide{index}")) == [
            "file_from_1.txt",
            "file_from_2.txt",
        ]

        # Test file reading
        with open("/pyodide{index}/file_from_1.txt", encoding="utf-8") as f:
            content = f.read()
        assert content == "pyodide1"

        with open("/pyodide{index}/file_from_2.txt", encoding="utf-8") as f:
            content = f.read()
        assert content == "pyodide2"

        # Test os.path.getsize
        file1_size = os.path.getsize("/pyodide{index}/file_from_1.txt")
        file2_size = os.path.getsize("/pyodide{index}/file_from_2.txt")
        assert file1_size == len(b"pyodide1")
        assert file2_size == len(b"pyodide2")

        # Test os.stat
        stat_info1 = os.stat("/pyodide{index}/file_from_1.txt")
        stat_info2 = os.stat("/pyodide{index}/file_from_2.txt")
        assert stat_info1.st_size == len(b"pyodide1")
        assert stat_info2.st_size == len(b"pyodide2")

    return (
        getsource(assert_created_files).format(index=index).lstrip()
        + f"{assert_created_files.__name__}()"
    )


def py_assert_removed_files_source(index: int) -> str:
    def assert_removed_files():
        import os

        assert not os.path.exists("/pyodide{index}")
        assert not os.path.isfile("/pyodide{index}")
        assert not os.path.isdir("/pyodide{index}")

        assert not os.path.exists("/pyodide{index}/file_from_1.txt")
        assert not os.path.exists("/pyodide{index}/file_from_2.txt")
        assert not os.path.isfile("/pyodide{index}/file_from_1.txt")
        assert not os.path.isfile("/pyodide{index}/file_from_2.txt")
        assert not os.path.isdir("/pyodide{index}/file_from_1.txt")
        assert not os.path.isdir("/pyodide{index}/file_from_2.txt")

    return (
        getsource(assert_removed_files).format(index=index).lstrip()
        + f"{assert_removed_files.__name__}()"
    )
