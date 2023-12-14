import pytest
from pytest_pyodide import run_in_pyodide

from conftest import only_node, strip_assertions_stderr


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_custom_stdin1(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    strings = [
        "hello world",
        "hello world\n",
        "This has a \x00 null byte in the middle...",
        "several\nlines\noftext",
        "pyodidé",
        "碘化物",
        "🐍",
        "",
    ]
    outstrings: list[str] = sum(
        ((s.removesuffix("\n") + "\n").splitlines(keepends=True) for s in strings), []
    )
    result = selenium.run_js(
        f"const strings = {strings};"
        f"const numOutlines = {len(outstrings)};"
        """
        let stdinStringsGen = strings[Symbol.iterator]();
        function stdin(){
            return stdinStringsGen.next().value;
        }
        const pyodide = await loadPyodide({
            fullStdLib: false,
            jsglobals : self,
            stdin,
        });
        self.pyodide = pyodide;
        globalThis.pyodide = pyodide;
        return pyodide.runPython(`
            import sys
            from js import console
            [sys.stdin.readline() for _ in range(${numOutlines})]
        `).toJs();
        """
    )
    assert result == outstrings


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_custom_stdout1(selenium_standalone_noload, runtime):
    selenium = selenium_standalone_noload
    [stdoutstrings, stderrstrings] = selenium.run_js(
        """
        self.stdoutStrings = [];
        self.stderrStrings = [];
        function stdout(s){
            stdoutStrings.push(s);
        }
        function stderr(s){
            stderrStrings.push(s);
        }
        const pyodide = await loadPyodide({
            fullStdLib: false,
            jsglobals : self,
            stdout,
            stderr,
        });
        self.pyodide = pyodide;
        globalThis.pyodide = pyodide;
        pyodide.runPython(`
            import sys
            print("something to stdout")
            print("something to stderr",file=sys.stderr)
        `);
        return [stdoutStrings, stderrStrings];
        """
    )
    assert stdoutstrings[-2:] == [
        "something to stdout",
    ]
    stderrstrings = strip_assertions_stderr(stderrstrings)
    assert stderrstrings == ["something to stderr"]
    IN_NODE = runtime == "node"
    selenium.run_js(
        f"""
        pyodide.runPython(`
            import sys
            assert sys.stdin.isatty() is {IN_NODE}
            assert not sys.stdout.isatty()
            assert not sys.stderr.isatty()
        `);
        pyodide.setStdin();
        pyodide.setStdout();
        pyodide.setStderr();
        pyodide.runPython(`
            import sys
            assert sys.stdin.isatty() is {IN_NODE}
            assert sys.stdout.isatty() is {IN_NODE}
            assert sys.stderr.isatty() is {IN_NODE}
        `);
        """
    )


def test_custom_stdin_stdout2(selenium):
    result = selenium.run_js(
        """
        const stdinStringsGen = [
            "hello there!\\nThis is a several\\nline\\nstring"
        ][Symbol.iterator]();
        function stdin(){
            return stdinStringsGen.next().value;
        }
        pyodide.setStdin({stdin});
        try {
            pyodide.runPython(`
                import sys
                assert sys.stdin.read(1) == "h"
                assert not sys.stdin.isatty()
            `);
            pyodide.setStdin({stdin, isatty: false});
            pyodide.runPython(`
                import sys
                assert sys.stdin.read(1) == "e"
            `);
            pyodide.setStdout();
            pyodide.runPython(`
                assert sys.stdin.read(1) == "l"
                assert not sys.stdin.isatty()
            `);
            pyodide.setStdin({stdin, isatty: true});
            pyodide.runPython(`
                assert sys.stdin.read(1) == "l"
                assert sys.stdin.isatty()
            `);

            let stdout_codes = [];
            function rawstdout(code) {
                stdout_codes.push(code);
            }
            pyodide.setStdout({raw: rawstdout});
            pyodide.runPython(`
                print("hello")
                assert sys.stdin.read(1) == "o"
                assert not sys.stdout.isatty()
                assert sys.stdin.isatty()
            `);
            pyodide.setStdout({raw: rawstdout, isatty: false});
            pyodide.runPython(`
                print("2hello again")
                assert sys.stdin.read(1) == " "
                assert not sys.stdout.isatty()
                assert sys.stdin.isatty()
            `);
            pyodide.setStdout({raw: rawstdout, isatty: true});
            pyodide.runPython(`
                print("3hello")
                assert sys.stdin.read(1) == "t"
                assert sys.stdout.isatty()
                assert sys.stdin.isatty()
            `);
            pyodide.runPython(`
                print("partial line", end="")
            `);
            let result1 = new TextDecoder().decode(new Uint8Array(stdout_codes));
            pyodide.runPython(`
                sys.stdout.flush()
            `);
            let result2 = new TextDecoder().decode(new Uint8Array(stdout_codes));
            return [result1, result2];
        } finally {
            // Flush stdin so other tests don't get messed up.
            pyodide.runPython(`sys.stdin.read()`);
            pyodide.runPython(`sys.stdin.read()`);
            pyodide.runPython(`sys.stdin.read()`);
            pyodide.setStdin();
            pyodide.setStdout();
            pyodide.setStderr();
        }
        """
    )
    assert result[0] == "hello\n2hello again\n3hello\n"
    assert result[1] == "hello\n2hello again\n3hello\npartial line"


@run_in_pyodide
def test_stdin_undefined(selenium):
    from pyodide.code import run_js

    run_js("pyodide.setStdin({stdin: () => undefined})")
    import sys

    try:
        print(sys.stdin.read())
    finally:
        run_js("pyodide.setStdin()")


@run_in_pyodide
def test_custom_stdin_bytes(selenium):
    from pyodide.code import run_js
    from pyodide_js import setStdin

    run_js(
        """
        const sg = [
            0x61,
            0x62,
            0x00,
            null,
            0x63,
            0x64,
            null,
            0x65,
            0x66,
            0x67,
        ][Symbol.iterator]();
        function stdin() {
            return sg.next().value;
        }
        pyodide.setStdin({stdin});
        """
    )
    try:
        import sys

        assert sys.stdin.read(5) == "ab\x00"
        assert sys.stdin.read(5) == "cd"
        assert sys.stdin.read(2) == "ef"
        assert sys.stdin.read(2) == "g"
        assert sys.stdin.read(2) == ""
    finally:
        setStdin()


@run_in_pyodide
def test_custom_stdin_buffer_autoeof(selenium):
    import sys

    from pyodide.code import run_js
    from pyodide_js import setStdin

    stdin = run_js(
        """
        const sg = [
            new Uint8Array([0x61, 0x62, 0x00]),
            new Uint8Array([0x63, 0x64]),
            null,
            new Uint8Array([0x65, 0x66, 0x67]),
        ][Symbol.iterator]();
        function stdin() {
            return sg.next().value;
        }
        stdin
        """
    )
    try:
        setStdin(stdin=stdin)
        assert sys.stdin.read(5) == "ab\x00"
        assert sys.stdin.read(5) == "cd"
        assert sys.stdin.read(2) == ""
        assert sys.stdin.read(2) == "ef"
        assert sys.stdin.read(2) == "g"
        assert sys.stdin.read(2) == ""
    finally:
        setStdin()


@run_in_pyodide
def test_custom_stdin_buffer_noautoeof(selenium):
    import sys

    from pyodide.code import run_js
    from pyodide_js import setStdin

    stdin = run_js(
        """
        const sg = [
            new Uint8Array([0x61, 0x62, 0x00]),
            new Uint8Array([0x63, 0x64]),
            null,
            new Uint8Array([0x65, 0x66, 0x67]),
        ][Symbol.iterator]();
        function stdin() {
            return sg.next().value;
        }
        stdin;
        """
    )
    try:
        setStdin(stdin=stdin, autoEOF=False)
        assert sys.stdin.read(5) == "ab\x00cd"
        assert sys.stdin.read(2) == "ef"
        assert sys.stdin.read(2) == "g"
        assert sys.stdin.read(2) == ""
    finally:
        setStdin()


@run_in_pyodide
def test_custom_stdin_string_autoeof(selenium):
    import sys

    from pyodide.code import run_js
    from pyodide_js import setStdin

    stdin = run_js(
        r"""
        const sg = [
            "ab\x00",
            "cd",
            null,
            "efg",
        ][Symbol.iterator]();
        function stdin() {
            return sg.next().value;
        }
        stdin
        """
    )
    try:
        setStdin(stdin=stdin)
        assert sys.stdin.read(5) == "ab\x00\nc"
        assert sys.stdin.read(5) == "d\n"
        assert sys.stdin.read(2) == "ef"
        assert sys.stdin.read(2) == "g\n"
        assert sys.stdin.read(2) == ""
    finally:
        sys.stdin.read()
        setStdin()


@run_in_pyodide
def test_custom_stdin_string_noautoeof(selenium):
    import sys

    from pyodide.code import run_js
    from pyodide_js import setStdin

    stdin = run_js(
        """
        const sg = [
            "ab\x00",
            "cd",
            null,
            "efg",
        ][Symbol.iterator]();
        function stdin() {
            return sg.next().value;
        }
        stdin;
        """
    )
    try:
        setStdin(stdin=stdin, autoEOF=False)
        assert sys.stdin.read(7) == "ab\x00\ncd\n"
        assert sys.stdin.read(2) == "ef"
        assert sys.stdin.read(3) == "g\n"
        assert sys.stdin.read(2) == ""
    finally:
        sys.stdin.read()
        setStdin()


@run_in_pyodide
def test_stdin_error(selenium):
    import pytest

    from pyodide_js import setStdin

    try:
        setStdin(error=True)
        with pytest.raises(OSError, match=r".Errno 29. I/O error"):
            input()
    finally:
        setStdin()


def test_custom_stdio_read_buggy(selenium):
    @run_in_pyodide
    def main(selenium):
        import pytest

        from pyodide.code import run_js
        from pyodide_js import setStdin

        setStdin(run_js("({read(buffer) {}})"))
        try:
            with pytest.raises(OSError, match=r"\[Errno 29\] I/O error"):
                input()
        finally:
            setStdin()

    main(selenium)
    # Test that we warned about the buggy write implementation
    assert selenium.logs.endswith(
        "read returned undefined; a correct implementation must return a number"
    )


def test_custom_stdio_write_buggy(selenium):
    @run_in_pyodide
    def main(selenium):
        import pytest

        from pyodide.code import run_js
        from pyodide_js import setStdout

        setStdout(run_js("({write(buffer) {}})"))
        try:
            with pytest.raises(OSError, match=r"\[Errno 29\] I/O error"):
                print("hi\\nthere!!")
        finally:
            setStdout()
            # flush stdout
            print("\n")

    main(selenium)
    # Test that we warned about the buggy write implementation
    expected = "write returned undefined; a correct implementation must return a number"
    assert expected in selenium.logs.splitlines()


def test_custom_stdio_write(selenium):
    result = selenium.run_js(
        r"""
        class MyWriter {
            constructor() {
                this.writtenBuffers = [];
            }
            write(buffer) {
                this.writtenBuffers.push(buffer.slice());
                return buffer.length;
            }
        }
        const o = new MyWriter();
        pyodide.setStdout(o);
        pyodide.runPython(String.raw`
            print('hi\nthere!!')
            print("This\nis a \tmessage!!\n")
        `);
        pyodide.setStdout();
        return o.writtenBuffers.map((b) => Array.from(b));
        """
    )
    assert [bytes(a).decode() for a in result] == [
        "hi\nthere!!",
        "\n",
        "This\nis a \tmessage!!\n",
        "\n",
    ]


@run_in_pyodide
def test_custom_stdin_read1(selenium):
    from pyodide.code import run_js
    from pyodide_js import setStdin

    Reader = run_js(
        r"""
        function* genFunc(){
            const encoder = new TextEncoder();
            let buffer = yield;
            for(const a of [
                "mystring",
                "",
                "a",
                "b",
                "c\n",
                "def\nghi",
                "jkl",
                ""
            ]) {
                encoder.encodeInto(a, buffer);
                buffer = yield a.length;
            }
        }
        class Reader {
            constructor() {
                this.g = genFunc();
                this.g.next();
            }
            read(buffer) {
                return this.g.next(buffer).value;
            }
        }
        Reader
        """
    )
    setStdin(Reader.new())
    try:
        assert input() == "mystring"
        assert input() == "abc"
        assert input() == "def"
        assert input() == "ghijkl"
    finally:
        setStdin()

    setStdin(Reader.new())
    import sys

    try:
        assert sys.stdin.readline() == "mystring"
        assert sys.stdin.readline() == "abc\n"
        assert sys.stdin.readline() == "def\n"
        assert sys.stdin.readline() == "ghijkl"
    finally:
        setStdin()
    setStdin(Reader.new())
    try:
        assert sys.stdin.read() == "mystring"
        assert sys.stdin.read() == "abc\ndef\nghijkl"
    finally:
        setStdin()


@pytest.mark.parametrize("method", ["read", "stdin"])
@run_in_pyodide
def test_custom_stdin_interrupts(selenium, method):
    import pytest

    from pyodide.code import run_js

    run_js(
        """
        ib = new Int32Array(1);
        pyodide.setInterruptBuffer(ib);
        pyodide.setStdin({
            %s () {
                ib[0] = 2;
                pyodide.checkInterrupt();
            }
        });
        """
        % method
    )
    try:
        with pytest.raises(KeyboardInterrupt):
            input()
    finally:
        run_js(
            """
            pyodide.setInterruptBuffer();
            pyodide.setStdin();
            """
        )


@pytest.mark.parametrize("method", ["batched", "raw", "write"])
@run_in_pyodide
def test_custom_stdout_interrupts(selenium, method):
    import pytest

    from pyodide.code import run_js

    run_js(
        """
        ib = new Int32Array(1);
        pyodide.setInterruptBuffer(ib);
        pyodide.setStdout({
            %s () {
                ib[0] = 2;
                pyodide.checkInterrupt();
            }
        });
        """
        % method
    )
    try:
        with pytest.raises(KeyboardInterrupt):
            print()
    finally:
        run_js(
            """
            pyodide.setInterruptBuffer();
            pyodide.setStdout();
            """
        )


@only_node
@run_in_pyodide
def test_node_eagain(selenium):
    from pyodide.code import run_js

    result = run_js(
        """
        pyodide.setStdin({
            i: 0,
            stdin() {
                this.i ++;
                if (this.i < 3) {
                    throw {code: "EAGAIN"};
                }
                this.i = 0;
                return "abcdefg";
            }
        });
        let result = [];
        pyodide.setStdout({
            i: 0,
            write(a) {
                this.i ++;
                if (this.i < 3) {
                    throw {code: "EAGAIN"};
                }
                this.i = 0;
                result.push(new TextDecoder().decode(a));
                return a.length;
            }
        });
        result
        """
    )
    try:
        assert input() == "abcdefg"
        print("hi there!")
        assert result[0] == "hi there!\n"
    finally:
        run_js(
            """
            pyodide.setStdin();
            """
        )
