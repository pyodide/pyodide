from setuptools import setup, find_packages
from pyodide_build import __version__

with open('README.md', 'rt') as fh:
    LONG_DESCRIPTION = fh.read()

setup(name='pyodide_build',
      version=__version__,
      description='pyodide builder',
      entry_points={
        'console_scripts': [
            'pyodide = pyodide_build.__main__:main'
        ]},
      url="https://github.com/iodide-project/pyodide",
      license='MPL',
      packages=find_packages())
