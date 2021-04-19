import pytest
import inspect
from typing import Optional, List, Callable, Union
import contextlib


def run_in_pyodide(
    _function: Optional[Callable] = None,
    standalone: bool = False,
    packages: List[str] = [],
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
            with set_webdriver_script_timeout(selenium, driver_timeout):
                if len(packages) > 0:
                    selenium.load_package(packages)
                lines, start_line = inspect.getsourcelines(f)
                # Remove first line, which is the decorator. Then pad with empty lines to fix line number.
                lines = ["\n"] * start_line + lines[1:]
                source = "".join(lines)

                err = None
                try:
                    # When writing the function, we set the filename to the file
                    # containing the source. This results in a more helpful
                    # traceback
                    selenium.run_js(
                        """pyodide._module.pyodide_py.eval_code({!r}, // code
                                pyodide._module.globals, // globals
                                pyodide._module.globals, // locals
                                "last_expr", // return_mode
                                true, // quiet_trailing_semicolon
                                {!r} // filename
                            )""".format(
                            source, inspect.getsourcefile(f)
                        )
                    )
                    # When invoking the function, use the default filename <eval>
                    selenium.run_js(
                        """pyodide._module.pyodide_py.eval_code("{}()", pyodide._module.globals)""".format(
                            f.__name__
                        )
                    )
                except selenium.JavascriptException as e:
                    err = e

            if err is not None:
                pytest.fail(
                    "Error running function in pyodide\n\n" + str(err),
                    pytrace=False,
                )

        if standalone:

            def wrapped_standalone(selenium_standalone):
                inner(selenium_standalone)

            return wrapped_standalone

        else:

            def wrapped(selenium):
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
        selenium.driver.set_script_timeout(script_timeout)
    yield
    # revert to the initial value
    if script_timeout is not None:
        selenium.driver.set_script_timeout(selenium.script_timeout)


def parse_driver_timeout(request) -> Optional[Union[int, float]]:
    """Parse driver timeout value from pytest request object"""
    mark = request.node.get_closest_marker("driver_timeout")
    if mark is None:
        return None
    else:
        return mark.args[0]
