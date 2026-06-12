import re

_SNAKE_TO_CAMEL_RE = re.compile(r"_([a-z])")
_CAMEL_TO_SNAKE_RE = re.compile(r"([a-z0-9])([A-Z])")


def snake_to_camel(name: str) -> str:
    """Convert a snake_case Python attribute name to a camelCase JS name.

    Leading underscores are preserved (so dunder names like ``__call__`` are
    untouched). A single trailing underscore is also preserved so that the
    reserved-word transform in ``pre.js`` still works (e.g. ``class_`` -> ``class_``).
    Internal underscores are removed and the following character is upper-cased.

    >>> snake_to_camel("foo_bar")
    'fooBar'
    >>> snake_to_camel("foo_bar_baz")
    'fooBarBaz'
    >>> snake_to_camel("already_lowerCase")
    'alreadyLowerCase'
    >>> snake_to_camel("__call__")
    '__call__'
    >>> snake_to_camel("class_")
    'class_'
    """
    if not name:
        return name
    # Python TitleCase ==> JavaScript TitleCase
    # If first alpha character is uppercase, it's in title case ==> leave it alone.
    first_alpha = next((c for c in name if c.isalnum()), None)
    if first_alpha is None or first_alpha.isupper():
        return name
    # Preserve leading underscores (dunders, sunders, private names).
    if name[:2] == "__":
        return name
    # Preserve all trailing underscores (used to escape reserved words).
    rstripped = name.rstrip("_")
    trailing = name[len(rstripped) :]
    stripped = rstripped.lstrip("_")
    leading = rstripped[: -len(stripped)]
    return (
        leading
        + _SNAKE_TO_CAMEL_RE.sub(lambda m: m.group(1).upper(), stripped)
        + trailing
    )


def camel_to_snake(name: str) -> str:
    """Convert a camelCase JS name to a snake_case Python attribute name.

    Inverse of :func:`snake_to_camel` for typical inputs.

    >>> camel_to_snake("fooBar")
    'foo_bar'
    >>> camel_to_snake("XMLHttpRequest")
    'XMLHttpRequest'
    >>> camel_to_snake("anXMLHttpRequest")
    'an_xml_http_request'
    >>> camel_to_snake("ALL_UPPERCASE")
    'ALL_UPPERCASE'
    >>> camel_to_snake("_TitleCasePrivate")
    '_TitleCasePrivate'
    >>> camel_to_snake("__call__")
    '__call__'
    """
    if not name:
        return name
    # JavaScript TitleCase ==> Python TitleCase
    # If first alpha character is uppercase, it's in title case ==> leave it alone.
    first_alpha = next((c for c in name if c.isalnum()), None)
    if first_alpha is None or first_alpha.isupper():
        return name
    # Lowercase everything except uppercase letters that are preceded by an
    # underscore (so e.g. "a_A" round-trips instead of collapsing to "a_a"/"aA").
    out = []
    saw_underscore = False
    saw_uppercase = False
    for c in name:
        # print("c", c, "out", out, "saw_underscore", saw_underscore)
        if saw_underscore or not c.isupper():
            out.append(c)
        elif saw_uppercase:
            # Two uppercase, send XML ==> xml not x_m_l
            out.extend(c.lower())
        else:
            # last character wasn't an underscore or uppercase and current
            # character is uppercase
            out.extend(["_", c.lower()])
        saw_underscore = c == "_"
        saw_uppercase = c.isupper()
    # print(out)
    return "".join(out)
