from pyodide_test_runner import run_in_pyodide


@run_in_pyodide(packages=["boost-histogram"])
def test_boost_histogram(selenium):
    import unittest

    import boost_histogram as bh

    h = bh.Histogram(bh.axis.Integer(0, 10))
    h.fill([1, 1, 1, 14])
    assert h[bh.underflow] == 0
    assert h[bh.loc(0)] == 0
    assert h[bh.loc(1)] == 3
    assert h[bh.overflow] == 1

    assert h.sum() == 3
    assert h.sum(flow=True) == 4
    assert h[sum] == 4

    h = bh.Histogram(bh.axis.Regular(10, 0, 10), bh.axis.Boolean())
    assert len(h.axes[0]) == 10
    assert len(h.axes[1]) == 2

    h.fill([0.5, 0.5, 3.5], [True, False, True])
    assert h[sum, bh.loc(True)] == 2
    assert h[sum, bh.loc(False)] == 1
    assert h[0, sum] == 2
    assert h[0, bh.loc(True)] == 1

    h = bh.Histogram(bh.axis.StrCategory([], growth=True))
    h.fill("fear leads to anger anger leads to hate hate leads to suffering".split())

    assert h[bh.loc("fear")] == 1
    assert h[bh.loc("anger")] == 2
    assert h[bh.loc("hate")] == 2
    assert h[bh.loc("to")] == 3

    # Test exception handling
    mean = bh.accumulators.Mean()

    with unittest.TestCase().assertRaises(KeyError):
        mean["invalid"]
