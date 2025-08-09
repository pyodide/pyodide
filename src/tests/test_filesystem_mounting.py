from pytest_pyodide import run_in_pyodide


@run_in_pyodide
def test_filesystem_mounting(selenium):
    import asyncio
    from string import Template

    from pyodide.code import run_js

    PYODIDE1_FLAG = "pyodide1"
    PYODIDE2_FLAG = "pyodide2"

    # setup the pyodide objects in js and return them to the python code
    setup_creation_in_js = Template(
        """
        async function set_pyodide_objects() {
            let pyodide1 = await loadPyodide();
            let pyodide2 = await loadPyodide();

            await pyodide1.FS.mkdir("${PYODIDE1_DIR}");
            await pyodide2.FS.mkdir("${PYODIDE2_DIR}");

            await pyodide2.FS.mount(
                pyodide2.FS.filesystems.PROXYFS,
                {
                    root: "${PYODIDE1_DIR}",
                    fs: pyodide1.FS,
                },
                "${PYODIDE2_DIR}"
            );
            self.pyodide1 = pyodide1;
            self.pyodide2 = pyodide2;
            return [pyodide1, pyodide2];
        }
        set_pyodide_objects();
        """
    )

    # setup the python code to write to the file in shared directory mounted in both pyodide objects
    # this code is executed in both pyodide objects
    setup_creation_in_python = Template(
        """
        import os

        with open("${MOUNT_DIR}/file_from_${FILE_SUFFIX}.txt", "w", encoding="utf-8") as f:
            f.write("${CONTENT}")
        """
    )

    # test the python code to read the file in shared directory mounted in both pyodide objects
    # this code is executed in both pyodide objects
    test_creation_in_python = Template(
        """
        # Test os.exists
        assert os.path.exists("${MOUNT_DIR}/file_from_${FILE_SUFFIX_1}.txt") is True
        assert os.path.exists("${MOUNT_DIR}/file_from_${FILE_SUFFIX_2}.txt") is True
        assert os.path.exists("${MOUNT_DIR}/file_from_nowhere.txt") is False

        # Test os.path.isfile and os.path.isdir
        assert os.path.isfile("${MOUNT_DIR}/file_from_${FILE_SUFFIX_1}.txt") is True
        assert os.path.isfile("${MOUNT_DIR}/file_from_${FILE_SUFFIX_2}.txt") is True
        assert os.path.isfile("${MOUNT_DIR}/file_from_nowhere.txt") is False
        assert os.path.isdir("${MOUNT_DIR}/file_from_${FILE_SUFFIX_1}.txt") is False
        assert os.path.isdir("${MOUNT_DIR}/file_from_${FILE_SUFFIX_2}.txt") is False
        assert os.path.isdir("${MOUNT_DIR}/file_from_nowhere.txt") is False
        assert os.path.isdir("${MOUNT_DIR}") is True
        assert os.path.isfile("${MOUNT_DIR}") is False

        # Test os.listdir
        assert set(os.listdir("${MOUNT_DIR}")) == { "file_from_${FILE_SUFFIX_1}.txt", "file_from_${FILE_SUFFIX_2}.txt" }

        # Test file reading
        with open("${MOUNT_DIR}/file_from_${FILE_SUFFIX_1}.txt", "r", encoding="utf-8") as f:
            content = f.read()
        assert content == "${CONTENT_1}"

        with open("${MOUNT_DIR}/file_from_${FILE_SUFFIX_2}.txt", "r", encoding="utf-8") as f:
            content = f.read()
        assert content == "${CONTENT_2}"

        # Test os.path.getsize
        file1_size = os.path.getsize("${MOUNT_DIR}/file_from_${FILE_SUFFIX_1}.txt")
        file2_size = os.path.getsize("${MOUNT_DIR}/file_from_${FILE_SUFFIX_2}.txt")
        assert file1_size == len("${CONTENT_1}".encode("utf-8"))
        assert file2_size == len("${CONTENT_2}".encode("utf-8"))

        # Test os.stat
        stat_info1 = os.stat("${MOUNT_DIR}/file_from_${FILE_SUFFIX_1}.txt")
        stat_info2 = os.stat("${MOUNT_DIR}/file_from_${FILE_SUFFIX_2}.txt")
        assert stat_info1.st_size == len("${CONTENT_1}".encode("utf-8"))
        assert stat_info2.st_size == len("${CONTENT_2}".encode("utf-8"))
        """
    )

    setup_removal_in_js = Template(
        """
        async function remove_directory() {
            await self.pyodide2.FS.unmount("${PYODIDE2_DIR}");
            await self.pyodide2.FS.rmdir("${PYODIDE2_DIR}");
            await self.pyodide1.FS.unlink("${PYODIDE1_DIR}/file_from_${FILE_SUFFIX_1}.txt");
            await self.pyodide1.FS.unlink("${PYODIDE1_DIR}/file_from_${FILE_SUFFIX_2}.txt");
            await self.pyodide1.FS.rmdir("${PYODIDE1_DIR}");
        }
        remove_directory();
        """
    )

    test_removal_in_python = Template(
        """
        assert os.path.exists("${MOUNT_DIR}") is False
        assert os.path.exists("${MOUNT_DIR}") is False
        assert os.path.isfile("${MOUNT_DIR}") is False
        assert os.path.isfile("${MOUNT_DIR}") is False
        assert os.path.isdir("${MOUNT_DIR}") is False
        assert os.path.isdir("${MOUNT_DIR}") is False

        assert os.path.exists("${MOUNT_DIR}/file_from_${FILE_SUFFIX_1}.txt") is False
        assert os.path.exists("${MOUNT_DIR}/file_from_${FILE_SUFFIX_2}.txt") is False
        assert os.path.isfile("${MOUNT_DIR}/file_from_${FILE_SUFFIX_1}.txt") is False
        assert os.path.isfile("${MOUNT_DIR}/file_from_${FILE_SUFFIX_2}.txt") is False
        assert os.path.isdir("${MOUNT_DIR}/file_from_${FILE_SUFFIX_1}.txt") is False
        assert os.path.isdir("${MOUNT_DIR}/file_from_${FILE_SUFFIX_2}.txt") is False
        """
    )

    set_pyodide_objects = run_js(
        setup_creation_in_js.substitute(
            PYODIDE1_DIR=f"/{PYODIDE1_FLAG}", PYODIDE2_DIR=f"/{PYODIDE2_FLAG}"
        )
    )
    asyncio.run(set_pyodide_objects)

    pyodides = set_pyodide_objects.result()
    pyodide1 = pyodides[0]
    pyodide2 = pyodides[1]

    for pyodide, pyodide_flag in zip(
        [pyodide1, pyodide2], [PYODIDE1_FLAG, PYODIDE2_FLAG], strict=True
    ):
        pyodide.runPython(
            setup_creation_in_python.substitute(
                MOUNT_DIR=f"/{pyodide_flag}",
                FILE_SUFFIX=pyodide_flag,
                CONTENT=pyodide_flag,
            )
        )

    for pyodide, pyodide_flag in zip(
        [pyodide1, pyodide2], [PYODIDE1_FLAG, PYODIDE2_FLAG], strict=True
    ):
        pyodide.runPython(
            test_creation_in_python.substitute(
                MOUNT_DIR=f"/{pyodide_flag}",
                FILE_SUFFIX_1=PYODIDE1_FLAG,
                FILE_SUFFIX_2=PYODIDE2_FLAG,
                CONTENT_1=PYODIDE1_FLAG,
                CONTENT_2=PYODIDE2_FLAG,
            )
        )

    remove_directory = run_js(
        setup_removal_in_js.substitute(
            PYODIDE1_DIR=f"/{PYODIDE1_FLAG}",
            PYODIDE2_DIR=f"/{PYODIDE2_FLAG}",
            FILE_SUFFIX_1=PYODIDE1_FLAG,
            FILE_SUFFIX_2=PYODIDE2_FLAG,
        )
    )
    asyncio.run(remove_directory)

    for pyodide, pyodide_flag in zip(
        [pyodide1, pyodide2], [PYODIDE1_FLAG, PYODIDE2_FLAG], strict=True
    ):
        pyodide.runPython(
            test_removal_in_python.substitute(
                MOUNT_DIR=f"/{pyodide_flag}",
                FILE_SUFFIX_1=PYODIDE1_FLAG,
                FILE_SUFFIX_2=PYODIDE1_FLAG,
            )
        )
