# mypy: ignore-errors
from importlib.machinery import ExtensionFileLoader
from importlib.abc import MetaPathFinder
from importlib.util import spec_from_loader
import sys


def create_module_inner(spec, jsproxy):
    """ Provided by C (jsimport.c) """


# From Python glossary: An importer is "both a finder and loader object."
class JsImporter(MetaPathFinder, ExtensionFileLoader):
    jsproxies = {}
    ### Finder methods
    @classmethod
    def find_spec(cls, fullname, path, target=None):
        # Wait until here to import so we know JsProxy isn't the dummy.
        from ._base import JsProxy

        [parent, _, child] = fullname.rpartition(".")
        if parent:
            parent_module = sys.modules[parent]
            if not hasattr(parent_module, "__loader__") or not isinstance(
                parent_module.__loader__, JsImporter
            ):
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
                jsproxy = JsImporter.jsproxies[fullname]
            except KeyError:
                return None
        loader = cls(fullname, jsproxy)
        return spec_from_loader(fullname, loader, origin="javascript")

    def __init__(self, name, jsproxy):
        super().__init__(name, None)
        self.jsproxy = jsproxy

    def __repr__(self) -> str:
        return "javascript module"

    @classmethod
    def find_module(cls, fullname, path):
        raise NotImplementedError(
            "find_module() is deprecated in favor of find_spec() since Python 3.4"
        )

    @staticmethod
    def invalidate_caches() -> None:
        pass

    ### Loader methods
    # Overwrite ExtensionFileLoader.create_module with our own mechanism
    # that short circuits the file system access stuff.
    # create_module_inner defined in jsimport.c
    def create_module(self, spec):
        return create_module_inner(spec, self.jsproxy)

    # use ExtensionFileLoader.exec_module (no override)

    # used by importlib.util.spec_from_loader
    def is_package(self, fullname):
        return True  # ???


def register_js_module(name, jsproxy):
    JsImporter.jsproxies[name] = jsproxy


def unregister_js_module(name):
    try:
        del JsImporter.jsproxies[name]
    except KeyError:
        raise ValueError(
            f"Cannot unregister {name!r}: no javacript module with that name is registered"
        ) from None
