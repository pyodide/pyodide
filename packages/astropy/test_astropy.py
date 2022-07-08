import pytest

astropy_js_test_setup= """await pyodide.loadPackage(['micropip','astropy']);
const micropip = pyodide.pyimport("micropip");
await micropip.install(['pytest','pytest_remotedata','pytest_doctestplus','pytest_astropy_header']);"""

astropy_test_verbosity= "False"

@pytest.mark.skip_refcount_check
def test_constants(selenium):
    selenium.run_js(
        f"""{astropy_js_test_setup}
        pyodide.runPython(`
            import pytest
            import astropy
            assert astropy.test(package='constants',
                                verbose={astropy_test_verbosity},
                                args="-k 'not test_angle_multithreading and not test_unitphysics'") == pytest.ExitCode.OK
        `);
        """
    )

@pytest.mark.skip_refcount_check
def test_coordinates(selenium):
    selenium.run_js(
        f"""{astropy_js_test_setup}
        pyodide.runPython(`
            import pytest
            import astropy
            assert astropy.test(package='coordinates',
                                verbose={astropy_test_verbosity},
                                args="-k 'not test_angle_multithreading and not test_unitphysics'") == pytest.ExitCode.OK
        `);
        """
    )

@pytest.mark.skip_refcount_check
def test_cosmology(selenium):
    selenium.run_js(
        f"""{astropy_js_test_setup}
        pyodide.runPython(`
            import pytest
            import astropy
            assert astropy.test(package='cosmology',
                                verbose={astropy_test_verbosity}) == pytest.ExitCode.OK
        `);
        """
    )

@pytest.mark.skip_refcount_check
def test_units(selenium):
    selenium.run_js(
        f"""{astropy_js_test_setup}
        pyodide.runPython(`
            import pytest
            import astropy
            assert astropy.test(package='units',
                                verbose={astropy_test_verbosity},
                                args="-k 'not test_thread_safety'") == pytest.ExitCode.OK
        `);
        """
    )
