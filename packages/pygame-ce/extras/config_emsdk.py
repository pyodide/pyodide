"""Config on Emscripten SDK is almost like Unix"""

import logging
import os
import sys
from glob import glob

from distutils.sysconfig import get_python_inc

configcommand = os.environ.get(
    "SDL_CONFIG",
    "sdl2-config",
)
configcommand = configcommand + " --version --cflags --libs"
localbase = os.environ.get("LOCALBASE", "")
if os.environ.get("PYGAME_EXTRA_BASE"):
    extrabases = os.environ["PYGAME_EXTRA_BASE"].split(":")
else:
    extrabases = []

EMSDK = os.environ.get("EMSDK", None)
is_wasm = EMSDK is not None
if not is_wasm:
    print("EMSDK not found")
    raise SystemExit(1)

# EMCC_CFLAGS="-s USE_SDL=2 is required to prevent '-iwithsysroot/include/SDL'
# which is SDL1 from ./emscripten/tools/ports/__init__.py
# but CI is not expected to have that problem and that would trigger useless
# rebuild

EMCC_CFLAGS = os.environ.get("EMCC_CFLAGS", "")

# user build, make sure ports are pulled in.
if os.environ.get("SDK_VERSION", None) is None:
    # EMCC_CFLAGS += " -sUSE_SDL=2"
    pass
else:
    # make sure CI only pick SDK components.
    SDKROOT = os.environ.get("SDKROOT", "/opt/python-wasm-sdk")
    emcc_cflags = [
        # only static build is supported at the moment
        "-DBUILD_STATIC",
        # for SDL2_image
        f"-I{SDKROOT}/devices/emsdk/usr/include/SDL2",
        # ftbuild.h
        f"-I{SDKROOT}/emsdk/upstream/emscripten/cache/sysroot/include/freetype2",
        # avoid some cython generated warnings.
        f"-Wno-unreachable-code-fallthrough {EMCC_CFLAGS}",
    ]
    EMCC_CFLAGS = " ".join(emcc_cflags)
os.environ["EMCC_CFLAGS"] = EMCC_CFLAGS.strip()


# CC = os.environ.get("CC", "emcc")
# os.environ["CC"] = CC.strip()


class DependencyProg:
    def __init__(
        self, name, envname, exename, minver, defaultlibs, version_flag="--version"
    ):
        self.name = name
        command = os.environ.get(envname, exename)
        self.lib_dir = ""
        self.inc_dir = ""
        self.libs = []
        self.cflags = ""
        try:
            # freetype-config for freetype2 version 2.3.7 on Debian lenny
            # does not recognize multiple command line options. So execute
            # 'command' separately for each option.
            config = (
                os.popen(command + " " + version_flag).readlines()
                + os.popen(command + " --cflags").readlines()
                + os.popen(command + " --libs").readlines()
            )
            flags = " ".join(config[1:]).split()

            # remove this GNU_SOURCE if there... since python has it already,
            #   it causes a warning.
            if "-D_GNU_SOURCE=1" in flags:
                flags.remove("-D_GNU_SOURCE=1")
            self.ver = config[0].strip()
            if minver and self.ver < minver:
                err = (
                    f"WARNING: requires {self.name} version {self.ver} ({minver} found)"
                )
                raise ValueError(err)
            self.found = 1
            self.cflags = ""
            for f in flags:
                if f[:2] in ("-l", "-D", "-I", "-L"):
                    self.cflags += f + " "
                elif f[:3] == "-Wl":
                    self.cflags += "-Xlinker " + f + " "

            # if self.name == "SDL":
            #     inc = f"-I{EMSDK}/upstream/emscripten/cache/sysroot/include/SDL2 "
            #     inc += f"-I{EMSDK}/upstream/emscripten/cache/sysroot/include/freetype2/freetype "
            #     self.cflags = inc + " " + self.cflags

            # if self.name == "FREETYPE":
            #     inc = f"-I{EMSDK}/upstream/emscripten/cache/sysroot/include/freetype2/freetype "
            #     self.cflags = inc + " " + self.cflags

        except (ValueError, TypeError):
            print(f'WARNING: "{command}" failed!')
            self.found = 0
            self.ver = "0"
            self.libs = defaultlibs

    def configure(self, incdirs, libdir):
        if self.found:
            print(self.name + "        "[len(self.name) :] + ": found " + self.ver)
            self.found = 1
        else:
            print(self.name + "        "[len(self.name) :] + ": not found")


class Dependency:
    def __init__(self, name, checkhead, checklib, libs):
        self.name = name
        self.inc_dir = None
        self.lib_dir = None
        self.libs = libs
        self.found = 0
        self.checklib = checklib
        self.checkhead = checkhead
        self.cflags = ""

    def configure(self, incdirs, libdirs):
        incname = self.checkhead
        libnames = self.checklib, self.name.lower()

        if incname:
            for dir in incdirs:
                path = os.path.join(dir, incname)
                if os.path.isfile(path):
                    self.inc_dir = dir

        for dir in libdirs:
            for name in libnames:
                path = os.path.join(dir, name)
                if any(map(os.path.isfile, glob(path + "*"))):
                    self.lib_dir = dir

        if (incname and self.lib_dir and self.inc_dir) or (
            not incname and self.lib_dir
        ):
            print(self.name + "        "[len(self.name) :] + ": found")
            self.found = 1
        else:

            if self.name in ["FONT", "IMAGE", "MIXER", "FREETYPE"]:
                self.found = 1
                print(
                    self.name
                    + "        "[len(self.name) :]
                    + ": FORCED (via emsdk builtins)"
                )
                return
            print(self.name + "        "[len(self.name) :] + ": not found")
            print(self.name, self.checkhead, self.checklib, incdirs, libdirs)


class DependencyPython:
    def __init__(self, name, module, header):
        self.name = name
        self.lib_dir = ""
        self.inc_dir = ""
        self.libs = []
        self.cflags = ""
        self.found = 0
        self.ver = "0"
        self.module = module
        self.header = header

    def configure(self, incdirs, libdirs):
        self.found = 1
        if self.module:
            try:
                self.ver = __import__(self.module).__version__
            except ImportError:
                self.found = 0
        if self.found and self.header:
            fullpath = os.path.join(get_python_inc(0), self.header)
            if not os.path.isfile(fullpath):
                self.found = 0
            else:
                self.inc_dir = os.path.split(fullpath)[0]
        if self.found:
            print(self.name + "        "[len(self.name) :] + ": found", self.ver)
        else:
            print(self.name + "        "[len(self.name) :] + ": not found")


sdl_lib_name = "SDL"


def main(auto_config=False):
    global origincdirs, origlibdirs

    # these get prefixes with $EMSDK
    origincdirs = ["/include"]
    origlibdirs = []

    print("\nHunting dependencies...")

    DEPS = [
        DependencyProg("SDL", "SDL_CONFIG", "sdl2-config", "2.0", ["sdl"]),
        Dependency("FONT", "SDL_ttf.h", "libSDL2_ttf.so", ["SDL2_ttf"]),
        Dependency("IMAGE", "SDL_image.h", "libSDL2_image.a", ["SDL2_image"]),
        Dependency("MIXER", "SDL_mixer.h", "libSDL2_mixer.a", ["SDL2_mixer"]),
        Dependency("FREETYPE", "ft2build.h", "libfreetype.a", []),
        # Dependency('GFX', 'SDL_gfxPrimitives.h', 'libSDL2_gfx.a', ['SDL2_gfx']),
    ]
    DEPS.extend(
        [
            # Dependency('SCRAP', '', 'libX11', ['X11']),
            # Dependency('GFX', 'SDL_gfxPrimitives.h', 'libSDL_gfx.a', ['SDL_gfx']),
        ]
    )

    if not DEPS[0].found:
        raise RuntimeError(
            'Unable to run "sdl-config". Please make sure a development version of SDL is installed.'
        )

    incdirs = []
    libdirs = []

    incdirs += [os.environ.get("PREFIX", "") + d for d in origincdirs]
    libdirs += [os.environ.get("PREFIX", "") + d for d in origlibdirs]

    # incdirs += [EMSDK + "/upstream/emscripten/cache/sysroot" + d for d in origincdirs]

    for extrabase in extrabases:
        incdirs += [extrabase + d for d in origincdirs]
        libdirs += [extrabase + d for d in origlibdirs]

    if localbase:
        incdirs = [localbase + d for d in origincdirs]
        libdirs = [localbase + d for d in origlibdirs]

    for arg in DEPS[0].cflags.split():
        if arg[:2] == "-I":
            incdirs.append(arg[2:])
        elif arg[:2] == "-L":
            libdirs.append(arg[2:])
    for d in DEPS:
        d.configure(incdirs, libdirs)

    for d in DEPS[1:]:
        if not d.found:
            if "-auto" not in sys.argv:
                logging.warning(
                    "Some pygame dependencies were not found. "
                    "Pygame can still compile and install, but games that "
                    "depend on those missing dependencies will not run. "
                    "Use -auto to continue building without all dependencies. "
                )
                raise SystemExit("Missing dependencies")
            break
    return DEPS


if __name__ == "__main__":
    print("This is the configuration subscript for Emscripten.")
    print('Please run "config.py" for full configuration.')

