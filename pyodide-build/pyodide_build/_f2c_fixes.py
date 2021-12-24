import re
from pathlib import Path
import subprocess


def fix_f2c_clapack_calls(f2c_output_name: str):
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
    lapack_other_names = ['lsame', 'ilaenv']
    # fmt: on
    lapack_names = []
    for name in lapack_czds_names:
        lapack_names.extend(f"{l}{name}_" for l in ["c", "z", "d", "s"])
    for name in lapack_cz_names:
        lapack_names.extend(f"{l}{name}_" for l in ["c", "z"])
    for name in lapack_ds_names:
        lapack_names.extend(f"{l}{name}_" for l in ["d", "s"])
    lapack_names.extend(lapack_other_names)
    code = None
    patch_output(f2c_output_name)

    with open(f2c_output_name, "r") as f:
        code = f.read()

    for cur_name in lapack_names:
        code = re.sub(rf"\b{cur_name}\b", "w" + cur_name, code)
    if f2c_output_name.endswith(
        "_lapack_subroutine_wrappers.c"
    ) or f2c_output_name.endswith("wrap_dummy_g77_abi.c"):
        code = fix_lapack_subroutine_wrappers(code)
    with open(f2c_output_name, "w") as f:
        f.write(code)


def patch_output(f2c_output_name: str):
    if f2c_output_name:
        c_file_name = Path(f2c_output_name).name
        patch_file = (Path("../../f2cpatches/") / c_file_name).with_suffix(".patch")
        if patch_file.exists():
            subprocess.run(
                [
                    "patch",
                    str(f2c_output_name),
                    str(patch_file),
                ]
            )


def fix_lapack_subroutine_wrappers(code: str) -> str:
    lines = code.split("\n")
    new_lines = []
    in_subroutine = False
    sub_lines = []
    for line in lines:
        if line.startswith("/* Subroutine */"):
            in_subroutine = True
        if in_subroutine:
            sub_lines.append(line.strip())
            if ")" in line:
                res_line = " ".join(sub_lines)
                res_line = re.sub(",\s*ftnlen [a-z]*_len", "", res_line)
                new_lines.append(res_line)
                sub_lines = []
                in_subroutine = False
        else:
            new_lines.append(line)
    return "\n".join(new_lines)


if __name__ == "__main__":
    fix_f2c_clapack_calls(
        "/home/hood/pyodide/packages/scipy/f2cfixes/_lapack_subroutine_wrappers.c"
    )

    # c_file_name = Path(f2c_output_name).name
    # patch = (Path("../../f2cpatches/") / c_file_name).with_suffix(".patch")
    # replacement_c_file = (Path("../../f2cpatches/") / c_file_name).resolve()
    # if replacement_c_file.exists():
    #     subprocess.run([
    #         "git",
    #         "diff",
    #         "--no-index",
    #         "--",
    #         f2c_output_name,
    #         str(replacement_c_file),
    #     ], stdout=open(patch, "w"))
    #     shutil.copy(replacement_c_file, f2c_output_name)
