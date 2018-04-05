import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.abspath(
     os.path.join(os.path.dirname(__file__), '..', 'test')))
import conftest


SKIP = set(['fft', 'hyantes'])


def run_native(hostpython, code):
    output = subprocess.check_output(
        [os.path.abspath(hostpython), '-c', code],
        cwd=os.path.dirname(__file__),
        env={
            'PYTHONPATH':
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))}
    )
    return float(output.strip().split()[-1])


def run_wasm(code):
    s = conftest.SeleniumWrapper()
    s.run(code)
    runtime = float(s.logs[-1])
    s.driver.quit()
    return runtime


def run_both(hostpython, code):
    a = run_native(hostpython, code)
    print(a)
    b = run_wasm(code)
    print(b)
    result = (a, b)
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
            m = re.match('^#(setup|run): (.*)$', line)
            if m:
                line = '{} = {!r}\n'.format(m.group(1), m.group(2))
            lines.append(line)
    return ''.join(lines)


def get_numpy_benchmarks():
    root = '../numpy-benchmarks/benchmarks'
    for filename in os.listdir(root):
        name = os.path.splitext(filename)[0]
        if name in SKIP:
            continue
        content = parse_numpy_benchmark(os.path.join(root, filename))
        content += (
            "setup = setup + '\\nfrom __main__ import {}'\n"
            "from timeit import Timer\n"
            "t = Timer(run, setup)\n"
            "r = t.repeat(11, 40)\n"
            "import numpy as np\n"
            "print(np.mean(r))\n".format(name))
        yield name, content


def get_benchmarks():
    yield from get_pystone_benchmarks()
    yield from get_numpy_benchmarks()


def main(hostpython):
    results = {}
    for k, v in get_benchmarks():
        print(k)
        results[k] = run_both(hostpython, v)
    return results


if __name__ == '__main__':
    results = main(sys.argv[-2])
    with open(sys.argv[-1], 'w') as fp:
        json.dump(results, fp)
