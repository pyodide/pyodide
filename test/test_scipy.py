def test_brentq(selenium_standalone):
    selenium_standalone.load_package("scipy")
    selenium_standalone.run("from scipy.optimize import brentq")
    selenium_standalone.run("brentq(lambda x: x, -1, 1)")
