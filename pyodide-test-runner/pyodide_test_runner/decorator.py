import ast
import pickle
import sys
from base64 import b64decode, b64encode
from traceback import TracebackException
from typing import Any, Callable, Collection

import pytest

from .utils import set_webdriver_script_timeout


class SeleniumType:
    JavascriptException: type
    browser: str

    def load_package(self, *args, **kwargs):
        ...

    def run_async(self, code: str):
        ...


def _encode(obj: Any) -> str:
    """
    Pickle and base 64 encode obj so we can send it to Pyodide using string
    templating.
    """
    return b64encode(pickle.dumps(obj)).decode()


class run_in_pyodide:
    def __new__(cls, function: Callable | None = None, /, **kwargs):
        if function:
            # Probably we were used like:
            #
            # @run_in_pyodide
            # def f():
            #   pass
            return run_in_pyodide(**kwargs)(function)
        else:
            # Just do normal __new__ behavior
            return object.__new__(cls)

    def __init__(
        self,
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

        from conftest import ORIGINAL_MODULE_ASTS, REWRITTEN_MODULE_ASTS

        self._module_asts_dict = (
            REWRITTEN_MODULE_ASTS if pytest_assert_rewrites else ORIGINAL_MODULE_ASTS
        )

        self._pkgs = list(packages)
        if pytest_assert_rewrites:
            self._pkgs.append("pytest")
        self._xfail_browsers = xfail_browsers or {}
        self._driver_timeout = driver_timeout
        self._pytest_assert_rewrites = pytest_assert_rewrites
        self._standalone = standalone
        self._module_scope = module_scope

    def _code_template(self) -> str:
        """
        Unpickle function ast and its arguments, compile and call function, and
        if the function is async await the result. Last, if there was an
        exception, pickle it and send it back.
        """
        return f"""
        async def __tmp():
            from base64 import b64encode, b64decode
            import pickle
            mod = pickle.loads(b64decode({_encode(self._mod)!r}))
            co = compile(mod, {self._module_filename!r}, "exec")
            d = {{}}
            exec(co, d)
            try:
                result = d[{self._func_name!r}]()
                if {self._async_func}:
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

    def _run_test(self, selenium: SeleniumType, f):
        if selenium.browser in self._xfail_browsers:
            xfail_message = self._xfail_browsers[selenium.browser]
            pytest.xfail(xfail_message)

        code = self._code_template()
        with set_webdriver_script_timeout(selenium, self._driver_timeout):
            if self._pkgs:
                selenium.load_package(self._pkgs)

            result = selenium.run_async(code)

        if result:
            err: TracebackException = pickle.loads(b64decode(result))
            err.stack.pop(0)  # Get rid of __tmp in traceback
            self._fail(err)

    def _fail(self, err: TracebackException):
        """
        Fail the test with a helpful message.

        Separated out for test mock purposes.
        """
        pytest.fail(
            "Error running function in pyodide\n\n" + "".join(err.format(chain=True)),
            pytrace=False,
        )

    def _generate_pyodide_ast(
        self, module_ast: ast.Module, funcname: str
    ) -> tuple[ast.Module, bool, ast.expr]:
        """Generates appropriate AST for the test to run in Pyodide.

        The test ast includes mypy magic imports and the test function definition.
        This will be pickled and sent to Pyodide.
        """
        nodes: list[ast.stmt] = []
        for node in module_ast.body:
            # We need to include the magic imports that pytest inserts
            if (
                isinstance(node, ast.Import)
                and node.names[0].asname
                and node.names[0].asname.startswith("@")
            ):
                nodes.append(node)

            # We also want the function definition for the current test
            if isinstance(node, ast.FunctionDef) or isinstance(
                node, ast.AsyncFunctionDef
            ):
                if node.name == funcname:
                    self._async_func = isinstance(node, ast.AsyncFunctionDef)
                    node.decorator_list = []
                    nodes.append(node)
                    break
        else:
            raise Exception(
                "Didn't find function in module. @run_in_pyodide can only be used with top-level names"
            )

        self._mod = ast.Module(nodes, type_ignores=[])
        ast.fix_missing_locations(self._mod)

    def __call__(self, f: Callable) -> Callable:
        func_name = f.__name__
        module_filename = sys.modules[f.__module__].__file__ or ""
        module_ast = self._module_asts_dict[module_filename]

        # _code_template needs this info.
        self._generate_pyodide_ast(module_ast, func_name)
        self._func_name = func_name
        self._module_filename = module_filename

        if self._standalone:

            def wrapper(selenium_standalone):
                self._run_test(selenium_standalone, f)

        elif self._module_scope:

            def wrapper(selenium_module_scope):  # type: ignore[misc]
                self._run_test(selenium_module_scope, f)

        else:

            def wrapper(selenium):  # type: ignore[misc]
                self._run_test(selenium, f)

        return wrapper
