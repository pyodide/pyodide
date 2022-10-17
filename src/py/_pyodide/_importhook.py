import sys
from collections.abc import Sequence
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec
from importlib.util import spec_from_loader
from types import ModuleType
from typing import Any


class JsFinder(MetaPathFinder):
    def __init__(self) -> None:
        self.jsproxies: dict[str, Any] = {}

    def find_spec(
        self,
        fullname: str,
        path: Sequence[bytes | str] | None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        assert JsProxy is not None
        [parent, _, child] = fullname.rpartition(".")
        if parent:
            parent_module = sys.modules[parent]
            if not isinstance(parent_module, JsProxy):
                # Not one of us.
                return None
            try:
                jsproxy = getattr(parent_module, child)
            except AttributeError:
                raise ModuleNotFoundError(
                    f"No module named {fullname!r}", name=fullname
                ) from None
            if not isinstance(jsproxy, JsProxy):
                raise ModuleNotFoundError(
                    f"No module named {fullname!r}", name=fullname
                )
        else:
            try:
                jsproxy = self.jsproxies[fullname]
            except KeyError:
                return None
        loader = JsLoader(jsproxy)
        return spec_from_loader(fullname, loader, origin="javascript")

    def register_js_module(self, name: str, jsproxy: Any) -> None:
        """
        Registers ``jsproxy`` as a JavaScript module named ``name``. The module
        can then be imported from Python using the standard Python import
        system. If another module by the same name has already been imported,
        this won't have much effect unless you also delete the imported module
        from ``sys.modules``. This is called by the JavaScript API
        :any:`pyodide.registerJsModule`.

        Parameters
        ----------
        name : str
            Name of js module

        jsproxy : JsProxy
            JavaScript object backing the module
        """
        assert JsProxy is not None
        if not isinstance(name, str):
            raise TypeError(
                f"Argument 'name' must be a str, not {type(name).__name__!r}"
            )
        if not isinstance(jsproxy, JsProxy):
            raise TypeError(
                f"Argument 'jsproxy' must be a JsProxy, not {type(jsproxy).__name__!r}"
            )
        self.jsproxies[name] = jsproxy

    def unregister_js_module(self, name: str) -> None:
        """
        Unregisters a JavaScript module with given name that has been previously
        registered with :any:`pyodide.registerJsModule` or
        :any:`pyodide.ffi.register_js_module`. If a JavaScript module with that name
        does not already exist, will raise an error. If the module has already
        been imported, this won't have much effect unless you also delete the
        imported module from ``sys.modules``. This is called by the JavaScript
        API :any:`pyodide.unregisterJsModule`.

        Parameters
        ----------
        name : str
            Name of js module
        """
        try:
            del self.jsproxies[name]
        except KeyError:
            raise ValueError(
                f"Cannot unregister {name!r}: no Javascript module with that name is registered"
            ) from None


class JsLoader(Loader):
    def __init__(self, jsproxy: Any) -> None:
        self.jsproxy = jsproxy

    def create_module(self, spec: ModuleSpec) -> Any:
        return self.jsproxy

    def exec_module(self, module: ModuleType) -> None:
        pass

    # used by importlib.util.spec_from_loader
    def is_package(self, fullname: str) -> bool:
        return True


JsProxy: type | None = None
jsfinder: JsFinder = JsFinder()
register_js_module = jsfinder.register_js_module
unregister_js_module = jsfinder.unregister_js_module


def register_js_finder() -> None:
    """A bootstrap function, called near the end of Pyodide initialization.

    It is called in ``loadPyodide`` in ``pyodide.js`` once ``_pyodide_core`` is ready
    to set up the js import mechanism.

        1. Put the right value into the global variable ``JsProxy`` so that
           ``JsFinder.find_spec`` can decide whether parent module is a Js module.
        2. Add ``jsfinder`` to metapath to allow js imports.

    This needs to be a function to allow the late import from ``_pyodide_core``.
    """
    import _pyodide_core

    global JsProxy
    JsProxy = _pyodide_core.JsProxy

    for importer in sys.meta_path:
        if isinstance(importer, JsFinder):
            raise RuntimeError("JsFinder already registered")

    sys.meta_path.append(jsfinder)


UNVENDORED_STDLIBS = ["distutils", "ssl", "lzma", "sqlite3"]
UNVENDORED_STDLIBS_AND_TEST = UNVENDORED_STDLIBS + ["test"]


class UnvendoredStdlibFinder(MetaPathFinder):
    """
    A MetaPathFinder that handles unvendored and removed stdlib modules.

    This class simply raises an error if a stdlib module is unvendored or removed.
    This needs to be added to the end of sys.meta_path, so if a unvendored stdlib
    is already loaded via pyodide.loadPackage, it can be handled by the existing finder.
    """

    def __init__(self) -> None:
        # `test`` is not a stdlib module, but we unvendors in anyway.
        self.stdlibs = sys.stdlib_module_names | {"test"}
        self.unvendored_stdlibs = set(UNVENDORED_STDLIBS_AND_TEST)
        assert not (
            self.unvendored_stdlibs - self.stdlibs
        ), "unvendored stdlibs not in stdlibs"

    def find_spec(
        self,
        fullname: str,
        path: Sequence[bytes | str] | None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        [parent, _, _] = fullname.partition(".")

        if not parent or parent in sys.modules or parent not in self.stdlibs:
            return None

        if parent in self.unvendored_stdlibs:
            raise ModuleNotFoundError(
                f"The module '{parent}' is unvendored from the Python standard library in the Pyodide distribution, "
                f'you can install it by calling: await micropip.install("{parent}"). '
                "See https://pyodide.org/en/stable/usage/wasm-constraints.html for more details."
            )
        else:
            raise ModuleNotFoundError(
                f"The module '{parent}' is removed from the Python standard library in the Pyodide distribution "
                "due to browser limitations. "
                "See https://pyodide.org/en/stable/usage/wasm-constraints.html for more details."
            )


def register_unvendored_stdlib_finder() -> None:
    """
    A function that adds UnvendoredStdlibFinder to the end of sys.meta_path.

    Note that this finder must be placed in the end of meta_paths
    in order to prevent any unexpected side effects.
    """

    for importer in sys.meta_path:
        if isinstance(importer, UnvendoredStdlibFinder):
            raise RuntimeError("UnvendoredStdlibFinder already registered")

    sys.meta_path.append(UnvendoredStdlibFinder())


class RepodataPackagesFinder(MetaPathFinder):
    """
    A MetaPathFinder that handles packages in repodata.json.

    This class simply raises an error if a package is in repodata.json but not loaded yet.
    This needs to be added to the end of sys.meta_path, so if a package
    is already loaded via pyodide.loadPackage, it can be handled by the existing finder.
    """

    def __init__(self, packages: dict[str, Any]) -> None:
        self.repodata_packages = packages

    def find_spec(
        self,
        fullname: str,
        path: Sequence[bytes | str] | None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        [parent, _, _] = fullname.partition(".")

        if not parent or parent in sys.modules or parent not in self.repodata_packages:
            return None

        if parent in self.repodata_packages:
            raise ModuleNotFoundError(
                f"The module '{parent}' is included in the Pyodide distribution, "
                f"but it is not installed. "
                f'You can install it by calling: await micropip.install("{parent}") in Python or '
                f'await pyodide.loadPackage("{parent}") in JavaScript. '
                "See https://pyodide.org/en/stable/usage/loading-packages.html for more details."
            )

        return None


def register_repodata_packages_finder(packages: Any) -> None:
    """
    A function that adds RepodataPackagesFinder to the end of sys.meta_path.

    Note that this finder must be placed in the end of meta_paths
    in order to prevent any unexpected side effects.
    """

    for importer in sys.meta_path:
        if isinstance(importer, RepodataPackagesFinder):
            raise RuntimeError("RepodataPackagesFinder already registered")

    sys.meta_path.append(RepodataPackagesFinder(packages.to_py()))
