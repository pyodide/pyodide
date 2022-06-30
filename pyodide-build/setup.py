# Needed for editable install
import setuptools

if __name__ == "__main__":
    setuptools.setup(
        entry_points={
            "console_scripts": [
                "pywasmbuild = pyodide_build.out_of_tree_main:out_of_tree_main",
                "_pywasmcross = pyodide_build.pywasmcross:entry",
            ]
        }
    )
