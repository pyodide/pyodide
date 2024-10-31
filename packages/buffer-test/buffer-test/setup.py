from setuptools import Extension, setup

setup(
    name="buffer-test",
    version="0.1.1",
    author="Hood Chatham",
    author_email="roberthoodchatham@gmail.com",
    description="Test Python buffers",
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    ext_modules=[Extension("buffer_test", ["buffer-test.c"])],
)
