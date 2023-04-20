from pytest_pyodide.decorator import run_in_pyodide


@run_in_pyodide(packages=["termcolor"])
def test_termcolor(selenium):
    import sys

    from termcolor import colored, cprint

    text = colored("Hello, World!", "red", attrs=["reverse", "blink"])
    print(text)
    cprint("Hello, World!", "green", "on_red")

    print_red_on_cyan = lambda x: cprint(x, "red", "on_cyan")
    print_red_on_cyan("Hello, World!")
    print_red_on_cyan("Hello, Universe!")

    for i in range(10):
        cprint(i, "magenta", end=" ")

    cprint("Attention!", "red", attrs=["bold"], file=sys.stderr)
