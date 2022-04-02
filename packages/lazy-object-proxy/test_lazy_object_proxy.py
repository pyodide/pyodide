from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(packages=["lazy-object-proxy"])
def test_lazy_object_proxy():
    import lazy_object_proxy

    def expensive_func():
        from time import sleep

        print("starting calculation")
        # just as example for a slow computation
        sleep(0.1)
        print("finished calculation")
        # return the result of the calculation
        return 10

    obj = lazy_object_proxy.Proxy(expensive_func)
    # function is called only when object is actually used
    assert obj == 10  # now expensive_func is called

    assert obj == 10  # the result without calling the expensive_func
