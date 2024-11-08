from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["zfpy", "numpy"])
def test_zfpy(selenium):
    import numpy as np
    import zfpy
    my_array = np.arange(1, 20)
    compressed_data = zfpy.compress_numpy(my_array)
    decompressed_array = zfpy.decompress_numpy(compressed_data)
    print(compressed_data) # debug; checking if it's indeed a string
    print(decompressed_array)

    np.testing.assert_array_equal(my_array, decompressed_array)
    print("zfpy agriya test passed")

# Gotta add more tests before merging
