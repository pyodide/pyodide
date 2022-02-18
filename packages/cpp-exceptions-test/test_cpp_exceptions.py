def test_uncaught_cpp_exceptions(selenium):
    selenium.run_js(
        """
        await pyodide.loadPackage("cpp-exceptions-test");
        const Tests = pyodide._api.tests;
        const idx = pyodide._module.LDSO.loadedLibNames["/lib/python3.9/site-packages/cpp-exceptions-test-throw.so"]
        const library = pyodide._module.LDSO.loadedLibs[idx];
        try {
            library.module.throw_20();
        } catch(e){
            let errString = Tests.convertCppException(e).toString();
            errString = errString.replace(/[0-9]+/, "xxx");
            assert(() => errString === "CppException int: The exception is an object of type int at address xxx which does not inherit from std::exception");
        }
        try {
            library.module.throw_my_exc();
        } catch(e){
            let errString = Tests.convertCppException(e).toString();
            assert(() => errString === 'CppException myexception: My exception happened');
        }
        try {
            library.module.throw_runtime_exc();
        } catch(e){
            let errString = Tests.convertCppException(e).toString();
            assert(() => errString === 'CppException std::runtime_error: Hello there!');
        }
        """
    )
