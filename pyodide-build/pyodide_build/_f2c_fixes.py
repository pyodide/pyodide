import re
import shutil
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
    lapack_names = [
        "lsame_", "cgbmv_", "cgemm_", "cgemv_", "chbmv_",
        "chemm_", "chemv_", "cher_", "cher2_", "cher2k_", "cherk_",
        "chpmv_", "chpr_", "chpr2_", "csymm_", "csyr2k_", "csyrk_",
        "ctbmv_", "ctbsv_", "ctpmv_", "ctpsv_", "ctrmm_", "ctrmv_",
        "ctrsm_", "ctrsv_", "dgbmv_", "dgemm_", "dgemv_", "dsbmv_",
        "dspmv_", "dspr_", "dspr2_", "dsymm_", "dsymv_", "dsyr_", "dsyr2_",
        "dsyr2k_", "dsyrk_", "dtbmv_", "dtbsv_", "dtpmv_", "dtpsv_",
        "dtrmm_", "dtrmv_", "dtrsm_", "dtrsv_", "sgbmv_", "sgemm_",
        "sgemv_", "ssbmv_", "sspmv_", "sspr_", "sspr2_", "ssymm_",
        "ssymv_", "ssyr_", "ssyr2_", "ssyr2k_", "ssyrk_", "stbmv_",
        "stbsv_", "stpmv_", "stpsv_", "strmm_", "strmv_", "strsm_",
        "strsv_", "zgbmv_", "zgemm_", "zgemv_", "zhbmv_", "zhemm_",
        "zhemv_", "zher_", "zher2_", "zher2k_", "zherk_", "zhpmv_",
        "zhpr_", "zhpr2_", "zsymm_", "zsyr2k_", "zsyrk_", "ztbmv_",
        "ztbsv_", "ztpmv_", "ztpsv_", "ztrmm_", "ztrmv_", "ztrsm_",
        "ztrsv_", "clangb_", "clange_", "clangt_", "clanhb_", "clanhe_",
        "clanhp_", "clanhs_", "clanht_", "clansb_", "clansp_", "clansy_",
        "clantb_", "clantp_", "clantr_", "dlamch_", "dlangb_", "dlange_",
        "dlangt_", "dlanhs_", "dlansb_", "dlansp_", "dlanst_", "dlansy_",
        "dlantb_", "dlantp_", "dlantr_", "slamch_", "slangb_", "slange_",
        "slangt_", "slanhs_", "slansb_", "slansp_", "slanst_", "slansy_",
        "slantb_", "slantp_", "slantr_", "zlangb_", "zlange_", "zlangt_",
        "zlanhb_", "zlanhe_", "zlanhp_", "zlanhs_", "zlanht_", "zlansb_",
        "zlansp_", "zlansy_", "zlantb_", "zlantp_", "zlantr_", "cbdsqr_",
        "cgbbrd_", "cgbcon_", "cgbrfs_", "cgbsvx_", "cgbtrs_", "cgebak_",
        "cgebal_", "cgecon_", "cgees_", "cgeesx_", "cgeev_", "cgeevx_",
        "cgels_", "cgerfs_", "cgesdd_", "cgesvd_", "cgesvx_", "cgetrs_",
        "cggbak_", "cggbal_", "cgges_", "cggesx_", "cggev_", "cggevx_",
        "cgghrd_", "cgtcon_", "cgtrfs_", "cgtsvx_", "cgttrs_", "chbev_",
        "chbevd_", "chbevx_", "chbgst_", "chbgv_", "chbgvd_", "chbgvx_",
        "chbtrd_", "checon_", "cheev_", "cheevd_", "cheevr_", "cheevx_",
        "chegs2_", "chegst_", "chegv_", "chegvd_", "chegvx_", "cherfs_",
        "chesv_", "chesvx_", "chetd2_", "chetf2_", "chetrd_", "chetrf_",
        "chetri_", "chetrs_", "chgeqz_", "chpcon_", "chpev_", "chpevd_",
        "chpevx_", "chpgst_", "chpgv_", "chpgvd_", "chpgvx_", "chprfs_",
        "chpsv_", "chpsvx_", "chptrd_", "chptrf_", "chptri_", "chptrs_",
        "chsein_", "chseqr_", "clacp2_", "clacpy_", "clagtm_", "clahef_",
        "clalsd_", "claqgb_", "claqge_", "claqhb_", "claqhe_", "claqhp_",
        "claqsb_", "claqsp_", "claqsy_", "clarf_", "clarfb_", "clarft_",
        "clarfx_", "clarz_", "clarzb_", "clarzt_", "clascl_", "claset_",
        "clasr_", "clasyf_", "clatbs_", "clatps_", "clatrd_", "clatrs_",
        "clauu2_", "clauum_", "cpbcon_", "cpbequ_", "cpbrfs_", "cpbstf_",
        "cpbsv_", "cpbsvx_", "cpbtf2_", "cpbtrf_", "cpbtrs_", "cpocon_",
        "cporfs_", "cposv_", "cposvx_", "cpotf2_", "cpotrf_", "cpotri_",
        "cpotrs_", "cppcon_", "cppequ_", "cpprfs_", "cppsv_", "cppsvx_",
        "cpptrf_", "cpptri_", "cpptrs_", "cpteqr_", "cptrfs_", "cptsvx_",
        "cpttrs_", "cspcon_", "cspmv_", "cspr_", "csprfs_", "cspsv_",
        "cspsvx_", "csptrf_", "csptri_", "csptrs_", "cstedc_", "cstegr_",
        "cstemr_", "csteqr_", "csycon_", "csymv_", "csyr_", "csyrfs_",
        "csysv_", "csysvx_", "csytf2_", "csytrf_", "csytri_", "csytrs_",
        "ctbcon_", "ctbrfs_", "ctbtrs_", "ctgevc_", "ctgsja_", "ctgsna_",
        "ctgsy2_", "ctgsyl_", "ctpcon_", "ctprfs_", "ctptri_", "ctptrs_",
        "ctrcon_", "ctrevc_", "ctrexc_", "ctrrfs_", "ctrsen_", "ctrsna_",
        "ctrsyl_", "ctrti2_", "ctrtri_", "ctrtrs_", "cungbr_", "cungtr_",
        "cunm2l_", "cunm2r_", "cunmbr_", "cunmhr_", "cunml2_", "cunmlq_",
        "cunmql_", "cunmqr_", "cunmr2_", "cunmr3_", "cunmrq_", "cunmrz_",
        "cunmtr_", "cupgtr_", "cupmtr_", "dbdsdc_", "dbdsqr_", "ddisna_",
        "dgbbrd_", "dgbcon_", "dgbrfs_", "dgbsvx_", "dgbtrs_", "dgebak_",
        "dgebal_", "dgecon_", "dgees_", "dgeesx_", "dgeev_", "dgeevx_", "dgels_",
        "dgerfs_", "dgesdd_", "dgesvd_", "dgesvx_", "dgetrs_", "dggbak_",
        "dggbal_", "dgges_", "dggesx_", "dggev_", "dggevx_", "dgghrd_", "dgtcon_",
        "dgtrfs_", "dgtsvx_", "dgttrs_", "dhgeqz_", "dhsein_", "dhseqr_",
        "dlacpy_", "dlagtm_", "dlalsd_", "dlaqgb_", "dlaqge_", "dlaqsb_",
        "dlaqsp_", "dlaqsy_", "dlarf_", "dlarfb_", "dlarft_", "dlarfx_", "dlarrc_",
        "dlarrd_", "dlarre_", "dlarz_", "dlarzb_", "dlarzt_", "dlascl_", "dlasdq_",
        "dlaset_", "dlasr_", "dlasrt_", "dlasyf_", "dlatbs_", "dlatps_", "dlatrd_",
        "dlatrs_", "dlauu2_", "dlauum_", "dopgtr_", "dopmtr_", "dorgbr_",
        "dorgtr_", "dorm2l_", "dorm2r_", "dormbr_", "dormhr_", "dorml2_",
        "dormlq_", "dormql_", "dormqr_", "dormr2_", "dormr3_", "dormrq_",
        "dormrz_", "dormtr_", "dpbcon_", "dpbequ_", "dpbrfs_", "dpbstf_", "dpbsv_",
        "dpbsvx_", "dpbtf2_", "dpbtrf_", "dpbtrs_", "dpocon_", "dporfs_", "dposv_",
        "dposvx_", "dpotf2_", "dpotrf_", "dpotri_", "dpotrs_", "dppcon_",
        "dppequ_", "dpprfs_", "dppsv_", "dppsvx_", "dpptrf_", "dpptri_", "dpptrs_",
        "dpteqr_", "dptsvx_", "dsbev_", "dsbevd_", "dsbevx_", "dsbgst_", "dsbgv_",
        "dsbgvd_", "dsbgvx_", "dsbtrd_", "dspcon_", "dspev_", "dspevd_", "dspevx_",
        "dspgst_", "dspgv_", "dspgvd_", "dspgvx_", "dsprfs_", "dspsv_", "dspsvx_",
        "dsptrd_", "dsptrf_", "dsptri_", "dsptrs_", "dstebz_", "dstedc_",
        "dstegr_", "dstemr_", "dsteqr_", "dstev_", "dstevd_", "dstevr_", "dstevx_",
        "dsycon_", "dsyev_", "dsyevd_", "dsyevr_", "dsyevx_", "dsygs2_", "dsygst_",
        "dsygv_", "dsygvd_", "dsygvx_", "dsyrfs_", "dsysv_", "dsysvx_", "dsytd2_",
        "dsytf2_", "dsytrd_", "dsytrf_", "dsytri_", "dsytrs_", "dtbcon_",
        "dtbrfs_", "dtbtrs_", "dtgevc_", "dtgsja_", "dtgsna_", "dtgsy2_",
        "dtgsyl_", "dtpcon_", "dtprfs_", "dtptri_", "dtptrs_", "dtrcon_",
        "dtrevc_", "dtrexc_", "dtrrfs_", "dtrsen_", "dtrsna_", "dtrsyl_",
        "dtrti2_", "dtrtri_", "dtrtrs_", "sbdsdc_", "sbdsqr_", "sdisna_",
        "sgbbrd_", "sgbcon_", "sgbrfs_", "sgbsvx_", "sgbtrs_", "sgebak_",
        "sgebal_", "sgecon_", "sgees_", "sgeesx_", "sgeev_", "sgeevx_", "sgels_",
        "sgerfs_", "sgesdd_", "sgesvd_", "sgesvx_", "sgetrs_", "sggbak_",
        "sggbal_", "sgges_", "sggesx_", "sggev_", "sggevx_", "sgghrd_", "sgtcon_",
        "sgtrfs_", "sgtsvx_", "sgttrs_", "shgeqz_", "shsein_", "shseqr_",
        "slacpy_", "slagtm_", "slalsd_", "slaqgb_", "slaqge_", "slaqsb_",
        "slaqsp_", "slaqsy_", "slarf_", "slarfb_", "slarft_", "slarfx_", "slarrc_",
        "slarrd_", "slarre_", "slarz_", "slarzb_", "slarzt_", "slascl_", "slasdq_",
        "slaset_", "slasr_", "slasrt_", "slasyf_", "slatbs_", "slatps_", "slatrd_",
        "slatrs_", "slauu2_", "slauum_", "sopgtr_", "sopmtr_", "sorgbr_",
        "sorgtr_", "sorm2l_", "sorm2r_", "sormbr_", "sormhr_", "sorml2_",
        "sormlq_", "sormql_", "sormqr_", "sormr2_", "sormr3_", "sormrq_",
        "sormrz_", "sormtr_", "spbcon_", "spbequ_", "spbrfs_", "spbstf_", "spbsv_",
        "spbsvx_", "spbtf2_", "spbtrf_", "spbtrs_", "spocon_", "sporfs_", "sposv_",
        "sposvx_", "spotf2_", "spotrf_", "spotri_", "spotrs_", "sppcon_",
        "sppequ_", "spprfs_", "sppsv_", "sppsvx_", "spptrf_", "spptri_", "spptrs_",
        "spteqr_", "sptsvx_", "ssbev_", "ssbevd_", "ssbevx_", "ssbgst_", "ssbgv_",
        "ssbgvd_", "ssbgvx_", "ssbtrd_", "sspcon_", "sspev_", "sspevd_", "sspevx_",
        "sspgst_", "sspgv_", "sspgvd_", "sspgvx_", "ssprfs_", "sspsv_", "sspsvx_",
        "ssptrd_", "ssptrf_", "ssptri_", "ssptrs_", "sstebz_", "sstedc_",
        "sstegr_", "sstemr_", "ssteqr_", "sstev_", "sstevd_", "sstevr_", "sstevx_",
        "ssycon_", "ssyev_", "ssyevd_", "ssyevr_", "ssyevx_", "ssygs2_", "ssygst_",
        "ssygv_", "ssygvd_", "ssygvx_", "ssyrfs_", "ssysv_", "ssysvx_", "ssytd2_",
        "ssytf2_", "ssytrd_", "ssytrf_", "ssytri_", "ssytrs_", "stbcon_",
        "stbrfs_", "stbtrs_", "stgevc_", "stgsja_", "stgsna_", "stgsy2_",
        "stgsyl_", "stpcon_", "stprfs_", "stptri_", "stptrs_", "strcon_",
        "strevc_", "strexc_", "strrfs_", "strsen_", "strsna_", "strsyl_",
        "strti2_", "strtri_", "strtrs_", "zbdsqr_", "zgbbrd_", "zgbcon_",
        "zgbrfs_", "zgbsvx_", "zgbtrs_", "zgebak_", "zgebal_", "zgecon_", "zgees_",
        "zgeesx_", "zgeev_", "zgeevx_", "zgels_", "zgerfs_", "zgesdd_", "zgesvd_",
        "zgesvx_", "zgetrs_", "zggbak_", "zggbal_", "zgges_", "zggesx_", "zggev_",
        "zggevx_", "zgghrd_", "zgtcon_", "zgtrfs_", "zgtsvx_", "zgttrs_", "zhbev_",
        "zhbevd_", "zhbevx_", "zhbgst_", "zhbgv_", "zhbgvd_", "zhbgvx_", "zhbtrd_",
        "zhecon_", "zheev_", "zheevd_", "zheevr_", "zheevx_", "zhegs2_", "zhegst_",
        "zhegv_", "zhegvd_", "zhegvx_", "zherfs_", "zhesv_", "zhesvx_", "zhetd2_",
        "zhetf2_", "zhetrd_", "zhetrf_", "zhetri_", "zhetrs_", "zhgeqz_",
        "zhpcon_", "zhpev_", "zhpevd_", "zhpevx_", "zhpgst_", "zhpgv_", "zhpgvd_",
        "zhpgvx_", "zhprfs_", "zhpsv_", "zhpsvx_", "zhptrd_", "zhptrf_", "zhptri_",
        "zhptrs_", "zhsein_", "zhseqr_", "zlacp2_", "zlacpy_", "zlagtm_",
        "zlahef_", "zlalsd_", "zlaqgb_", "zlaqge_", "zlaqhb_", "zlaqhe_",
        "zlaqhp_", "zlaqsb_", "zlaqsp_", "zlaqsy_", "zlarf_", "zlarfb_", "zlarft_",
        "zlarfx_", "zlarz_", "zlarzb_", "zlarzt_", "zlascl_", "zlaset_", "zlasr_",
        "zlasyf_", "zlatbs_", "zlatps_", "zlatrd_", "zlatrs_", "zlauu2_",
        "zlauum_", "zpbcon_", "zpbequ_", "zpbrfs_", "zpbstf_", "zpbsv_", "zpbsvx_",
        "zpbtf2_", "zpbtrf_", "zpbtrs_", "zpocon_", "zporfs_", "zposv_", "zposvx_",
        "zpotf2_", "zpotrf_", "zpotri_", "zpotrs_", "zppcon_", "zppequ_",
        "zpprfs_", "zppsv_", "zppsvx_", "zpptrf_", "zpptri_", "zpptrs_", "zpteqr_",
        "zptrfs_", "zptsvx_", "zpttrs_", "zspcon_", "zspmv_", "zspr_", "zsprfs_",
        "zspsv_", "zspsvx_", "zsptrf_", "zsptri_", "zsptrs_", "zstedc_", "zstegr_",
        "zstemr_", "zsteqr_", "zsycon_", "zsymv_", "zsyr_", "zsyrfs_", "zsysv_",
        "zsysvx_", "zsytf2_", "zsytrf_", "zsytri_", "zsytrs_", "ztbcon_",
        "ztbrfs_", "ztbtrs_", "ztgevc_", "ztgsja_", "ztgsna_", "ztgsy2_",
        "ztgsyl_", "ztpcon_", "ztprfs_", "ztptri_", "ztptrs_", "ztrcon_",
        "ztrevc_", "ztrexc_", "ztrrfs_", "ztrsen_", "ztrsna_", "ztrsyl_",
        "ztrti2_", "ztrtri_", "ztrtrs_", "zungbr_", "zungtr_", "zunm2l_",
        "zunm2r_", "zunmbr_", "zunmhr_", "zunml2_", "zunmlq_", "zunmql_",
        "zunmqr_", "zunmr2_", "zunmr3_", "zunmrq_", "zunmrz_", "zunmtr_",
        "zupgtr_", "zupmtr_", "ilaenv_",
    ]
    # fmt: on
    code = None
    patch_output(f2c_output_name)

    with open(f2c_output_name, "r") as f:
        code = f.read()

    for cur_name in lapack_names:
        code = re.sub(rf"\b{cur_name}\b", "w" + cur_name, code)
    if f2c_output_name.endswith("_lapack_subroutine_wrappers.c"):
        code = fix_lapack_subroutine_wrappers(code)
    with open(f2c_output_name, "w") as f:
        f.write(code)


def patch_output(f2c_output_name):
    if f2c_output_name:
        c_file_name = Path(f2c_output_name).name
        patch_file = (Path("../../f2cpatches/") / c_file_name).with_suffix(".patch")
        if patch_file.exists():
            subprocess.run(
                [
                    "patch",
                    "-p1",
                    "-i",
                    str(patch_file),
                ]
            )


def fix_lapack_subroutine_wrappers(code):
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
