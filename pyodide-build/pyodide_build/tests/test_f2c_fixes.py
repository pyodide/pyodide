from textwrap import dedent

from pyodide_build._f2c_fixes import fix_f2c_clapack_calls


def test_fix_f2c_clapack_calls(tmpdir):
    code = dedent(
        """
       #include "f2c.h"

       int sgemv_(char *trans, integer *m, integer *n, real *alpha)
       {
          return 0;
       }
       """
    )

    source_file = tmpdir / "sgemv.c"
    with open(source_file, "w") as fh:
        fh.write(code)

    fix_f2c_clapack_calls(str(source_file))

    with open(source_file, "r") as fh:
        code_fixed = fh.read()

    assert code_fixed == code.replace("sgemv_", "wsgemv_")
