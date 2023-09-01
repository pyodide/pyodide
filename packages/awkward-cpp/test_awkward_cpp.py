from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["awkward-cpp"])
def test_awkward_cpp(selenium):
    # Test a single kernel
    import ctypes

    import numpy as np
    from awkward_cpp.cpu_kernels import lib

    num_null = np.array([123], dtype=np.int64)
    mask = np.array([1, 1, 0, 1, 1, 0], dtype=np.int8)
    length = 6
    valid_when = True

    kernel_impl = lib.awkward_ByteMaskedArray_numnull
    args = [
        ctypes.cast(num_null.ctypes, kernel_impl.argtypes[0]),  # type: ignore[arg-type]
        ctypes.cast(mask.ctypes, kernel_impl.argtypes[1]),  # type: ignore[arg-type]
        length,
        valid_when,
    ]

    ret_pass = kernel_impl(*args)
    assert ret_pass.str is None
    assert num_null[0] == 2
