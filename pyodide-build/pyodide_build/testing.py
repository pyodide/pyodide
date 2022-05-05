import contextlib
from typing import Callable, Collection

import pytest

def chunkstring(string, length):
    return (string[0 + i : length + i] for i in range(0, len(string), length))


def _encode_ast(module_ast, funcname):
    import ast
    import pickle
    from base64 import b64encode 
    nodes = []
    for node in module_ast.body:
        if isinstance(node, ast.Import) and node.names[0].asname and node.names[0].asname.startswith("@"):
            nodes.append(node)

        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            if node.name == funcname:
                node.decorator_list = []
                nodes.append(node)
                break
    mod = ast.Module(nodes, type_ignores=[])
    ast.fix_missing_locations(mod)


    from astpretty import pprint
    pprint(mod)
    serialized_mod = pickle.dumps(mod)
    encoded_mod = b64encode(serialized_mod)
    string_mod = encoded_mod.decode()
    return string_mod


def run_in_pyodide(
    _function: Callable | None = None,
    *,
    standalone: bool = False,
    module_scope: bool = False,
    packages: Collection[str] = (),
    xfail_browsers: dict[str, str] | None = None,
    driver_timeout: float | None = None,
    use_pytest: bool = True,
) -> Callable:
    """
    This decorator can be called in two ways --- with arguments and without
    arguments. If it is called without arguments, then the `_function` kwarg
    catches the function the decorator is applied to. Otherwise, standalone
    and packages are the actual arguments to the decorator.

    See docs/testing.md for details on how to use this.

    Parameters
    ----------
    standalone : bool, default=False
        Whether to use a standalone selenium instance to run the test or not
    packages : List[str]
        List of packages to load before running the test
    driver_timeout : Optional[float]
        selenium driver timeout (in seconds)
    """
    xfail_browsers_local = xfail_browsers or {}

    def decorator(f):

        import sys
        

        from conftest import ORIGINAL_MODULE_ASTS, REWRITTEN_MODULE_ASTS
        
        import sys
        module_fname = sys.modules[f.__module__].__file__
        if module_fname not in ORIGINAL_MODULE_ASTS:
            return

        if use_pytest:
            module_ast = REWRITTEN_MODULE_ASTS[module_fname]
        else:
            module_ast = ORIGINAL_MODULE_ASTS[module_fname]

        string_mod = _encode_ast(module_ast, f.__name__)

     

        def inner(selenium):
            if selenium.browser in xfail_browsers_local:
                xfail_message = xfail_browsers_local[selenium.browser]
                pytest.xfail(xfail_message)
            with set_webdriver_script_timeout(selenium, driver_timeout):
                pkgs = list(packages)
                if use_pytest:
                    pkgs.append("pytest")
                selenium.load_package(pkgs)
                err = None
                try:
                    selenium.run(
                        f"""
                        def tmp():
                            from base64 import b64decode
                            import pickle
                            serialized_mod = b64decode({string_mod!r})
                            mod = pickle.loads(serialized_mod)
                            co = compile(mod, {module_fname!r}, "exec")
                            d = {{}}
                            exec(co, d)
                            d[{f.__name__!r}]()

                        try:
                            tmp()
                        finally:
                            del tmp
                        """
                    )
                except selenium.JavascriptException as e:
                    err = e

            if err is not None:
                pytest.fail(
                    "Error running function in pyodide\n\n" + str(err),
                    pytrace=False,
                )

        if standalone:

            def wrapped(selenium_standalone):
                inner(selenium_standalone)

        elif module_scope:

            def wrapped(selenium_module_scope):  # type: ignore[misc]
                inner(selenium_module_scope)

        else:

            def wrapped(selenium):  # type: ignore[misc]
                inner(selenium)

        return wrapped

    if _function is not None:
        return decorator(_function)
    else:
        return decorator


@contextlib.contextmanager
def set_webdriver_script_timeout(selenium, script_timeout: float | None):
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


def parse_driver_timeout(request) -> float | None:
    """Parse driver timeout value from pytest request object"""
    mark = request.node.get_closest_marker("driver_timeout")
    if mark is None:
        return None
    else:
        return mark.args[0]
