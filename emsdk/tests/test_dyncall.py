import subprocess
from . import common


def test_dyncall(tmpdir):
    with tmpdir.as_cwd():
        with open("library.c", "w") as f:
            f.write(
                """\
#include <stdio.h>
#include <stdlib.h>
#include <setjmp.h>
#include <assert.h>

// This can be any function that has a signature not found in main.
__attribute__ ((noinline)) int indirect_function(int a, float b, int c, double d) {
  return a;
}

typedef int (*type_iifid) (int, float, int, double);

void foo() {
  // Hack to force inclusion of malloc
  volatile int x = (int) malloc(1);
  free((void *) x);

  type_iifid fp = &indirect_function;

  jmp_buf buf;
  int i = setjmp(buf);

  printf("%d\\n", i);
  assert(fp(i, 0, 0, 0) == i);

  if (i == 0) longjmp(buf, 1);

}
"""
            )
        with open("main.c", "w") as f:
            f.write(common.MAIN_C)

        subprocess.run(
            [
                "emcc",
                "-g4",
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
                "-g4",
                "-s",
                "MAIN_MODULE=1",
                "main.c",
                "--embed-file",
                "library.wasm",
                "-s",
                "EMULATE_FUNCTION_POINTER_CASTS=1",
            ],
            check=True,
        )
        out = subprocess.run(["node", "a.out.js"], capture_output=True, check=True)
        assert out.stdout == b"hello from main\n0\n1\n"
