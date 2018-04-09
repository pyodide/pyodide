import lazy_import

print("Setting up lazy importing...")

lazy_import.lazy_module("numpy.linalg")
lazy_import.lazy_module("numpy.fft")
lazy_import.lazy_module("numpy.polynomial")
lazy_import.lazy_module("numpy.random")
lazy_import.lazy_module("numpy.ctypeslib")

import sys
sys.argv = ['pyodide']
