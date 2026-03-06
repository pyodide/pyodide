#!/usr/bin/env python3
"""Run pystone benchmarks across tail-calling dist-* directories.

    python tools/tail-calling/run-benchmarks.py [-n ITERATIONS] [NAME]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
V8_PATH = Path.home() / ".jsvu" / "bin" / "v8"
DEFAULT_ITERATIONS = 3


def main():
    parser = argparse.ArgumentParser(
        description="Run pystone benchmarks across dist-* directories",
    )
    parser.add_argument(
        "name",
        nargs="?",
        help="Run a single variant by name (without the dist- prefix)",
    )
    parser.add_argument(
        "-n",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"Number of pystone runs per dist directory (default: {DEFAULT_ITERATIONS})",
    )
    args = parser.parse_args()

    if not V8_PATH.is_file() or not os.access(V8_PATH, os.X_OK):
        print(f"Error: v8 not found at {V8_PATH}", file=sys.stderr)
        print(
            "Install via: npx jsvu --engines=v8 --os=linux64", file=sys.stderr
        )
        sys.exit(1)

    if args.name:
        dist_dirs = [TOOLS_DIR / f"dist-{args.name}"]
        if not dist_dirs[0].is_dir():
            print(
                f"Error: directory {dist_dirs[0]} not found",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        dist_dirs = sorted(p for p in TOOLS_DIR.glob("dist-*") if p.is_dir())
        if not dist_dirs:
            print(
                f"Error: no dist-*/ directories found in {TOOLS_DIR}",
                file=sys.stderr,
            )
            sys.exit(1)

    print(f"Running pystone benchmark ({args.n} iterations per build)")
    print(f"Dist directories: {' '.join(d.name + '/' for d in dist_dirs)}")
    print()

    for dist_dir in dist_dirs:
        entry_path = dist_dir / "_bench-entry.mjs"
        entry_path.write_text(
            f'import {{ loadPyodide }} from "./pyodide.mjs";\n'
            f'import {{ runBenchmark }} from "../bench-pystone.mjs";\n'
            f'await runBenchmark(loadPyodide, "{dist_dir.name}", {args.n}, "{(TOOLS_DIR / "pystone.py").as_posix()}");\n'
        )

        subprocess.run(
            [str(V8_PATH), 
            "--enable-os-system", 
            # "--experimental-wasm-assume-ref-cast-succeeds",
            # "--experimental-wasm-ref-cast-nop",
            # "--experimental-wasm-skip-bounds-checks",
            # "--experimental-wasm-skip-null-checks",
            # "--no-wasm-bounds-checks",
            # "--no-wasm-stack-checks",
            # "--test-only-unsafe",
            "--module", str(entry_path)],
            check=True,
        )
        print()


if __name__ == "__main__":
    main()
