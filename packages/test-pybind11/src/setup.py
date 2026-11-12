from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

setup(
    ext_modules=[
        Pybind11Extension(
            "pybind11_test", ["pybind11_test.cpp"], extra_compile_args=["-std=c++17"]
        )
    ],
    cmdclass={"build_ext": build_ext},
)
