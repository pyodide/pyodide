# Needed for editable install
import setuptools

if __name__ == "__main__":
    setuptools.setup(
        entry_points={
            "console_scripts": [
                "_pywasmcross = pyodide_build.pywasmcross:compiler_main",
            ]
        }
    )
