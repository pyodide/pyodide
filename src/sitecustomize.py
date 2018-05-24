"""
Pyodide-specific startup code that's always run at Python startup.
"""

# We weren't invoked at the commandline, but set some commandline arguments as
# if we were anyway. Helps many of the CPython tests pass.
import sys
sys.argv = ['pyodide']
