import sys

IN_BROWSER = False
if "pyodide" in sys.modules:
    from pyodide import IN_BROWSER

if not IN_BROWSER:
    raise Exception("This shouldn't happen!")

# Prevent microprocessing.synchronize from raising an error at import time.
def SemLock(*args, **kwargs):
    raise OSError("Not implemented")

SemLock.SEM_VALUE_MAX = 0

def sem_unlink(*args, **kwargs):
    raise OSError("Not implemented")
