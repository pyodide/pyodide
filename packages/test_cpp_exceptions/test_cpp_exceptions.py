

def test_sharedlib(selenium):
    selenium.run_js(
        """
        await pyodide.loadPackage("test_cpp_exceptions");
        const idx = pyodide._module.LDSO.loadedLibNames["/lib/python3.9/site-packages/test_cpp_exceptions.so"]
        const library = pyodide._module.LDSO.loadedLibs[idx];
        try {
            library.module.throw_20();
        } catch(e){
            let errString = pyodide._module.convertCppException(e).toString();
            errString = errString.replace(/[0-9]+/, "xxx");
            assert(() => errString === "CppException: The pointer xxx was thrown as a C++ exception, but it doesn't seem to inherit from std::exception.");
        }
        try {
            library.module.throw_my_exc();
        } catch(e){
            let errString = pyodide._module.convertCppException(e).toString();
            assert(() => errString === 'CppException: My exception happened');
        }
        try {
            library.module.throw_runtime_exc();
        } catch(e){
            let errString = pyodide._module.convertCppException(e).toString();
            assert(() => errString === 'CppException: Hello there!');
        }
        """
    )
