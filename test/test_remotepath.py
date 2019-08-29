

def test_runpythonasync_remotepath_single(selenium):
    selenium.run_js("""
        pyodide.remotePath = "/test/remotepath";
    """)

    result = selenium.run_async("""
        import single
        single.name
    """)

    assert result == "single"


def test_runpythonasync_remotepath_folder(selenium):
    selenium.run_js("""
        pyodide.remotePath = "/test/remotepath";
    """)

    result = selenium.run_async("""
        import folder
        folder.name
    """)

    assert result == "folder"


def test_runpythonasync_remotepath_xyz(selenium):
    selenium.run_js("""
        pyodide.remotePath = "/test/remotepath";
    """)

    result = selenium.run_async("""
        import xyz
        xyz.name
    """)

    assert result == "xyz"


def test_runpythonasync_remotepath_mixedimports(selenium):
    selenium.run_js("""
        pyodide.remotePath = ["/test/remotepath"];
    """)

    result = selenium.run_async("""
        import mixedimports
        mixedimports.result
    """)

    assert len(result) == 2
    assert result[0] == "xyz"
    assert isinstance(result[1], str)
