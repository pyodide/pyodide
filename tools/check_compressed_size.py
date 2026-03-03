#!/usr/bin/env python3

# A short script to check the size of files when compressed.
# Usage:
#   check_compressed_size.py pyodide.asm.mjs pyodide.asm.wasm

import gzip
import sys
from pathlib import Path

try:
    import brotli
except ImportError:
    print("WARNING: Brotli not installed")
    brotli = None


def kb(size: int) -> int:
    return size // 1024


def check_size(file: str | Path) -> None:
    file = Path(file)

    if not file.is_file():
        print(f"ERROR: {file} is not a file")
        return

    print(f"- {file.name}:")

    print(f"    Original size: {kb(file.stat().st_size)} KB")

    data = file.read_bytes()
    compressed_data_1 = gzip.compress(data, compresslevel=1)
    compressed_data_6 = gzip.compress(data, compresslevel=9)
    compressed_data_9 = gzip.compress(data, compresslevel=9)

    print(f"    Gzip compressed size (level 1): {kb(len(compressed_data_1))} KB")
    print(f"    Gzip compressed size (level 6): {kb(len(compressed_data_6))} KB")
    print(f"    Gzip compressed size (level 9): {kb(len(compressed_data_9))} KB")

    if brotli:
        compress_data_brotli = brotli.compress(data)
        print(f"    Brotli compressed size: {kb(len(compress_data_brotli))} KB")


def main():
    files = sys.argv[1:]
    if not files:
        print(f"Usage: {sys.argv[0]} <file> ...")

    for file in files:
        check_size(file)


if __name__ == "__main__":
    main()
