import ast
import pickle
import sys
from base64 import b64decode, b64encode
from copy import deepcopy
from typing import Any, Callable, Collection

from pyodide_test_runner.utils import package_is_built as _package_is_built


def package_is_built(package_name):
    return _package_is_built(package_name, pytest.pyodide_dist_dir)


import pytest


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


def _create_outer_test_function(
    run_test: Callable,
    node: ast.stmt,
) -> Callable:
    """
    Create the top level item: it will be called by pytest and it calls
    run_test.

    If the original function looked like:

        @outer_decorators
        @run_in_pyodide
        @inner_decorators
        <async?> def func(<selenium_arg_name>, arg1, arg2, arg3):
            # do stuff

    This wrapper looks like:

        def <func_name>(<selenium_arg_name>, arg1, arg2, arg3):
            run_test(<selenium_arg_name>, (arg1, arg2, arg3))

    Any inner_decorators get ignored. Any outer_decorators get applied by
    the Python interpreter via the normal mechanism
    """
    node_args = deepcopy(node.args)
    if not node_args.args:
        raise ValueError(
            f"Function {node.name} should take at least one argument whose name should start with 'selenium'"
        )

    selenium_arg_name = node_args.args[0].arg
    if not selenium_arg_name.startswith("selenium"):
        raise ValueError(
            f"Function {node.name}'s first argument name '{selenium_arg_name}' should start with 'selenium'"
        )

    new_node = ast.FunctionDef(
        name=node.name, args=node_args, body=[], lineno=1, decorator_list=[]
    )

    # Make onwards call with two args:
    # 1. <selenium_arg_name>
    # 2. all other arguments in a tuple
    func_body = ast.parse("run_test(selenium_arg_name, (arg1, arg2, ...))").body
    onwards_call = func_body[0].value
    onwards_call.args[0].id = selenium_arg_name  # Set variable name
    onwards_call.args[1].elts = [  # Set tuple elements
        ast.Name(id=arg.arg, ctx=ast.Load()) for arg in node_args.args[1:]
    ]

    # Add extra <selenium_arg_name> argument
    new_node.body = func_body

    # Make a best effort to show something that isn't total nonsense in the
    # traceback for the generated function when there is an error.
    # This will show:
    # >   run_test(selenium_arg_name, (arg1, arg2, ...))
    # in the traceback.
    def fake_body_for_traceback(arg1, arg2, selenium_arg_name):
        run_test(selenium_arg_name, (arg1, arg2, ...))

    # Adjust line numbers to point into our fake function
    lineno = fake_body_for_traceback.__code__.co_firstlineno
    ast.increment_lineno(new_node, lineno)

    mod = ast.Module([new_node], type_ignores=[])
    ast.fix_missing_locations(mod)
    co = compile(mod, __file__, "exec")

    # Need to give our code access to the actual "run_test" object which it
    # invokes.
    globs = {"run_test": run_test}
    exec(co, globs)

    return globs[node.name]


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
        packages: Collection[str] = (),
        pytest_assert_rewrites: bool = True,
        *,
        _force_assert_rewrites: bool = False,
    ):
        """
        This decorator can be called in two ways --- with arguments and without
        arguments. If it is called without arguments, then the `function` argument
        catches the function the decorator is applied to. Otherwise, standalone and
        packages are the actual arguments to the decorator.

        See docs/testing.md for details on how to use this.

        Parameters
        ----------
        packages : List[str]
            List of packages to load before running the test

        pytest_assert_rewrites : bool, default = True
            If True, use pytest assertion rewrites. This gives better error messages
            when an assertion fails, but requires us to load pytest.
        """

        from conftest import ORIGINAL_MODULE_ASTS, REWRITTEN_MODULE_ASTS

        self._pkgs = list(packages)
        self._pytest_not_built = False
        if (
            pytest_assert_rewrites
            and not package_is_built("pytest")
            and not _force_assert_rewrites
        ):
            pytest_assert_rewrites = False
            self._pytest_not_built = True

        if pytest_assert_rewrites:
            self._pkgs.append("pytest")

        self._module_asts_dict = (
            REWRITTEN_MODULE_ASTS if pytest_assert_rewrites else ORIGINAL_MODULE_ASTS
        )

        if package_is_built("tblib"):
            self._pkgs.append("tblib")

        self._pytest_assert_rewrites = pytest_assert_rewrites

    def _code_template(self, args: tuple) -> str:
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
            args = pickle.loads(b64decode({_encode(args)!r}))
            co = compile(mod, {self._module_filename!r}, "exec")
            d = {{}}
            exec(co, d)
            def encode(x):
                return b64encode(pickle.dumps(x)).decode()
            try:
                result = d[{self._func_name!r}](None, *args)
                if {self._async_func}:
                    result = await result
                return [0, encode(result)]
            except BaseException as e:
                try:
                    from tblib import pickling_support
                    pickling_support.install()
                except ImportError:
                    pass
                return [1, encode(e)]

        try:
            result = await __tmp()
        finally:
            del __tmp
        result
        """

    def _run_test(self, selenium: SeleniumType, args: tuple):
        """The main test runner, called from the AST generated in
        _create_outer_test_function."""
        code = self._code_template(args)
        if self._pkgs:
            selenium.load_package(self._pkgs)

        r = selenium.run_async(code)
        [status, result] = r

        result = pickle.loads(b64decode(result))
        if status:
            raise result
        else:
            return result

    def _generate_pyodide_ast(
        self, module_ast: ast.Module, funcname: str, func_line_no: int
    ) -> tuple[ast.Module, bool, ast.expr]:
        """Generates appropriate AST for the test to run in Pyodide.

        The test ast includes mypy magic imports and the test function definition.
        This will be pickled and sent to Pyodide.
        """
        nodes: list[ast.stmt] = []
        it = iter(module_ast.body)
        while True:
            try:
                node = next(it)
            except StopIteration:
                raise Exception(
                    f"Didn't find function {funcname} (line {func_line_no}) in module."
                ) from None
            # We need to include the magic imports that pytest inserts
            if (
                isinstance(node, ast.Import)
                and node.names[0].asname
                and node.names[0].asname.startswith("@")
            ):
                nodes.append(node)

            # We also want the function definition for the current test
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.end_lineno > func_line_no and node.lineno < func_line_no:
                it = iter(node.body)
                continue

            if node.lineno < func_line_no:
                continue

            if node.name != funcname:
                raise RuntimeError(
                    f"Internal run_in_pyodide error: looking for function '{funcname}' but found '{node.name}'"
                )

            self._async_func = isinstance(node, ast.AsyncFunctionDef)
            node.decorator_list = []
            nodes.append(node)
            break

        self._mod = ast.Module(nodes, type_ignores=[])
        ast.fix_missing_locations(self._mod)

        self._node = node

    def __call__(self, f: Callable) -> Callable:
        func_name = f.__name__
        module_filename = sys.modules[f.__module__].__file__ or ""
        module_ast = self._module_asts_dict[module_filename]

        func_line_no = f.__code__.co_firstlineno

        # _code_template needs this info.
        self._generate_pyodide_ast(module_ast, func_name, func_line_no)
        self._func_name = func_name
        self._module_filename = module_filename

        wrapper = _create_outer_test_function(self._run_test, self._node)

        return wrapper
