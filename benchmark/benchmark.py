import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(
    0, str((Path(__file__).resolve().parents[1] / 'test')))
sys.path.insert(
    0, str((Path(__file__).resolve().parents[1])))

import conftest  # noqa: E402


SKIP = set(['fft', 'hyantes', 'README'])


def run_native(hostpython, code):
    output = subprocess.check_output(
        [hostpython.resolve(), '-c', code],
        cwd=Path(__file__).resolve().parent,
        env={
            'PYTHONPATH':
            str(Path(__file__).resolve().parents[1] / 'src')
        }
    )
    return float(output.strip().split()[-1])


def run_wasm(code, cls, port):
    s = cls(port)
    try:
        s.load_package('numpy')
        s.run(code)
        try:
            runtime = float(s.logs.split('\n')[-1])
        except ValueError:
            print(s.logs)
            raise
    finally:
        s.driver.quit()
    return runtime


def run_all(hostpython, port, code):
    a = run_native(hostpython, code)
    print("native:", a)
    b = run_wasm(code, conftest.FirefoxWrapper, port)
    print("firefox:", b)
    c = run_wasm(code, conftest.ChromeWrapper, port)
    print("chrome:", c)
    result = {
        'native': a,
        'firefox': b,
        'chrome': c
    }
    return result


def get_pystone_benchmarks():
    yield 'pystone', (
        "import pystone\n"
        "pystone.main(pystone.LOOPS)\n"
    )


def parse_numpy_benchmark(filename):
    lines = []
    with open(filename) as fp:
        for line in fp:
            m = re.match(r'^#\s*(setup|run): (.*)$', line)
            if m:
                line = '{} = {!r}\n'.format(m.group(1), m.group(2))
            lines.append(line)
    return ''.join(lines)


def get_numpy_benchmarks():
    root = Path(__file__).resolve().parent / 'benchmarks'
    for filename in root.iterdir():
        name = filename.stem
        if name in SKIP:
            continue
        content = parse_numpy_benchmark(filename)
        content += (
            "import numpy as np\n"
            "_ = np.empty(())\n"
            "setup = setup + '\\nfrom __main__ import {}'\n"
            "from timeit import Timer\n"
            "t = Timer(run, setup)\n"
            "r = t.repeat(11, 40)\n"
            "r.remove(min(r))\n"
            "r.remove(max(r))\n"
            "print(np.mean(r))\n".format(name))
        yield name, content


def get_benchmarks():
    yield from get_pystone_benchmarks()
    yield from get_numpy_benchmarks()


def main(hostpython):
    with conftest.spawn_web_server() as (hostname, port, log_path):
        results = {}
        for k, v in get_benchmarks():
            print(k)
            results[k] = run_all(hostpython, port, v)
    return results


if __name__ == '__main__':
    results = main(Path(sys.argv[-2]).resolve())
    with open(sys.argv[-1], 'w') as fp:
        json.dump(results, fp)
