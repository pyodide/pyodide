from pytest_pyodide import run_in_pyodide


@run_in_pyodide(
    packages=["platformdirs"],
)
def test_platformdirs_basic(selenium):
    import platformdirs

    app_dirs = platformdirs.PlatformDirs(appname="testapp", appauthor="testauthor")
    user_data_dir = app_dirs.user_data_dir
    user_config_dir = app_dirs.user_config_dir

    # In Pyodide, these asserts should return paths that make sense
    # in the browser context based on a browser-based file system (or
    # a Node.js based one)
    assert isinstance(user_data_dir, str)
    assert isinstance(user_config_dir, str)
    assert len(user_data_dir) > 0
    assert len(user_config_dir) > 0

    # Test that the appname is included in the paths
    assert "testapp" in user_data_dir.lower() or "testapp" in user_config_dir.lower()
