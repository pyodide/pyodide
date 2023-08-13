from setuptools import Extension, setup

setup(
    ext_modules=[
        Extension(
            name="emscripten_loop_test",
            sources=["emscripten-loop-test.cpp"],
        ),
    ]
)
