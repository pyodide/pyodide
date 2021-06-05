from .jsdoc import PyodideAnalyzer
from .lexers import PyodideLexer, HtmlPyodideLexer
from .jsdoc import get_jsdoc_summary_directive, get_jsdoc_content_directive


def wrap_analyzer(app):
    app._sphinxjs_analyzer = PyodideAnalyzer(app._sphinxjs_analyzer)


from typing import Any, Dict, List, Tuple
from sphinx.util.inspect import safe_getattr
from sphinx.ext.autodoc import ModuleDocumenter, ObjectMember  # type: ignore

# Monkey patch autodoc to include submodules as well.
# We have to import the submodules for it to find them.
def get_module_members(module: Any) -> List[Tuple[str, Any]]:
    members = {}  # type: Dict[str, Tuple[str, Any]]
    for name in dir(module):
        try:
            value = safe_getattr(module, name, None)
            # Before patch this used to always do
            # members[name] = (name, value)
            # We want to also recursively look up names on submodules.
            if type(value).__name__ != "module":
                members[name] = (name, value)
                continue
            if name.startswith("_"):
                continue
            submodule = value  # Rename for clarity
            [base, _, rest] = submodule.__name__.partition(".")
            if not base == module.__name__:
                # Not part of package, don't document
                continue

            for (sub_name, sub_val) in get_module_members(submodule):
                # Skip names not in __all__
                if hasattr(submodule, "__all__") and sub_name not in submodule.__all__:
                    continue
                qual_name = rest + "." + sub_name
                members[qual_name] = (qual_name, sub_val)
            continue
        except AttributeError:
            continue

    return sorted(list(members.values()))


# For some reason I was unable to monkey patch get_module_members
# so we monkey patch get_object_members instead...
# This is similar to the original function but I dropped a branch (for brevity only)
def get_object_members(self, want_all: bool):
    members = get_module_members(self.object)
    if not self.__all__:
        # for implicit module members, check __module__ to avoid
        # documenting imported objects
        return True, members
    else:
        ret = []
        for name, value in members:
            if name in self.__all__ or "." in name:
                ret.append(ObjectMember(name, value))
            else:
                ret.append(ObjectMember(name, value, skipped=True))

        return False, ret


ModuleDocumenter.get_object_members = get_object_members  # type: ignore


def setup(app):
    app.add_lexer("pyodide", PyodideLexer)
    app.add_lexer("html-pyodide", HtmlPyodideLexer)
    app.setup_extension("sphinx_js")
    app.connect("builder-inited", wrap_analyzer)
    app.add_directive("js-doc-summary", get_jsdoc_summary_directive(app))
    app.add_directive("js-doc-content", get_jsdoc_content_directive(app))
