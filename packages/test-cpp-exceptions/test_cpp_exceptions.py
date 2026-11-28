import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.requires_dynamic_linking
def test_uncaught_cpp_exceptions(selenium):
    # An exception that escapes C++ would be a fatal error if it unwound
    # through the interpreter, so call the throwing function directly from JS to
    # check how uncaught C++ exceptions are converted into JS errors.
    selenium.load_package("test-cpp-exceptions")
    assert selenium.run_js(
        """
        const libthrow = pyodide.runPython(`
            from pathlib import Path
            import cpp_exceptions_test
            str(Path(cpp_exceptions_test.__file__).parent / "libthrow.so")
        `);
        const Tests = pyodide._api.tests;
        const throwlib = pyodide._module.LDSO.loadedLibsByName[libthrow].exports;
        function t(x){
            try {
                throwlib.throw_exc(x);
            } catch(e){
                let errString = Tests.convertCppException(e).toString();
                errString = errString.replace(/[0-9]+/, "xxx");
                return errString;
            }
        }
        return [t(1), t(2), t(3), t(4), t(5)];
        """
    ) == [
        "CppException int: The exception is an object of type int at address xxx "
        "which does not inherit from std::exception",
        "CppException char: The exception is an object of type char at address xxx "
        "which does not inherit from std::exception",
        "CppException std::runtime_error: abc",
        "CppException myexception: My exception happened",
        "CppException char const*: The exception is an object of type char const* at "
        "address xxx which does not inherit from std::exception",
    ]


@pytest.mark.requires_dynamic_linking
@run_in_pyodide(packages=["test-cpp-exceptions"])
def test_cpp_exception_catching(selenium):
    from cpp_exceptions_test import catch_exc

    assert [catch_exc(x) for x in [1, 2, 3, 5]] == [
        "caught int 1000",
        "caught char 99",
        "caught runtime_error abc",
        "caught ????",
    ]


@pytest.mark.requires_dynamic_linking
@run_in_pyodide(packages=["test-cpp-exceptions"])
def test_sjlj(selenium):
    from cpp_exceptions_test import set_jmp_func

    assert set_jmp_func() == 5


@pytest.mark.requires_dynamic_linking
@run_in_pyodide(packages=["test-cpp-exceptions"])
def test_cpp_exception_catching_invoke(selenium):
    """Test invoke functions. See explanation in catch.cpp"""
    from cpp_exceptions_test import catch_invoke_func

    assert [catch_invoke_func(x) for x in [0, 1]] == [
        "caught runtime_error standard invoke 1 2",
        "caught runtime_error custom invoke 1 2 3 4 5 6 7",
    ]
