import ast
import pickle
import sys
import traceback
from base64 import b64decode, b64encode
from typing import Any, Callable, Collection

import pytest

from .utils import set_webdriver_script_timeout


def _encode_ast(module_ast, funcname):
    """Generates an appropriate AST for the test.

    The test ast should include mypy magic imports and the test function
    definition. Once we generate this module, we pickle it and base64 encode it
    so we can send it to Pyodide using string templating.
    """

    nodes: list[Any] = []
    for node in module_ast.body:
        # We need to include the magic imports that pytest inserts
        if (
            isinstance(node, ast.Import)
            and node.names[0].asname
            and node.names[0].asname.startswith("@")
        ):
            nodes.append(node)

        # We also want the function definition for the current test
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            if node.name == funcname:
                async_func = isinstance(node, ast.AsyncFunctionDef)
                node.decorator_list = []
                nodes.append(node)
                break
    mod = ast.Module(nodes, type_ignores=[])
    ast.fix_missing_locations(mod)

    serialized_mod = pickle.dumps(mod)
    encoded_mod = b64encode(serialized_mod)
    string_mod = encoded_mod.decode()
    return string_mod, async_func


def _run_in_pyodide_run(
    selenium: Any, f: Any, module_asts_dict: dict[str, ast.Module]
) -> traceback.TracebackException | None:
    module_fname = sys.modules[f.__module__].__file__ or ""
    module_ast = module_asts_dict[module_fname]
    string_mod, async_func = _encode_ast(module_ast, f.__name__)
    result = selenium.run_async(
        f"""
        async def __tmp():
            from base64 import b64encode, b64decode
            import pickle
            serialized_mod = b64decode({string_mod!r})
            mod = pickle.loads(serialized_mod)
            co = compile(mod, {module_fname!r}, "exec")
            d = {{}}
            exec(co, d)
            try:
                result = d[{f.__name__!r}]()
                if {async_func}:
                    result = await result
            except BaseException as e:
                import traceback
                tb = traceback.TracebackException(type(e), e, e.__traceback__)
                serialized_err = pickle.dumps(tb)
                return b64encode(serialized_err).decode()

        try:
            result = await __tmp()
        finally:
            del __tmp
        result
        """
    )
    if result:
        return pickle.loads(b64decode(result))
    else:
        return None


def run_in_pyodide(
    _function: Callable | None = None,
    *,
    standalone: bool = False,
    module_scope: bool = False,
    packages: Collection[str] = (),
    xfail_browsers: dict[str, str] | None = None,
    driver_timeout: float | None = None,
    pytest_assert_rewrites: bool = True,
) -> Callable:
    """
    This decorator can be called in two ways --- with arguments and without
    arguments. If it is called without arguments, then the `_function` kwarg
    catches the function the decorator is applied to. Otherwise, standalone and
    packages are the actual arguments to the decorator.

    See docs/testing.md for details on how to use this.

    Parameters
    ----------
    standalone : bool, default=False
        Whether to use a standalone selenium instance to run the test or not

    packages : List[str]
        List of packages to load before running the test

    xfail_browsers: dict[str, str]
        A dictionary of browsers to xfail the test and reasons for the xfails.

    driver_timeout : Optional[float]
        selenium driver timeout (in seconds). If missing, use the default
        timeout.

    pytest_assert_rewrites : bool, default = True
        If True, use pytest assertion rewrites. This gives better error messages
        when an assertion fails, but requires us to load pytest.
    """
    xfail_browsers_local = xfail_browsers or {}

    from conftest import ORIGINAL_MODULE_ASTS, REWRITTEN_MODULE_ASTS

    module_asts_dict = (
        REWRITTEN_MODULE_ASTS if pytest_assert_rewrites else ORIGINAL_MODULE_ASTS
    )

    pkgs = list(packages)
    if pytest_assert_rewrites:
        pkgs.append("pytest")

    def decorator(f):
        def run_test(selenium):
            if selenium.browser in xfail_browsers_local:
                xfail_message = xfail_browsers_local[selenium.browser]
                pytest.xfail(xfail_message)

            with set_webdriver_script_timeout(selenium, driver_timeout):
                if pkgs:
                    selenium.load_package(pkgs)
                err = _run_in_pyodide_run(selenium, f, module_asts_dict)

            if err:
                pytest.fail(
                    "Error running function in pyodide\n\n"
                    + "".join(err.format(chain=True)),
                    pytrace=False,
                )

        if standalone:

            def wrapped(selenium_standalone):
                run_test(selenium_standalone)

        elif module_scope:

            def wrapped(selenium_module_scope):  # type: ignore[misc]
                run_test(selenium_module_scope)

        else:

            def wrapped(selenium):  # type: ignore[misc]
                run_test(selenium)

        return wrapped

    if _function is not None:
        return decorator(_function)
    else:
        return decorator
