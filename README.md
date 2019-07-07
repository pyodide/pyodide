**[What is Pyodide?](#what-is-pyodide)** |
**[Try Pyodide](#try-pyodide-no-installation-needed)** |
**[Getting Started](#getting-started)** |
**[Contributing](#contributing)** |
**[License](#license)**

# [Pyodide](https://github.com/iodide-project/pyodide)


[![Build Status](https://circleci.com/gh/iodide-project/pyodide.png)](https://circleci.com/gh/iodide-project/pyodide)

The Python scientific stack, compiled to WebAssembly.

[**Try Pyodide and Iodide in your browser**](https://alpha.iodide.io/notebooks/300/)

## What is Pyodide?

**Pyodide** brings the Python runtime to the browser via WebAssembly, along with the Python scientific stack including NumPy, Pandas, Matplotlib, parts of SciPy, and NetworkX. The [`packages` directory](https://github.com/iodide-project/pyodide/tree/master/packages) lists over 35 packages which are currently available.

**Pyodide** provides transparent conversion of objects between Javascript and Python.
When used inside a browser, Python has full access to the Web APIs.

While closely related to the [iodide project](https://iodide.io), a tool for *literate scientific computing and communication for the web*, Pyodide goes beyond running in a notebook environment. To maximize the flexibility of the modern web, **Pyodide** may
be used standalone in any context where you want to **run Python inside a web
browser**.

## Try Pyodide (no installation needed)

For more information, try [the demo](https://alpha.iodide.io/notebooks/300/) and look through the
[documentation](https://pyodide.readthedocs.io/).

## Getting Started

Pyodide offers three different ways to get started depending on your needs and technical resources.
These include:

- [Download a pre-built version](#download-a-pre-built-version) (the quickest way to get started)
- [Build Pyodide from source](#building-from-source) (this method requires installing prerequistes and using `make`. Primarily for Linux users who want to experiment or contribute back to the project.)
- [Use a Docker image](#using-docker) (recommended for Windows and macOS users and for Linux users who prefer a Debian-based Docker image on Docker Hub with the dependencies
already installed)


### Download a pre-built version

Pre-built versions of Pyodide may be downloaded from
this repository's [releases page](https://github.com/iodide-project/pyodide/releases/).


### Building from source

Building is easiest on Linux. For other platforms, we recommend using
the Docker image (described below) to build Pyodide.

Make sure the prerequisites for [emsdk](https://github.com/emscripten-core/emsdk) are
installed. Pyodide will build a custom, patched version of emsdk, so there is no
need to build it yourself prior.

Additional build prerequisites are:

- A working native compiler toolchain, enough to build CPython.
- A native Python 3.7 to run the build scripts.
- PyYAML
- [lessc](http://lesscss.org/) to compile less to css.
- [uglifyjs](https://github.com/mishoo/UglifyJS) to minify Javascript builds.
- [ccache](https://ccache.samba.org) (optional) recommended for much faster rebuilds.

#### Build using `make`

After installing the build prerequisites, run from the command line:

```bash
make
```

### Using Docker

We provide a Debian-based Docker image on Docker Hub with the dependencies
already installed to make it easier to build Pyodide.

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

## Contributing

Please view the [CONTRIBUTING](CONTRIBUTING.md) document for tips on filing
issues, making changes, and submitting pull requests. The following sections
describe how to run tests, run Pyodide benchmarks, and lint the source code.


### Testing

Install the following dependencies into the default Python installation:

```bash
pip install pytest selenium pytest-instafail
```

Install [geckodriver](https://github.com/mozilla/geckodriver/releases) and
[chromedriver](https://sites.google.com/a/chromium.org/chromedriver/downloads)
and check that they are in your `PATH`.

### Automated testing

To run the pytest suite of tests, type on the command line:

```bash
pytest test/ packages/
```

### Manual interactive testing

To run manual interactive tests, a docker environment and a webserver will be
used.

1. Bind port 8000 for testing. To automatically bind port 8000 of the docker
environment and the host system, run: `./run_docker`

2. Now, this can be used to test the `pyodide` builds running within the
docker environment using external browser programs on the host system. To do
this, run: `./bin/pyodide serve`

3. This serves the ``build`` directory of the ``pyodide`` project on port 8000.
    * To serve a different directory, use the ``--build_dir`` argument followed
      by the path of the directory.
    * To serve on a different port, use the ``--port`` argument followed by the
      desired port number. Make sure that the port passed in ``--port`` argument
      is same as the one defined as ``DOCKER_PORT`` in the ``run_docker`` script.


4. Once the webserver is running, simple interactive testing can be run by
   visiting this URL:
   [http://localhost:8000/console.html](http://localhost:8000/console.html)

### Benchmarking

To run common benchmarks to understand Pyodide's performance, begin by
installing the same prerequisites as for testing. Then run:

```bash
make benchmark
```

### Linting

Python is linted with `flake8`.  C and Javascript are linted with
`clang-format`.

To lint the code, run:

```bash
make lint
```

## License

Pyodide uses the Mozilla Public License Version 2.0. See the
[LICENSE file](LICENSE) for more details.

---

**[What is Pyodide?](#what-is-pyodide)** |
**[Try Pyodide](#try-pyodide-no-installation-needed)** |
**[Getting Started](#getting-started)** |
**[Contributing](#contributing)** |
**[License](#license)** |
**[Back to top](#pyodide)**
