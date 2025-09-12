import sys

# Runtime environment flags
IN_BROWSER = "_pyodide_core" in sys.modules

IN_NODE = False
IN_NODE_COMMONJS = False
IN_NODE_ESM = False
IN_BUN = False
IN_DENO = False
IN_BROWSER_MAIN_THREAD = False
IN_BROWSER_WEB_WORKER = False
IN_SAFARI = False
IN_SHELL = False

__all__ = [
    "IN_BROWSER",
    "IN_NODE",
    "IN_NODE_COMMONJS",
    "IN_NODE_ESM",
    "IN_BUN",
    "IN_DENO",
    "IN_BROWSER_MAIN_THREAD",
    "IN_BROWSER_WEB_WORKER",
    "IN_SAFARI",
    "IN_SHELL",
]
