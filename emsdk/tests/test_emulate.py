import subprocess
from . import common


def test_emulate_function(tmpdir):
    with tmpdir.as_cwd():
        with open("library.c", "w") as f:
            f.write(
                """\
#include <stdio.h>

// emulate function pointer casts - this has the
// wrong arguments and return type
int foo(int extra_args) {
  puts("hello from library");
  return 0;
}"""
            )
        with open("main.c", "w") as f:
            f.write(common.MAIN_C)

        subprocess.run(
            [
                "emcc",
                "-g",
                "-s",
                "SIDE_MODULE=1",
                "library.c",
                "-o",
                "library.wasm",
                "-s",
                "EMULATE_FUNCTION_POINTER_CASTS=1",
                "-s",
                "EXPORT_ALL=1",
            ],
            check=True,
        )
        subprocess.run(
            [
                "emcc",
                "-g",
                "-s",
                "MAIN_MODULE=1",
                "main.c",
                "--embed-file",
                "library.wasm",
                "-s",
                "EMULATE_FUNCTION_POINTER_CASTS=1",
                "-s",
                "EXPORT_ALL=1",
            ],
            check=True,
        )
        out = subprocess.run(["node", "a.out.js"], capture_output=True, check=True)
        assert out.stdout == b"hello from main\nhello from library\n"
