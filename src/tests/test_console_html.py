import pytest
from pyodide_build.testing import run_in_pyodide
from conftest import selenium_common


@pytest.mark.skip_refcount_check
@run_in_pyodide
async def test_console_imports():
    from pyodide.console import PyodideConsole

    shell = PyodideConsole()

    async def get_result(input):
        res = shell.push(input)
        [status, fut] = res
        assert status == "complete"
        [status, value] = await fut
        assert status == "success"
        return value

    assert await get_result("import pytz") == None
    assert await get_result("pytz.utc.zone") == "UTC"


@pytest.fixture(params=["firefox", "chrome"], scope="function")
def console_html_fixture(request, web_server_main):
    with selenium_common(request, web_server_main, False) as selenium:
        selenium.driver.get(
            f"http://{selenium.server_hostname}:{selenium.server_port}/console.html"
        )
        selenium.javascript_setup()
        try:
            yield selenium
        finally:
            print(selenium.logs)


def test_console_html(console_html_fixture):
    selenium = console_html_fixture
    selenium.run_js(
        """
        await window.console_ready;
        """
    )
    result = selenium.run_js(
        r"""
        let result = [];
        assert(() => term.get_output().startsWith("Welcome to the Pyodide terminal emulator 🐍"))

        term.clear();
        term.exec("1+1");
        await term.ready;
        assert(() => term.get_output().trim() === ">>> 1+1\n2", term.get_output().trim());


        term.clear();
        term.exec("1+");
        await term.ready;
        result.push([term.get_output(),
`>>> 1+
[[;;;terminal-error]  File "<console>", line 1
    1+
      ^
SyntaxError: invalid syntax]`
        ]);

        term.clear();
        term.exec("raise Exception('hi')");
        await term.ready;
        result.push([term.get_output(),
`>>> raise Exception('hi')
[[;;;terminal-error]Traceback (most recent call last):
  File "<console>", line 1, in <module>
Exception: hi]`
        ]);

        term.clear();
        term.exec("from _pyodide_core import trigger_fatal_error; trigger_fatal_error()");
        await sleep(100);
        result.push([term.get_output(),
`>>> from _pyodide_core import trigger_fatal_error; trigger_fatal_error()
[[;;;terminal-error]Pyodide has suffered a fatal error. Please report this to the Pyodide maintainers.]
[[;;;terminal-error]The cause of the fatal error was:]
[[;;;terminal-error]Error: intentionally triggered fatal error!]
[[;;;terminal-error]Look in the browser console for more details.]`
        ]);

        assert(() => term.paused());
        return result;
        """
    )
    for [x, y] in result:
        assert x == y
