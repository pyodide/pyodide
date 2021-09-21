import pytest
import inspect
from typing import Callable, Dict, List, Optional, Union
import contextlib
from base64 import b64encode


def _run_in_pyodide_get_source(f):
    lines, start_line = inspect.getsourcelines(f)
    num_decorator_lines = 0
    for line in lines:
        if line.startswith("def") or line.startswith("async def"):
            break
        num_decorator_lines += 1
    start_line += num_decorator_lines - 1
    # Remove first line, which is the decorator. Then pad with empty lines to fix line number.
    lines = ["\n"] * start_line + lines[num_decorator_lines:]
    return "".join(lines)


def chunkstring(string, length):
    return (string[0 + i : length + i] for i in range(0, len(string), length))


from pprint import pformat


def run_in_pyodide(
    _function: Optional[Callable] = None,
    *,
    standalone: bool = False,
    module_scope: bool = False,
    packages: List[str] = [],
    xfail_browsers: Dict[str, str] = {},
    driver_timeout: Optional[Union[str, int]] = None,
) -> Callable:
    """
    This decorator can be called in two ways --- with arguments and without
    arguments. If it is called without arguments, then the `_function` kwarg
    catches the function the decorator is applied to. Otherewise, standalone
    and packages are the actual arguments to the decorator.

    See docs/testing.md for details on how to use this.

    Parameters
    ----------
    standalone : bool, default=False
        Whether to use a standalone selenium instance to run the test or not
    packages : List[str]
        List of packages to load before running the test
    driver_timeout : Optional[Union[str, int]]
        selenium driver timeout (in seconds)
    """

    def decorator(f):
        def inner(selenium):
            if selenium.browser in xfail_browsers:
                xfail_message = xfail_browsers[selenium.browser]
                pytest.xfail(xfail_message)
            with set_webdriver_script_timeout(selenium, driver_timeout):
                if len(packages) > 0:
                    selenium.load_package(packages)
                err = None
                try:
                    # When writing the function, we set the filename to the file
                    # containing the source. This results in a more helpful
                    # traceback
                    if inspect.iscoroutinefunction(f):
                        run_python = "pyodide.runPythonAsync"
                        await_kw = "await "
                    else:
                        run_python = "pyodide.runPython"
                        await_kw = ""
                    source = _run_in_pyodide_get_source(f)
                    filename = inspect.getsourcefile(f)
                    encoded = pformat(
                        list(chunkstring(b64encode(source.encode()).decode(), 100))
                    )

                    selenium.run_js(
                        f"""
                        let eval_code = pyodide.pyodide_py.eval_code;
                        try {{
                            eval_code.callKwargs(
                                {{
                                    source : atob({encoded}.join("")),
                                    globals : pyodide._module.globals,
                                    filename : {filename!r}
                                }}
                            )
                        }} finally {{
                            eval_code.destroy();
                        }}
                        """
                    )
                    # When invoking the function, use the default filename <eval>
                    selenium.run_js(
                        f"""{await_kw}{run_python}("{await_kw}{f.__name__}()", pyodide.globals)"""
                    )
                except selenium.JavascriptException as e:
                    err = e

            if err is not None:
                pytest.fail(
                    "Error running function in pyodide\n\n" + str(err),
                    pytrace=False,
                )

        if standalone:

            def wrapped(selenium_standalone):  # type: ignore
                inner(selenium_standalone)

        elif module_scope:

            def wrapped(selenium_module_scope):  # type: ignore
                inner(selenium_module_scope)

        else:

            def wrapped(selenium):  # type: ignore
                inner(selenium)

        return wrapped

    if _function is not None:
        return decorator(_function)
    else:
        return decorator


@contextlib.contextmanager
def set_webdriver_script_timeout(selenium, script_timeout: Optional[Union[int, float]]):
    """Set selenium script timeout

    Parameters
    ----------
    selenum : SeleniumWrapper
       a SeleniumWrapper wrapper instance
    script_timeout : int | float
       value of the timeout in seconds
    """
    if script_timeout is not None:
        selenium.set_script_timeout(script_timeout)
    yield
    # revert to the initial value
    if script_timeout is not None:
        selenium.set_script_timeout(selenium.script_timeout)


def parse_driver_timeout(request) -> Optional[Union[int, float]]:
    """Parse driver timeout value from pytest request object"""
    mark = request.node.get_closest_marker("driver_timeout")
    if mark is None:
        return None
    else:
        return mark.args[0]
