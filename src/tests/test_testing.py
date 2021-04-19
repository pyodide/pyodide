import pathlib
from pyodide_build.testing import run_in_pyodide


def test_web_server_secondary(selenium, web_server_secondary):
    host, port, logs = web_server_secondary
    assert pathlib.Path(logs).exists()
    assert selenium.server_port != port


@run_in_pyodide
def test_run_in_pyodide():
    pass


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
