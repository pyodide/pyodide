def my_setup(selenium):
    selenium.run_js(
        """
        window.py2js_deep = pyodide._module.TestEntrypoints.py2js_deep;
        window.py2js_shallow = pyodide._module.TestEntrypoints.py2js_shallow;
        window.py2js_minimal = pyodide._module.TestEntrypoints.py2js_minimal;
        window.isPyProxy = pyodide._module.TestEntrypoints.isPyProxy;
        """
    )


def test_py2js_deep(selenium):
    my_setup(selenium)
    selenium.run("a = [1, 2, 3]")
    assert selenium.run_js(
        """
        res = py2js_deep("a");
        return (res instanceof window.Array) && JSON.stringify(res) === "[1,2,3]";
        """
    )
    selenium.run("a = (1, 2, 3)")
    assert selenium.run_js(
        """
        res = py2js_deep("a");
        return (res instanceof window.Array) && JSON.stringify(res) === "[1,2,3]";
        """
    )
    selenium.run("a = [(1,2), (3,4), [5, 6], { 2 : 3,  4 : 9}]")
    assert selenium.run_js(
        """
        a3 = py2js_deep("a");
        result = true;
        result &= a3 instanceof window.Array;
        result &= JSON.stringify(a3) === `[[1,2],[3,4],[5,6],{"2":3,"4":9}]`;
        return result;
        """
    )
    selenium.run("a = (1, (2, (3, [4, 5])))")
    assert selenium.run_js(
        """
        a4 = py2js_deep("a");
        result = true;
        result &= a4 instanceof window.Array;
        result &= a4[1] instanceof window.Array;
        result &= a4[1][1] instanceof window.Array;
        result &= a4[1][1][1] instanceof window.Array;
        result &= JSON.stringify(a4) === "[1,[2,[3,[4,5]]]]";
        return result
        """
    )
    selenium.run("a = {1, 2, 3}")
    # TODO: should convert to a javascript Set.


def test_py2js_shallow(selenium):
    my_setup(selenium)
    selenium.run("a = [1, 2, 3]")
    assert selenium.run_js(
        """
        res = py2js_shallow("a");
        return (res instanceof window.Array) && JSON.stringify(res) === "[1,2,3]";
        """
    )
    selenium.run("a = (1, 2, 3)")
    assert selenium.run_js(
        """
        res = py2js_shallow("a");
        return (res instanceof window.Array) && JSON.stringify(res) === "[1,2,3]";
        """
    )
    selenium.run("a = [(1,2), (3,4), [5, 6], { 2 : 3,  4 : 9}]")
    assert selenium.run_js(
        """
        a3 = py2js_shallow("a");
        result = true;
        result &= a3 instanceof window.Array;
        result &= JSON.stringify(a3.map(x => isPyProxy(x))) === `[false,false,true,true]`;
        result &= JSON.stringify(a3[0]) === "[1,2]";
        result &= JSON.stringify(a3[1]) === "[3,4]";
        result &= a3[2].toString() === "[5, 6]";
        result &= a3[3].toString() === "{2: 3, 4: 9}";
        return result;
        """
    )
    selenium.run("a = (1, (2, (3, [4, 5])))")
    assert selenium.run_js(
        """
        a4 = py2js_shallow("a");
        result = true;
        result &= a4 instanceof window.Array;
        result &= a4[1] instanceof window.Array;
        result &= a4[1][1] instanceof window.Array;
        result &= isPyProxy(a4[1][1][1]);
        return result
        """
    )
    selenium.run("a = {1, 2, 3}")
    # TODO: should convert to a javascript Set.


def test_py2js_minimal(selenium):
    my_setup(selenium)
    selenium.run("a = [1, 2, 3]")
    assert selenium.run_js(
        """
        res = py2js_minimal("a");
        return isPyProxy(res) && res.toString() === "[1, 2, 3]"
        """
    )
    selenium.run("a = (1, 2, 3)")
    assert selenium.run_js(
        """
        res = py2js_minimal("a");
        return (res instanceof window.Array) && JSON.stringify(res) === "[1,2,3]"
        """
    )
    selenium.run("a = [(1,2), (3,4), [5, 6], { 2 : 3,  4 : 9}]")
    assert selenium.run_js(
        """
        a3 = py2js_minimal("a");
        result = true;
        result &= isPyProxy(a3);
        result &= a3.toString() === "[(1, 2), (3, 4), [5, 6], {2: 3, 4: 9}]";
        return result;
        """
    )
    selenium.run("a = (1, (2, (3, [4, 5])))")
    assert selenium.run_js(
        """
        a4 = py2js_minimal("a");
        result = true;
        result &= a4 instanceof window.Array;
        result &= a4[1] instanceof window.Array;
        result &= a4[1][1] instanceof window.Array;
        result &= isPyProxy(a4[1][1][1]);
        return result
        """
    )
    selenium.run("a = {1, 2, 3}")
    assert (
        selenium.run_js(
            """
        a5 = py2js_minimal("a");
        result = true;
        return [isPyProxy(a5), a5.toString()];
        """
        )
        == [True, "{1, 2, 3}"]
    )
