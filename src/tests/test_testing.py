import pathlib
from pyodide_build.testing import run_in_pyodide, _run_in_pyodide_get_source
from textwrap import dedent


def test_web_server_secondary(selenium, web_server_secondary):
    host, port, logs = web_server_secondary
    assert pathlib.Path(logs).exists()
    assert selenium.server_port != port


@run_in_pyodide
def test_run_in_pyodide():
    pass


def dummy_decorator(*args, **kwargs):
    def func(f):
        return f

    return func


@dummy_decorator(
    packages=["nlopt"],
    xfail_browsers={
        "chrome": "nlopt set_min_objective triggers a fatal runtime error in chrome 89 see #1493",
    },
)
def some_func():
    import numpy as np
    import nlopt

    opt = nlopt.opt(nlopt.LD_SLSQP, 2)
    opt.set_min_objective(f)
    opt.set_lower_bounds(np.array([2.5, 7]))


def test_run_in_pyodide_multiline_decorator():
    assert (
        _run_in_pyodide_get_source(some_func).strip()
        == dedent(
            """
            def some_func():
                import numpy as np
                import nlopt

                opt = nlopt.opt(nlopt.LD_SLSQP, 2)
                opt.set_min_objective(f)
                opt.set_lower_bounds(np.array([2.5, 7]))
            """
        ).strip()
    )


def test_assert(selenium):
    selenium.run_js(
        r"""
        let shouldPass;
        shouldPass = true;
        assert(() => shouldPass, "blah");
        shouldPass = false;
        let threw = false;
        try {
            assert(() => shouldPass, "blah");
        } catch(e){
            threw = true;
            if(e.message !== `Assertion failed: shouldPass\nblah`){
                throw new Error(`Unexpected message:\n${e.message}`);
            }
        }
        if(!threw){
            throw new Error("Didn't throw!");
        }
        """
    )

    selenium.run_js(
        r"""
        let shouldPass;
        let threw;
        assertThrows(() => { throw new TypeError("aaabbbccc") }, "TypeError", "bbc");
        assertThrows(() => { throw new TypeError("aaabbbccc") }, "TypeError", /.{3}.{3}.{3}/);

        threw = false;
        try {
            assertThrows(() => 0, "TypeError", /.*/);
        } catch(e) {
            threw = true;
            assert(() => e.message == `assertThrows(() => 0, "TypeError", /.*/) failed, no error thrown`, e.message);
        }
        assert(() => threw);

        threw = false;
        try {
            assertThrows(() => { throw new ReferenceError("blah"); }, "TypeError", /.*/);
        } catch(e) {
            threw = true;
            assert(() => e.message.endsWith("expected error of type 'TypeError' got type 'ReferenceError'"));
        }
        assert(() => threw);

        threw = false;
        try {
            assertThrows(() => { throw new TypeError("blah"); }, "TypeError", "abcd");
        } catch(e) {
            threw = true;
            console.log(`!!${e.message}!!`);
            assert(() => e.message.endsWith(`expected error message to match pattern "abcd" got:\nblah`));
        }
        assert(() => threw);

        threw = false;
        try {
            assertThrows(() => { throw new TypeError("blah"); }, "TypeError", /a..d/);
        } catch(e) {
            threw = true;
            console.log(`!!${e.message}!!`);
            assert(() => e.message.endsWith(`expected error message to match pattern /a..d/ got:\nblah`));
        }
        assert(() => threw);
        """
    )
