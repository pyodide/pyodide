import re
import subprocess
from typing import List, Iterable, Iterator, Tuple
from pathlib import Path


def fix_f2c_clapack_calls(f2c_output_path: str):
    """Fix F2C CLAPACK calls

    f2c compiles code with fortran linkage, which means that
    strings are passed as char* plus extra length argument at
    the end.

    CLAPACK uses C null terminated strings.

    In scipy, we build fortran linkage wrappers for all char* CLAPACK calls.
    We just need to replace the calls and extern definitions in f2c generated code.

    Annoyingly, we can't just patch the fortran code to use the wrapped names because f2c
    has a limit of 6 character function names.
    """
    # fmt: off
    lapack_czds_names = [
        'gbmv', 'gemm', 'gemv', 'symm', 'syr2k', 'syrk', 'tbmv', 'tbsv', 'tpmv',
        'tpsv', 'trmm', 'trmv', 'trsm', 'trsv', 'spmv', 'spr', 'symv', 'syr',
        'langb', 'lange', 'langt', 'lanhs', 'lansb', 'lansp', 'lansy', 'lantb',
        'lantp', 'lantr', 'bdsqr', 'gbbrd', 'gbcon', 'gbrfs', 'gbsvx', 'gbtrs',
        'gebak', 'gebal', 'gecon', 'gees', 'geesx', 'geev', 'geevx', 'gels',
        'gerfs', 'gesdd', 'gesvd', 'gesvx', 'getrs', 'ggbak', 'ggbal', 'gges',
        'ggesx', 'ggev', 'ggevx', 'gghrd', 'gtcon', 'gtrfs', 'gtsvx', 'gttrs',
        'hgeqz', 'hsein', 'hseqr', 'lacpy', 'lagtm', 'lalsd', 'laqgb', 'laqge',
        'laqsb', 'laqsp', 'laqsy', 'larf', 'larfb', 'larft', 'larfx', 'larz',
        'larzb', 'larzt', 'lascl', 'laset', 'lasr', 'lasyf', 'latbs', 'latps',
        'latrd', 'latrs', 'lauu2', 'lauum', 'pbcon', 'pbequ', 'pbrfs', 'pbstf',
        'pbsv', 'pbsvx', 'pbtf2', 'pbtrf', 'pbtrs', 'pocon', 'porfs', 'posv',
        'posvx', 'potf2', 'potrf', 'potri', 'potrs', 'ppcon', 'ppequ', 'pprfs',
        'ppsv', 'ppsvx', 'pptrf', 'pptri', 'pptrs', 'pteqr', 'ptsvx', 'spcon',
        'sprfs', 'spsv', 'spsvx', 'sptrf', 'sptri', 'sptrs', 'stedc', 'stegr',
        'stemr', 'steqr', 'sycon', 'syrfs', 'sysv', 'sysvx', 'sytf2', 'sytrf',
        'sytri', 'sytrs', 'tbcon', 'tbrfs', 'tbtrs', 'tgevc', 'tgsja', 'tgsna',
        'tgsy2', 'tgsyl', 'tpcon', 'tprfs', 'tptri', 'tptrs', 'trcon', 'trevc',
        'trexc', 'trrfs', 'trsen', 'trsna', 'trsyl', 'trti2', 'trtri', 'trtrs',
    ]
    lapack_ds_names = [
        'sbmv', 'spr2', 'syr2', 'lamch', 'lanst', 'bdsdc', 'disna', 'larrc',
        'larrd', 'larre', 'lasdq', 'lasrt', 'opgtr', 'opmtr', 'orgbr', 'orgtr',
        'orm2l', 'orm2r', 'ormbr', 'ormhr', 'orml2', 'ormlq', 'ormql', 'ormqr',
        'ormr2', 'ormr3', 'ormrq', 'ormrz', 'ormtr', 'sbev', 'sbevd', 'sbevx',
        'sbgst', 'sbgv', 'sbgvd', 'sbgvx', 'sbtrd', 'spev', 'spevd', 'spevx',
        'spgst', 'spgv', 'spgvd', 'spgvx', 'sptrd', 'stebz', 'stev', 'stevd',
        'stevr', 'stevx', 'syev', 'syevd', 'syevr', 'syevx', 'sygs2', 'sygst',
        'sygv', 'sygvd', 'sygvx', 'sytd2', 'sytrd'
    ]
    lapack_cz_names = [
        'hbmv', 'hemm', 'hemv', 'her', 'her2', 'her2k', 'herk', 'hpmv', 'hpr',
        'hpr2', 'lanhb', 'lanhe', 'lanhp', 'lanht', 'hbev', 'hbevd', 'hbevx',
        'hbgst', 'hbgv', 'hbgvd', 'hbgvx', 'hbtrd', 'hecon', 'heev', 'heevd',
        'heevr', 'heevx', 'hegs2', 'hegst', 'hegv', 'hegvd', 'hegvx', 'herfs',
        'hesv', 'hesvx', 'hetd2', 'hetf2', 'hetrd', 'hetrf', 'hetri', 'hetrs',
        'hpcon', 'hpev', 'hpevd', 'hpevx', 'hpgst', 'hpgv', 'hpgvd', 'hpgvx',
        'hprfs', 'hpsv', 'hpsvx', 'hptrd', 'hptrf', 'hptri', 'hptrs', 'lacp2',
        'lahef', 'laqhb', 'laqhe', 'laqhp', 'ptrfs', 'pttrs', 'ungbr', 'ungtr',
        'unm2l', 'unm2r', 'unmbr', 'unmhr', 'unml2', 'unmlq', 'unmql', 'unmqr',
        'unmr2', 'unmr3', 'unmrq', 'unmrz', 'unmtr', 'upgtr', 'upmtr',
    ]
    lapack_other_names = ['lsame_', 'ilaenv_']
    # fmt: on
    lapack_names = lapack_other_names
    for name in lapack_czds_names:
        lapack_names.extend(f"{l}{name}_" for l in ["c", "z", "d", "s"])
    for name in lapack_cz_names:
        lapack_names.extend(f"{l}{name}_" for l in ["c", "z"])
    for name in lapack_ds_names:
        lapack_names.extend(f"{l}{name}_" for l in ["d", "s"])

    f2c_output = Path(f2c_output_path)
    if f2c_output.name == "dfft.c":
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

    with open(f2c_output, "r") as f:
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
    ]:
        lines = remove_ftnlen_args(lines)

    code = "".join(lines)
    for cur_name in lapack_names:
        code = re.sub(rf"\b{cur_name}\b", "w" + cur_name, code)

    with open(f2c_output, "w") as f:
        f.write(code)


def remove_ftnlen_args(lines: List[str]) -> List[str]:
    new_lines = []
    for line in regroup_lines(lines):
        if line.startswith("/* Subroutine */"):
            line = re.sub(",\s*ftnlen [a-z]*_len", "", line)
        new_lines.append(line)
    return new_lines


def add_externs_to_structs(lines: List[str]):
    for idx, line in enumerate(lines):
        if line.startswith("struct"):
            lines[idx] = "extern struct {"


def regroup_lines(lines: Iterable[str]) -> Iterator[str]:
    """
    Make sure that functions and declarations have their argument list only on
    one line.
    """
    line_iter = iter(lines)
    for line in line_iter:
        if not "/* Subroutine */" in line:
            yield line
            continue

        is_definition = line.startswith("/* Subroutine */")
        stop = ")" if is_definition else ";"

        sub_lines = [line.strip()]
        for line in line_iter:
            sub_lines.append(line.strip())
            if stop in line:
                break
        joined_line = " ".join(sub_lines)
        if is_definition:
            yield joined_line
        else:
            yield from (x + ";" for x in joined_line.split(";")[:-1])


def fix_inconsistent_decls(lines: List[str]) -> List[str]:
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


def get_subroutine_decl(sub: str) -> Tuple[str, List[str]]:
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


if __name__ == "__main__":
    fix_f2c_clapack_calls(
        "/home/hood/pyodide/packages/scipy/f2cfixes/_lapack_subroutine_wrappers.c"
    )
