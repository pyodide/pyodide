import re
import subprocess
from pathlib import Path
from textwrap import dedent  # for doctests
from typing import Iterable, Iterator


def fix_f2c_output(f2c_output_path: str):
    """
    This function is called on the name of each C output file. It fixes up the C
    output in various ways to compensate for the lack of f2c support for Fortan
    90 and Fortran 95.
    """
    f2c_output = Path(f2c_output_path)
    if f2c_output.name == "lapack_extras.c":
        # dfft.c has a bunch of implicit cast args coming from functions copied
        # out of future lapack versions. fix_inconsistent_decls will fix all
        # except string to int.
        subprocess.check_call(
            [
                "patch",
                str(f2c_output_path),
                f"../../patches/fix-implicit-cast-args-from-newer-lapack.patch",
            ]
        )

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

    if f2c_output.name in [
        "wrap_dummy_g77_abi.c",
        "_lapack_subroutine_wrappers.c",
        "_blas_subroutine_wrappers.c",
        "_flapack-f2pywrappers.c",
    ]:
        lines = remove_ftnlen_args(lines)

    with open(f2c_output, "w") as f:
        f.writelines(lines)


def prepare_doctest(x):
    return dedent(x).strip().split("\n")


def remove_ftnlen_args(lines: list[str]) -> list[str]:
    """
    Functions with "character" arguments have these extra ftnlen arguments at
    the end (which are never used). Other places declare these arguments as
    "integer" which don't get length arguments. This automates the removal of
    the problematic arguments.

    >>> print("\\n".join(remove_ftnlen_args(prepare_doctest('''
    ...     /* Subroutine */ int chla_transtypewrp__(char *ret, integer *trans, ftnlen
    ...     	ret_len)
    ... '''))))
    /* Subroutine */ int chla_transtypewrp__(char *ret, integer *trans)

    >>> print("\\n".join(remove_ftnlen_args(prepare_doctest('''
    ...     /* Subroutine */ int clanhfwrp_(real *ret, char *norm, char *transr, char *
    ...     	uplo, integer *n, complex *a, real *work, ftnlen norm_len, ftnlen
    ...     	transr_len, ftnlen uplo_len)
    ... '''))))
    /* Subroutine */ int clanhfwrp_(real *ret, char *norm, char *transr, char * uplo, integer *n, complex *a, real *work)
    """
    new_lines = []
    for line in regroup_lines(lines):
        if line.startswith("/* Subroutine */"):
            line = re.sub(r",\s*ftnlen [a-z]*_len", "", line)
        new_lines.append(line)
    return new_lines


def add_externs_to_structs(lines: list[str]):
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
    >>> print("\\n".join(lines))
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

    >>> print("\\n".join(regroup_lines(prepare_doctest('''
    ...     /* Subroutine */ int clanhfwrp_(real *ret, char *norm, char *transr, char *
    ...     	uplo, integer *n, complex *a, real *work, ftnlen norm_len, ftnlen
    ...     	transr_len, ftnlen uplo_len)
    ...     {
    ...        static doublereal psum[52];
    ...        extern /* Subroutine */ int dqelg_(integer *, doublereal *, doublereal *,
    ...            doublereal *, doublereal *, integer *);
    ... '''))))
    /* Subroutine */ int clanhfwrp_(real *ret, char *norm, char *transr, char * uplo, integer *n, complex *a, real *work, ftnlen norm_len, ftnlen transr_len, ftnlen uplo_len)
    {
       static doublereal psum[52];
       extern /* Subroutine */ int dqelg_(integer *, doublereal *, doublereal *, doublereal *, doublereal *, integer *);

    """
    line_iter = iter(lines)
    for line in line_iter:
        if not "/* Subroutine */" in line:
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

    >>> print("\\n".join(fix_inconsistent_decls(prepare_doctest('''
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
        if not "extern /* Subroutine */" in line:
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
