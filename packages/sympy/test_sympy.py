def test_sympy(selenium):
    selenium.load_package("sympy")
    assert selenium.run(
        """
        import sympy

        a, b = sympy.symbols('a,b')
        c = sympy.sqrt(a**2 + b**2)

        c.subs({a:3, b:4}) == 5
    """
    )


def test_parse_latex(selenium):
    selenium.load_package("antlr4-python3-runtime")
    assert selenium.run(
        r"""
        from sympy.parsing.latex import parse_latex

        z = parse_latex(r"\frac{4}{y}+\sqrt{x^2+y^2}")

        z.subs({'y':4, 'x':3}) == 6
    """
    )
