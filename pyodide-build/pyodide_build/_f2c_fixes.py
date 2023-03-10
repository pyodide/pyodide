import re
from collections.abc import Iterable, Iterator
from pathlib import Path
from textwrap import dedent  # for doctests


def prepare_doctest(x: str) -> list[str]:
    return dedent(x).strip().splitlines(True)


def fix_f2c_input(f2c_input_path: str) -> None:
    """
    CLAPACK has been manually modified to remove useless arguments generated by
    f2c. But the mismatches between the f2c ABI and the human-curated sensible
    ABI in CLAPACK cause us great pain.

    This stuff applies to actual source files, but scipy also has multiple
    templating engines for Fortran, so these changes have to be applied
    immediately prior to f2c'ing a .f file to ensure that they also work
    correctly on templated files.

    Fortran seems to be mostly case insensitive. The templated files in
    particular can include weird mixtures of lower and upper case.

    Mostly the issues are related to 'character' types. Most LAPACK functions
    that take string arguments use them as enums and only care about the first
    character of the string. f2c generates a 'length' argument to indicate how
    long the string is, but CLAPACK leaves these length arguments out because
    the strings are assumed to have length 1.

    So the goal is to cause f2c to generate no length argument. We can achieve
    this by replacing the string with the ascii code of the first character
    e.g.,:

        f('UPPER') --> f(85)

    Coming from C this surprises me a bit. I would expect `f(85)` to cause a
    segfault or something when f tries to find its string at memory address 85.

    f("UPPER") gets f2c'd to:

        f("UPPER", 5)

    But f2c compiles f(85) to the C code:

        static integer c__85 = 85;
        f(&c__85);

    This is perfect. Not sure why it does this, but it's very convenient for us.

    chla_transtype is a special case. The CLAPACK version of chla_transtype takes
    a return argument, whereas f2c thinks it should return the value.

    """
    f2c_input = Path(f2c_input_path)
    with open(f2c_input) as f:
        lines = f.readlines()
    new_lines = []
    lines = char1_args_to_int(lines)

    for line in lines:
        line = fix_string_args(line)

        if f2c_input_path.endswith("_flapack-f2pywrappers.f"):
            line = line.replace("character cmach", "integer cmach")
            line = line.replace("character norm", "integer norm")
        if "id_dist" in str(f2c_input):
            line = line.replace("character*1 jobz", "integer jobz")
            if "jobz =" in line:
                line = re.sub("'(.)'", lambda r: str(ord(r.group(1))), line)

        if f2c_input.name in [
            "_lapack_subroutine_wrappers.f",
            "_blas_subroutine_wrappers.f",
        ]:
            line = line.replace("character", "integer")
            line = line.replace("ret = chla_transtype(", "call chla_transtype(ret, 1,")

        # f2c has no support for variable sized arrays, so we replace them with
        # dummy fixed sized arrays and then put the formulas back in in
        # fix_f2c_output. Luckily, variable sized arrays are scarce in the scipy
        # code base.
        if "PROPACK" in str(f2c_input):
            line = line.replace("ylocal(n)", "ylocal(123001)")
            line = line.replace("character*1", "integer")

        if f2c_input.name == "mvndst.f":
            line = re.sub(r"(infin|stdev|nlower|nupper)\(d\)", r"\1(123001)", line)
            line = line.replace("rho(d*(d-1)/2)", "rho(123002)")

        new_lines.append(line)

    with open(f2c_input_path, "w") as f:
        f.writelines(new_lines)


def fix_string_args(line: str) -> str:
    """
    The two functions ilaenv and xerbla have real string args, f2c generates
    inaccurate signatures for them. Instead of manually fixing the signatures
    (xerbla happens a lot) we inject wrappers called `xerblaf2py` and
    `ilaenvf2py` that have the signatures f2c expects and call these instead.

    Also, replace all single character strings in (the first line of) "call"
    statements with their ascci codes.
    """
    line = re.sub("ilaenv", "ilaenvf2py", line, flags=re.I)
    if (
        not re.search("call", line, re.I)
        and "SIGNST" not in line
        and "TRANST" not in line
    ):
        return line
    if re.search("xerbla", line, re.I):
        return re.sub("xerbla", "xerblaf2py", line, flags=re.I)
    else:
        return re.sub("'[A-Za-z0-9]'", lambda y: str(ord(y.group(0)[1])), line)


def char1_to_int(x: str) -> str:
    """
    Replace multicharacter strings with the ascii code of their first character.

    >>> char1_to_int("CALL sTRSV( 'UPPER', 'NOTRANS', 'NONUNIT', J, H, LDH, Y, 1 )")
    'CALL sTRSV( 85, 78, 78, J, H, LDH, Y, 1 )'
    """
    return re.sub("'(.)[A-Za-z -]*'", lambda r: str(ord(r.group(1))), x)


def char1_args_to_int(lines: list[str]) -> list[str]:
    """
    Replace strings with the ascii code of their first character if they are
    arguments to one of a long list of hard coded LAPACK functions (see
    fncstems). This handles multiline function calls.

    >>> print(char1_args_to_int(["CALL sTRSV( 'UPPER', 'NOTRANS', 'NONUNIT', J, H, LDH, Y, 1 )"]))
    ['CALL sTRSV( 85, 78, 78, J, H, LDH, Y, 1 )']

    >>> print("".join(char1_args_to_int(prepare_doctest('''
    ...               call cvout (logfil, nconv, workl(ihbds), ndigit,
    ...     &            '_neupd: Last row of the eigenvector matrix for T')
    ...     call ctrmm('Right'   , 'Upper'      , 'No transpose',
    ...     &                  'Non-unit', n            , nconv         ,
    ...     &                  one       , workl(invsub), ldq           ,
    ...     &                  z         , ldz)
    ... '''))))
    call cvout (logfil, nconv, workl(ihbds), ndigit,
    &            '_neupd: Last row of the eigenvector matrix for T')
    call ctrmm(82   , 85      , 78,
    &                  78, n            , nconv         ,
    &                  one       , workl(invsub), ldq           ,
    &                  z         , ldz)
    """
    fncstems = [
        "gemm",
        "ggbak",
        "gghrd",
        "lacpy",
        "lamch",
        "lanhs",
        "lanst",
        "larf",
        "lascl",
        "laset",
        "lasr",
        "ormqr",
        "orm2r",
        "steqr",
        "stevr",
        "trevc",
        "trmm",
        "trsen",
        "trsv",
        "unm2r",
        "unmqr",
    ]
    fncnames = []
    for c in "cdsz":
        for stem in fncstems:
            fncnames.append(c + stem)
    fncnames += ["lsame"]

    funcs_pattern = "|".join(fncnames)
    new_lines = []
    replace = False
    for line in lines:
        if re.search(funcs_pattern, line, re.IGNORECASE):
            replace = True
        if replace:
            line = char1_to_int(line)
        if not re.search(r",\s*$", line):
            replace = False
        new_lines.append(line)
    return new_lines


def fix_f2c_output(f2c_output_path: str) -> str | None:
    """
    This function is called on the name of each C output file. It fixes up the C
    output in various ways to compensate for the lack of f2c support for Fortran
    90 and Fortran 95.
    """
    f2c_output = Path(f2c_output_path)

    with open(f2c_output) as f:
        lines = f.readlines()
    if "id_dist" in f2c_output_path:
        # Fix implicit casts in id_dist.
        lines = fix_inconsistent_decls(lines)
    if "odepack" in f2c_output_path or f2c_output.name == "mvndst.c":
        # Mark all but one declaration of each struct as extern.
        if f2c_output.name == "blkdta000.c":
            # extern marking in blkdata000.c doesn't work properly so we let it
            # define the one copy of the structs. It doesn't talk about lsa001
            # at all though, so we need to add a definition of it.
            lines.append(
                """
                struct {    doublereal rownd2, pdest, pdlast, ratio, cm1[12], cm2[5], pdnorm;
                    integer iownd2[3], icount, irflag, jtyp, mused, mxordn, mxords;
                } lsa001_;
                """
            )
        else:
            add_externs_to_structs(lines)

    if f2c_output.name == "_lapack_subroutine_wrappers.c":
        lines = [
            line.replace("integer chla_transtype__", "void chla_transtype__")
            for line in lines
        ]
    if f2c_output.name == "_blas_subroutine_wrappers.c":
        lines = [
            line.replace("extern doublereal sasum_", "extern float sasum_")
            for line in lines
        ]

    # Substitute back the dummy fixed array sizes. We also have to remove the
    # "static" storage specifier since variable sized arrays can't have static
    # storage.
    if f2c_output.name == "mvndst.c":
        lines = fix_inconsistent_decls(lines)

        def fix_line(line: str) -> str:
            if "12300" in line:
                return (
                    line.replace("static", "")
                    .replace("123001", "(*d__)")
                    .replace("123002", "(*d__)*((*d__)-1)/2")
                )
            return line

        lines = list(map(fix_line, lines))

    if "PROPACK" in str(f2c_output):

        def fix_line(line: str) -> str:
            if f2c_output.name != "cgemm_ovwr.c":
                line = line.replace("struct", "extern struct")
            if "12300" in line:
                return line.replace("static", "").replace("123001", "(*n)")
            return line

        lines = list(map(fix_line, lines))
        if f2c_output.name.endswith("lansvd.c"):
            lines.append(
                """
                #include <time.h>

                int second_(real *t) {
                    *t = clock()/1000;
                    return 0;
                }
                """
            )

    with open(f2c_output, "w") as f:
        f.writelines(lines)

    return None


def add_externs_to_structs(lines: list[str]) -> None:
    """
    The fortran "common" keyword is supposed to share variables between a bunch
    of files. f2c doesn't handle this correctly (it isn't possible for it to
    handle it correctly because it only looks one file at a time).

    We mark all the structs as externs and then (separately) add one non extern
    version to each file.
    >>> lines = prepare_doctest('''
    ...     struct {    doublereal rls[218];
    ...         integer ils[39];
    ...     } ls0001_;
    ...     struct {    doublereal rlsa[22];
    ...         integer ilsa[9];
    ...     } lsa001_;
    ...     struct {    integer ieh[2];
    ...     } eh0001_;
    ... ''')
    >>> add_externs_to_structs(lines)
    >>> print("".join(lines))
    extern struct {    doublereal rls[218];
        integer ils[39];
    } ls0001_;
    extern struct {    doublereal rlsa[22];
        integer ilsa[9];
    } lsa001_;
    extern struct {    integer ieh[2];
    } eh0001_;
    """
    for idx, line in enumerate(lines):
        if line.startswith("struct"):
            lines[idx] = "extern " + lines[idx]


def regroup_lines(lines: Iterable[str]) -> Iterator[str]:
    """
    Make sure that functions and declarations have their argument list only on
    one line.

    >>> print("".join(regroup_lines(prepare_doctest('''
    ...     /* Subroutine */ int clanhfwrp_(real *ret, char *norm, char *transr, char *
    ...     	uplo, integer *n, complex *a, real *work, ftnlen norm_len, ftnlen
    ...     	transr_len, ftnlen uplo_len)
    ...     {
    ...        static doublereal psum[52];
    ...        extern /* Subroutine */ int dqelg_(integer *, doublereal *, doublereal *,
    ...            doublereal *, doublereal *, integer *);
    ... '''))))
    /* Subroutine */ int clanhfwrp_(real *ret, char *norm, char *transr, char * uplo, integer *n, complex *a, real *work, ftnlen norm_len, ftnlen transr_len, ftnlen uplo_len){
       static doublereal psum[52];
       extern /* Subroutine */ int dqelg_(integer *, doublereal *, doublereal *, doublereal *, doublereal *, integer *);

    """
    line_iter = iter(lines)
    for line in line_iter:
        if "/* Subroutine */" not in line:
            yield line
            continue

        is_definition = line.startswith("/* Subroutine */")
        stop = ")" if is_definition else ";"
        if stop in line:
            yield line
            continue

        sub_lines = [line.rstrip()]
        for line in line_iter:
            sub_lines.append(line.strip())
            if stop in line:
                break
        joined_line = " ".join(sub_lines)
        if is_definition:
            yield joined_line
        else:
            yield from (x + ";" for x in joined_line.split(";")[:-1])


def fix_inconsistent_decls(lines: list[str]) -> list[str]:
    """
    Fortran functions in id_dist use implicit casting of function args which f2c
    doesn't support.

    The fortran equivalent of the following code:

        double f(double x){
            return x + 5;
        }
        double g(int x){
            return f(x);
        }

    gets f2c'd to:

        double f(double x){
            return x + 5;
        }
        double g(int x){
            double f(int);
            return f(x);
        }

    which fails to compile because the declaration of f type clashes with the
    definition. Gather up all the definitions in each file and then gathers the
    declarations and fixes them if necessary so that the declaration matches the
    definition.

    >>> print("".join(fix_inconsistent_decls(prepare_doctest('''
    ...    /* Subroutine */ double f(double x){
    ...        return x + 5;
    ...    }
    ...    /* Subroutine */ double g(int x){
    ...        extern /* Subroutine */ double f(int);
    ...        return f(x);
    ...    }
    ... '''))))
    /* Subroutine */ double f(double x){
        return x + 5;
    }
    /* Subroutine */ double g(int x){
        extern /* Subroutine */ double f(double);
        return f(x);
    }
    """
    func_types = {}
    lines = list(regroup_lines(lines))
    for line in lines:
        if not line.startswith("/* Subroutine */"):
            continue
        [func_name, types] = get_subroutine_decl(line)
        func_types[func_name] = types

    for idx, line in enumerate(lines):
        if "extern /* Subroutine */" not in line:
            continue
        decls = line.split(")")[:-1]
        for decl in decls:
            [func_name, types] = get_subroutine_decl(decl)
            if func_name not in func_types or types == func_types[func_name]:
                continue
            types = func_types[func_name]
            l = list(line.partition(func_name + "("))
            l[2:] = list(l[2].partition(")"))
            l[2] = ", ".join(types)
            line = "".join(l)
        lines[idx] = line
    return lines


def get_subroutine_decl(sub: str) -> tuple[str, list[str]]:
    """
    >>> get_subroutine_decl(
    ...     "extern /* Subroutine */ int dqelg_(integer *, doublereal *, doublereal *, doublereal *, doublereal *, integer *);"
    ... )
    ('dqelg_', ['integer *', 'doublereal *', 'doublereal *', 'doublereal *', 'doublereal *', 'integer *'])
    """
    func_name = sub.partition("(")[0].rpartition(" ")[2]
    args_str = sub.partition("(")[2].partition(")")[0]
    args = args_str.split(",")
    types = []
    for arg in args:
        arg = arg.strip()
        if "*" in arg:
            type = "".join(arg.partition("*")[:-1])
        else:
            type = arg.partition(" ")[0]
        types.append(type.strip())
    return (func_name, types)


def scipy_fix_cfile(path: str) -> None:
    """
    Replace void return types with int return types in various generated .c and
    .h files. We can't achieve this with a simple patch because these files are
    not in the sdist, they are generated as part of the build.
    """
    source_path = Path(path)
    text = source_path.read_text()
    text = text.replace("extern void F_WRAPPEDFUNC", "extern int F_WRAPPEDFUNC")
    text = text.replace("extern void F_FUNC", "extern int F_FUNC")
    text = text.replace("void (*f2py_func)", "int (*f2py_func)")
    text = text.replace("static void cb_", "static int cb_")
    text = text.replace("typedef void(*cb_", "typedef int(*cb_")
    text = text.replace("void(*)", "int(*)")
    text = text.replace("static void f2py_setup_", "static int f2py_setup_")

    if path.endswith("_flapackmodule.c"):
        text = text.replace(",size_t", "")
        text = re.sub(r",slen\([a-z]*\)\)", ")", text)

    if path.endswith("_fblasmodule.c"):
        text = text.replace(" float (*f2py_func)", " double (*f2py_func)")

    source_path.write_text(text)

    for lib in ["lapack", "blas"]:
        if path.endswith(f"cython_{lib}.c"):
            header_path = Path(path).with_name(f"_{lib}_subroutines.h")
            header_text = header_path.read_text()
            header_text = header_text.replace("void F_FUNC", "int F_FUNC")
            header_path.write_text(header_text)


def scipy_fixes(args: list[str]) -> None:
    for arg in args:
        if arg.endswith(".c"):
            scipy_fix_cfile(arg)
