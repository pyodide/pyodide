"""Runs the pyperformance benchmarks of the pyperformance suite with the host
Python, to compare Pyodide with native CPython.

Usage:
  python3 pyperformance_native.py [--filter REGEX] OUTPUT_FILE [PYPERF_ARGS...]

--filter selects benchmarks like the --filter option of run.mjs: only the ones
whose "pyperformance/NAME" matches REGEX.

Runs the same benchmarks as ../suites/pyperformance.mjs, each in a new process
and with pyperf's --in-process option like in Pyodide, and writes pyperf's
results to OUTPUT_FILE. Compare them with a file from PYPERFORMANCE_OUTPUT_DIR:

  python3 -m pyperf compare_to OUTPUT_FILE new.json

The suite must have run before, to install pyperf and pyperformance into
PYPERFORMANCE_DEPS_DIR (default: benchmark/node/.pyperformance).
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEPS_DIR = os.environ.get(
    "PYPERFORMANCE_DEPS_DIR", str(Path(__file__).parent.parent / ".pyperformance")
)
sys.path.insert(0, DEPS_DIR)

import pyperformance_driver  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--filter")
    parser.add_argument("output_file")
    args, pyperf_args = parser.parse_known_args()
    output_file = os.path.abspath(args.output_file)
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    if os.path.exists(output_file):
        os.remove(output_file)
    names = json.loads(pyperformance_driver.list_benchmarks())
    if args.filter:
        names = [n for n in names if re.search(args.filter, f"pyperformance/{n}")]
    benchmarks = pyperformance_driver._benchmarks()
    env = dict(os.environ, PYTHONPATH=DEPS_DIR)
    for i, name in enumerate(names):
        bench = benchmarks[name]
        cmd = [
            sys.executable,
            bench.runscript,
            *bench.extra_opts,
            *pyperf_args,
            "--in-process",
            "--quiet",
            "--append",
            output_file,
        ]
        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, check=False
        )
        progress = f"[{i + 1}/{len(names)}] native pyperformance/{name}"
        if result.returncode != 0:
            print(f"{progress} failed:\n{result.stderr}", file=sys.stderr)
        else:
            print(progress, file=sys.stderr)


if __name__ == "__main__":
    main()
