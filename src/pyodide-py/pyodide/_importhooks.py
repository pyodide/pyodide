from ._core import JsProxy
from importlib.abc import MetaPathFinder, Loader
from importlib.util import spec_from_loader
import sys


class JsFinder(MetaPathFinder):
    def __init__(self):
        self.jsproxies = {}

    def find_spec(self, fullname, path, target=None):
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

    def register_js_module(self, name, jsproxy):
        if not isinstance(name, str):
            raise TypeError(f"Argument 'name' must be a str, not {type(name).__name__!r}")
        if not isinstance(jsproxy, JsProxy):
            raise TypeError(f"Argument 'jsproxy' must be a JsProxy, not {type(jsproxy).__name__!r}")
        self.jsproxies[name] = jsproxy

    def unregister_js_module(self, name):
        try:
            del self.jsproxies[name]
        except KeyError:
            raise ValueError(
                f"Cannot unregister {name!r}: no javascript module with that name is registered"
            ) from None


class JsLoader(Loader):
    def __init__(self, jsproxy):
        self.jsproxy = jsproxy

    def create_module(self, spec):
        return self.jsproxy

    # used by importlib.util.spec_from_loader
    def is_package(self, fullname):
        return True
