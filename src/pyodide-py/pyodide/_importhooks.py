# mypy: ignore-errors
from importlib.machinery import ExtensionFileLoader
from importlib.abc import MetaPathFinder
from importlib.util import spec_from_loader


def create_module_inner(spec, jsproxy):
    """ Provided by C (jsimport.c) """


# From Python glossary: An importer is "both a finder and loader object."
class JsImporter(MetaPathFinder, ExtensionFileLoader):
    jsproxies = {}
    ### Finder methods
    @classmethod
    def find_spec(cls, fullname, path, target=None):
        [base_name, *splitname] = fullname.split(".")
        if base_name not in JsImporter.jsproxies:
            return None
        jsproxy = JsImporter.jsproxies[base_name]
        for part in splitname:
            jsproxy = getattr(jsproxy, part)
        name = splitname[-1] if splitname else base_name  # or should we use fullname?
        loader = cls(name, jsproxy)
        return spec_from_loader(fullname, loader, origin="javascript")

    def __init__(self, name, jsproxy):
        super().__init__(name, "<javscript module>")
        self.jsproxy = jsproxy

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
    del JsImporter.jsproxies[name]
