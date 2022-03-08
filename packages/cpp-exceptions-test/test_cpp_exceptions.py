from pyodide_build.testing import PYVERSION


def test_uncaught_cpp_exceptions(selenium):
    assert (
        selenium.run_js(
            f"""
            await pyodide.loadPackage("cpp-exceptions-test");
            const Tests = pyodide._api.tests;
            const idx = pyodide._module.LDSO.loadedLibNames["/lib/{PYVERSION}/site-packages/cpp-exceptions-test-throw.so"]
            const throwlib = pyodide._module.LDSO.loadedLibs[idx].module;
            """
            """\
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
        )
        == [
            "CppException int: The exception is an object of type int at address xxx "
            "which does not inherit from std::exception",
            "CppException char: The exception is an object of type char at address xxx "
            "which does not inherit from std::exception",
            "CppException std::runtime_error: abc",
            "CppException myexception: My exception happened",
            "CppException char const*: The exception is an object of type char const* at "
            "address xxx which does not inherit from std::exception",
        ]
    )


def test_cpp_exception_catching(selenium):
    assert (
        selenium.run_js(
            f"""
            await pyodide.loadPackage("cpp-exceptions-test");
            const Module = pyodide._module;
            const idx = Module.LDSO.loadedLibNames["/lib/{PYVERSION}/site-packages/cpp-exceptions-test-catch.so"]
            const catchlib = Module.LDSO.loadedLibs[idx].module;
            """
            """\
            function t(x){
                const ptr = catchlib.catch_exc(x);
                const res = Module.UTF8ToString(ptr);
                Module._free(ptr);
                return res;
            }

            return [t(1), t(2), t(3), t(5)];
            """
        )
        == [
            "caught int 1000",
            "caught char 99",
            "caught runtime_error abc",
            "caught ????",
        ]
    )
