import pyodide.runtime as rt


def test_runtime_flags_initialized():
    # Ensure flags exist and are booleans
    assert isinstance(rt.IN_BROWSER, bool)
    assert isinstance(rt.IN_NODE, bool)
    assert isinstance(rt.IN_DENO, bool)
    assert isinstance(rt.IN_BUN, bool)
    assert isinstance(rt.IN_NODE_COMMONJS, bool)
    assert isinstance(rt.IN_NODE_ESM, bool)
    assert isinstance(rt.IN_BROWSER_MAIN_THREAD, bool)
    assert isinstance(rt.IN_BROWSER_WEB_WORKER, bool)
    assert isinstance(rt.IN_SAFARI, bool)
    assert isinstance(rt.IN_SHELL, bool)
