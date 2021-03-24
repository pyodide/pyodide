(building_from_sources)=
# Building from sources

Building is easiest on Linux and relatively straightforward on Mac. For Windows,
we currently recommend using the Docker image (described below) to build
Pyodide. Another option for building on Windows is to use
[WSL2](https://docs.microsoft.com/en-us/windows/wsl/install-win10) to create a
Linux build environment.

## Build using `make`

Make sure the prerequisites for
[emsdk](https://github.com/emscripten-core/emsdk) are installed. Pyodide will
build a custom, patched version of emsdk, so there is no need to build it
yourself prior.

Additional build prerequisites are:

- A working native compiler toolchain, enough to build
  [CPython](https://devguide.python.org/setup/#linux).
- A native Python 3.8 to run the build scripts.
- CMake
- PyYAML
- FreeType 2 development libraries to compile Matplotlib.
- Cython to compile SciPy
- SWIG to compile NLopt
- gfortran (GNU Fortran 95 compiler)
- [f2c](http://www.netlib.org/f2c/)
- [ccache](https://ccache.samba.org) (optional) *highly* recommended for much faster rebuilds.

On Mac, you will also need:

- [Homebrew](https://brew.sh/) for installing dependencies
- System libraries in the root directory (
  `sudo installer -pkg /Library/Developer/CommandLineTools/Packages/macOS_SDK_headers_for_macOS_10.14.pkg -target /` 
  should do it, see https://github.com/pyenv/pyenv/issues/1219#issuecomment-428305417)
- coreutils for md5sum and other essential Unix utilities (`brew install coreutils`)
- cmake (`brew install cmake`)
- Cython to compile SciPy (`brew install cython`)
- SWIG to compile NLopt (`brew install swig`)
- pkg-config (`brew install pkg-config`)
- openssl (`brew install openssl`)
- gfortran (`brew cask install gfortran`)
- f2c: Install wget (`brew install wget`), and then run the buildf2c script from
  the root directory (`sudo ./tools/buildf2c`)


After installing the build prerequisites, run from the command line:

```bash
make
```

## Using Docker

We provide a Debian-based Docker image on Docker Hub with the dependencies
already installed to make it easier to build Pyodide. On top of that we provide
a pre-built image which can be used for fast custom and partial builds of
pyodide. Note that building from the non pre-built the Docker image is *very*
slow on Mac, building on the host machine is preferred if at all possible.

1. Install Docker

2. From a git checkout of Pyodide, run `./run_docker` or `./run_docker --pre-built`

3. Run `make` to build.

Note: You can control the resources allocated to the build by setting the env
vars `EMSDK_NUM_CORE`, `EMCC_CORES` and `PYODIDE_JOBS` (the default for each is
4).


If running ``make`` deterministically stops at one point in each subsequent try,
increasing the maximum RAM usage available to the docker container might help
[This is different from the physical RAM capacity inside the system]. Ideally,
at least 3 GB of RAM should be available to the docker container to build
Pyodide smoothly. These settings can be changed via Docker Preferences (See
[here](https://stackoverflow.com/questions/44533319/how-to-assign-more-memory-to-docker-container)).

You can edit the files in your source checkout on your host machine, and then
repeatedly run `make` inside the Docker environment to test your changes.

(partial-builds)=
## Partial builds

To build a subset of available packages in Pyodide, set the environment variable
`PYODIDE_PACKAGES` to a comma separated list of packages. For instance,

```
PYODIDE_PACKAGES="toolz,attrs" make
```

Dependencies of the listed packages will be built automatically as well. The
package names must match the folder names in `packages/` exactly; in particular
they are case sensitive.

To build a minimal version of Pyodide, set `PYODIDE_PACKAGES="micropip"`. The
packages micropip and distutils are always automatically included (but an empty
`PYODIDE_PACKAGES` is interpreted as unset). As a shorthand for this, one can
say `make minimal`.

## Environment variables

Following environment variables additionally impact the build,
 - `PYODIDE_JOBS`: the `-j` option passed to the `emmake make` command when
   applicable for parallel compilation. Default: 3.
 - `PYODIDE_BASE_URL`: Base URL where Pyodide packages are deployed. It must end
   with a trailing `/`. Default: `./` to load Pyodide packages from the same
   base URL path as where `pyodide.js` is located.  Example:
   `https://cdn.jsdelivr.net/pyodide/dev/full/`
 - `EXTRA_CFLAGS` : Add extra compilation flags.
 - `EXTRA_LDFLAGS` : Add extra linker flags.

Setting `EXTRA_CFLAGS="-D DEBUG_F"` provides detailed diagnostic information
whenever error branches are taken inside of the Pyodide core code. These error
messages are frequently helpful even when the problem is a fatal configuration
problem and Pyodide cannot even be initialized. These error branches occur also
in correctly working code, but they are relatively uncommon so in practice the
amount of noise generated isn't too large. The shorthand `make debug`
automatically sets this flag.

In certain cases, setting `EXTRA_LDFLAGS="-s ASSERTIONS=1` or `ASSERTIONS=2` can
also be helpful, but this slows down the linking and the runtime speed of
Pyodide a lot and generates a large amount of noise in the console.
