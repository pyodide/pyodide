# Building from sources

Building is easiest on Linux and relatively straightforward on Mac. For
Windows, we currently recommend using the Docker image (described below) to
build Pyodide.

## Build using `make`

Make sure the prerequisites for [emsdk](https://github.com/emscripten-core/emsdk) are
installed. Pyodide will build a custom, patched version of emsdk, so there is no
need to build it yourself prior.

Additional build prerequisites are:

- A working native compiler toolchain, enough to build CPython.
- A native Python 3.7 to run the build scripts.
- PyYAML
- [lessc](http://lesscss.org/) to compile less to css.
- [uglifyjs](https://github.com/mishoo/UglifyJS) to minify Javascript builds.
- gfortran (GNU Fortran 95 compiler)
- [f2c](http://www.netlib.org/f2c/)
- [ccache](https://ccache.samba.org) (optional) *highly* recommended for much faster rebuilds.

On Mac, you will also need:

- [Homebrew](https://brew.sh/) for installing dependencies
- System libraries in the root directory (`sudo installer -pkg /Library/Developer/CommandLineTools/Packages/macOS_SDK_headers_for_macOS_10.14.pkg -target /` should do it, see https://github.com/pyenv/pyenv/issues/1219#issuecomment-428305417)
- coreutils for md5sum and other essential Unix utilities (`brew install coreutils`)
- cmake (`brew install cmake`)
- pkg-config (`brew install pkg-config`)
- openssl (`brew install openssl`)
- gfortran (`brew cask install gfortran`)
- f2c: Install wget (`brew install wget`), and then run the buildf2c script from the root directory (`sudo ./tools/buildf2c`)


After installing the build prerequisites, run from the command line:

```bash
make
```

## Using Docker

We provide a Debian-based Docker image on Docker Hub with the dependencies
already installed to make it easier to build Pyodide. Note that building from
the Docker image is *very* slow on Mac, building on the host machine is
preferred if at all possible.

1. Install Docker

2. From a git checkout of Pyodide, run `./run_docker`

3. Run `make` to build.

If running ``make`` deterministically stops at one point in each subsequent try, increasing
the maximum RAM usage available to the docker container might help [This is different
from the physical RAM capacity inside the system]. Ideally, at least 3 GB of RAM
should be available to the docker container to build `pyodide` smoothly. These settings can
be changed via Docker Preferences [See [here](https://stackoverflow.com/questions/44533319/how-to-assign-more-memory-to-docker-container)].

You can edit the files in your source checkout on your host machine, and then
repeatedly run `make` inside the Docker environment to test your changes.

## Partial builds

To build a subset of available packages in pyodide, set the environment
variable `PYODIDE_PACKAGES` to a comma separated list of packages. For
instance,

```
PYODIDE_PACKAGES="toolz,attrs" make
```

Note that this environment variable must contain both the packages and their
dependencies. The package names must match the folder names in `packages/`
exactly; in particular they are case sensitive.

To build a minimal version of pyodide, set `PYODIDE_PACKAGES="micropip"`. The
micropip and package is generally always included for any non empty value of
`PYODIDE_PACKAGES`.

If scipy is included in `PYODIDE_PACKAGES`, BLAS/LAPACK must be manually built
first with `make -c CLAPACK`.
