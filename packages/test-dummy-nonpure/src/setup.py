from setuptools import Extension, setup

setup(
    name="test-dummy-nonpure",
    version="1.0.0",
    author="Pyodide",
    author_email="pyodide@gmail.com",
    description="Just a dummy package with c-extension for testing Pyodide package loading logics",
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
    ],
    ext_modules=[Extension("dummy_nonpure", ["dummy_nonpure.c"])],
)
