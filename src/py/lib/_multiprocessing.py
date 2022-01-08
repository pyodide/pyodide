import sys

IN_BROWSER = False
if "pyodide" in sys.modules:
    from pyodide import IN_BROWSER

if not IN_BROWSER:
    raise Exception("This shouldn't happen!")

# Prevent microprocessing.synchronize from raising an error at import time.
SemLock = None
sem_unlink = None
