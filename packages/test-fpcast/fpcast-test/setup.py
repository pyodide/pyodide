from sysconfig import get_config_var

from setuptools import Extension, setup

if get_config_var("SIZEOF_VOID_P") != 4:
    # pyodide_build.pypabuild will run this three times, the first time it fails
    # and the exception is caught but the second and third times it must
    # succeed.
    raise Exception(
        """
This should appear in the log exactly one time. If it appears more than once,
the Pyodide build system has misconfigured sysconfigdata (and also the build
will fail).
"""
    )

setup(
    name="fpcast-test",
    version="0.1.1",
    author="Hood Chatham",
    author_email="roberthoodchatham@gmail.com",
    description="Test function pointer casts.",
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    # packages=["fpcast_test"],
    ext_modules=[Extension("fpcast_test", ["fpcast-test.c"])],
    # python_requires='>=3.6',
)
