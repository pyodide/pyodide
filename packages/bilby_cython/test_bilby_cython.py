from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["bilby_cython"])
def test_time_delay_from_geocenter(selenium):
    import bilby_cython
    import numpy as np
    assert abs(
        bilby_cython.geometry.time_delay_from_geocenter(np.array([30000.0, 40000.0, 50000.0]), 6.0, 7.0, 8.0)
        - 1.5504686860116492e-05
    ) < 1e-10


@run_in_pyodide(packages=["bilby_cython"])
def test_frame_conversion(selenium):
    import bilby_cython
    import numpy as np
    theta, phi = bilby_cython.geometry.zenith_azimuth_to_theta_phi(7.0, 8.0, np.array([30000.0, 40000.0, 50000.0]))
    assert abs(theta - 1.3005416123794573) < 1e-5
    assert abs(phi - 1.5202320529440563) < 1e-5


@run_in_pyodide(packages=["bilby_cython"])
def test_polarization_tensor(selenium):
    import bilby_cython
    import numpy as np
    np.testing.assert_array_almost_equal(
        bilby_cython.geometry.get_polarization_tensor(3.0, 4.0, 5.0, 6.0, "plus"),
        np.array([
            [0.35242077, -0.75868979, 0.485414],
            [-0.75868979, 0.00811582, 0.2482672],
            [0.485414, 0.2482672, -0.36053659],
        ])
    )


@run_in_pyodide(packages=["bilby_cython"])
def test_detector_tensor(selenium):
    import bilby_cython
    import numpy as np
    np.testing.assert_array_almost_equal(
        bilby_cython.geometry.detector_tensor(np.array([2.0, 3.0, 4.0]), np.array([5.0, 6.0, 7.0])),
        np.array([
            [-10.5, -12. , -13.5],
            [-12. , -13.5, -15. ],
            [-13.5, -15. , -16.5],
        ])
    )


@run_in_pyodide(packages=["bilby_cython"])
def test_greenwich_sidereal_time(selenium):
    import bilby_cython
    assert abs(bilby_cython.time.greenwich_sidereal_time(1400000000.0, 3.0)- 56098.53252485254) < 1e-5
