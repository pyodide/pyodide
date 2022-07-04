def test_pytest_benchmark(selenium):
    selenium.run_js(
        """
        await pyodide.loadPackage(["pytest-benchmark", "pytest"]);
        pyodide.FS.mkdir("/tests")
        pyodide.FS.writeFile("/tests/test_blah.py",
`
import pytest

@pytest.mark.benchmark
def test_blah(benchmark):
    @benchmark
    def f():
        for i in range(100_000):
            pass
    assert benchmark.stats.stats.min >= 0.000001
    assert benchmark.stats.stats.max <= 10
`
        );
        pyodide.FS.chdir("/tests");
        const pytest = pyodide.pyimport("pytest");
        pytest.main();
        pytest.destroy();
        """
    )
    assert "benchmark: 1 tests" in selenium.logs
    assert "Name (time in ms)" in selenium.logs
