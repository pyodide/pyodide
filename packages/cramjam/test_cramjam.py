from typing import Any

import pytest
from pytest_pyodide import run_in_pyodide

VARIANTS = ("snappy", "brotli", "bzip2", "lz4", "gzip", "deflate", "zstd")


@pytest.mark.parametrize("variant_str", VARIANTS)
@run_in_pyodide(packages=["cramjam"])
def test_variants_simple(selenium, variant_str):
    import random

    import cramjam

    uncompressed: Any = [random.getrandbits(8) for x in range(1048576)]
    variant = getattr(cramjam, variant_str)

    uncompressed = bytearray(uncompressed)

    compressed = variant.compress(uncompressed)
    assert compressed.read() != uncompressed
    compressed.seek(0)
    assert isinstance(compressed, cramjam.Buffer)

    decompressed = variant.decompress(compressed, output_len=len(uncompressed))
    assert decompressed.read() == uncompressed
    assert isinstance(decompressed, cramjam.Buffer)
