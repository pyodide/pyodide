import time


def test_install_simple(selenium_standalone):
    selenium_standalone.run("import os")
    selenium_standalone.load_package("micropip")
    selenium_standalone.run("import micropip")
    selenium_standalone.run("micropip.install('pyodide-micropip-test')")
    # Package 'pyodide-micropip-test' has dependency on 'snowballstemmer'
    # It is used to test markers support

    for i in range(10):
        if selenium_standalone.run(
                "os.path.exists"
                "('/lib/python3.6/site-packages/snowballstemmer')"
        ):
            break
        else:
            time.sleep(1)

    selenium_standalone.run("import snowballstemmer")
    selenium_standalone.run("stemmer = snowballstemmer.stemmer('english')")
    assert selenium_standalone.run(
        "stemmer.stemWords('go going goes gone'.split())") == [
            'go', 'go', 'goe', 'gone'
        ]
