from setuptools import setup, Extension

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
    ext_modules=[Extension("fpcast_test", ["fpcast-test.c"])]
    # python_requires='>=3.6',
)
