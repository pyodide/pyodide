from textwrap import dedent


def dedent_docstring(docstring):
    first_newline = docstring.find("\n")
    if first_newline == -1:
        return docstring
    docstring = docstring[:first_newline] + dedent(docstring[first_newline:])
    return docstring


def get_cmeth_docstring(func):
    """Get the value to use for the PyMethodDef.ml_doc attribute for a builtin
    function. This is used in docstring.c.

    The ml_doc should start with a signature which cannot have any type
    annotations. The signature must end with the exact characters ")\n--\n\n".
    For example: "funcname(arg1, arg2)\n--\n\n"

    See:
    https://github.com/python/cpython/blob/v3.8.2/Objects/typeobject.c#L84
    """
    from inspect import signature, _empty

    sig = signature(func)
    # remove param and return annotations and
    for param in sig.parameters.values():
        param._annotation = _empty
    sig._return_annotation = _empty

    return func.__name__ + str(sig) + "\n--\n\n" + dedent_docstring(func.__doc__)
