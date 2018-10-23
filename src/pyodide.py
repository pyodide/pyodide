"""
A library of helper utilities for connecting Python to the browser environment.
"""

import ast
import io
import sys

__version__ = '0.1.11'


def open_url(url):
    """
    Fetches a given *url* and returns a io.StringIO to access its contents.
    """
    from js import XMLHttpRequest

    req = XMLHttpRequest.new()
    req.open('GET', url, False)
    req.send(None)
    return io.StringIO(req.response)


def eval_code(code, ns):
    """
    Runs a string of code, the last part of which may be an expression.
    """
    mod = ast.parse(code)
    if isinstance(mod.body[-1], ast.Expr):
        expr = ast.Expression(mod.body[-1].value)
        del mod.body[-1]
    else:
        expr = None

    if len(mod.body):
        exec(compile(mod, '<exec>', mode='exec'), ns, ns)
    if expr is not None:
        return eval(compile(expr, '<eval>', mode='eval'), ns, ns)
    else:
        return None


def find_imports(code):
    """
    Finds the imports in a string of code and returns a list of their package
    names.
    """
    mod = ast.parse(code)
    imports = set()
    for node in ast.walk(mod):
        if isinstance(node, ast.Import):
            for name in node.names:
                name = name.name
                imports.add(name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            name = node.module
            imports.add(name.split('.')[0])
    return list(imports)


_renamed_modules = {}


def register_import_hook(mock_modules=None, rename_modules=None,
                         mock_class=None):
    """Registed the import hook

    This can be used to either to mock some modules that are missing,
    or import instead of another.

    Only one such hook can be active at a time. For repeated calls,
    only the last one is taken into account, except for module renaming which
    are permanent.

    Parameters
    ----------
    mock_modules : list, default=None
       list of modules names to mock if they cannot be imported.
       This converts ImportError to an ImportWarning and mock modules.

    rename_modules : dict, default=None
       a mapping between the requested modules and the actually
       imported modules

    mock_class : {callable, None}, default=None
       class used to mock modules, must be a subclass of types.ModuleType
    """

    import importlib
    import importlib.abc
    import importlib.machinery
    import warnings
    import types

    if mock_class is None:
        class PyodideMockModule(types.ModuleType):
            def __getattr__(self, key):
                def _raise(*cargs, **kwargs):
                    """The mocked method is called"""
                    raise NotImplementedError(
                            f'{self.name}.{key} is mocked in pyodide..')
                return _raise
    else:
        PyodideMockModule = mock_class

    class PyodidePackageLoader(importlib.abc.Loader):
        def create_module(self, spec):
            module = PyodideMockModule(spec.name)
            module.__spec__ = spec
            return module

        def exec_module(self, module):
            pass

    class FallbackFinder(importlib.abc.MetaPathFinder):
        """This finder will be used if a module is not found by other means

        A module in the whitelist that fails to import will raise an
        ImportWarning instead of an ImportError, and the corresponding
        module will be mocked.
        """
        def find_spec(self, fullname, path, target=None):
            if fullname in mock_modules:
                # only whitelisted modules are mocked
                warnings.warn(f'Failed to import {fullname}, mocking..',
                              ImportWarning, stacklevel=2)
                spec = importlib.machinery.ModuleSpec(
                        fullname, PyodidePackageLoader())
                return spec

    warnings.filterwarnings("default", category=ImportWarning)

    # remove existing hooks
    for finder in list(sys.meta_path):
        if finder.__class__.__name__ == 'FallbackFinder':
            sys.meta_path.remove(finder)

    if mock_modules is not None:
        sys.meta_path.append(FallbackFinder())

    if rename_modules is not None:
        for source, target in rename_modules.items():
            print(f'Renaming modules: {source} -> {target}')
            if target not in sys.modules:
                sys.modules[target] = importlib.import_module(source)
                _renamed_modules[source] = target


__all__ = ['open_url', 'eval_code', 'find_imports']
