# Testing and benchmarking

## Testing

### Requirements

Install the following dependencies into the default Python installation:

```bash
pip install pytest selenium pytest-instafail
```

Install [geckodriver](https://github.com/mozilla/geckodriver/releases) and
[chromedriver](https://sites.google.com/a/chromium.org/chromedriver/downloads)
and check that they are in your `PATH`.

### Running the test suite

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

## Benchmarking

To run common benchmarks to understand Pyodide's performance, begin by
installing the same prerequisites as for testing. Then run:

```bash
make benchmark
```

## Linting

Python is linted with `flake8`.  C and Javascript are linted with
`clang-format`.

To lint the code, run:

```bash
make lint
```
