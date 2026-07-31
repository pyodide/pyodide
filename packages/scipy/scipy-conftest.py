import random
import re
import threading

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
todo_overflow_msg = "TODO overflow not raised"
todo_runtime_warning = "TODO runtime warning not shown"


tests_to_mark = [
    ("test_odeint_jac\\.py", skip, "test module removed: uses Fortran extension not built for WASM"),
    ("io/tests/test_fortran\\.py", skip, "test module removed: uses Fortran extension not built for WASM"),
    # scipy/_lib/tests
    (
        "test__threadsafety.py::test_parallel_threads",
        xfail,
        thread_msg,
    ),
    ("test__threadsafety.py::test_parallel_threads", xfail, thread_msg),
    ("test__util.py::test_pool", xfail, process_msg),
    ("test__util.py::test_mapwrapper_parallel", xfail, process_msg),
    ("test__util.py::test__workers_wrapper", xfail, process_msg),
    ("test_ccallback.py::test_threadsafety", xfail, thread_msg),
    ("test_import_cycles.py::test_modules_importable", xfail, process_msg),
    ("test_import_cycles.py::test_public_modules_importable", xfail, process_msg),
    # scipy/fft/tests
    (
        r"test_basic.py::TestFFT1D.test_dtypes\[float32-numpy\]",
        xfail,
        "TODO small floating point difference on the CI but not locally",
    ),
    ("test_basic.py::TestFFTThreadSafe", xfail, thread_msg),
    ("test_basic.py::test_multiprocess", xfail, process_msg),
    ("test_fft_function.py::test_fft_function", xfail, process_msg),
    (
        "test_multithreading.py::test_mixed_threads_processes",
        xfail,
        thread_msg,
    ),
    # scipy/integrate tests
    ("test__quad_vec.py::TestQuadVec.test_quad_vec_pool.*", xfail, process_msg),
    (
        "test_quadpack.py.+TestCtypesQuad.test_ctypes.*",
        xfail,
        "Test relying on finding libm.so shared library",
    ),
    # scipy/interpolate
    (
        "test_fitpack.+test_kink",
        xfail,
        "TODO error not raised, maybe due to no floating point exception?",
    ),
    (
        "test_rbf.py::test_rbf_concurrency",
        xfail,
        thread_msg,
    ),
    # scipy/io
    ("test_mmio.py::.+fast_matrix_market", skip, thread_msg),
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
    ("test_cython_abi.py::test_cython_blas_abi_stability", xfail, todo_signature_mismatch_msg),
    ("test_cython_abi.py::test_cython_lapack_abi_stability", xfail, todo_signature_mismatch_msg),
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
        "test_linprog.py::TestLinprogSimplexNoPresolve.test_bounds_infeasible_2",
        xfail,
        "TODO no warnings emitted maybe due to no floating point exception?",
    ),
    ("test_minpack.py::TestFSolve.test_concurrent.+", xfail, process_msg),
    ("test_minpack.py::TestLeastSq.test_concurrent.+", xfail, process_msg),
    ("test_optimize.py::test_cobyla_threadsafe", xfail, thread_msg),
    ("test_optimize.py::TestBrute.test_workers", xfail, process_msg),
    (
        "test__numdiff.py::TestApproxDerivativesDense.test_scalar_vector",
        xfail,
        process_msg,
    ),
    (
        "test__numdiff.py::TestApproxDerivativesDense.test_workers_evaluations_and_nfev",
        xfail,
        process_msg,
    ),
    (
        "test__numdiff.py::TestApproxDerivativesDense.test_vector_vector",
        xfail,
        process_msg,
    ),
    (
        "test__numdiff.py::TestApproxDerivativeSparse.test_all",
        xfail,
        process_msg,
    ),
    (
        ".*test_workers.*",
        xfail,
        process_msg,
    ),
    # workers=None passes (uses no multiprocessing), workers=N fails
    (
        "test_optimize.py::TestWorkers.+-[0-9]+\\]",
        xfail,
        process_msg,
    ),
    (
        "test_optimize.py::test_multiprocessing_too_many_open_files_23080",
        xfail,
        process_msg,
    ),
    # scipy/signal/tests
    # N=963 float32 passes, but N=964 float32 exceeds atol=1e-5 by a tiny margin on WASM
    (
        "test_fir_filter_design.py::TestMinimumPhase.+test_nyquist.+float32-964",
        xfail,
        todo_genuine_difference_msg,
    ),
    (
        "test_signaltools.py::TestMedFilt.test_medfilt2d_parallel",
        xfail,
        thread_msg,
    ),
    # scipy/sparse/linalg/_isolve/tests
    # rand-sym-pd with float32 (-F-) doesn't converge, but all other tfqmr variants pass as of 1.18.
    (
        "test_iterative.py.+(test_convergence|test_precond_dummy).+rand-sym-pd-F-tfqmr",
        xfail,
        todo_genuine_difference_msg,
    ),
    # scipy/sparse/tests
    ("test_arpack.py::test_parallel_threads", xfail, thread_msg),
    ("test_array_api.py::test_sparse_dense_divide", xfail, fp_exception_msg),
    ("test_linsolve.py::TestSplu.test_threads_parallel", xfail, thread_msg),
    ("test_sparsetools.py::test_threads", xfail, thread_msg),
    # scipy/sparse/csgraph/tests
    ("test_shortest_path.py::test_gh_17782_segfault", xfail, thread_msg),
    # scipy/sparse/linalg/tests
    # scipy/spatial/tests
    (
        "test_kdtree.py::test_query_ball_point_multithreading",
        xfail,
        thread_msg,
    ),
    ("test_kdtree.py::test_ckdtree_parallel", xfail, thread_msg),
    (
        "test_kdtree.py::test_query_ball_point_multithreaded_workers",
        xfail,
        thread_msg,
    ),
    (
        "test_kdtree.py::test_query_ball_point_multithreaded_explicit",
        xfail,
        thread_msg,
    ),
    ("test_kdtree.py::test_multithreaded_tree_access", xfail, thread_msg),
    # scipy/special/tests
    (
        "test_round.py::test_add_round_(up|down)",
        xfail,
        "TODO small floating point difference, maybe due to lack of floating point "
        "support for controlling rounding, see "
        "https://github.com/WebAssembly/design/issues/1384",
    ),
    (
        "test_sf_error.py::test_check_overflow_message",
        xfail,
        todo_overflow_msg,
    ),
    ("test_qmc.py::TestVDC.test_van_der_corput", xfail, thread_msg),
    ("test_qmc.py::TestHalton.test_workers", xfail, thread_msg),
    (
        "test_qmc.py::TestUtils.test_discrepancy_parallel",
        skip,
        "thread constructor fails and leaves C destructor with WASM function-pointer mismatch, causing a fatal error during pytest GC cleanup",
    ),
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
        "Marked @pytest.mark.slow upstream. There's an n=10kx11k exact KS computation "
        "here that still takes >5 minutes after the vectorisation efforts done in 1.18",
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
    (
        "test_fit.py::test_fit_error",
        xfail,
        todo_runtime_warning,
    ),
    (
        "test_stats.py::TestWassersteinDistance.test_inf_values",
        xfail,
        todo_runtime_warning,
    ),
    (
        "test_stats.py::TestEnergyDistance.test_inf_values",
        xfail,
        todo_runtime_warning,
    ),
    # many
    (".*test_concurrency.*", xfail, thread_msg),
]


def pytest_configure(config):  # noqa: ARG001
    # threading.get_native_id is not available in Pyodide's WASM environment
    if not hasattr(threading, "get_native_id"):
        threading.get_native_id = lambda: random.randint(0, 10000)

    # pytest's gc_collect_harder triggers the garbage collector during cleanup.
    # FIXME: we can currently make it a no-op to let pytest finish normally, with
    # summary prints, and the correct exit code) without the fatal error. We need
    # a better way to handle this.
    try:
        import _pytest.unraisableexception as _ue

        _ue.gc_collect_harder = lambda *args, **kwargs: None
    except (ImportError, AttributeError):
        pass


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    # C-extension destructors in SciPy call Fortran functions with void/int
    # signature mismatches. These run both
    # during the gc cleanup (gc_collect_harder in _pytest/unraisableexception)
    # and during Python's own finalization sequence, causing fatal errors that
    # cannot be caught in Python as they crash the interpreter. Registering
    # os._exit as an atexit handler as LIFO can at least bypass both of these.
    # atexit is necessary for us here for allowing the terminal summary to
    # print, since that happens in the terminal reporter's own
    # pytest_sessionfinish which runs before this trylast hook.
    import atexit
    import os

    atexit.register(os._exit, int(exitstatus))


def pytest_collection_modifyitems(config, items):
    for item in items:
        path, line, name = item.reportinfo()
        full_name = f"{str(path)}::{name}"
        for pattern, mark, reason in tests_to_mark:
            if re.search(pattern, full_name):
                item.add_marker(mark(reason=reason))
