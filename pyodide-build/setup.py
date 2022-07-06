# Needed for editable install
import setuptools

if __name__ == "__main__":
    setuptools.setup(
        entry_points={
            "console_scripts": [
                "pywasm = pyodide_build.out_of_tree.__main__:main",
                "_pywasmcross = pyodide_build.pywasmcross:compiler_main",
            ]
        }
    )
