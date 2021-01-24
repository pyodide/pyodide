#!/usr/bin/env python3
"""Helper for cross-compiling distutils-based Python extensions.

distutils has never had a proper cross-compilation story. This is a hack, which
miraculously works, to get around that.

The gist is:

- Compile the package natively, replacing calls to the compiler and linker with
  wrappers that store the arguments in a log, and then delegate along to the
  real native compiler and linker.

- Remove all of the native build products.

- Play back the log, replacing the native compiler with emscripten and
  adjusting include paths and flags as necessary for cross-compiling to
  emscripten. This overwrites the results from the original native compilation.

While this results in more work than strictly necessary (it builds a native
version of the package, even though we then throw it away), it seems to be the
only reliable way to automatically build a package that interleaves
configuration with build.
"""


import argparse
import importlib.machinery
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import shutil
import sys


# absolute import is necessary as this file will be symlinked
# under tools
from pyodide_build import common


TOOLSDIR = common.TOOLSDIR
symlinks = set(["cc", "c++", "ld", "ar", "gcc", "gfortran"])


class EnvironmentRewritingArgument(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        for e_name, e_value in os.environ.items():
            values = values.replace(f"$({e_name})", e_value)
        setattr(namespace, self.dest, values)


def collect_args(basename):
    """
    This is called when this script is called through a symlink that looks like
    a compiler or linker.

    It writes the arguments to the build.log, and then delegates to the real
    native compiler or linker.
    """
    # Remove the symlink compiler from the PATH, so we can delegate to the
    # native compiler
    env = dict(os.environ)
    path = env["PATH"]
    while str(TOOLSDIR) + ":" in path:
        path = path.replace(str(TOOLSDIR) + ":", "")
    env["PATH"] = path

    skip_host = "SKIP_HOST" in os.environ

    # Skip compilations of C/Fortran extensions for the target environment.
    # We still need to generate the output files for distutils to continue
    # the build.
    # TODO: This may need slight tuning for new projects. In particular,
    #       currently ar is not skipped, so a known failure would happen when
    #       we create some object files (that are empty as gcc is skipped), on
    #       which we run the actual ar command.
    skip = False
    if (
        basename in ["gcc", "cc", "c++", "gfortran", "ld"]
        and "-o" in sys.argv[1:]
        # do not skip numpy as it is needed as build time
        # dependency by other packages (e.g. matplotlib)
        and skip_host
    ):
        out_idx = sys.argv.index("-o")
        if (out_idx + 1) < len(sys.argv):
            # get the index of the output file path
            out_idx += 1
            with open(sys.argv[out_idx], "wb") as fh:
                fh.write(b"")
            skip = True

    with open("build.log", "a") as fd:
        # TODO: store skip status in the build.log
        json.dump([basename] + sys.argv[1:], fd)
        fd.write("\n")

    if skip:
        sys.exit(0)
    compiler_command = [basename]
    if shutil.which("ccache") is not None:
        # Enable ccache if it's installed
        compiler_command.insert(0, "ccache")

    sys.exit(subprocess.run(compiler_command + sys.argv[1:], env=env).returncode)


def make_symlinks(env):
    """
    Makes sure all of the symlinks that make this script look like a compiler
    exist.
    """
    exec_path = Path(__file__).resolve()
    for symlink in symlinks:
        symlink_path = TOOLSDIR / symlink
        if os.path.lexists(symlink_path) and not symlink_path.exists():
            # remove broken symlink so it can be re-created
            symlink_path.unlink()
        try:
            symlink_path.symlink_to(exec_path)
        except FileExistsError:
            pass
        if symlink == "c++":
            var = "CXX"
        else:
            var = symlink.upper()
        env[var] = symlink


def capture_compile(args):
    env = dict(os.environ)
    make_symlinks(env)
    env["PATH"] = str(TOOLSDIR) + ":" + os.environ["PATH"]

    cmd = [sys.executable, "setup.py", "install"]
    if args.install_dir == "skip":
        cmd[-1] = "build"
    elif args.install_dir != "":
        cmd.extend(["--home", args.install_dir])

    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        build_log_path = Path("build.log")
        if build_log_path.exists():
            build_log_path.unlink()
        sys.exit(result.returncode)


def f2c(args, dryrun=False):
    """Apply f2c to compilation arguments

    Parameters
    ----------
    args : iterable
       input compiler arguments
    dryrun : bool, default=True
       if False run f2c on detected fortran files

    Returns
    -------
    new_args : list
       output compiler arguments


    Examples
    --------

    >>> f2c(['gfortran', 'test.f'], dryrun=True)
    ['gfortran', 'test.c']
    """
    new_args = []
    found_source = False
    for arg in args:
        if arg.endswith(".f"):
            filename = os.path.abspath(arg)
            if not dryrun:
                subprocess.check_call(
                    ["f2c", os.path.basename(filename)], cwd=os.path.dirname(filename)
                )
                fix_f2c_clapack_calls(arg[:-2]+".c")
            new_args.append(arg[:-2] + ".c")
            found_source = True
        else:
            new_args.append(arg)

    new_args_str = " ".join(args)
    if ".so" in new_args_str and "libgfortran.so" not in new_args_str:
        found_source = True

    if not found_source:
        print(f"f2c: source not found, skipping: {new_args_str}")
        return None
    return new_args


def fix_f2c_clapack_calls(f2c_output_name):
    """    
    f2c compiles code with fortran linkage, which means that
    strings are passed as char* plus extra length argument at 
    the end. 

    CLAPACK uses C null terminated strings.

    In scipy, we build fortran linkage wrappers for all char* CLAPACK calls.
    We just need to replace the calls and extern definitions in f2c generated code.

    Annoyingly, we can't just patch the fortran code to use the wrapped names because f2c
    has a limit of 6 character function names.
    """ 
    lapack_names=[
"lsame_","cgbmv_","cgemm_","cgemv_","chbmv_","chemm_","chemv_","cher_","cher2_","cher2k_",
"cherk_","chpmv_","chpr_","chpr2_","csymm_","csyr2k_","csyrk_","ctbmv_","ctbsv_","ctpmv_",
"ctpsv_","ctrmm_","ctrmv_","ctrsm_","ctrsv_","dgbmv_","dgemm_","dgemv_","dsbmv_","dspmv_",
"dspr_","dspr2_","dsymm_","dsymv_","dsyr_","dsyr2_","dsyr2k_","dsyrk_","dtbmv_","dtbsv_",
"dtpmv_","dtpsv_","dtrmm_","dtrmv_","dtrsm_","dtrsv_","sgbmv_","sgemm_","sgemv_","ssbmv_",
"sspmv_","sspr_","sspr2_","ssymm_","ssymv_","ssyr_","ssyr2_","ssyr2k_","ssyrk_","stbmv_",
"stbsv_","stpmv_","stpsv_","strmm_","strmv_","strsm_","strsv_","zgbmv_","zgemm_","zgemv_",
"zhbmv_","zhemm_","zhemv_","zher_","zher2_","zher2k_","zherk_","zhpmv_","zhpr_","zhpr2_",
"zsymm_","zsyr2k_","zsyrk_","ztbmv_","ztbsv_","ztpmv_","ztpsv_","ztrmm_","ztrmv_","ztrsm_",
"ztrsv_","clangb_","clange_","clangt_","clanhb_","clanhe_","clanhp_","clanhs_","clanht_","clansb_",
"clansp_","clansy_","clantb_","clantp_","clantr_","dlamch_","dlangb_","dlange_","dlangt_","dlanhs_",
"dlansb_","dlansp_","dlanst_","dlansy_","dlantb_","dlantp_","dlantr_","slamch_","slangb_","slange_",
"slangt_","slanhs_","slansb_","slansp_","slanst_","slansy_","slantb_","slantp_","slantr_","zlangb_",
"zlange_","zlangt_","zlanhb_","zlanhe_","zlanhp_","zlanhs_","zlanht_","zlansb_","zlansp_","zlansy_",
"zlantb_","zlantp_","zlantr_","cbdsqr_","cgbbrd_","cgbcon_","cgbrfs_","cgbsvx_","cgbtrs_","cgebak_",
"cgebal_","cgecon_","cgees_","cgeesx_","cgeev_","cgeevx_","cgels_","cgerfs_","cgesdd_","cgesvd_",
"cgesvx_","cgetrs_","cggbak_","cggbal_","cgges_","cggesx_","cggev_","cggevx_","cgghrd_","cgtcon_",
"cgtrfs_","cgtsvx_","cgttrs_","chbev_","chbevd_","chbevx_","chbgst_","chbgv_","chbgvd_","chbgvx_",
"chbtrd_","checon_","cheev_","cheevd_","cheevr_","cheevx_","chegs2_","chegst_","chegv_","chegvd_",
"chegvx_","cherfs_","chesv_","chesvx_","chetd2_","chetf2_","chetrd_","chetrf_","chetri_","chetrs_",
"chgeqz_","chpcon_","chpev_","chpevd_","chpevx_","chpgst_","chpgv_","chpgvd_","chpgvx_","chprfs_",
"chpsv_","chpsvx_","chptrd_","chptrf_","chptri_","chptrs_","chsein_","chseqr_","clacp2_","clacpy_",
"clagtm_","clahef_","clalsd_","claqgb_","claqge_","claqhb_","claqhe_","claqhp_","claqsb_","claqsp_",
"claqsy_","clarf_","clarfb_","clarft_","clarfx_","clarz_","clarzb_","clarzt_","clascl_","claset_",
"clasr_","clasyf_","clatbs_","clatps_","clatrd_","clatrs_","clauu2_","clauum_","cpbcon_","cpbequ_",
"cpbrfs_","cpbstf_","cpbsv_","cpbsvx_","cpbtf2_","cpbtrf_","cpbtrs_","cpocon_","cporfs_","cposv_",
"cposvx_","cpotf2_","cpotrf_","cpotri_","cpotrs_","cppcon_","cppequ_","cpprfs_","cppsv_","cppsvx_",
"cpptrf_","cpptri_","cpptrs_","cpteqr_","cptrfs_","cptsvx_","cpttrs_","cspcon_","cspmv_","cspr_",
"csprfs_","cspsv_","cspsvx_","csptrf_","csptri_","csptrs_","cstedc_","cstegr_","cstemr_","csteqr_",
"csycon_","csymv_","csyr_","csyrfs_","csysv_","csysvx_","csytf2_","csytrf_","csytri_","csytrs_",
"ctbcon_","ctbrfs_","ctbtrs_","ctgevc_","ctgsja_","ctgsna_","ctgsy2_","ctgsyl_","ctpcon_","ctprfs_",
"ctptri_","ctptrs_","ctrcon_","ctrevc_","ctrexc_","ctrrfs_","ctrsen_","ctrsna_","ctrsyl_","ctrti2_",
"ctrtri_","ctrtrs_","cungbr_","cungtr_","cunm2l_","cunm2r_","cunmbr_","cunmhr_","cunml2_","cunmlq_",
"cunmql_","cunmqr_","cunmr2_","cunmr3_","cunmrq_","cunmrz_","cunmtr_","cupgtr_","cupmtr_","dbdsdc_",
"dbdsqr_","ddisna_","dgbbrd_","dgbcon_","dgbrfs_","dgbsvx_","dgbtrs_","dgebak_","dgebal_","dgecon_",
"dgees_","dgeesx_","dgeev_","dgeevx_","dgels_","dgerfs_","dgesdd_","dgesvd_","dgesvx_","dgetrs_",
"dggbak_","dggbal_","dgges_","dggesx_","dggev_","dggevx_","dgghrd_","dgtcon_","dgtrfs_","dgtsvx_",
"dgttrs_","dhgeqz_","dhsein_","dhseqr_","dlacpy_","dlagtm_","dlalsd_","dlaqgb_","dlaqge_","dlaqsb_",
"dlaqsp_","dlaqsy_","dlarf_","dlarfb_","dlarft_","dlarfx_","dlarrc_","dlarrd_","dlarre_","dlarz_",
"dlarzb_","dlarzt_","dlascl_","dlasdq_","dlaset_","dlasr_","dlasrt_","dlasyf_","dlatbs_","dlatps_",
"dlatrd_","dlatrs_","dlauu2_","dlauum_","dopgtr_","dopmtr_","dorgbr_","dorgtr_","dorm2l_","dorm2r_",
"dormbr_","dormhr_","dorml2_","dormlq_","dormql_","dormqr_","dormr2_","dormr3_","dormrq_","dormrz_",
"dormtr_","dpbcon_","dpbequ_","dpbrfs_","dpbstf_","dpbsv_","dpbsvx_","dpbtf2_","dpbtrf_","dpbtrs_",
"dpocon_","dporfs_","dposv_","dposvx_","dpotf2_","dpotrf_","dpotri_","dpotrs_","dppcon_","dppequ_",
"dpprfs_","dppsv_","dppsvx_","dpptrf_","dpptri_","dpptrs_","dpteqr_","dptsvx_","dsbev_","dsbevd_",
"dsbevx_","dsbgst_","dsbgv_","dsbgvd_","dsbgvx_","dsbtrd_","dspcon_","dspev_","dspevd_","dspevx_",
"dspgst_","dspgv_","dspgvd_","dspgvx_","dsprfs_","dspsv_","dspsvx_","dsptrd_","dsptrf_","dsptri_",
"dsptrs_","dstebz_","dstedc_","dstegr_","dstemr_","dsteqr_","dstev_","dstevd_","dstevr_","dstevx_",
"dsycon_","dsyev_","dsyevd_","dsyevr_","dsyevx_","dsygs2_","dsygst_","dsygv_","dsygvd_","dsygvx_",
"dsyrfs_","dsysv_","dsysvx_","dsytd2_","dsytf2_","dsytrd_","dsytrf_","dsytri_","dsytrs_","dtbcon_",
"dtbrfs_","dtbtrs_","dtgevc_","dtgsja_","dtgsna_","dtgsy2_","dtgsyl_","dtpcon_","dtprfs_","dtptri_",
"dtptrs_","dtrcon_","dtrevc_","dtrexc_","dtrrfs_","dtrsen_","dtrsna_","dtrsyl_","dtrti2_","dtrtri_",
"dtrtrs_","sbdsdc_","sbdsqr_","sdisna_","sgbbrd_","sgbcon_","sgbrfs_","sgbsvx_","sgbtrs_","sgebak_",
"sgebal_","sgecon_","sgees_","sgeesx_","sgeev_","sgeevx_","sgels_","sgerfs_","sgesdd_","sgesvd_",
"sgesvx_","sgetrs_","sggbak_","sggbal_","sgges_","sggesx_","sggev_","sggevx_","sgghrd_","sgtcon_",
"sgtrfs_","sgtsvx_","sgttrs_","shgeqz_","shsein_","shseqr_","slacpy_","slagtm_","slalsd_","slaqgb_",
"slaqge_","slaqsb_","slaqsp_","slaqsy_","slarf_","slarfb_","slarft_","slarfx_","slarrc_","slarrd_",
"slarre_","slarz_","slarzb_","slarzt_","slascl_","slasdq_","slaset_","slasr_","slasrt_","slasyf_",
"slatbs_","slatps_","slatrd_","slatrs_","slauu2_","slauum_","sopgtr_","sopmtr_","sorgbr_","sorgtr_",
"sorm2l_","sorm2r_","sormbr_","sormhr_","sorml2_","sormlq_","sormql_","sormqr_","sormr2_","sormr3_",
"sormrq_","sormrz_","sormtr_","spbcon_","spbequ_","spbrfs_","spbstf_","spbsv_","spbsvx_","spbtf2_",
"spbtrf_","spbtrs_","spocon_","sporfs_","sposv_","sposvx_","spotf2_","spotrf_","spotri_","spotrs_",
"sppcon_","sppequ_","spprfs_","sppsv_","sppsvx_","spptrf_","spptri_","spptrs_","spteqr_","sptsvx_",
"ssbev_","ssbevd_","ssbevx_","ssbgst_","ssbgv_","ssbgvd_","ssbgvx_","ssbtrd_","sspcon_","sspev_",
"sspevd_","sspevx_","sspgst_","sspgv_","sspgvd_","sspgvx_","ssprfs_","sspsv_","sspsvx_","ssptrd_",
"ssptrf_","ssptri_","ssptrs_","sstebz_","sstedc_","sstegr_","sstemr_","ssteqr_","sstev_","sstevd_",
"sstevr_","sstevx_","ssycon_","ssyev_","ssyevd_","ssyevr_","ssyevx_","ssygs2_","ssygst_","ssygv_",
"ssygvd_","ssygvx_","ssyrfs_","ssysv_","ssysvx_","ssytd2_","ssytf2_","ssytrd_","ssytrf_","ssytri_",
"ssytrs_","stbcon_","stbrfs_","stbtrs_","stgevc_","stgsja_","stgsna_","stgsy2_","stgsyl_","stpcon_",
"stprfs_","stptri_","stptrs_","strcon_","strevc_","strexc_","strrfs_","strsen_","strsna_","strsyl_",
"strti2_","strtri_","strtrs_","zbdsqr_","zgbbrd_","zgbcon_","zgbrfs_","zgbsvx_","zgbtrs_","zgebak_",
"zgebal_","zgecon_","zgees_","zgeesx_","zgeev_","zgeevx_","zgels_","zgerfs_","zgesdd_","zgesvd_",
"zgesvx_","zgetrs_","zggbak_","zggbal_","zgges_","zggesx_","zggev_","zggevx_","zgghrd_","zgtcon_",
"zgtrfs_","zgtsvx_","zgttrs_","zhbev_","zhbevd_","zhbevx_","zhbgst_","zhbgv_","zhbgvd_","zhbgvx_",
"zhbtrd_","zhecon_","zheev_","zheevd_","zheevr_","zheevx_","zhegs2_","zhegst_","zhegv_","zhegvd_",
"zhegvx_","zherfs_","zhesv_","zhesvx_","zhetd2_","zhetf2_","zhetrd_","zhetrf_","zhetri_","zhetrs_",
"zhgeqz_","zhpcon_","zhpev_","zhpevd_","zhpevx_","zhpgst_","zhpgv_","zhpgvd_","zhpgvx_","zhprfs_",
"zhpsv_","zhpsvx_","zhptrd_","zhptrf_","zhptri_","zhptrs_","zhsein_","zhseqr_","zlacp2_","zlacpy_",
"zlagtm_","zlahef_","zlalsd_","zlaqgb_","zlaqge_","zlaqhb_","zlaqhe_","zlaqhp_","zlaqsb_","zlaqsp_",
"zlaqsy_","zlarf_","zlarfb_","zlarft_","zlarfx_","zlarz_","zlarzb_","zlarzt_","zlascl_","zlaset_",
"zlasr_","zlasyf_","zlatbs_","zlatps_","zlatrd_","zlatrs_","zlauu2_","zlauum_","zpbcon_","zpbequ_",
"zpbrfs_","zpbstf_","zpbsv_","zpbsvx_","zpbtf2_","zpbtrf_","zpbtrs_","zpocon_","zporfs_","zposv_",
"zposvx_","zpotf2_","zpotrf_","zpotri_","zpotrs_","zppcon_","zppequ_","zpprfs_","zppsv_","zppsvx_",
"zpptrf_","zpptri_","zpptrs_","zpteqr_","zptrfs_","zptsvx_","zpttrs_","zspcon_","zspmv_","zspr_",
"zsprfs_","zspsv_","zspsvx_","zsptrf_","zsptri_","zsptrs_","zstedc_","zstegr_","zstemr_","zsteqr_",
"zsycon_","zsymv_","zsyr_","zsyrfs_","zsysv_","zsysvx_","zsytf2_","zsytrf_","zsytri_","zsytrs_",
"ztbcon_","ztbrfs_","ztbtrs_","ztgevc_","ztgsja_","ztgsna_","ztgsy2_","ztgsyl_","ztpcon_","ztprfs_",
"ztptri_","ztptrs_","ztrcon_","ztrevc_","ztrexc_","ztrrfs_","ztrsen_","ztrsna_","ztrsyl_","ztrti2_",
"ztrtri_","ztrtrs_","zungbr_","zungtr_","zunm2l_","zunm2r_","zunmbr_","zunmhr_","zunml2_","zunmlq_",
"zunmql_","zunmqr_","zunmr2_","zunmr3_","zunmrq_","zunmrz_","zunmtr_","zupgtr_","zupmtr_","ilaenv_",
    ]
    code=None
    with open(f2c_output_name,"r") as f:
        code=f.read()
        for cur_name in lapack_names:
            code=re.sub(rf'\b{cur_name}\b','w'+cur_name,code)
    if code:
        with open(f2c_output_name,"w") as f:
            f.write(code)


def handle_command(line, args, dryrun=False):
    """Handle a compilation command

    Parameters
    ----------
    line : iterable
       an iterable with the compilation arguments
    args : {object, namedtuple}
       an container with additional compilation options,
       in particular containing ``args.cflags``, ``args.cxxflags``, and ``args.ldflags``
    dryrun : bool, default=False
       if True do not run the resulting command, only return it

    Examples
    --------

    >>> from collections import namedtuple
    >>> Args = namedtuple('args', ['cflags', 'cxxflags', 'ldflags', 'host','replace_libs','install_dir'])
    >>> args = Args(cflags='', cxxflags='', ldflags='', host='',replace_libs='',install_dir='')
    >>> handle_command(['gcc', 'test.c'], args, dryrun=True)
    emcc test.c
    ['emcc', 'test.c']
    """
    # some libraries have different names on wasm e.g. png16 = png
    replace_libs = {}
    for l in args.replace_libs.split(";"):
        if len(l) > 0:
            from_lib, to_lib = l.split("=")
            replace_libs[from_lib] = to_lib

    # This is a special case to skip the compilation tests in numpy that aren't
    # actually part of the build
    for arg in line:
        if r"/file.c" in arg or "_configtest" in arg:
            return
        if re.match(r"/tmp/.*/source\.[bco]+", arg):
            return
        if arg == "-print-multiarch":
            return
        if arg.startswith("/tmp"):
            return

    if line[0] == "gfortran":
        result = f2c(line)
        if result is None:
            return
        line = result
        new_args = ["emcc"]
    elif line[0] == "ar":
        new_args = ["emar"]
    elif line[0] == "c++":
        new_args = ["em++"]
    else:
        new_args = ["emcc"]
        # distutils doesn't use the c++ compiler when compiling c++ <sigh>
        if any(arg.endswith((".cpp", ".cc")) for arg in line):
            new_args = ["em++"]
    library_output = False
    for arg in line:
        if arg.endswith(".so") and not arg.startswith("-"):
            library_output = True

    if library_output:
        new_args.extend(args.ldflags.split())
    elif new_args[0] == "emcc":
        new_args.extend(args.cflags.split())
    elif new_args[0] == "em++":
        new_args.extend(args.cflags.split() + args.cxxflags.split())

    lapack_dir = None

    used_libs = set()

    # Go through and adjust arguments
    for arg in line[1:]:
        if arg.startswith("-I"):
            if (
                str(Path(arg[2:]).resolve()).startswith(sys.prefix + "/include/python")
                and "site-packages" not in arg
            ):
                arg = arg.replace("-I" + sys.prefix, "-I" + args.target)
            # Don't include any system directories
            elif arg[2:].startswith("/usr"):
                continue
        # Don't include any system directories
        if arg.startswith("-L/usr"):
            continue
        if arg.startswith("-l"):
            for lib_name in replace_libs.keys():
                # this enables glob style **/* matching
                if PurePosixPath(arg[2:]).match(lib_name):
                    if len(replace_libs[lib_name]) > 0:
                        arg = "-l" + replace_libs[lib_name]
                    else:
                        continue
        if arg.startswith("-l"):
            # WASM link doesn't like libraries being included twice
            # skip second one
            if arg in used_libs:
                continue
            used_libs.add(arg)
        # threading is disabled for now
        if arg == "-pthread":
            continue
        # On Mac, we need to omit some darwin-specific arguments
        if arg in ["-bundle", "-undefined", "dynamic_lookup"]:
            continue
        # The native build is possibly multithreaded, but the emscripten one
        # definitely isn't
        arg = re.sub(r"/python([0-9]\.[0-9]+)m", r"/python\1", arg)
        if arg.endswith(".so"):
            output = arg
        # don't include libraries from native builds
        if (
            len(args.install_dir) > 0
            and arg.startswith("-l" + args.install_dir)
            or arg.startswith("-L" + args.install_dir)
        ):
            continue

        # Fix for scipy to link to the correct BLAS/LAPACK files
        if arg.startswith("-L") and "CLAPACK" in arg:
            out_idx = line.index("-o")
            out_idx += 1
            module_name = line[out_idx]
            module_name = Path(module_name).name.split(".")[0]

            lapack_dir = arg.replace("-L", "")
            # For convenience we determine needed scipy link libraries
            # here, instead of in patch files
            link_libs = ["F2CLIBS/libf2c.a", "blas_WA.a"]
            if module_name in [
                "_flapack",
                "_flinalg",
                "_calc_lwork",
                "cython_lapack",
                "_iterative",
                "_arpack",
            ]:
                link_libs.append("lapack_WA.a")

            for lib_name in link_libs:
                arg = os.path.join(lapack_dir, f"{lib_name}")
                new_args.append(arg)

            new_args.extend(["-s", "INLINING_LIMIT=5"])
            continue

        # Use -Os for files that are statically linked to CLAPACK
        if (
            arg.startswith("-O")
            and "CLAPACK" in " ".join(line)
            and "-L" in " ".join(line)
        ):
            new_args.append("-Os")
            continue

        if new_args[-1].startswith("-B") and "compiler_compat" in arg:
            # conda uses custom compiler search paths with the compiler_compat folder.
            # Ignore it.
            del new_args[-1]
            continue

        # See https://github.com/emscripten-core/emscripten/issues/8650
        if arg in ["-lfreetype", "-lz", "-lpng", "-lgfortran"]:
            continue
        # don't use -shared, SIDE_MODULE is already used
        # and -shared breaks it
        if arg in ["-shared"]:
            continue

        new_args.append(arg)

    # This can only be used for incremental rebuilds -- it generates
    # an error during clean build of numpy
    # if os.path.isfile(output):
    #     print('SKIPPING: ' + ' '.join(new_args))
    #     return

    print(" ".join(new_args))

    if not dryrun:
        result = subprocess.run(new_args)
        if result.returncode != 0:
            sys.exit(result.returncode)

    # Emscripten .so files shouldn't have the native platform slug
    if library_output:
        renamed = output
        for ext in importlib.machinery.EXTENSION_SUFFIXES:
            if ext == ".so":
                continue
            if renamed.endswith(ext):
                renamed = renamed[: -len(ext)] + ".so"
                break
        if not dryrun and output != renamed:
            os.rename(output, renamed)
    return new_args


def replay_compile(args):
    # If pure Python, there will be no build.log file, which is fine -- just do
    # nothing
    build_log_path = Path("build.log")
    if build_log_path.is_file():
        with open(build_log_path, "r") as fd:
            for line in fd:
                line = json.loads(line)
                handle_command(line, args)


def clean_out_native_artifacts():
    for root, dirs, files in os.walk("."):
        for file in files:
            path = Path(root) / file
            if path.suffix in (".o", ".so", ".a"):
                path.unlink()


def install_for_distribution(args):
    commands = [
        sys.executable,
        "setup.py",
        "install",
        "--skip-build",
        "--prefix=install",
        "--old-and-unmanageable",
    ]
    try:
        subprocess.check_call(commands)
    except Exception:
        print(
            f'Warning: {" ".join(str(arg) for arg in commands)} failed '
            f"with distutils, possibly due to the use of distutils "
            f"that does not support the --old-and-unmanageable "
            "argument. Re-trying the install without this argument."
        )
        subprocess.check_call(commands[:-1])


def build_wrap(args):
    build_log_path = Path("build.log")
    if not build_log_path.is_file():
        capture_compile(args)
    clean_out_native_artifacts()
    replay_compile(args)
    install_for_distribution(args)


def make_parser(parser):
    basename = Path(sys.argv[0]).name
    if basename in symlinks:
        # skip parsing of all arguments
        parser._actions = []
    else:
        parser.description = (
            "Cross compile a Python distutils package. "
            "Run from the root directory of the package's source"
        )
        parser.add_argument(
            "--cflags",
            type=str,
            nargs="?",
            default=common.DEFAULTCFLAGS,
            help="Extra compiling flags",
            action=EnvironmentRewritingArgument,
        )
        parser.add_argument(
            "--cxxflags",
            type=str,
            nargs="?",
            default=common.DEFAULTCXXFLAGS,
            help="Extra C++ specific compiling flags",
            action=EnvironmentRewritingArgument,
        )
        parser.add_argument(
            "--ldflags",
            type=str,
            nargs="?",
            default=common.DEFAULTLDFLAGS,
            help="Extra linking flags",
            action=EnvironmentRewritingArgument,
        )
        parser.add_argument(
            "--target",
            type=str,
            nargs="?",
            default=common.TARGETPYTHON,
            help="The path to the target Python installation",
        )
        parser.add_argument(
            "--install-dir",
            type=str,
            nargs="?",
            default="",
            help=(
                "Directory for installing built host packages. Defaults to setup.py "
                "default. Set to 'skip' to skip installation. Installation is "
                "needed if you want to build other packages that depend on this one."
            ),
        )
        parser.add_argument(
            "--replace-libs",
            type=str,
            nargs="?",
            default="",
            help="Libraries to replace in final link",
            action=EnvironmentRewritingArgument,
        )
    return parser


def main(args):
    basename = Path(sys.argv[0]).name
    if basename in symlinks:
        collect_args(basename)
    else:
        build_wrap(args)


if __name__ == "__main__":
    basename = Path(sys.argv[0]).name
    if basename in symlinks:
        main(None)
    else:
        parser = make_parser(argparse.ArgumentParser())
        args = parser.parse_args()
        main(args)
