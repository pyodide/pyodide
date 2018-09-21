from setuptools import setup
import sys
from pyodide_build import __version__

if 'install' in sys.argv or 'bdist_wheel' in sys.argv:
    print("Error: pyodode_build is currently not fully standalone, "
          "and can only be installed in development mode. Use:\n"
          "        pip install -e . \n"
          "to install it.")
    sys.exit(1)


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
      packages=['pyodide_build'])
