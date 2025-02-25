import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.parametrize("dtype", ["f4", "f8", "i4", "i8", "u4", "u8"])
@run_in_pyodide(packages=["pcodec", "numpy"])
def test_simple_round_trip(selenium, dtype):
    """Test basic compression and decompression with different dtypes."""
    import numpy as np
    from pcodec import ChunkConfig, standalone

    np.random.seed(42)

    data = np.random.uniform(0, 1000, size=100).astype(dtype)
    compressed = standalone.simple_compress(data, ChunkConfig())
    decompressed = standalone.simple_decompress(compressed)

    np.testing.assert_array_equal(data, decompressed)


@run_in_pyodide(packages=["pcodec", "numpy"])
def test_partial_decompression(selenium):
    """Test decompressing a part of the data into a smaller array."""
    import numpy as np
    from pcodec import ChunkConfig, standalone

    np.random.seed(42)

    data = np.random.uniform(0, 1000, size=50).astype(np.float32)
    compressed = standalone.simple_compress(data, ChunkConfig())

    out = np.zeros(10, dtype=np.float32)
    progress = standalone.simple_decompress_into(compressed, out)

    np.testing.assert_array_equal(out, data[:10])
    assert progress.n_processed == 10
    assert not progress.finished


@pytest.mark.parametrize("length", [0, 100, 1000])
@run_in_pyodide(packages=["pcodec", "numpy"])
def test_different_lengths(selenium, length):
    """Test compression/decompression with different array lengths."""
    import numpy as np
    from pcodec import ChunkConfig, standalone

    np.random.seed(42)

    data = np.random.uniform(0, 1000, size=length).astype(np.float64)

    compressed = standalone.simple_compress(data, ChunkConfig())
    decompressed = standalone.simple_decompress(compressed)

    np.testing.assert_array_equal(data, decompressed)
