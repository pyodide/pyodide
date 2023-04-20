#!/usr/bin/env python
import os
import re
from pathlib import Path
from subprocess import check_call

from numpy import get_include
from setuptools import Extension, setup
from setuptools.command.build_py import build_py


def create_pkg_directory():
    with open("CMakeLists.txt") as f:
        content = f.read()
        version = []
        for s in ("MAJOR", "MINOR", "BUGFIX"):
            m = re.search(f"NLOPT_{s}_VERSION *['\"](.+)['\"]", content)
            version.append(m.group(1))
        version = ".".join(version)

    pkg_folder = Path("nlopt")
    pkg_folder.mkdir(exist_ok=True)
    with (pkg_folder / "__init__.py").open("w") as f:
        f.write(
            f"""
from .nlopt import *

__version__ = '{version}'
    """.strip()
            + "\n"
        )

    return version


def configure_with_cmake():
    # There are 2 header files that are created by cmake (nlopt_config.h
    # and nlopt.hpp)
    # cmake is used to configure only, actual compile will be handled
    # by setuptools build_ext
    cmd = [
        "emcmake",
        "cmake",
        "-LAH",
        "-DNLOPT_GUILE=OFF",
        "-DNLOPT_MATLAB=OFF",
        "-DNLOPT_OCTAVE=OFF",
        ".",
    ]

    check_call(cmd, env=os.environ)

    # Need to generate nlopt.hpp
    cmd = [
        "emcmake",
        "cmake",
        "-DAPI_SOURCE_DIR=./src/api",
        "-P",
        "./cmake/generate-cpp.cmake",
    ]

    check_call(cmd, env=os.environ)


version = create_pkg_directory()


class build_py_after_build_ext(build_py):
    def run(self):
        configure_with_cmake()
        self.run_command("build_ext")
        return super().run()


setup(
    name="nlopt",
    version=version,
    packages=["nlopt"],
    install_requires=["numpy >=1.14"],
    ext_modules=[
        Extension(
            "nlopt._nlopt",
            [
                "src/algs/direct/DIRect.c",
                "src/algs/direct/direct_wrap.c",
                "src/algs/direct/DIRserial.c",
                "src/algs/direct/DIRsubrout.c",
                "src/algs/cdirect/cdirect.c",
                "src/algs/cdirect/hybrid.c",
                "src/algs/praxis/praxis.c",
                "src/algs/luksan/plis.c",
                "src/algs/luksan/plip.c",
                "src/algs/luksan/pnet.c",
                "src/algs/luksan/mssubs.c",
                "src/algs/luksan/pssubs.c",
                "src/algs/crs/crs.c",
                "src/algs/mlsl/mlsl.c",
                "src/algs/mma/mma.c",
                "src/algs/mma/ccsa_quadratic.c",
                "src/algs/cobyla/cobyla.c",
                "src/algs/newuoa/newuoa.c",
                "src/algs/neldermead/nldrmd.c",
                "src/algs/neldermead/sbplx.c",
                "src/algs/auglag/auglag.c",
                "src/algs/bobyqa/bobyqa.c",
                "src/algs/isres/isres.c",
                "src/algs/slsqp/slsqp.c",
                "src/algs/esch/esch.c",
                "src/api/general.c",
                "src/api/options.c",
                "src/api/optimize.c",
                "src/api/deprecated.c",
                "src/api/f77api.c",
                "src/util/mt19937ar.c",
                "src/util/sobolseq.c",
                "src/util/timer.c",
                "src/util/stop.c",
                "src/util/redblack.c",
                "src/util/qsort_r.c",
                "src/util/rescale.c",
                "src/algs/stogo/global.cc",
                "src/algs/stogo/linalg.cc",
                "src/algs/stogo/local.cc",
                "src/algs/stogo/stogo.cc",
                "src/algs/stogo/tools.cc",
                "src/algs/ags/evolvent.cc",
                "src/algs/ags/solver.cc",
                "src/algs/ags/local_optimizer.cc",
                "src/algs/ags/ags.cc",
                "src/swig/nlopt.i",
            ],
            include_dirs=[
                "./src/util",
                "./",
                "./src/api",
                "./src/algs/praxis",
                "./src/algs/direct",
                "./src/algs/stogo",
                "./src/algs/ags",
                "./src/algs/cdirect",
                "./src/algs/luksan",
                "./src/algs/crs",
                "./src/algs/mlsl",
                "./src/algs/mma",
                "./src/algs/cobyla",
                "./src/algs/newuoa",
                "./src/algs/neldermead",
                "./src/algs/auglag",
                "./src/algs/bobyqa",
                "./src/algs/isres",
                "./src/algs/esch",
                "./src/algs/slsqp",
                get_include(),
            ],
            swig_opts=["-c++", "-interface", "_nlopt", "-outdir", "./nlopt"],
        )
    ],
    zip_safe=False,
    cmdclass={"build_py": build_py_after_build_ext},
)
