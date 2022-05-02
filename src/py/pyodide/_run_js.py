def run_js(code, /):
    from js import eval

    if not isinstance(code, str):
        raise ValueError(
            f"argument should have type 'string' not type '{code.__name__}'"
        )
    return eval(code)
