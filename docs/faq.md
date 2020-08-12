# Frequently Asked Questions (FAQ)

### How can I load external python files in Pyodide?

The two possible solutions are,

- include these files in a python package, build a pure python wheel with
  `python setup.py bdist_wheel` and [load it with micropip](./pypi.html#installing-wheels-from-arbitrary-urls).
- fetch the python code as a string and evaluate it in Python,
  ```js
  pyodide.eval_code(pyodide.open_url('https://some_url/...'))
  ```

In both cases, files need to be served with a web server and cannot be loaded from local file system.

### Why can't I load files from the local file system?

For security reasons JavaScript in the browser is not allowed to load local
data files. You need to serve them with a web-browser.
