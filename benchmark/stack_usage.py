import pytest


@pytest.fixture(scope="session")
def print_info():
    headings = [
        "browser",
        "py_usage",
        "js_depth",
        "py_depth",
        "js_depth/py_usage",
        "js_depth/py_depth",
    ]
    fmt = "## {{:{:d}s}}  {{:{:d}.2f}}  {{:{:d}g}}  {{:{:d}g}}  {{:{:d}g}}  {{:{:d}g}}".format(
        *map(len, headings)
    )
    printed_heading = False

    def print_info(*args):
        nonlocal printed_heading
        if not printed_heading:
            printed_heading = True
            print("## " + "  ".join(headings))
        print(fmt.format(*args))

    yield print_info


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_stack_usage(selenium, print_info):
    res = selenium.run_js(
        """
        window.measure_available_js_stack_depth = () => {
            let depth = 0;
            function recurse() { depth += 1; recurse(); }
            try { recurse(); } catch (err) { }
            return depth;
        };
        let py_usage = pyodide.runPython(`
            from js import measure_available_js_stack_depth
            def recurse(n):
                return measure_available_js_stack_depth() if n==0 else recurse(n-1)
            (recurse(0)-recurse(100))/100
        `);
        let js_depth = measure_available_js_stack_depth();
        window.py_depth = [0];
        try {
        pyodide.runPython(`
        import sys
        from js import py_depth
        sys.setrecursionlimit(2000)
        def infiniterecurse():
            py_depth[0] += 1
            infiniterecurse()
        infiniterecurse()
        `);
        } catch {}

        py_depth = py_depth[0];
        return [
            py_usage,
            js_depth,
            py_depth,
            Math.floor(js_depth/py_usage),
            Math.floor(js_depth/py_depth),
        ]
        """
    )
    # "py_usage",
    # "js_depth",
    # "py_depth",
    # "js_depth/py_usage",
    # "js_depth/py_depth",

    print_info(selenium.browser, *res)

    selenium.clean_logs()
