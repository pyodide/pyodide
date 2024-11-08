from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["zfpy", "numpy"])
def test_compression(selenium):
    import numpy as np
    import zfpy

    my_array = np.arange(1, 20)
    compressed_data = zfpy.compress_numpy(my_array)
    decompressed_array = zfpy.decompress_numpy(compressed_data)
    np.testing.assert_array_equal(my_array, decompressed_array)


@run_in_pyodide(packages=["zfpy", "numpy"])
def test_compression_with_tolerance(selenium):
    import numpy as np
    import zfpy

    my_array = np.linspace(0, 1, 1000)
    compressed_data = zfpy.compress_numpy(my_array, tolerance=1e-3)
    decompressed_array = zfpy.decompress_numpy(compressed_data)
    np.testing.assert_allclose(my_array, decompressed_array, atol=1e-3)


@run_in_pyodide(packages=["zfpy", "numpy"])
def test_different_dimensions(selenium) -> None:
    import numpy as np
    import zfpy

    np.random.seed(42)

    # Test arrays; from 1D to 4D
    for dimensions in range(1, 5):
        # 1. test with uniform dimensions
        shape1 = tuple([5] * dimensions)
        array = np.random.rand(*shape1).astype(np.float64)
        compressed1 = zfpy.compress_numpy(array, write_header=True)
        decompressed1 = zfpy.decompress_numpy(compressed1)
        np.testing.assert_array_equal(decompressed1, array)

        # 2. test with increasing dimensions
        shape2 = tuple(range(2, 2 + dimensions))
        array = np.random.rand(*shape2).astype(np.float64)
        compressed2 = zfpy.compress_numpy(array, write_header=True)
        decompressed2 = zfpy.decompress_numpy(compressed2)
        np.testing.assert_array_equal(decompressed2, array)


@run_in_pyodide(packages=["zfpy", "numpy"])
def test_different_dtypes(selenium) -> None:
    """Test ZFP compression/decompression with different numeric dtypes."""
    import numpy as np
    import zfpy

    np.random.seed(42)

    shape = (5, 5)
    num_elements = np.prod(shape)

    # Test floating-point types
    for dtype in [np.float32, np.float64]:
        elements = np.random.random_sample(num_elements)
        array = np.reshape(elements, shape).astype(dtype)
        compressed1 = zfpy.compress_numpy(array, write_header=True)
        decompressed1 = zfpy.decompress_numpy(compressed1)
        np.testing.assert_array_equal(decompressed1, array)

    # Test integer types
    for dtype in [np.int32, np.int64]:
        array = np.random.randint(low=-(2**30), high=2**30, size=shape, dtype=dtype)
        compressed2 = zfpy.compress_numpy(array, write_header=True)
        decompressed2 = zfpy.decompress_numpy(compressed2)
        np.testing.assert_array_equal(decompressed2, array)
