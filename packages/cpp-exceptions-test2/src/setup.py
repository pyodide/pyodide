from setuptools import Extension, setup

setup(
    name="cpp-exceptions-test2",
    version="1.0",
    ext_modules=[
        Extension(
            name="cpp_exceptions_test2",  # as it would be imported
            # may include packages/namespaces separated by `.`
            language="c++",
            sources=[
                "cpp_exceptions_test2.cpp"
            ],  # all sources are compiled into a single binary file
        ),
    ],
)
