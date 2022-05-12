import ast
import asyncio
import inspect
import pathlib

from pyodide_test_runner.decorator import _run_in_pyodide_run, run_in_pyodide

from conftest import REWRITE_CONFIG, rewrite_asserts
from pyodide import eval_code_async


def test_web_server_secondary(selenium, web_server_secondary):
    host, port, logs = web_server_secondary
    assert pathlib.Path(logs).exists()
    assert selenium.server_port != port


def example_func():
    x = 6
    y = 7
    assert x == y


async def async_example_func():
    from asyncio import sleep

    await sleep(0.01)
    x = 6
    await sleep(0.01)
    y = 7
    assert x == y


def run_in_pyodide_test_helper(selenium):
    source = inspect.getsource(example_func)
    tree = ast.parse(source, filename=__file__)
    rewrite_asserts(tree, source, __file__, REWRITE_CONFIG)
    return _run_in_pyodide_run(selenium, example_func, {__file__: tree})


def test_run_in_pyodide_local():
    class selenium_mock:
        JavascriptException = Exception

        @staticmethod
        def run_async(code: str):
            return asyncio.get_event_loop().run_until_complete(eval_code_async(code))

    err = run_in_pyodide_test_helper(selenium_mock)
    assert err.exc_type is AssertionError
    assert "".join(err.format_exception_only()) == "AssertionError: assert 6 == 7\n"


def test_run_in_pyodide_selenium(selenium):
    selenium.load_package(["pytest"])
    err = run_in_pyodide_test_helper(selenium)
    assert err.exc_type is AssertionError
    assert "".join(err.format_exception_only()) == "AssertionError: assert 6 == 7\n"


@run_in_pyodide
def test_run_in_pyodide1():
    x = 6
    assert x == 6


@run_in_pyodide(pytest_assert_rewrites=False)
def test_run_in_pyodide2():
    x = 6
    assert x == 6


@run_in_pyodide
async def test_run_in_pyodide_async():
    from asyncio import sleep

    x = 6
    await sleep(0.01)
    assert x == 6


def test_assert(selenium):
    selenium.run_js(
        r"""
        let shouldPass;
        shouldPass = true;
        assert(() => shouldPass, "blah");
        shouldPass = false;
        let threw = false;
        try {
            assert(() => shouldPass, "blah");
        } catch(e){
            threw = true;
            if(e.message !== `Assertion failed: shouldPass\nblah`){
                throw new Error(`Unexpected message:\n${e.message}`);
            }
        }
        if(!threw){
            throw new Error("Didn't throw!");
        }
        """
    )

    selenium.run_js(
        r"""
        let shouldPass;
        let threw;
        assertThrows(() => { throw new TypeError("aaabbbccc") }, "TypeError", "bbc");
        assertThrows(() => { throw new TypeError("aaabbbccc") }, "TypeError", /.{3}.{3}.{3}/);
        threw = false;
        try {
            assertThrows(() => 0, "TypeError", /.*/);
        } catch(e) {
            threw = true;
            assert(() => e.message == `assertThrows(() => 0, "TypeError", /.*/) failed, no error thrown`, e.message);
        }
        assert(() => threw);
        threw = false;
        try {
            assertThrows(() => { throw new ReferenceError("blah"); }, "TypeError", /.*/);
        } catch(e) {
            threw = true;
            assert(() => e.message.endsWith("expected error of type 'TypeError' got type 'ReferenceError'"));
        }
        assert(() => threw);
        threw = false;
        try {
            assertThrows(() => { throw new TypeError("blah"); }, "TypeError", "abcd");
        } catch(e) {
            threw = true;
            console.log(`!!${e.message}!!`);
            assert(() => e.message.endsWith(`expected error message to match pattern "abcd" got:\nblah`));
        }
        assert(() => threw);
        threw = false;
        try {
            assertThrows(() => { throw new TypeError("blah"); }, "TypeError", /a..d/);
        } catch(e) {
            threw = true;
            console.log(`!!${e.message}!!`);
            assert(() => e.message.endsWith(`expected error message to match pattern /a..d/ got:\nblah`));
        }
        assert(() => threw);
        """
    )
