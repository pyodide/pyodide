import re

import pytest

xfail = pytest.mark.xfail
skip = pytest.mark.skip

fp_exception_msg = (
    "no floating point exceptions, "
    "see https://github.com/numpy/numpy/pull/21895#issuecomment-1311525881"
)
process_msg = "no process support"
thread_msg = "no thread support"
todo_signature_mismatch_msg = "TODO signature mismatch"
todo_memory_corruption_msgt = "TODO memory corruption"
todo_genuine_difference_msg = "TODO genuine difference to be investigated"
todo_fp_exception_msg = "TODO did not raise maybe no floating point exception support?"


tests_to_mark = [
    # scipy/_lib/tests
    (
        "test__threadsafety.py::test_parallel_threads",
        xfail,
        thread_msg,
    ),
    ("test__threadsafety.py::test_parallel_threads", xfail, thread_msg),
    ("test__util.py::test_pool", xfail, process_msg),
    ("test__util.py::test_mapwrapper_parallel", xfail, process_msg),
    ("test_ccallback.py::test_threadsafety", xfail, thread_msg),
    ("test_import_cycles.py::test_modules_importable", xfail, process_msg),
    ("test_import_cycles.py::test_public_modules_importable", xfail, process_msg),
    # scipy/datasets/tests
    ("test_data.py::TestDatasets", xfail, "TODO datasets not working right now"),
    # scipy/fft/tests
    (
        r"test_basic.py::TestFFT1D.test_dtypes\[float32-numpy\]",
        xfail,
        "TODO small floating point difference on the CI but not locally",
    ),
    ("test_basic.py::TestFFTThreadSafe", xfail, thread_msg),
    ("test_basic.py::test_multiprocess", xfail, process_msg),
    ("test_fft_function.py::test_fft_function", xfail, process_msg),
    ("test_multithreading.py::test_threaded_same", xfail, thread_msg),
    (
        "test_multithreading.py::test_mixed_threads_processes",
        xfail,
        thread_msg,
    ),
    # scipy/integrate tests
    ("test__quad_vec.py::test_quad_vec_pool", xfail, process_msg),
    (
        "test_quadpack.py.+TestCtypesQuad.test_ctypes.*",
        xfail,
        "Test relying on finding libm.so shared library",
    ),
    (
        "test_quadrature.py.+TestQMCQuad.test_basic",
        xfail,
        todo_genuine_difference_msg,
    ),
    (
        "test_quadrature.py.+TestQMCQuad.test_sign",
        xfail,
        todo_genuine_difference_msg,
    ),
    # scipy/interpolate
    (
        "test_fitpack.+test_kink",
        xfail,
        "TODO error not raised, maybe due to no floating point exception?",
    ),
    # scipy/io
    (
        "test_mmio.py::.+fast_matrix_market",
        xfail,
        thread_msg,
    ),
    (
        "test_mmio.py::TestMMIOCoordinate.test_precision",
        xfail,
        thread_msg,
    ),
    (
        "test_paths.py::TestPaths.test_mmio_(read|write)",
        xfail,
        thread_msg,
    ),
    # scipy/linalg tests
    ("test_blas.+test_complex_dotu", skip, todo_signature_mismatch_msg),
    ("test_cython_blas.+complex", skip, todo_signature_mismatch_msg),
    ("test_lapack.py.+larfg_larf", skip, todo_signature_mismatch_msg),
    # scipy/ndimage/tests
    ("test_filters.py::TestThreading", xfail, thread_msg),
    # scipy/optimize/tests
    (
        "test__differential_evolution.py::"
        "TestDifferentialEvolutionSolver.test_immediate_updating",
        xfail,
        process_msg,
    ),
    (
        "test__differential_evolution.py::TestDifferentialEvolutionSolver.test_parallel",
        xfail,
        process_msg,
    ),
    (
        "test__shgo.py.+test_19_parallelization",
        xfail,
        process_msg,
    ),
    (
        "test__shgo.py.+",
        xfail,
        "Test failing on 32bit (skipped on win32)",
    ),
    (
        "test_linprog.py::TestLinprogSimplexNoPresolve.test_bounds_infeasible_2",
        xfail,
        "TODO no warnings emitted maybe due to no floating point exception?",
    ),
    ("test_minpack.py::TestFSolve.test_concurrent.+", xfail, process_msg),
    ("test_minpack.py::TestLeastSq.test_concurrent+", xfail, process_msg),
    ("test_optimize.py::test_cobyla_threadsafe", xfail, thread_msg),
    ("test_optimize.py::TestBrute.test_workers", xfail, process_msg),
    # scipy/signal/tests
    (
        "test_signaltools.py::TestMedFilt.test_medfilt2d_parallel",
        xfail,
        thread_msg,
    ),
    # scipy/sparse/tests
    ("test_arpack.py::test_parallel_threads", xfail, thread_msg),
    ("test_array_api.py::test_sparse_dense_divide", xfail, fp_exception_msg),
    ("test_linsolve.py::TestSplu.test_threads_parallel", xfail, thread_msg),
    ("test_propack", skip, todo_signature_mismatch_msg),
    ("test_sparsetools.py::test_threads", xfail, thread_msg),
    # scipy/sparse/csgraph/tests
    ("test_shortest_path.py::test_gh_17782_segfault", xfail, thread_msg),
    # scipy/sparse/linalg/tests
    ("test_svds.py::Test_SVDS_PROPACK", skip, todo_signature_mismatch_msg),
    # scipy/spatial/tests
    (
        "test_kdtree.py::test_query_ball_point_multithreading",
        xfail,
        thread_msg,
    ),
    ("test_kdtree.py::test_ckdtree_parallel", xfail, thread_msg),
    # scipy/special/tests
    (
        "test_exponential_integrals.py::TestExp1.test_branch_cut",
        xfail,
        "TODO maybe float support since +0 and -0 difference",
    ),
    (
        "test_round.py::test_add_round_(up|down)",
        xfail,
        "TODO small floating point difference, maybe due to lack of floating point "
        "support for controlling rounding, see "
        "https://github.com/WebAssembly/design/issues/1384",
    ),
    (
        # This test is skipped for PyPy as well, maybe for a related reason?,
        # see
        # https://github.com/conda-forge/scipy-feedstock/pull/196#issuecomment-979317832
        "test_distributions.py::TestBeta.test_boost_eval_issue_14606",
        skip,
        "TODO C++ exception that causes a Pyodide fatal error",
    ),
    # The following four tests do not raise the required
    # <class 'scipy.special._sf_error.SpecialFunctionError'>
    (
        "test_basic.py::test_error_raising",
        xfail,
        todo_fp_exception_msg,
    ),
    (
        "test_sf_error.py::test_errstate_pyx_basic",
        xfail,
        todo_fp_exception_msg,
    ),
    (
        "test_sf_error.py::test_errstate_cpp_scipy_special",
        xfail,
        todo_fp_exception_msg,
    ),
    (
        "test_sf_error.py::test_errstate_cpp_alt_ufunc_machinery",
        xfail,
        todo_fp_exception_msg,
    ),
    (
        "test_kdeoth.py::test_kde_[12]d",
        xfail,
        todo_genuine_difference_msg,
    ),
    (
        "test_multivariate.py::TestMultivariateT.test_cdf_against_generic_integrators",
        skip,
        "TODO tplquad integration does not seem to converge",
    ),
    (
        "test_multivariate.py::TestCovariance.test_mvn_with_covariance_cdf.+Precision-size1",
        xfail,
        "TODO small floating point difference 6e-7 relative diff instead of 1e-7",
    ),
    (
        "test_multivariate.py::TestMultivariateNormal.test_logcdf_default_values",
        xfail,
        todo_genuine_difference_msg,
    ),
    (
        "test_multivariate.py::TestMultivariateNormal.test_broadcasting",
        xfail,
        todo_genuine_difference_msg,
    ),
    (
        "test_multivariate.py::TestMultivariateNormal.test_normal_1D",
        xfail,
        todo_genuine_difference_msg,
    ),
    (
        "test_multivariate.py::TestMultivariateNormal.test_R_values",
        xfail,
        todo_genuine_difference_msg,
    ),
    (
        "test_multivariate.py::TestMultivariateNormal.test_cdf_with_lower_limit",
        xfail,
        todo_genuine_difference_msg,
    ),
    (
        "test_multivariate.py::TestMultivariateT.test_cdf_against_multivariate_normal",
        xfail,
        todo_genuine_difference_msg,
    ),
    ("test_qmc.py::TestVDC.test_van_der_corput", xfail, thread_msg),
    ("test_qmc.py::TestHalton.test_workers", xfail, thread_msg),
    ("test_qmc.py::TestUtils.test_discrepancy_parallel", xfail, thread_msg),
    (
        "test_qmc.py::TestMultivariateNormalQMC.test_validations",
        xfail,
        todo_fp_exception_msg,
    ),
    (
        "test_qmc.py::TestMultivariateNormalQMC.test_MultivariateNormalQMCDegenerate",
        xfail,
        todo_genuine_difference_msg,
    ),
    ("test_sampling.py::test_threading_behaviour", xfail, thread_msg),
    ("test_stats.py::TestMGCStat.test_workers", xfail, process_msg),
    (
        "test_stats.py::TestKSTwoSamples.testLargeBoth",
        skip,
        "TODO test taking > 5 minutes after scipy 1.10.1 update",
    ),
    (
        "test_stats.py::TestKSTwoSamples.test_some_code_paths",
        xfail,
        todo_fp_exception_msg,
    ),
    (
        "test_stats.py::TestGeometricStandardDeviation.test_raises_value_error",
        xfail,
        todo_fp_exception_msg,
    ),
    (
        "test_stats.py::TestBrunnerMunzel.test_brunnermunzel_normal_dist",
        xfail,
        fp_exception_msg,
    ),
]


def pytest_collection_modifyitems(config, items):
    for item in items:
        path, line, name = item.reportinfo()
        path = str(path)
        full_name = f"{path}::{name}"
        for pattern, mark, reason in tests_to_mark:
            if re.search(pattern, full_name):
                # print(full_name)
                item.add_marker(mark(reason=reason))
