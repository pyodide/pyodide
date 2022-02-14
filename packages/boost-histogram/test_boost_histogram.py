from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(packages=["boost-histogram"])
def test_boost_histogram():
    import boost_histogram as bh
    import unittest

    class TestBasicHistogram(unittest.TestCase):
        def test_1d_histogram(self):
            h = bh.Histogram(bh.axis.Integer(0, 10))
            h.fill([1, 1, 1, 14])
            self.assertEquals(h[bh.underflow], 0)
            self.assertEquals(h[bh.loc(0)], 0)
            self.assertEquals(h[bh.loc(1)], 3)
            self.assertEquals(h[bh.overflow], 1)

            self.assertEquals(h.sum(), 3)
            self.assertEquals(h.sum(flow=True), 4)
            self.assertEquals(h[sum], 4)

        def test_2d_histogram(self):
            h = bh.Histogram(bh.axis.Regular(10, 0, 10), bh.axis.Boolean())
            self.assertEquals(len(h.axes[0]), 10)
            self.assertEquals(len(h.axes[1]), 2)

            h.fill([0.5, 0.5, 3.5], [True, False, True])
            self.assertEquals(h[sum, bh.loc(True)], 2)
            self.assertEquals(h[sum, bh.loc(False)], 1)
            self.assertEquals(h[0, sum], 2)
            self.assertEquals(h[0, bh.loc(True)], 1)

        def test_cat_histogram(self):
            h = bh.Histogram(bh.axis.StrCategory([], growth=True))
            h.fill(
                "fear leads to anger anger leads to hate hate leads to suffering".split()
            )

            self.assertEquals(h[bh.loc("fear")], 1)
            self.assertEquals(h[bh.loc("anger")], 2)
            self.assertEquals(h[bh.loc("hate")], 2)
            self.assertEquals(h[bh.loc("to")], 3)
