def run_js(code, /):
    from js import eval

    if not isinstance(code, str):
        raise TypeError(
            f"argument should have type 'string' not type '{type(code).__name__}'"
        )
    return eval(code)
