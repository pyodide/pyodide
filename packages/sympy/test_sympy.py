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
