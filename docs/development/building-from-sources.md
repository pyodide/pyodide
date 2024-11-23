(building_from_sources)=

# Building from sources

```{warning}
If you are building the latest development version of Pyodide from the `main`
branch, please make sure to follow the build instructions from the dev
version of the documentation at
[pyodide.org/en/latest/](https://pyodide.org/en/latest/development/building-from-sources.html)
```

Pyodide can be built from sources on different platforms,

- on **Linux** it is easiest using the Pyodide Docker image. This approach
  works with any native operating system as long as Docker is installed. You
  can also build on your native Linux OS if the correct build prerequisites
  are installed.
- on **MacOS** it is recommended to install dependencies via conda-forge or
  using Homebrew, particularly with the M1 ARM CPU. Building with Docker is
  possible but very slow.
- It is not possible to build on **Windows**, but you can use [Windows Subsystem
  for Linux](https://docs.microsoft.com/en-us/windows/wsl/install-win10) to
  create a Linux build environment.

## Build instructions

The Pyodide repository has a git submodule called `pyodide-build`. Make sure to
do a recursive clone:
```bash
git clone --recursive https://github.com/pyodide/pyodide
```
or if you have already cloned the Pyodide repository without the `--recursive`
flag, you may initialize the submodule with:
```bash
git submodule update --init
```
If you change git branches, make sure you update `pyodide-build` with
`git submodule update`.

### Using Docker

We provide a Debian-based x86_64 Docker image
([`pyodide/pyodide-env`](https://hub.docker.com/r/pyodide/pyodide-env)) on
Docker Hub with the dependencies already installed to make it easier to build
Pyodide.

```{note}
These Docker images are also available from the Github packages at
[`github.com/orgs/pyodide/packages`](https://github.com/orgs/pyodide/packages).
```

1. Install Docker

2. From a git checkout of Pyodide, run `./run_docker`

3. Run `make` to build.

```{note}
If `make` is failing with `Permission denied`, you can run `./run_docker` with root permissions: `./run_docker --root`
```

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

### Using the "Docker" dev container

We provide a dev container configuration that is equivalent to the use of
`./run_docker` script. It can be used in [Visual Studio Code](https://code.visualstudio.com/docs/devcontainers/containers) and
on [GitHub Codespaces](https://docs.github.com/en/codespaces/overview).
When prompted, select "Docker".

### Using the "Conda" dev container

We provide another dev container configuration that corresponds to
the "Linux with conda" method described below. When [Visual Studio Code](https://code.visualstudio.com/docs/devcontainers/containers) or
[GitHub Codespaces](https://docs.github.com/en/codespaces/overview)
prompts for the dev container configuration, select "Conda".

## Using `make`

Make sure the prerequisites for
[emsdk](https://github.com/emscripten-core/emsdk) are installed. Pyodide will
build a custom, patched version of emsdk, so there is no need to build it
yourself prior.

You need Python 3.11.2 to run the build scripts. To make sure that the correct
Python is used during the build it is recommended to use a [virtual
environment](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/#creating-a-virtual-environment)
or a conda environment.

````{tab-set}

```{tab-item} Linux

To build on Linux, you need:

- A working native compiler toolchain, enough to build
  [CPython](https://devguide.python.org/getting-started/setup-building/index.html#linux).
- CMake (required to install Emscripten)

```

```{tab-item} Linux with conda


You would need a working native compiler toolchain, enough to build
  [CPython](https://devguide.python.org/getting-started/setup-building/index.html#linux), for example,
- `apt install build-essential` on Debian based systems.
- Conda which can be installed from [MiniForge](https://github.com/conda-forge/miniforge)

Then install the required Python version and other build dependencies in a separate conda environment,

    conda env create -f environment.yml
    conda activate pyodide-env

```
```{tab-item} MacOS with conda

You would need,
- System libraries in the root directory:
  `xcode-select --install`
- Conda which can be installed using [Miniforge](https://github.com/conda-forge/miniforge) (both for Intel and M1 CPU)


Then install the required Python version and other build dependencies in a separate conda environment,

    conda env create -f environment.yml
    conda activate pyodide-env

```

```{tab-item} MacOS with Homebrew

To build on MacOS with Homebrew, you need:

- System command line tools
  `xcode-select --install`
- [Homebrew](https://brew.sh/) for installing dependencies
- `brew install coreutils cmake autoconf automake libtool libffi ccache`
- It is also recommended installing the GNU patch and
  GNU sed (`brew install gpatch gnu-sed`)
  and [re-defining them temporarily as `patch` and
  `sed`](https://formulae.brew.sh/formula/gnu-sed).
```
````

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

If `PYODIDE_PACKAGES` is not set, a minimal set of packages necessary to run
the core test suite is installed, including "micropip", "pyparsing", "pytz",
"packaging", "Jinja2", "regex". This is equivalent to setting
`PYODIDE_PACKAGES='tag:core'`
meta-package. Other supported meta-packages are,

- "tag:min-scipy-stack": includes the "core" meta-package as well as some
  core packages from the scientific python stack and their dependencies:
  "numpy", "scipy", "pandas", "matplotlib", "scikit-learn", "joblib",
  "pytest". This option is non exhaustive and is mainly intended to make build
  faster while testing a diverse set of scientific packages.
- "\*" builds all packages
- You can exclude a package by prefixing it with "!".

micropip is always automatically included.

## Environment variables

The following environment variables additionally impact the build:

- `PYODIDE_JOBS`: the `-j` option passed to the `emmake make` command when
  applicable for parallel compilation. Default: 3.
- `PYODIDE_BASE_URL`: Base URL where Pyodide packages are deployed. It must end
  with a trailing `/`. Default: `./` to load Pyodide packages from the same
  base URL path as where `pyodide.js` is located. Example:
  `{{PYODIDE_CDN_URL}}`
- `EXTRA_CFLAGS`: Add extra compilation flags.
- `EXTRA_LDFLAGS`: Add extra linker flags.

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
