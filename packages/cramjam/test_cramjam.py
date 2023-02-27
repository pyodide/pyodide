import pytest
from pytest_pyodide import run_in_pyodide

import os
import gzip
import cramjam
import hashlib
from datetime import timedelta

VARIANTS = ("snappy", "brotli", "bzip2", "lz4", "gzip", "deflate", "zstd")

@pytest.mark.parametrize("is_bytearray", (True, False))
@pytest.mark.parametrize("variant_str", VARIANTS)
@run_in_pyodide(packages=["cramjam"])
def test_variants_simple(selenium,variant_str, is_bytearray):
    import random
    uncompressed=[random.getrandbits(8) for x in range(1048576)]
    variant = getattr(cramjam, variant_str)

    if is_bytearray:
        uncompressed = bytearray(uncompressed)

    compressed = variant.compress(uncompressed)
    assert compressed.read() != uncompressed
    compressed.seek(0)
    assert isinstance(compressed, cramjam.Buffer)

    decompressed = variant.decompress(compressed, output_len=len(uncompressed))
    assert decompressed.read() == uncompressed
    assert isinstance(decompressed, cramjam.Buffer)


