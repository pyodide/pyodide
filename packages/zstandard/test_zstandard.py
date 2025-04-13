import pytest
from pytest_pyodide import run_in_pyodide


# Run tests against both the C extension and the CFFI backend
@run_in_pyodide(packages=["zstandard"])
def set_zstd_backend(selenium, backend):
    import zstandard as zstd

    zstd.backend = backend


@pytest.fixture(params=["cext", "cffi"], autouse=True)
def zstd_backend(selenium, request):
    # Runs in host, request not pickleable so we can't send it to Pyodide.
    # Look up `request.param` which is a string hence pickleable and send that to Pyodide
    backend = request.param
    set_zstd_backend(selenium, backend)


# ------- Some compression tests ----------------------------------------------


@run_in_pyodide(packages=["zstandard"])
def test_zstandard_compression_and_decompression(selenium):
    import zstandard as zstd

    data = b"foo"
    compress = zstd.ZstdCompressor(
        write_checksum=True, write_content_size=True
    ).compress
    decompress = zstd.ZstdDecompressor().decompress

    assert decompress(compress(data)) == data


@run_in_pyodide(packages=["zstandard"])
def test_zstandard_compression_and_decompression_with_level(selenium):
    import zstandard as zstd

    data = b"foo"
    compress = zstd.ZstdCompressor(
        level=1, write_checksum=True, write_content_size=True
    ).compress
    decompress = zstd.ZstdDecompressor().decompress

    assert decompress(compress(data)) == data


@run_in_pyodide(packages=["zstandard"])
def test_compress_empty(selenium):
    import zstandard as zstd

    cctx = zstd.ZstdCompressor(level=1, write_content_size=False)

    result = cctx.compress(b"")
    assert result == b"\x28\xb5\x2f\xfd\x00\x00\x01\x00\x00"

    params = zstd.get_frame_parameters(result)
    assert params.window_size == 1024
    assert params.dict_id == 0
    assert params.has_checksum is False

    cctx = zstd.ZstdCompressor()
    result = cctx.compress(b"")
    assert result == b"\x28\xb5\x2f\xfd\x20\x00\x01\x00\x00"
    params = zstd.get_frame_parameters(result)
    assert params.content_size == 0


@run_in_pyodide(packages=["zstandard"])
def test_compress_large(selenium):
    import struct

    import zstandard as zstd

    chunks = []
    for i in range(255):
        chunks.append(struct.Struct(">B").pack(i) * 16384)

    cctx = zstd.ZstdCompressor(level=3, write_content_size=False)
    result = cctx.compress(b"".join(chunks))
    assert len(result) == 999
    assert result[0:4] == b"\x28\xb5\x2f\xfd"

    cctx = zstd.ZstdCompressor(level=1, write_content_size=False)
    result = cctx.compress(b"f" * zstd.COMPRESSION_RECOMMENDED_INPUT_SIZE + b"o")
    assert (
        result == b"\x28\xb5\x2f\xfd\x00\x40\x54\x00\x00"
        b"\x10\x66\x66\x01\x00\xfb\xff\x39\xc0"
        b"\x02\x09\x00\x00\x6f"
    )


# ------- Some decompression tests --------------------------------------------


@run_in_pyodide(packages=["zstandard"])
def test_empty(selenium):
    import zstandard as zstd

    cctx = zstd.ZstdCompressor()
    frame = cctx.compress(b"")

    assert zstd.frame_content_size(frame) == 0


@run_in_pyodide(packages=["zstandard"])
def test_basic(selenium):
    import zstandard as zstd

    cctx = zstd.ZstdCompressor()
    frame = cctx.compress(b"foobar")

    assert zstd.frame_content_size(frame) == 6


@run_in_pyodide(packages=["zstandard"])
def test_dictionary(selenium):
    import zstandard as zstd

    samples = []
    for _ in range(128):
        samples.append(b"foo" * 64)
        samples.append(b"bar" * 64)
        samples.append(b"foobar" * 64)
        samples.append(b"qwert" * 64)
        samples.append(b"yuiop" * 64)
        samples.append(b"asdfg" * 64)
        samples.append(b"hijkl" * 64)

    d = zstd.train_dictionary(8192, samples)

    orig = b"foobar" * 16384
    cctx = zstd.ZstdCompressor(level=1, dict_data=d)
    compressed = cctx.compress(orig)

    dctx = zstd.ZstdDecompressor(dict_data=d)
    decompressed = dctx.decompress(compressed)

    assert decompressed == orig
