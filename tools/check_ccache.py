import re
import subprocess
import sys


def main():
    result = subprocess.run(
        ["emcc", "--version"], capture_output=True, encoding="utf8", check=False
    )
    if result.returncode == 0:
        return 0
    if re.search("GLIBC.*not found.*ccache", result.stderr):
        print(
            "Emscripten ccache was linked against an incompatible version of glibc.\n"
            "Run `make -C emsdk clean` and try again.\n"
            "If this error persists, please open an issue to ask for help."
        )
    else:
        print("Something is wrong but I'm not sure what.")
        print("Info:")
        print(result)
    return 1


if __name__ == "__main__":
    sys.exit(main())
