from typing import List, Optional


def get_completions(
    code: str, cursor: Optional[int] = None, namespaces: Optional[List] = None
) -> List[str]:
    """
    Get code autocompletion candidates

    Note that this function requires to have the jedi module loaded.

    Parameters
    ----------
    code
       the Python code to complete.
    cursor
       optional position in the code at which to autocomplete
    namespaces
       a list of namespaces

    Returns
    -------
    a list of autocompleted modules
    """
    import jedi
    import __main__

    if namespaces is None:
        namespaces = [__main__.__dict__]

    if cursor is None:
        cursor = len(code)
    code = code[:cursor]
    interp = jedi.Interpreter(code, namespaces)
    completions = interp.completions()

    return [x.name for x in completions]
