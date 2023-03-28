import pytest


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_unwind_state_save_restore(selenium_standalone):
    selenium = selenium_standalone

    selenium.run_js(
        """
        throw_unwind = () => {
            throw "unwind";
        }

        pyodide.loop.saveThreadState()

        pyodide.runPython(`
            from _pyodide_core import raw_call
            from js import throw_unwind

            def unwind_call():
                raw_call(throw_unwind)

            unwind_call()
        `)

        pyodide.runPython(`
            import sys
            frame = sys._getframe()
            func_names = []
            while frame:
                func_names.append(frame.f_code.co_name)
                frame = frame.f_back

            assert "unwind_call" in func_names
            print(func_names)
        `)

        pyodide.loop.cancel()

        pyodide.loop.restoreThreadState()

        pyodide.runPython(`
            import sys
            frame = sys._getframe()
            func_names = []
            while frame:
                func_names.append(frame.f_code.co_name)
                frame = frame.f_back

            assert "unwind_call" not in func_names
            print(func_names)
        `)
        """
    )


# @pytest.mark.skip_refcount_check
# @pytest.mark.skip_pyproxy_check
# def test_unwind(selenium_standalone):
#     selenium = selenium_standalone

#     selenium.run_js(
#         """
#         throw_unwind = () => {
#             throw "unwind";
#         }

#         pyodide.runPython(`
#             from _pyodide_core import raw_call
#             from js import throw_unwind

#             def unwind_call():
#                 raw_call(throw_unwind)

#             unwind_call()
#         `)

#         pyodide.runPython(`
#             import sys
#             frame = sys._getframe()
#             func_names = []
#             while frame:
#                 func_names.append(frame.f_code.co_name)
#                 frame = frame.f_back

#             assert "unwind_call" in func_names
#         `)
#         """
#     )

#     assert "No thread state saved" in selenium.logs
