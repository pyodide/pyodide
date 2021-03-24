(using_from_javascript)=

# Using Pyodide from Javascript

This document describes using Pyodide directly from Javascript.

## Startup

To include Pyodide in your project you can use the following CDN URL,

  https://cdn.jsdelivr.net/pyodide/v0.17.0a2/full/pyodide.js

You can also download a release from
[Github releases](https://github.com/iodide-project/pyodide/releases)
(or build it yourself), include its contents in your distribution, and import
the `pyodide.js` file there from a `<script>` tag. See the following section on
{ref}`serving_pyodide_packages` for more details.

The `pyodide.js` file has a single `Promise` object which bootstraps the Python
environment: `languagePluginLoader`. Since this must happen asynchronously, it
is a `Promise`, which you must call `then` on to complete initialization. When
the promise resolves, Pyodide will have installed a namespace in the global
scope called {js:mod}`pyodide`.

```pyodide
languagePluginLoader.then(() => {
  // Pyodide is now ready to use...
  console.log(pyodide.runPython(`import sys\nsys.version`));
});
```

## Running Python code

Python code is run using the {any}`pyodide.runPython`
function. It takes as input a string of Python
code. If the code ends in an expression, it returns the result of the
expression, translated to Javascript objects (see {ref}`type-translations`).

```pyodide
pyodide.runPython(`
import sys
sys.version
`);
```

After importing Pyodide, only packages from the standard library are available.
See {ref}`loading_packages` documentation to load additional packages.

## Complete example

Create and save a test `index.html` page with the following contents:
```html-pyodide
<!DOCTYPE html>
<html>
  <head>
      <script type="text/javascript">
          // set the Pyodide files URL (packages.json, pyodide.asm.data etc)
          window.languagePluginUrl = 'https://cdn.jsdelivr.net/pyodide/v0.17.0a2/full/';
      </script>
      <script src="https://cdn.jsdelivr.net/pyodide/v0.17.0a2/full/pyodide.js"></script>
  </head>
  <body>
    Pyodide test page <br>
    Open your browser console to see Pyodide output
    <script type="text/javascript">
          languagePluginLoader.then(function () {
              console.log(pyodide.runPython(`
                  import sys
                  sys.version
              `));
              console.log(pyodide.runPython(`print(1 + 2)`));
          });
    </script>
  </body>
</html>
```


## Alternative Example

```html
<!DOCTYPE html>
<html>
<head>
    <script type="text/javascript">
        window.languagePluginUrl = 'https://cdn.jsdelivr.net/pyodide/v0.17.0a2/full/';
    </script>
    <script src="https://cdn.jsdelivr.net/pyodide/v0.17.0a2/full/pyodide.js"></script>
</head>

<body>
  <p>You can execute any Python code. Just enter something in the box below and click the button.</p>
  <input id='code' value='sum([1, 2, 3, 4, 5])'>
  <button onclick='evaluatePython()'>Run</button>
  <br>
  <br>
  <div>
    Output:
  </div>
  <textarea id='output' style='width: 100%;' rows='6' disabled></textarea>

  <script>
    const output = document.getElementById("output");
    const code = document.getElementById("code");

    function addToOutput(s) {
      output.value += '>>>' + code.value + '\n' + s + '\n';
    }

    output.value = 'Initializing...\n';
    // init Pyodide
    languagePluginLoader.then(() => { output.value += 'Ready!\n'; });

    function evaluatePython() {
      pyodide.runPythonAsync(code.value)
        .then(output => addToOutput(output))
        .catch((err) => { addToOutput(err) });
    }
  </script>
</body>

</html>
```

## Accessing Python scope from Javascript

You can also access from Javascript all functions and variables defined in
Python by using the {any}`pyodide.globals` object.

For example, if you run the code `x = numpy.ones([3,3])` in Python, you can
access the variable ``x`` from Javascript in your browser's developer console
as `pyodide.globals.get("x")`. The same goes
for functions and imports. See {ref}`type-translations` for more details.

You can try it yourself in the browser console:
```js
pyodide.runPython(`import numpy`);
pyodide.runPython(`x=numpy.ones((3, 4))`);
pyodide.globals.get('x').toJs();
// >>> [ Float64Array(4), Float64Array(4), Float64Array(4) ]

// create the same 3x4 ndarray from js
x = pyodide.globals.get('numpy').ones(new Int32Array([3, 4])).toJs();
// x >>> [ Float64Array(4), Float64Array(4), Float64Array(4) ]
```

Since you have full access to Python global scope, you can also re-assign new
values or even Javascript functions to variables, and create new ones from
Javascript:

```js
// re-assign a new value to an existing variable
pyodide.globals.set("x", 'x will be now string');

// create a new js function that will be available from Python
// this will show a browser alert if the function is called from Python
pyodide.globals.set("alert", alert);

// this new function will also be available in Python and will return the squared value.
pyodide.globals.set("square", x => x*x);

// You can test your new Python function in the console by running
pyodide.runPython(`square(3)`);

```

Feel free to play around with the code using the browser console and the above example.

## Accessing Javascript scope from Python

The Javascript scope can be accessed from Python using the `js` module (see
{ref}`type-translations_using-js-obj-from-py`). This module represents the
global object `window` that allows us to directly manipulate the DOM and access
global variables and functions from Python.

```python
import js

div = js.document.createElement("div")
div.innerHTML = "<h1>This element was created from Python</h1>"
js.document.body.prepend(div)
```

See {ref}`serving_pyodide_packages` to distribute Pyodide files locally.
