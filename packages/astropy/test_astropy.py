import pytest

@pytest.mark.skip_refcount_check
@pytest.mark.parametrize(
    "package,specific_test",
    [
        ('constants','test_'),
        ('units','test_physical.py'),
        ('units','test_quantity.py'),
        ('units','test_quantity_ufuncs.py'),
        ('units','test_quantity_non_ufuncs.py'),
        ('units','test_units.py'),
        ('coordinates','test_angles.py'),
        ('coordinates','test_angular_separation.py'),
        ('coordinates','test_arrays.py'),
        ('coordinates','test_celestial_transformations.py'),
        ('coordinates','test_erfa_astrom.py'),
        ('coordinates','test_frames_with_velocity.py'),
        ('coordinates','test_icrs_observed_transformations.py'),
        ('coordinates','test_matching.py'),
        ('coordinates','test_representation.py and not test_unitphysics'),
        ('coordinates','test_sky_coord.py'),
        ('coordinates','test_sky_coord_velocities.py'),
        ('coordinates','test_transformations.py'),
        ('cosmology','test_base.py'),
        ('cosmology','test_lambdacdm.py'),
        ('cosmology','test_units.py'),
    ]
)
def test_astropy(selenium,package,specific_test):
    selenium.run_js(
        f"""await pyodide.loadPackage(['micropip','astropy']);
        const micropip = pyodide.pyimport("micropip");
        await micropip.install(['pytest','pytest_remotedata','pytest_doctestplus','pytest_astropy_header']);
        pyodide.runPython(`
            import pytest
            import astropy
            assert astropy.test(package='{package}',
                                verbose=False,
                                args="-k '{specific_test} and not thread'") == pytest.ExitCode.OK
        `);
        """
    )
