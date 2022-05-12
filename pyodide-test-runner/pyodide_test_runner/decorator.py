import ast
import pickle
import sys
from ast import (
    Assign,
    AsyncFunctionDef,
    Call,
    Expr,
    FunctionDef,
    Import,
    Load,
    Module,
    Name,
    Store,
    Tuple,
)
from base64 import b64decode, b64encode
from copy import deepcopy
from traceback import TracebackException
from typing import Any, Callable, Collection

import pytest

from .utils import set_webdriver_script_timeout

REWRITTEN_MODULES: dict[str, Any] = {}
ORIGINAL_MODULES: dict[str, Any] = {}


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


def _generate_pyodide_ast(
    module_ast: ast.Module, funcname: str
) -> tuple[ast.Module, bool, ast.expr]:
    """Generates appropriate AST for the test to run in Pyodide.

    The test ast includes mypy magic imports and the test function definition.
    This will be pickled and sent to Pyodide.
    """
    nodes: list[ast.stmt] = []
    for node in module_ast.body:
        # We need to include the magic imports that pytest inserts
        if (
            isinstance(node, Import)
            and node.names[0].asname
            and node.names[0].asname.startswith("@")
        ):
            nodes.append(node)

        # We also want the function definition for the current test
        if isinstance(node, FunctionDef) or isinstance(node, AsyncFunctionDef):
            if node.name == funcname:
                async_func = isinstance(node, AsyncFunctionDef)
                node.decorator_list = []
                nodes.append(node)
                break
    else:
        raise Exception(
            "Didn't find function in module. @run_in_pyodide can only be used with top-level names"
        )
    mod = ast.Module(nodes, type_ignores=[])
    ast.fix_missing_locations(mod)

    return mod, async_func, node


def _create_outer_test_function(
    run_test: Callable,
    selenium_arg_name: str,
    node: ast.stmt,
) -> Callable:
    """
    Create the top level item: it will be called by pytest and it calls
    run_test.

    If the original function looked like:

        @outer_decorators
        @run_in_pyodide
        @inner_decorators
        <async?> def func(arg1, arg2, arg3):
            # do stuff

    This wrapper looks like:

        def <func_name>(arg1, arg2, arg3, <selenium_arg_name>):
            run_test(<selenium_arg_name>, tuple(arg1, arg2, arg3))

    Any inner_decorators get applied in __call__. Any outer_decorators get applied
    by the Python interpreter via the normal mechanism
    """
    node = deepcopy(node)

    if isinstance(node, AsyncFunctionDef):
        # wrapper should be sync, convert AsyncFunctionDef ==> FunctionDef.
        node = FunctionDef(**node.__dict__)

    # tuple (arg1, arg2, arg3)
    func_args_tuple = Tuple(
        [Name(id=arg.arg, ctx=Load()) for arg in node.args.args], ctx=Load()
    )

    # Add extra <selenium_arg_name> argument
    node.args.args.append(ast.arg(arg=selenium_arg_name))

    # Make onwards call with two args:
    # 1. <selenium_arg_name>
    # 2. all other arguments in a tuple
    onwargs_call_args = [Name(id=selenium_arg_name, ctx=Load()), func_args_tuple]
    onwargs_call = Call(
        func=Name(id="run_test", ctx=Load()), args=onwargs_call_args, keywords=[]
    )
    node.body = [Expr(value=onwargs_call)]

    mod = Module([node], type_ignores=[])
    ast.fix_missing_locations(mod)
    co = compile(mod, __file__, "exec")

    # Need to give our code access to the actual "run_test" object!
    globs = {"run_test": run_test}
    exec(co, globs)

    return globs[node.name]


def _execute_module_for_decorators(
    module_ast: ast.Module, module_filename: str
) -> dict[str, any]:
    """
    Collect the actual real-life objects that were applied to the function into
    a magic variable called @decorators@<func_name>

    This helps us to locate `run_in_pyodide` to remove it in a way that is
    robust to renaming. This also allows us to use other decorators in a way
    that is robust to renaming.
    """
    for i, node in reversed(list(enumerate(module_ast.body))):
        if isinstance(node, FunctionDef) or isinstance(node, AsyncFunctionDef):
            # Store the decorators for each FunctionDef into our magic variable
            assign_target = [Name(id="@decorators@" + node.name, ctx=Store())]
            assign_value = Tuple(node.decorator_list, ctx=Load())
            decs = Assign(targets=assign_target, value=assign_value)
            module_ast.body.insert(i, decs)
            node.decorator_list = []  # Avoid recursion issues
    ast.fix_missing_locations(module_ast)
    co = compile(module_ast, module_filename, "exec")

    import types

    module = types.ModuleType(module_filename)
    module.__file__ = module_filename
    exec(co, module.__dict__)
    return module.__dict__


# This has to be a class so we can identify it in and remove it from a list of
# decorators
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
        standalone: bool = False,
        module_scope: bool = False,
        packages: Collection[str] = (),
        xfail_browsers: dict[str, str] | None = None,
        driver_timeout: float | None = None,
        pytest_assert_rewrites: bool = True,
    ):
        """
        This decorator can be called in two ways --- with arguments and without
        arguments. If it is called without arguments, then the `function` argument
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
        self._module_dict = (
            REWRITTEN_MODULES if pytest_assert_rewrites else ORIGINAL_MODULES
        )

        self._pkgs = list(packages)
        if pytest_assert_rewrites:
            self._pkgs.append("pytest")
        self._xfail_browsers = xfail_browsers or {}
        self._driver_timeout = driver_timeout
        self._pytest_assert_rewrites = pytest_assert_rewrites
        if standalone:
            self._selenium_fixture_name = "selenium_standalone"
        elif module_scope:
            self._selenium_fixture_name = "selenium_module_scope"
        else:
            self._selenium_fixture_name = "selenium"

    def _code_template(self, args: tuple) -> str:
        """
        Unpickle function ast and its arguments, compile and call function, and
        if the function is async await the result. Last, if there was an
        exception, pickle it and send it back.
        """
        print("args: ======", args)
        return f"""
        async def __tmp():
            from base64 import b64encode, b64decode
            import pickle
            mod = pickle.loads(b64decode({_encode(self._mod)!r}))
            args = pickle.loads(b64decode({_encode(args)!r}))
            co = compile(mod, {self._module_filename!r}, "exec")
            d = {{}}
            exec(co, d)
            try:
                result = d[{self._func_name!r}](*args)
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

    def _run_test(self, selenium: SeleniumType, args: tuple):
        """The main test runner, called from the AST generated in
        _create_outer_test_function."""
        if selenium.browser in self._xfail_browsers:
            xfail_message = self._xfail_browsers[selenium.browser]
            pytest.xfail(xfail_message)

        code = self._code_template(args)

        with set_webdriver_script_timeout(selenium, self._driver_timeout):
            if self._pkgs:
                selenium.load_package(self._pkgs)

            result = selenium.run_async(code)

        if result:
            err = pickle.loads(b64decode(result))
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

    def __call__(self, f: Callable) -> Callable:
        func_name = f.__name__
        module_filename = sys.modules[f.__module__].__file__ or ""
        module_ast = self._module_asts_dict[module_filename]

        # We need to get the decorator list off of self._module_dict
        if module_filename not in self._module_dict:
            self._module_dict[module_filename] = _execute_module_for_decorators(
                module_ast, module_filename
            )
        module_env = self._module_dict[module_filename]
        orig_decorator_list = module_env[f"@decorators@{func_name}"]

        # We are currently applying the run_in_pyodide decorator, all of the
        # decorators before it will be applied later. We need to track down the
        # decorators inside of us and apply them.
        for _idx, dec in enumerate(orig_decorator_list):
            if dec == run_in_pyodide or isinstance(dec, run_in_pyodide):
                break
        decorators = orig_decorator_list[_idx + 1 :]

        # _code_template needs this info.
        self._mod, self._async_func, self._node = _generate_pyodide_ast(
            module_ast, func_name
        )
        self._func_name = func_name
        self._module_filename = module_filename

        wrapper = _create_outer_test_function(
            self._run_test, self._selenium_fixture_name, self._node
        )
        # Apply the inside decorators ourselves.
        # Technically it would be more accurate to pickle these and apply them
        # in Pyodide, but I'm slightly pessimistic about that working.
        for dec in reversed(decorators):
            wrapper = dec(wrapper)
        return wrapper
