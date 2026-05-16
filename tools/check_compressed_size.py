#!/usr/bin/env python3

# /// script
# dependencies = [
#   "brotli",
# ]
# ///

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


def fmt(size: int) -> str:
    return f"{size:,} bytes ({size / 1024:.2f} KB)"


def check_size(file: str | Path) -> None:
    file = Path(file)

    if not file.is_file():
        print(f"ERROR: {file} is not a file")
        return

    print(f"- {file.name}:")

    print(f"    Original size: {fmt(file.stat().st_size)}")

    data = file.read_bytes()
    compressed_data_1 = gzip.compress(data, compresslevel=1)
    compressed_data_6 = gzip.compress(data, compresslevel=6)
    compressed_data_9 = gzip.compress(data, compresslevel=9)

    print(f"    Gzip compressed size (level 1): {fmt(len(compressed_data_1))}")
    print(f"    Gzip compressed size (level 6): {fmt(len(compressed_data_6))}")
    print(f"    Gzip compressed size (level 9): {fmt(len(compressed_data_9))}")

    if brotli:
        compress_data_brotli = brotli.compress(data)
        print(f"    Brotli compressed size: {fmt(len(compress_data_brotli))}")


def main():
    files = sys.argv[1:]
    if not files:
        print(f"Usage: {sys.argv[0]} <file> ...")

    for file in files:
        check_size(file)


if __name__ == "__main__":
    main()
