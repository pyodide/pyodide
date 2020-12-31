(using_from_javascript)=

# Using Pyodide from Javascript

This document describes using Pyodide directly from Javascript. For information about using Pyodide from Iodide, see {ref}`using_from_iodide`.

## Startup

To include Pyodide in your project you can use the following CDN URL,

  https://cdn.jsdelivr.net/pyodide/v0.16.1/full/pyodide.js

You can also download a release from
[Github releases](https://github.com/iodide-project/pyodide/releases)
(or build it yourself), include its contents in your distribution, and import
the `pyodide.js` file there from a `<script>` tag. See the following section on
[serving pyodide files](#serving-pyodide-files) for more details.

The `pyodide.js` file has a single `Promise` object which bootstraps the Python
environment: `languagePluginLoader`. Since this must happen asynchronously, it
is a `Promise`, which you must call `then` on to complete initialization. When
the promise resolves, pyodide will have installed a namespace in global scope:
`pyodide`.

```javascript
languagePluginLoader.then(() => {
  // pyodide is now ready to use...
  console.log(pyodide.runPython('import sys\nsys.version'));
});
```

## Running Python code

Python code is run using the {ref}`pyodide.runPython <js_api_pyodide_runPython>`
function. It takes as input a string of Python
code. If the code ends in an expression, it returns the result of the
expression, converted to Javascript objects (see {ref}`type_conversions`).

```javascript
pyodide.runPython(`
import sys
sys.version
`);
```

After importing pyodide, only packages from the standard library are available.
See {ref}`loading_packages` documentation to load additional packages.

## Complete example

Create and save a test `index.html` page with the following contents:
```html
<!DOCTYPE html>
<html>
  <head>
      <script type="text/javascript">
          // set the pyodide files URL (packages.json, pyodide.asm.data etc)
          window.languagePluginUrl = 'https://cdn.jsdelivr.net/pyodide/v0.16.1/full/';
      </script>
      <script src="https://cdn.jsdelivr.net/pyodide/v0.16.1/full/pyodide.js"></script>
  </head>
  <body>
    Pyodide test page <br>
    Open your browser console to see pyodide output
    <script type="text/javascript">
          languagePluginLoader.then(function () {
              console.log(pyodide.runPython(`
                  import sys
                  sys.version
              `));
              console.log(pyodide.runPython('print(1 + 2)'));
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
        window.languagePluginUrl = 'https://cdn.jsdelivr.net/pyodide/v0.16.1/full/';
    </script>
    <script src="https://cdn.jsdelivr.net/pyodide/v0.16.1/full/pyodide.js"></script>
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
    // init pyodide
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

## Accessing Python scope from JavaScript

You can also access from JavaScript all functions and variables defined in Python using the {ref}`pyodide.globals <js_api_pyodide_globals>`) object.

For example, if you initialize the variable `x = numpy.ones([3,3])` in Python, you can access it from JavaScript in your browser's developer console as follows: `pyodide.globals.x`. The same goes for functions and imports. See {ref}`type_conversions` for more details.

You can try it yourself in the browser console:
```js
pyodide.globals.x
// >>> [Float64Array(3), Float64Array(3), Float64Array(3)]

// create the same 3x3 ndarray from js
let x = pyodide.globals.numpy.ones(new Int32Array([3, 3]))
// x >>> [Float64Array(3), Float64Array(3), Float64Array(3)]
```

Since you have full scope access, you can also re-assign new values or even JavaScript functions to variables, and create new ones from JavaScript:

```js
// re-assign a new value to an existing variable
pyodide.globals.x = 'x will be now string'

// create a new js function that will be available from Python
// this will show a browser alert if the function is called from Python
pyodide.globals.alert = msg => alert(msg)

// this new function will also be available in Python and will return the squared value.
pyodide.globals.squer = x => x*x
```

Feel free to play around with the code using the browser console and the above example.

## Accessing JavaScript scope from Python

The JavaScript scope can be accessed from Python using the `js` module (see {ref}`type_conversions_using_js_obj_from_py`). This module represents the global object `window` that allows us to directly manipulate the DOM and access global variables and functions from Python.

```python
import js

div = js.document.createElement("div")
div.innerHTML = "<h1>This element was created from Python</h1>"
js.document.body.prepend(div)
```

See {ref}`serving_pyodide_packages` to distribute pyodide files locally.
