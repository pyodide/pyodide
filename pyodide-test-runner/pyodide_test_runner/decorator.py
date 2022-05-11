import ast
import pickle
import sys
import traceback
from copy import deepcopy
from base64 import b64decode, b64encode
from typing import Any, Callable, Collection

import pytest

from .utils import set_webdriver_script_timeout


def _encode_ast(module_ast : ast.Module, funcname : str) -> tuple[str, bool, ast.expr, list[ast.Import]]:
    """Generates an appropriate AST for the test.

    The test ast should include mypy magic imports and the test function
    definition. Once we generate this module, we pickle it and base64 encode it
    so we can send it to Pyodide using string templating.
    """
    from ast import Import, Try, ExceptHandler, Pass, Name, Load
    imports : list[ast.Import] = []
    nodes: list[ast.stmt] = []
    for node in module_ast.body:
        # We need to include the magic imports that pytest inserts
        if isinstance(node, ast.Import):
            imports.append(node)
            nodes.append(
                Try(body=[node], handlers=[
                    ExceptHandler(type=Name(id='ImportError', ctx=Load()), name=None, body=[
                        Pass(),
                    ]),
                ], orelse=[], finalbody=[])
            )

        # We also want the function definition for the current test
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            if node.name == funcname:
                saved_node = deepcopy(node)
                async_func = isinstance(node, ast.AsyncFunctionDef)
                node.decorator_list = []
                nodes.append(node)
                break
    else:
        raise Exception("Didn't find function in module. @run_in_pyodide can only be used with top-level names")
    mod = ast.Module(nodes, type_ignores=[])
    ast.fix_missing_locations(mod)

    serialized_mod = pickle.dumps(mod)
    encoded_mod = b64encode(serialized_mod)
    string_mod = encoded_mod.decode()
    return string_mod, async_func, saved_node, imports


def _code_template(
    encoded_ast : str, module_filename : str, func_name : str, async_func : bool, args
) -> str:
    return f"""
    async def __tmp():
        from base64 import b64encode, b64decode
        import pickle
        serialized_mod = b64decode({encoded_ast!r})
        mod = pickle.loads(serialized_mod)
        co = compile(mod, {module_filename!r}, "exec")
        d = {{}}
        exec(co, d)
        try:
            result = d[{func_name!r}](*{args!r})
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

def _run_test(selenium : any, encoded_ast : str, module_filename : str, func_name : str, async_func : bool, args):
    code = _code_template(encoded_ast, module_filename, func_name, async_func, args)
    result = selenium.run_async(code)
    if result:
        return pickle.loads(b64decode(result))
    else:
        return None

def _create_wrapper(func_name, run_test, selenium_arg_name, node, imports):
    from ast import Module, FunctionDef, Name, Load, Expr, Call, Tuple
    access_selenium = Name(id=selenium_arg_name, ctx=Load())
    
    node = deepcopy(node)
    from pprintast import pprintast
    call_args = [Name(id=selenium_arg_name, ctx=Load())]
    func_args = []
    for arg in node.args.args:
        func_args.append(Name(id=arg.arg, ctx=Load()))
    call_args.append(Tuple(func_args, ctx=Load()))
    node.args.args.append(ast.arg(arg=selenium_arg_name))
    # pprintast(node)
    node.body = [Expr(value=Call(func=Name(id='run_test', ctx=Load()), args=call_args, keywords=[]))]

    for i, dec in enumerate(node.decorator_list):
        if isinstance(dec, Name):
            name = dec.id
        elif isinstance(dec, Call):
            name = dec.func.id
        if name == "run_in_pyodide":
            del node.decorator_list[i]
            break
    mod = Module(imports + [node], type_ignores=[])
    ast.fix_missing_locations(mod)
    co = compile(mod, __file__, "exec")
    globs = {"run_test" : run_test}
    exec(co, globs)
    return globs[func_name]

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
        func_name = f.__name__
        module_filename = sys.modules[f.__module__].__file__ or ""
        module_ast = module_asts_dict[module_filename]
        encoded_ast, async_func, node, imports = _encode_ast(module_ast, func_name)

        def run_test(selenium, args):
            if selenium.browser in xfail_browsers_local:
                xfail_message = xfail_browsers_local[selenium.browser]
                pytest.xfail(xfail_message)

            with set_webdriver_script_timeout(selenium, driver_timeout):
                if pkgs:
                    selenium.load_package(pkgs)
                err = _run_test(selenium, encoded_ast, module_filename, func_name, async_func, args)

            if err:
                pytest.fail(
                    "Error running function in pyodide\n\n"
                    + "".join(err.format(chain=True)),
                    pytrace=False,
                )
        
        if standalone:
            selenium_arg_name = "selenium_standalone"
        elif module_scope:
            selenium_arg_name = "selenium_module_scope"
        else:
            selenium_arg_name = "selenium"
        return _create_wrapper(func_name, run_test, selenium_arg_name, node, imports)
    if _function is not None:
        return decorator(_function)
    else:
        return decorator
