# See also test_typeconversions, and test_python.
import pytest


def test_jsproxy_dir(selenium):
    result = selenium.run_js(
        """
        window.a = { x : 2, y : "9" };
        return pyodide.runPython(`
            from js import a
            dir(a)
        `);
        """
    )
    assert set(result).issuperset(
        [
            "__bool__",
            "__call__",
            "__class__",
            "__defineGetter__",
            "__defineSetter__",
            "__delattr__",
            "__delitem__",
            "constructor",
            "new",
            "toString",
            "typeof",
            "valueOf",
            "x",
        ]
    )


def test_jsproxy_getattr(selenium):
    assert (
        selenium.run_js(
            """
        window.a = { x : 2, y : "9", typeof : 7 };
        return pyodide.runPython(`
            from js import a
            [ a.x, a.y, a.typeof ]
        `);
        """
        )
        == [2, "9", "object"]
    )


def test_jsproxy(selenium):
    assert (
        selenium.run(
            """
        from js import document
        el = document.createElement('div')
        document.body.appendChild(el)
        document.body.children.length"""
        )
        == 1
    )
    assert selenium.run("document.body.children[0].tagName") == "DIV"
    assert selenium.run("repr(document)") == "[object HTMLDocument]"
    selenium.run_js("window.square = function (x) { return x*x; }")
    assert selenium.run("from js import square\n" "square(2)") == 4
    assert selenium.run("from js import ImageData\n" "ImageData.new(64, 64)")
    assert selenium.run("from js import ImageData\n" "ImageData.typeof") == "function"
    selenium.run_js(
        """
        class Point {
          constructor(x, y) {
            this.x = x;
            this.y = y;
          }
        }
        window.TEST = new Point(42, 43);"""
    )
    assert (
        selenium.run(
            """
        from js import TEST
        del TEST.y
        hasattr(TEST, 'y')"""
        )
        is False
    )
    selenium.run_js(
        """
        class Point {
          constructor(x, y) {
            this.x = x;
            this.y = y;
          }
        }
        window.TEST = new Point(42, 43);"""
    )
    assert (
        selenium.run(
            """
        from js import TEST
        del TEST['y']
        'y' in TEST"""
        )
        is False
    )
    assert selenium.run(
        """
        from js import TEST
        TEST == TEST
        """
    )
    assert selenium.run(
        """
        from js import TEST
        TEST != 'foo'
        """
    )
    selenium.run_js(
        """
        window.TEST = {foo: 'bar', baz: 'bap'}
        """
    )
    assert (
        selenium.run(
            """
        from js import TEST
        dict(TEST) == {'foo': 'bar', 'baz': 'bap'}
        """
        )
        is True
    )
    assert (
        selenium.run(
            """
        from js import document
        el = document.createElement('div')
        len(dir(el)) >= 200 and 'appendChild' in dir(el)
        """
        )
        is True
    )


def test_jsproxy_iter(selenium):
    selenium.run_js(
        """
        function makeIterator(array) {
          let nextIndex = 0;
          return {
            next: function() {
              return nextIndex < array.length ?
                {value: array[nextIndex++], done: false} :
                {done: true};
            }
          };
        }
        window.ITER = makeIterator([1, 2, 3]);"""
    )
    assert selenium.run("from js import ITER\n" "list(ITER)") == [1, 2, 3]


def test_jsproxy_implicit_iter(selenium):
    selenium.run_js(
        """
        window.ITER = [1, 2, 3];"""
    )
    assert selenium.run("from js import ITER, Object\n" "list(ITER)") == [1, 2, 3]
    assert selenium.run("from js import ITER, Object\n" "list(ITER.values())") == [
        1,
        2,
        3,
    ]
    assert selenium.run(
        "from js import ITER, Object\n" "list(Object.values(ITER))"
    ) == [1, 2, 3]


def test_jsproxy_kwargs(selenium):
    selenium.run_js(
        """
        window.kwarg_function = ({ a = 1, b = 1 }) => {
            return a / b;
        };
        """
    )
    assert (
        selenium.run(
            """
        from js import kwarg_function
        kwarg_function(b = 2, a = 10)
        """
        )
        == 5
    )


import time

ASYNCIO_EVENT_LOOP_STARTUP = """
import asyncio
class DumbLoop(asyncio.AbstractEventLoop):
    def create_future(self):
        fut = asyncio.Future(loop=self)
        old_set_result = fut.set_result
        old_set_exception = fut.set_exception
        def set_result(a):
            print("set_result:", a)
            old_set_result(a)
        fut.set_result = set_result
        def set_exception(a):
            print("set_exception:", a)
            old_set_exception(a)
        fut.set_exception = set_exception
        return fut

    def get_debug(self):
        return False

asyncio.set_event_loop(DumbLoop())
"""


def test_await_jsproxy(selenium):
    selenium.run(ASYNCIO_EVENT_LOOP_STARTUP)
    selenium.run(
        """
        def prom(res,rej):
            global resolve
            resolve = res
        from js import Promise
        p = Promise.new(prom)
        async def temp():
            x = await p
            return x + 7
        resolve(10)
        c = temp()
        r = c.send(None)
        """
    )
    time.sleep(0.01)
    msg = "StopIteration: 17"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run(
            """
            c.send(r.result())
            """
        )


def test_await_fetch(selenium):
    selenium.run(ASYNCIO_EVENT_LOOP_STARTUP)
    selenium.run(
        """
        from js import fetch, window
        async def test():
            response = await fetch("console.html")
            result = await response.text()
            print(result)
            return result
        fetch = fetch.bind(window)

        c = test()
        r1 = c.send(None)
        """
    )
    time.sleep(0.1)
    selenium.run(
        """
        r2 = c.send(r1.result())
        """
    )
    time.sleep(0.1)
    msg = "StopIteration: <!doctype html>"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run(
            """
            c.send(r2.result())
            """
        )


def test_await_error(selenium):
    selenium.run_js(
        """
        async function async_js_raises(){
            console.log("Hello there???");
            throw new Error("This is an error message!");
        }
        window.async_js_raises = async_js_raises;
        function js_raises(){
            throw new Error("This is an error message!");
        }
        window.js_raises = js_raises;
        """
    )
    selenium.run(ASYNCIO_EVENT_LOOP_STARTUP)
    selenium.run(
        """
        from js import async_js_raises, js_raises
        async def test():
            c = await async_js_raises()
            return c
        c = test()
        r1 = c.send(None)
        """
    )
    msg = "This is an error message!"
    with pytest.raises(selenium.JavascriptException, match=msg):
        # Wait for event loop to go around for chome
        selenium.run(
            """
            r2 = c.send(r1.result())
            """
        )
