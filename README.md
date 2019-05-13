# Pyodide


[![Build Status](https://circleci.com/gh/iodide-project/pyodide.png)](https://circleci.com/gh/iodide-project/pyodide)

The Python scientific stack, compiled to WebAssembly.

It provides transparent conversion of objects between Javascript and Python.
When inside a browser, this means Python has full access to the Web APIs.

**While closely related to the [iodide project](https://iodide.io), Pyodide may
be used standalone in any context where you want to run Python inside a web
browser.**

For more information, see [the demo](https://extremely-alpha.iodide.io/notebooks/222/) and the
[documentation](https://github.com/iodide-project/pyodide/tree/master/docs).

# Building

Building is easiest on Linux. For other platforms, we recommend using
the Docker image (described below) to build Pyodide.

Make sure the prerequisites for [emsdk](https://github.com/juj/emsdk) are
installed. Pyodide will build a custom, patched version of emsdk, so there is no
need to build it yourself prior.

Additional build prerequisites are:

- A working native compiler toolchain, enough to build CPython.
- A native Python 3.7 to run the build scripts.
- PyYAML
- [lessc](https://lesscss.org/) to compile less to css.
- [uglifyjs](https://github.com/mishoo/UglifyJS) to minify Javascript builds.
- [ccache](https://ccache.samba.org) (optional) recommended for much faster rebuilds.


`make`

## Using Docker

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

# Testing

Install the following dependencies into the default Python installation:

   `pip install pytest selenium pytest-instafail`

Install [geckodriver](https://github.com/mozilla/geckodriver/releases) and
[chromedriver](https://sites.google.com/a/chromium.org/chromedriver/downloads) somewhere
on your `PATH`.

`pytest test/`

# Manual Testing

The port 8000 of the docker environment and the host system are automatically
binded when ``./run_docker`` is run.

This can be used to test the ``pyodide`` builds running within the docker
environment using external browser programs on the host system.

To do this, simply run ``./bin/pyodide serve``

This serves the ``build`` directory of the ``pyodide`` project on port 8000.

* To serve a different directory, use the ``--build_dir`` argument followed by
the path of the directory
* To serve on a different port, use the ``--port`` argument followed by the
desired port number

Make sure that the port passed in ``--port`` argument is same as the one
defined as ``DOCKER_PORT`` in the ``run_docker`` script.

Once the webserver is running, for simple interactive testing, visit the URL
[http://localhost:8000/console.html](http://localhost:8000/console.html)

# Benchmarking

Install the same dependencies as for testing.

`make benchmark`

# Linting

Python is linted with `flake8`.  C and Javascript are linted with `clang-format`.

`make lint`
