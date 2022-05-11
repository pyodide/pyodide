import ast
import pickle
import sys
import traceback
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
from typing import Any, Callable, Collection

import pytest

from .utils import set_webdriver_script_timeout

REWRITTEN_MODULES: dict[str, Any] = {}
ORIGINAL_MODULES: dict[str, Any] = {}


def _encode(obj: Any) -> str:
    """
    Pickle and base 64 encode
    """
    return b64encode(pickle.dumps(obj)).decode()


def _generate_ast(
    module_ast: ast.Module, funcname: str
) -> tuple[ast.Module, bool, ast.expr]:
    """Generates an appropriate AST for the test.

    The test ast should include mypy magic imports and the test function
    definition. Once we generate this module, we pickle it and base64 encode it
    so we can send it to Pyodide using string templating.
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


def _create_wrapper(
    func_name: str,
    run_test: Callable,
    selenium_arg_name: str,
    node: ast.stmt,
) -> Callable:
    node = deepcopy(node)
    call_args = [Name(id=selenium_arg_name, ctx=Load())]
    func_args = []
    for arg in node.args.args:
        func_args.append(Name(id=arg.arg, ctx=Load()))
    call_args.append(Tuple(func_args, ctx=Load()))
    node.args.args.append(ast.arg(arg=selenium_arg_name))
    node.body = [
        Expr(
            value=Call(
                func=Name(id="run_test", ctx=Load()), args=call_args, keywords=[]
            )
        )
    ]

    mod = Module([node], type_ignores=[])
    ast.fix_missing_locations(mod)
    co = compile(mod, __file__, "exec")
    globs = {"run_test": run_test}
    exec(co, globs)

    return globs[func_name]


def _process_module(module_ast: ast.Module, module_filename: str) -> dict[str, any]:
    for i, node in reversed(list(enumerate(module_ast.body))):
        if isinstance(node, FunctionDef) or isinstance(node, AsyncFunctionDef):
            assign_target = [Name(id="@decorators@" + node.name, ctx=Store())]
            assign_value = Tuple(node.decorator_list, ctx=Load())
            decs = Assign(targets=assign_target, value=assign_value)
            module_ast.body.insert(i, decs)
            node.decorator_list = []
    ast.fix_missing_locations(module_ast)
    co = compile(module_ast, module_filename, "exec")
    result = {}
    exec(co, result)
    return result


class run_in_pyodide:
    def __new__(cls, function: Callable | None = None, /, **kwargs):
        if function:
            return run_in_pyodide(**kwargs)(function)
        else:
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
        self.xfail_browsers = xfail_browsers or {}

        from conftest import ORIGINAL_MODULE_ASTS, REWRITTEN_MODULE_ASTS

        self.module_asts_dict = (
            REWRITTEN_MODULE_ASTS if pytest_assert_rewrites else ORIGINAL_MODULE_ASTS
        )
        self.module_dict = (
            REWRITTEN_MODULES if pytest_assert_rewrites else ORIGINAL_MODULES
        )

        self.pkgs = list(packages)
        if pytest_assert_rewrites:
            self.pkgs.append("pytest")
        self.xfail_browsers = xfail_browsers or {}
        self.driver_timeout = driver_timeout
        self.pytest_assert_rewrites = pytest_assert_rewrites
        if standalone:
            self.selenium_fixture_name = "selenium_standalone"
        elif module_scope:
            self.selenium_fixture_name = "selenium_module_scope"
        else:
            self.selenium_fixture_name = "selenium"

    def _code_template(self, args) -> str:
        return f"""
        async def __tmp():
            from base64 import b64encode, b64decode
            import pickle
            mod = pickle.loads(b64decode({_encode(self.mod)!r}))
            args = pickle.loads(b64decode({_encode(args)!r}))
            co = compile(mod, {self.module_filename!r}, "exec")
            d = {{}}
            exec(co, d)
            try:
                result = d[{self.func_name!r}](*args)
                if {self.async_func}:
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

    def run_test(self, selenium, args):
        if selenium.browser in self.xfail_browsers:
            xfail_message = self.xfail_browsers[selenium.browser]
            pytest.xfail(xfail_message)

        with set_webdriver_script_timeout(selenium, self.driver_timeout):
            if self.pkgs:
                selenium.load_package(self.pkgs)

            code = self._code_template(args)
            result = selenium.run_async(code)
            if result:
                err: traceback.TracebackException = pickle.loads(b64decode(result))
            else:
                err = None

        if err:
            pytest.fail(
                "Error running function in pyodide\n\n"
                + "".join(err.format(chain=True)),
                pytrace=False,
            )

    def __call__(self, f):
        func_name = f.__name__
        module_filename = sys.modules[f.__module__].__file__ or ""
        module_ast = self.module_asts_dict[module_filename]
        if module_filename not in self.module_dict:
            self.module_dict[module_filename] = _process_module(
                module_ast, module_filename
            )
        module_env = self.module_dict[module_filename]
        decorators = []
        for dec in module_env[f"@decorators@{func_name}"]:
            if dec != run_in_pyodide and not isinstance(dec, run_in_pyodide):
                decorators.append(dec)

        self.mod, self.async_func, self.node = _generate_ast(module_ast, func_name)
        self.func_name = func_name
        self.module_filename = module_filename

        wrapper = _create_wrapper(
            func_name, self.run_test, self.selenium_fixture_name, self.node
        )
        for dec in reversed(decorators):
            wrapper = dec(wrapper)
        return wrapper
