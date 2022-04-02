(building_from_sources)=

# Building from sources

```{warning}
If you are building the latest development version of Pyodide from the `main`
branch, please make sure to follow the build instructions from the dev
version of the documentation at
[pyodide.org/en/latest/](https://pyodide.org/en/latest/development/building-from-sources.html)
```

Building on any operating system is easiest using the Pyodide Docker image. This approach works
with any native operating system as long as Docker is installed. You can also build on your
native Linux OS if the correct build prerequisites are installed. Building on MacOS is
possible, but there are known issues as of version 0.18 that you will need to work around.
It is not possible to build on Windows, but you can use
[WSL2](https://docs.microsoft.com/en-us/windows/wsl/install-win10) to create a
Linux build environment.

## Build instructions

### Using Docker

We provide a Debian-based Docker image
([`pyodide/pyodide-env`](https://hub.docker.com/r/pyodide/pyodide-env)) on
Docker Hub with the dependencies already installed to make it easier to build
Pyodide. On top of that we provide
a pre-built image
([`pyodide/pyodide`](https://hub.docker.com/r/pyodide/pyodide)) which can be
used for fast custom and partial builds. Note that building from the non
pre-built Docker image is _very_ slow on Mac, building on the host machine
is preferred if at all possible.

```{note}
These Docker images are also available from the Github packages at
[`github.com/orgs/pyodide/packages`](https://github.com/orgs/pyodide/packages).
```

1. Install Docker

1. From a git checkout of Pyodide, run `./run_docker` or `./run_docker --pre-built`

1. Run `make` to build.

```{note}
You can control the resources allocated to the build by setting the env
vars `EMSDK_NUM_CORE`, `EMCC_CORES` and `PYODIDE_JOBS` (the default for each is
4).
```

If running `make` deterministically stops at some point,
increasing the maximum RAM usage available to the docker container might help.
(The RAM available to the container is different from the physical RAM capacity of the machine.)
Ideally,
at least 3 GB of RAM should be available to the docker container to build
Pyodide smoothly. These settings can be changed via Docker preferences (see
[here](https://stackoverflow.com/questions/44533319/how-to-assign-more-memory-to-docker-container)).

You can edit the files in the shared `pyodide` source folder on your host
machine (outside of Docker), and then repeatedly run `make` inside the Docker
environment to test your changes.

## Using `make`

Make sure the prerequisites for
[emsdk](https://github.com/emscripten-core/emsdk) are installed. Pyodide will
build a custom, patched version of emsdk, so there is no need to build it
yourself prior.

You need Python 3.10.2 to run the build scripts. To make sure that the correct
Python is used during the build it is recommended to use a [virtual
environment](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/#creating-a-virtual-environment),

```{tabbed} Linux

Additional build prerequisites are:

- A working native compiler toolchain, enough to build
  [CPython](https://devguide.python.org/setup/#linux).
- CMake
- FreeType 2 development libraries to compile Matplotlib.
- gfortran (GNU Fortran 95 compiler)
- [f2c](http://www.netlib.org/f2c/)
- [ccache](https://ccache.samba.org) (optional) _highly_ recommended for much faster rebuilds.
- (optional) SWIG to compile NLopt

```

```{tabbed} MacOS

To build on MacOS, you need:

- [Homebrew](https://brew.sh/) for installing dependencies
- System libraries in the root directory (
  `sudo installer -pkg /Library/Developer/CommandLineTools/Packages/macOS_SDK_headers_for_macOS_10.14.pkg -target /`
  should do it, see https://github.com/pyenv/pyenv/issues/1219#issuecomment-428305417)
- coreutils for md5sum and other essential Unix utilities (`brew install coreutils`).
- cmake (`brew install cmake`)
- pkg-config (`brew install pkg-config`)
- openssl (`brew install openssl`)
- gfortran (`brew cask install gfortran`)
- f2c: Install wget (`brew install wget`), and then run the buildf2c script from
  the root directory (`sudo ./tools/buildf2c`)
- It is also recommended installing the GNU patch (`brew install gpatch`), and
  GNU sed (`brew install gnu-sed`) and [re-defining them temporarily as `patch` and
  `sed`](https://formulae.brew.sh/formula/gnu-sed).
- (optional) SWIG to compile NLopt (`brew install swig`)

```

```{note}
If you encounter issues with the requirements, it is useful to check the exact
list in the
[Dockerfile](https://github.com/pyodide/pyodide/blob/main/Dockerfile) which is
tested in the CI.
```

You can install the Python dependencies from the requirement file at the root of Pyodide folder:
`pip install -r requirements.txt`

After installing the build prerequisites, run from the command line:

```bash
make
```

(partial-builds)=

## Partial builds

To build a subset of available packages in Pyodide, set the environment variable
`PYODIDE_PACKAGES` to a comma separated list of packages. For instance,

```
PYODIDE_PACKAGES="toolz,attrs" make
```

Dependencies of the listed packages will be built automatically as well. The
package names must match the folder names in `packages/` exactly; in particular
they are case-sensitive.

If `PYODIDE_PACKAGES` is not set, a minimal set of packages necessairy to run
the core test suite is installed, including "micropip", "pyparsing", "pytz",
"packaging", "Jinja2", "regex". This is equivalent to setting
`PYODIDE_PACKAGES='core'`
meta-package. Other supported meta-packages are,

- "min-scipy-stack": includes the "core" meta-package as well as some
  core packages from the scientific python stack and their dependencies:
  "numpy", "scipy", "pandas", "matplotlib", "scikit-learn", "joblib",
  "pytest". This option is non exaustive and is mainly intended to make build
  faster while testing a diverse set of scientific packages.
- "\*" builds all packages

micropip and distutils are always automatically included.

## Environment variables

The following environment variables additionally impact the build:

- `PYODIDE_JOBS`: the `-j` option passed to the `emmake make` command when
  applicable for parallel compilation. Default: 3.
- `PYODIDE_BASE_URL`: Base URL where Pyodide packages are deployed. It must end
  with a trailing `/`. Default: `./` to load Pyodide packages from the same
  base URL path as where `pyodide.js` is located. Example:
  `https://cdn.jsdelivr.net/pyodide/v0.19.0/full/`
- `EXTRA_CFLAGS` : Add extra compilation flags.
- `EXTRA_LDFLAGS` : Add extra linker flags.

Setting `EXTRA_CFLAGS="-D DEBUG_F"` provides detailed diagnostic information
whenever error branches are taken inside the Pyodide core code. These error
messages are frequently helpful even when the problem is a fatal configuration
problem and Pyodide cannot even be initialized. These error branches occur also
in correctly working code, but they are relatively uncommon so in practice the
amount of noise generated isn't too large. The shorthand `make debug`
automatically sets this flag.

In certain cases, setting `EXTRA_LDFLAGS="-s ASSERTIONS=1` or `ASSERTIONS=2` can
also be helpful, but this slows down the linking and the runtime speed of
Pyodide a lot and generates a large amount of noise in the console.
