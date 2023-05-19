# Needed for editable install
import os

from setuptools import setup


def find_stubs(package):
    stubs = []
    for root, _dirs, files in os.walk(package):
        for file in files:
            path = os.path.join(root, file).replace(package + os.sep, "", 1)
            stubs.append(path)
    return {package: stubs}


setup(
    package_data=find_stubs("js-stubs"),
)
