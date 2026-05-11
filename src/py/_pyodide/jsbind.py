from collections.abc import Callable
from inspect import (
    Parameter,
    getattr_static,
    isclass,
    iscoroutinefunction,
    ismethod,
    signature,
)
from types import GenericAlias
from typing import (  # type:ignore[attr-defined]
    Any,
    _AnnotatedAlias,
    _GenericAlias,
    _UnionGenericAlias,
    get_type_hints,
)

from _pyodide_core import (
    Js2PyConverter,
    JsFuncSignature,
    Py2JsConverter,
    create_promise_converter,
    js2py_as_py_json,
    js2py_deep,
    js2py_default,
    js2py_default_call_result,
    py2js_as_js_json,
    py2js_deep,
    py2js_default,
)

from .camel_to_snake import camel_to_snake, snake_to_camel


class Py2JsConverterMeta(type):
    def __new__(metaclass, name, bases, namespace):
        result = namespace.get("converter", py2js_default).copy()
        pc1 = namespace["pre_convert"]
        pc2 = getattr(result, "pre_convert", None)
        if pc1 and pc2:

            def pcfinal(o):
                return pc2(pc1(o))
        else:
            pcfinal = pc1 or pc2  # type:ignore[assignment]
        result.pre_convert = pcfinal
        return result


class Js2PyConverterMeta(type):
    def __new__(metaclass, name, bases, namespace):
        result = namespace.get("converter", js2py_default).copy()
        pc1 = namespace["post_convert"]
        pc2 = getattr(result, "post_convert", None)
        if pc1 and pc2:

            def pcfinal(o):
                return pc1(pc2(o))
        else:
            pcfinal = pc1 or pc2  # type:ignore[assignment]
        result.post_convert = pcfinal
        return result


def js2py_bind(x):
    class Converter(metaclass=Js2PyConverterMeta):
        @staticmethod
        def post_convert(obj):
            return obj.bind_sig(x)

    return Converter


class Json:
    py2js = py2js_as_js_json
    js2py = js2py_as_py_json


class Deep:
    js2py = js2py_deep
    py2js = py2js_deep


class Default:
    pass


class BindClass:
    """Marker base class for jsbind signature classes.

    Subclasses describe the structure of a JS object so that attribute
    accesses, method calls, and conversions can be type-checked at the
    boundary.

    Subclasses may configure how Python attribute names are mapped onto JS
    property names by overriding the ``_js_name`` static method::

        class Screaming(BindClass):
            @staticmethod
            def _js_name(name: str) -> str:
                return name.upper()

    Per-member overrides are available via :class:`JsName` /
    :func:`js_name` (pin an exact JS name) and :class:`CamelCase` /
    :func:`camel_case` (apply ``snake_to_camel`` to a single member).

    See :class:`CamelCase` for a built-in mixin that exposes camelCase JS
    properties via snake_case Python attribute names.
    """

    @staticmethod
    def _js_name(py_name: str) -> str:
        return py_name


class CamelCase(BindClass):
    """A :class:`BindClass` mixin that translates ``snake_case`` Python
    attribute names to ``camelCase`` JS property names.

    Use as a base class instead of :class:`BindClass`::

        class Foo(CamelCase):
            x_y: int

            def do_something(self, /) -> None: ...

    Then ``foo.x_y`` reads JS ``foo.xY`` and ``foo.do_something()`` calls
    JS ``foo.doSomething()``.

    Individual members may opt out via :class:`JsName` / :func:`js_name`
    to pin an exact JS name::

        class Foo(CamelCase):
            my_id: Annotated[int, JsName("id")]

            @js_name("doStuff")
            def do_stuff(self, /): ...
    """


class JsName:
    """Annotation marker that pins a specific JS property name.

    Use inside :class:`typing.Annotated` on attribute or return-value
    annotations of a :class:`BindClass` subclass to override any class-level
    name translation::

        from typing import Annotated
        from _pyodide.jsbind import CamelCase, JsName

        class Foo(CamelCase):
            # Read JS property "id" instead of the default "myId".
            my_id: Annotated[int, JsName("id")]

    For methods, the :func:`js_name` decorator is more convenient.
    """

    __slots__ = ("name",)

    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return f"JsName({self.name!r})"


# Annotation markers that act as per-attribute name translators. Mapping is
# ``marker -> translator(py_name) -> js_name``. The marker may either be a
# class (e.g. :class:`CamelCase`) or any object usable as ``Annotated`` metadata.
_NAME_TRANSLATORS: "dict[Any, Any]" = {
    CamelCase: snake_to_camel,
}


def js_name[F: Callable[..., Any]](name: str) -> Callable[[F], F]:
    """Decorator that pins the JS property name for a method.

    The decorated method's Python name will be translated to ``name`` when
    looking it up on the underlying JS object, regardless of any class-level
    name translation::

        class Foo(CamelCase):
            @js_name("doStuff")
            def do_stuff(self, /): ...
    """

    def decorator(f: F) -> F:
        f.__js_name__ = name  # type: ignore[attr-defined]
        return f

    return decorator


def camel_case[F: Callable[..., Any]](f: F) -> F:
    """Decorator that opts a single method into ``snake_case`` ->
    ``camelCase`` JS-name translation, regardless of the class-level
    configuration::

        class Foo(BindClass):
            @camel_case
            def do_stuff(self, /): ...   # calls jsproxy.doStuff()
    """
    f.__js_name__ = snake_to_camel(f.__name__)  # type: ignore[attr-defined]
    return f


def _extract_js_name_override(annotation, py_name):
    """If ``annotation`` is ``Annotated[T, ...]`` and one of the metadata
    items is a :class:`JsName` instance or a registered name-translator
    marker (such as :class:`CamelCase`), return the resulting JS name.
    Otherwise return ``None``."""
    if not isinstance(annotation, _AnnotatedAlias):
        return None
    for meta in annotation.__metadata__:
        if isinstance(meta, JsName):
            return meta.name
        translator = _NAME_TRANSLATORS.get(meta)
        if translator is not None:
            return translator(py_name)
    return None


def _get_name_cache(sig: type) -> tuple[dict[str, str], dict[str, str]]:
    """Return the ``(py_to_js, js_to_py)`` name caches for ``sig``, building
    them lazily on first access.

    The forward cache contains an entry for every Python attribute name with
    an explicit override (via an ``Annotated[..., JsName(...)]`` /
    ``Annotated[..., CamelCase]`` annotation, or an ``@js_name`` /
    ``@camel_case`` decorator). After the first call, ``_resolve_js_name``
    also memoizes results from the class-level ``_js_name`` translator into
    the same cache.
    """
    if res := getattr(sig, "_js_name_cache", None):
        return res
    cache: dict[str, str] = {}
    # Annotated[..., JsName(...)] / Annotated[..., CamelCase] markers.
    if not hasattr(sig, "_type_hints"):
        try:
            sig._type_hints = get_type_hints(sig, include_extras=True)  # type: ignore[attr-defined]
        except Exception:
            sig._type_hints = {}  # type: ignore[attr-defined]
    for py, ann in sig._type_hints.items():  # type: ignore[attr-defined]
        explicit = _extract_js_name_override(ann, py)
        if explicit is not None:
            cache[py] = explicit
    # Method decorators (@js_name / @camel_case).
    for cls in getattr(sig, "__mro__", (sig,)):
        for py, member in getattr(cls, "__dict__", {}).items():
            if py in cache:
                continue
            explicit = getattr(member, "__js_name__", None)
            if isinstance(explicit, str):
                cache[py] = explicit
    # Eagerly build the reverse map for dir(). This is O(n) but only done
    # once per sig class.
    reverse: dict[str, str] = {js: py for py, js in cache.items()}
    res = (cache, reverse)
    sig._js_name_cache = res  # type: ignore[attr-defined]
    return res


def _resolve_js_name(sig: type | None, py_name: str) -> str:
    """Translate a Python attribute name to its JS property name for ``sig``.

    Called from C in ``JsProxy_GetAttr_helper`` and ``JsProxy_SetAttr``
    (``src/core/jsproxy.c``). Resolution order:

    1. Explicit override (``JsName`` / ``CamelCase`` annotation,
       ``@js_name`` / ``@camel_case`` decorator).
    2. ``sig._js_name(py_name)`` (the class-level translator).
    3. ``py_name`` unchanged.

    The result is memoized so subsequent lookups of the same name don't
    re-run any translation.
    """
    if sig is None:
        return py_name
    cache, reverse = _get_name_cache(sig)
    js_name = cache.get(py_name)
    if js_name is not None:
        return js_name
    if issubclass(sig, CamelCase):
        js_name = snake_to_camel(py_name)
    else:
        js_name = py_name
    cache[py_name] = js_name
    reverse[js_name] = py_name
    return js_name


def _reverse_dir_names(sig: type | None, js_names: list[str]) -> list[str]:
    """Translate a list of JS property names back to Python attribute names.

    Called from C in ``JsProxy_Dir`` (``src/core/jsproxy.c``). If no inverse
    translation is available the names are returned unchanged.
    """
    if sig is None:
        return js_names
    return [_reverse_js_name(sig, n) for n in js_names]


def _reverse_js_name(sig: type, js_name: str) -> str:
    """Translate a JS property name back to its Python attribute name for ``sig``.

    The lookup is best-effort: if the inverse cannot be determined,
    ``js_name`` is returned unchanged.
    """
    _, reverse = _get_name_cache(sig)
    if js_name in reverse:
        return reverse[js_name]
    # If it's a CamelCase class, apply camel_to_snake to try to invert
    # snake_to_camel.
    if issubclass(sig, CamelCase):
        return camel_to_snake(js_name)
    return js_name


class _TypeConverter:
    def unpack_generic_alias(self, x: _GenericAlias) -> Any:
        if isinstance(x, _UnionGenericAlias):
            if len(x.__args__) != 2:
                return None
            e0 = x.__args__[0]
            e1 = x.__args__[1]
            e0isNone = e0 == type(None)  # noqa: E721
            e1isNone = e1 == type(None)  # noqa: E721
            if (not e0isNone) and (not e1isNone):
                return None
            if e0isNone:
                x = e1
            if e1isNone:
                x = e0
        if isinstance(x, GenericAlias) and x.__name__ in ["Future", "Awaitable"]:
            arg = x.__args__[0]
            return create_promise_converter(self.js2py_annotation(arg))
        if isinstance(x, _AnnotatedAlias):
            # Skip over name-translation markers; they only configure the JS
            # property name, not the value conversion.
            for meta in x.__metadata__:
                if isinstance(meta, JsName):
                    continue
                if meta in _NAME_TRANSLATORS:
                    continue
                return meta
            return None
        return None

    def js2py_annotation(self, annotation: Any) -> "Js2PyConverter":
        if isinstance(annotation, (_GenericAlias, GenericAlias)):  # noqa: UP038
            annotation = self.unpack_generic_alias(annotation)
        if annotation is None:
            return None
        if isinstance(annotation, Js2PyConverter):
            return annotation
        res = getattr(annotation, "js2py", None)
        if res:
            return res

        if issubclass(annotation, BindClass):
            return js2py_bind(annotation)
        return None

    def py2js_annotation(self, annotation: Any) -> "Py2JsConverter":
        if isinstance(annotation, _GenericAlias):
            annotation = self.unpack_generic_alias(annotation)
        if annotation is None:
            return None
        if isinstance(annotation, Py2JsConverter):
            return annotation
        res = getattr(annotation, "py2js", None)
        if res:
            return res

        return None


_type_converter = _TypeConverter()


def _get_attr_sig_prop(attr_sig):
    """Helper for _get_attr_sig in case that the attribute we're looking up is a
    property with annotation.
    """
    # If the attribute is marked with BindClass, then we should attach bind it
    # to the resulting proxy.
    if isinstance(attr_sig, BindClass):
        return (False, attr_sig)
    # Otherwise, make it into a converter.
    if converter := _type_converter.js2py_annotation(attr_sig):
        return (True, converter)
    return (False, None)


def _get_attr_sig_method_helper(sig, attr):
    """Check if sig has a method named attr. If so, get the appropriate
    signature.

    Returns: None or a valid _get_attr_sig return value.
    """
    res_attr = getattr_static(sig, attr, None)
    # If it isn't a static method, it has one too many arguments. Easiest way to
    # communicate this to _func_to_sig is to use __get__ to bind an argument. We
    # have to do this manually because `sig` is a class not an instance.
    if res_attr and callable(res_attr):
        # The argument to __get__ doesn't matter.
        res_attr = res_attr.__get__(sig)
    if res_attr:
        return res_attr

    sig_getattr = getattr(sig, "__getattr__", None)
    if not sig_getattr:
        return None
    if not hasattr(sig_getattr, "_type_hints"):
        sig_getattr._type_hints = get_type_hints(sig_getattr)
    if not sig_getattr._type_hints:
        return None
    attr_sig = sig_getattr._type_hints.get("return")
    if not attr_sig:
        return None

    return attr_sig


def _get_attr_sig_method(sig, attr):
    if not hasattr(sig, "_method_cache"):
        sig._method_cache = {}
    if res_attr := sig._method_cache.get(attr, None):
        return res_attr
    res = _get_attr_sig_method_helper(sig, attr)
    sig._method_cache[attr] = res
    return res


def _get_attr_sig(sig, attr):
    """Called from C in ``JsProxy_GetAttr_helper`` (``src/core/jsproxy.c``)
    when the proxy has a signature.

    Must return a triple:

        (js_name, False, sig) -- if the result is a JsProxy bind sig to it
        (js_name, True, converter) -- apply converter to the result

    ``js_name`` is the JS property name to look up (after applying any name
    translation configured on ``sig``).
    """
    js_name = _resolve_js_name(sig, attr)
    # Look up type hints and cache them if we haven't yet. We could use
    # `functools.cache` for this, but it seems to keep `sig` alive for longer
    # than necessary.
    # TODO: Make a cache decorator that uses a weakmap.
    if not hasattr(sig, "_type_hints"):
        sig._type_hints = get_type_hints(sig, include_extras=True)
    # See if there is an attribute type hint
    if prop_sig := sig._type_hints.get(attr, None):
        got_converter, value = _get_attr_sig_prop(prop_sig)
        return (js_name, got_converter, value)
    if res := _get_attr_sig_method(sig, attr):
        return (js_name, False, res)
    return (js_name, False, None)


no_default = Parameter.empty


def _func_to_sig(f):
    """Called from C in ``jsproxy_call.c`` when we're about to call a
    callable.

    Has to return an appropriate JsFuncSignature.
    """
    cache_name = "_js_sig"
    if getattr(f, "__qualname__", None) == "type":
        cls = f.__args__[0]
        cache = cls
    else:
        if isclass(f):
            cache = f.__call__
            f = f.__call__.__get__(f)
        else:
            cache = f
        if ismethod(cache):
            # We can't add extra attributes to a methodwrapper.
            cache = cache.__func__
            cache_name = "_js_meth_sig"
        cls = None
    if res := getattr(cache, cache_name, None):
        return res
    if cls:
        f = cls.__init__.__get__(cls)

    res = _func_to_sig_inner(f, cls)
    setattr(cache, cache_name, res)
    return res


def _func_to_sig_inner(f, cls):
    sig = signature(f)
    posparams = []
    posparams_defaults = []
    posparams_nmandatory = 0
    varpos = None
    kwparam_names = []
    kwparam_converters = []
    kwparam_defaults = []
    varkwd = None
    types = get_type_hints(f, include_extras=True)
    should_construct = bool(cls)

    for p in sig.parameters.values():
        converter = (
            _type_converter.py2js_annotation(types.get(p.name, None)) or py2js_default
        )
        match p.kind:
            case Parameter.POSITIONAL_ONLY:
                posparams.append(converter)
                if p.default == Parameter.empty:
                    posparams_nmandatory += 1
                else:
                    posparams_defaults.append(p.default)
            case Parameter.POSITIONAL_OR_KEYWORD:
                raise RuntimeError("Don't currently handle POS_OR_KWD args")
            case Parameter.KEYWORD_ONLY:
                kwparam_names.append(p.name)
                kwparam_converters.append(converter)
                kwparam_defaults.append(p.default)
            case Parameter.VAR_POSITIONAL:
                varpos = converter
            case Parameter.VAR_KEYWORD:
                varkwd = converter
            case _:
                raise RuntimeError("Unreachable")
    if len(kwparam_names) > 64:
        # We use a bitflag to check which kwparams have been passed to fill in
        # defaults / raise type error.
        raise RuntimeError("Cannot handle function with more than 64 kwonly args")
    result = _type_converter.js2py_annotation(types.get("return", cls))
    if iscoroutinefunction(f):
        if result is None:
            result = js2py_default
        result = create_promise_converter(result)
    elif result is None:
        result = js2py_default_call_result

    return JsFuncSignature(
        f,
        should_construct,
        posparams_nmandatory,
        tuple(posparams),
        tuple(posparams_defaults),
        varpos,
        tuple(kwparam_names),
        tuple(kwparam_converters),
        tuple(kwparam_defaults),
        varkwd,
        result,
    )


def _default_sig_stencil(*args, **kwargs):
    pass


_default_signature = _func_to_sig_inner(_default_sig_stencil, None)


def _bind_class_sig(sig):
    """Called from JsProxy_bind_class.

    Just replace sig with type[sig]. This is consistent with what we'd get from
    a function return value: if a function returns a class then it should be typed:

    def f() -> type[A]:
        ...
    """
    return type[sig]
