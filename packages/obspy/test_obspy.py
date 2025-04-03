from pyodide_build import run_in_pyodide


@run_in_pyodide(packages=["obspy"])
def test_write_mseed():
    """
    Test using one of our C extensions, writing data to MiniSEED
    """
    import numpy as np
    from obspy import Stream, Trace
    from obspy.io.mseed.core import _read_mseed, _write_mseed

    tr = Trace(data=np.random.randint(-100, 100, 1000))
    st = Stream([tr])
    _write_mseed(st, "/tmp/test.mseed")
    st2 = _read_mseed("/tmp/test.mseed")
    for tr in st2:
        tr.stats.pop("mseed")
        tr.stats.pop("_format")
    assert st == st2
