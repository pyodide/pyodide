# Runs pyperformance benchmarks inside Pyodide.
#
# pyperformance normally creates a venv and runs each benchmark script in a
# subprocess. Neither works in Pyodide, so this runs the benchmark scripts from
# the installed pyperformance package directly, with pyperf's --in-process
# option so that pyperf doesn't spawn worker processes either.

import json
import os
import runpy
import sys

import pyperf
from pyperformance import _manifest

# Benchmarks that can't run in Pyodide.
UNSUPPORTED = {
    "2to3": "starts a subprocess",
    "python_startup": "starts a subprocess",
    "python_startup_no_site": "starts a subprocess",
    "stdlib_startup": "starts a subprocess",
    "concurrent_imap": "uses multiprocessing",
    "asyncio_tcp": "starts a server",
    "asyncio_tcp_ssl": "starts a server",
    "asyncio_websockets": "starts a server",
    "tornado_http": "starts a server",
    "fastapi": "starts a server",
    "dask": "needs psutil",
}

RESULT_FILE = "/tmp/pyperformance_result.json"


def _benchmarks():
    # Private API, maybe we should upstream this to make it public?
    return {b.name: b for b in _manifest.load_manifest(None).benchmarks}


def list_benchmarks() -> str:
    """The names of the benchmarks that can be run, as JSON."""
    names = []
    for name, bench in _benchmarks().items():
        if name in UNSUPPORTED:
            continue
        # Benchmarks with a requirements.txt need third-party packages, which
        # aren't installed yet.
        if os.path.exists(bench.requirements_lockfile):
            continue
        names.append(name)
    return json.dumps(sorted(names))


def run_benchmark(name: str, pyperf_args: list[str]) -> str:
    """Run a benchmark, returning the median time of each of its pyperf
    benchmarks in ms, as JSON.
    """
    bench = _benchmarks()[name]
    if os.path.exists(RESULT_FILE):
        os.remove(RESULT_FILE)
    sys.argv = [
        bench.runscript,
        *bench.extra_opts,
        *pyperf_args,
        "--in-process",
        "--output",
        RESULT_FILE,
    ]
    # some benchmark scripts import modules from the same directory
    sys.path.insert(0, os.path.dirname(bench.runscript))
    try:
        runpy.run_path(bench.runscript, run_name="__main__")
    except SystemExit as e:
        # pyperf exits on errors, e.g. on invalid arguments
        if e.code not in (None, 0):
            raise RuntimeError(f"{name} exited with {e.code}") from None

    results = {}
    for b in pyperf.BenchmarkSuite.load(RESULT_FILE):
        if b.get_unit() != "second":
            raise RuntimeError(f"Unexpected unit {b.get_unit()} for {b.get_name()}")
        results[b.get_name()] = b.median() * 1000
    return json.dumps(results)
