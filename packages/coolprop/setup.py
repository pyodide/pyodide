import os
import sys

wrappers_python_path = os.path.join(os.path.dirname(__file__), "wrappers", "Python")
sys.path.append(wrappers_python_path)
os.chdir(wrappers_python_path)
SETUP_PATH = "setup.py"
with open(SETUP_PATH) as f:
    globals = {
        "__file__": SETUP_PATH,
        "__name__": "__main__",
        "sys": sys,
        "argv": sys.argv,
    }
    code = compile(f.read(), SETUP_PATH, "exec")
    exec(code, globals, None)
