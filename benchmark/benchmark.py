import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from time import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parents[1] / "pyodide-test-runner"))

from pyodide_test_runner import (  # noqa: E402
    SeleniumChromeWrapper,
    SeleniumFirefoxWrapper,
    spawn_web_server,
)

SKIP = {"fft", "hyantes"}


def print_entry(name, res):
    print(" - ", name)
    print(" " * 4, end="")
    for name, dt in res.items():
        print(f"{name}: {dt:.6f}  ", end="")
    print("")


def run_native(code):
    if "# non-native" in code:
        return float("NaN")

    root = Path(__file__).resolve().parents[1]
    output = subprocess.check_output(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parent,
        env={
            "PYTHONPATH": str(root / "src/py/lib")
            + ":"
            + str(root / "packages" / ".artifacts" / "lib" / "python")
        },
    )
    return float(output.strip().split()[-1])


def run_wasm(code, selenium, interrupt_buffer):
    if interrupt_buffer:
        selenium.run_js(
            """
            let interrupt_buffer = new Int32Array(1);
            pyodide.setInterruptBuffer(interrupt_buffer)
            """
        )

    selenium.run(code)
    try:
        runtime = float(selenium.logs.split("\n")[-1])
    except ValueError:
        print(selenium.logs)
        raise
    return runtime


def run_all(selenium_backends, code):
    result = {"native": run_native(code)}

    for browser_name, selenium in selenium_backends.items():
        for interrupt_buffer in [False, True]:
            dt = run_wasm(code, selenium, interrupt_buffer)
            if interrupt_buffer:
                browser_name += "(w/ ib)"
            result[browser_name] = dt
    return result


def parse_benchmark(filename):
    lines = []
    with open(filename) as fp:
        for line in fp:
            m = re.match(r"^#\s*(setup|run): (.*)$", line)
            if m:
                line = f"{m.group(1)} = {m.group(2)!r}\n"
            lines.append(line)
    return "".join(lines)


def get_benchmark_scripts(scripts_dir, repeat=5, number=5):
    root = Path(__file__).resolve().parent / scripts_dir
    for filename in sorted(root.iterdir()):
        name = filename.stem

        if name in SKIP:
            continue

        content = parse_benchmark(filename)
        content += (
            "import numpy as np\n"
            "_ = np.empty(())\n"
            f"setup = setup + '\\nfrom __main__ import {name}'\n"
            "from timeit import Timer\n"
            "t = Timer(run, setup)\n"
            f"r = t.repeat({repeat}, {number})\n"
            "r.remove(min(r))\n"
            "r.remove(max(r))\n"
            "print(np.mean(r))\n"
        )

        yield name, content


def get_pystone_benchmarks():
    return get_benchmark_scripts("benchmarks/pystone_benchmarks", repeat=5, number=1)


def get_numpy_benchmarks():
    return get_benchmark_scripts("benchmarks/numpy_benchmarks")


def get_matplotlib_benchmarks():
    return get_benchmark_scripts("benchmarks/matplotlib_benchmarks")


def get_pandas_benchmarks():
    return get_benchmark_scripts("benchmarks/pandas_benchmarks")


def get_benchmarks(benchmarks, targets=("all",)):
    if "all" in targets:
        for benchmark in benchmarks.values():
            yield from benchmark()
    else:
        for target in targets:
            yield from benchmarks[target]()


def parse_args(benchmarks):
    benchmarks.append("all")

    parser = argparse.ArgumentParser("Run benchmarks on Pyodide's performance")
    parser.add_argument(
        "target",
        choices=benchmarks,
        nargs="+",
        help="Benchmarks to run ('all' to run all benchmarks)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="dist/benchmarks.json",
        help="path to the json file where benchmark results will be saved",
    )
    parser.add_argument(
        "--timeout",
        default=1200,
        type=int,
        help="Browser timeout(sec) for each benchmark (default: %(default)s)",
    )
    parser.add_argument(
        "--dist-dir",
        default=str(Path(__file__).parents[1] / "dist"),
        help="Pyodide dist directory (default: %(default)s)",
    )

    return parser.parse_args()


def main():

    BENCHMARKS = {
        "pystone": get_pystone_benchmarks,
        "numpy": get_numpy_benchmarks,
        "matplotlib": get_matplotlib_benchmarks,
        "pandas": get_pandas_benchmarks,
    }

    args = parse_args(list(BENCHMARKS.keys()))
    targets = [t.lower() for t in args.target]
    output = Path(args.output).resolve()
    timeout = args.timeout

    results = {}
    selenium_backends = {}
    browser_cls = [
        ("firefox", SeleniumFirefoxWrapper),
        ("chrome", SeleniumChromeWrapper),
    ]

    with spawn_web_server(args.dist_dir) as (hostname, port, log_path):

        # selenium initialization time
        result = {"native": float("NaN")}
        for browser_name, cls in browser_cls:
            try:
                t0 = time()
                selenium = cls(port, script_timeout=timeout)
                result[browser_name] = time() - t0
            finally:
                selenium.driver.quit()

        results["selenium init"] = result
        print_entry("selenium init", result)

        # package loading time
        for package_name in ["numpy", "pandas", "matplotlib"]:
            result = {"native": float("NaN")}
            for browser_name, cls in browser_cls:
                selenium = cls(port, script_timeout=timeout)
                try:
                    t0 = time()
                    selenium.load_package(package_name)
                    result[browser_name] = time() - t0
                finally:
                    selenium.driver.quit()

            results[f"load {package_name}"] = result
            print_entry(f"load {package_name}", result)

        # run benchmarks
        for benchmark_name, content in get_benchmarks(BENCHMARKS, targets):
            try:
                # instantiate browsers for each benchmark to prevent side effects
                for browser_name, cls in browser_cls:
                    selenium_backends[browser_name] = cls(port, script_timeout=timeout)
                    # pre-load numpy, matplotlib and pandas for the selenium instance used in benchmarks
                    selenium_backends[browser_name].load_package(
                        ["numpy", "matplotlib", "pandas"]
                    )

                results[benchmark_name] = run_all(selenium_backends, content)
                print_entry(benchmark_name, results[benchmark_name])
            finally:
                for selenium in selenium_backends.values():
                    selenium.driver.quit()

    output.parent.mkdir(exist_ok=True, parents=True)
    output.write_text(json.dumps(results))


if __name__ == "__main__":
    main()
