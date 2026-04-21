(quickstart)=

# Getting started

## Try it online

Try Pyodide in a [REPL](../console.html){.external} directly in your browser
(no installation needed).

## Setup

There is a [complete example](complete-example) that you can copy & paste
into an html file below. To include Pyodide in your project you can use the
following CDN URL:

```text
{{PYODIDE_CDN_URL}}pyodide.js
```

You can also download a release from [GitHub
releases](https://github.com/pyodide/pyodide/releases) or build Pyodide
yourself. See {ref}`downloading_deploying` for more details.

The `pyodide.js` file defines a single async function called
{js:func}`~exports.loadPyodide` which sets up the Python environment
and returns {js:mod}`the Pyodide top level namespace <pyodide>`.

```pyodide
async function main() {
  let pyodide = await loadPyodide();
  // Pyodide is now ready to use...
  console.log(pyodide.runPython(`
    import sys
    sys.version
  `));
};
main();
```

## Running Python code

Python code is run using the {js:func}`pyodide.runPython` function. It takes as
input a string of Python code. If the code ends in an expression, it returns the
result of the expression, translated to JavaScript objects (see
{ref}`type-translations`). For example the following code will return the
version string as a JavaScript string:

```pyodide
pyodide.runPython(`
  import sys
  sys.version
`);
```

After importing Pyodide, only packages from the standard library are available.
See {ref}`loading_packages` for information about loading additional packages.

(complete-example)=

## Complete example

Create and save a test `index.html` page with the following contents:

```html-pyodide
<!doctype html>
<html>
  <head>
      <script src="{{PYODIDE_CDN_URL}}pyodide.js"></script>
  </head>
  <body>
    Pyodide test page <br>
    Open your browser console to see Pyodide output
    <script type="text/javascript">
      async function main(){
        let pyodide = await loadPyodide();
        console.log(pyodide.runPython(`
            import sys
            sys.version
        `));
        pyodide.runPython("print(1 + 2)");
      }
      main();
    </script>
  </body>
</html>
```

## Alternative Example

```html
<!doctype html>
<html>
  <head>
    <script src="{{PYODIDE_CDN_URL}}pyodide.js"></script>
  </head>

  <body>
    <p>
      You can execute any Python code. Just enter something in the box below and
      click the button.
    </p>
    <input id="code" value="sum([1, 2, 3, 4, 5])" />
    <button onclick="evaluatePython()">Run</button>
    <br />
    <br />
    <div>Output:</div>
    <textarea id="output" style="width: 100%;" rows="6" disabled></textarea>

    <script>
      const output = document.getElementById("output");
      const code = document.getElementById("code");

      function addToOutput(s) {
        output.value += ">>>" + code.value + "\n" + s + "\n";
      }

      output.value = "Initializing...\n";
      // init Pyodide
      async function main() {
        let pyodide = await loadPyodide();
        output.value += "Ready!\n";
        return pyodide;
      }
      let pyodideReadyPromise = main();

      async function evaluatePython() {
        let pyodide = await pyodideReadyPromise;
        try {
          let output = pyodide.runPython(code.value);
          addToOutput(output);
        } catch (err) {
          addToOutput(err);
        }
      }
    </script>
  </body>
</html>
```

## Accessing Python scope from JavaScript

All functions and variables defined in the Python global scope are accessible
via the {js:attr}`pyodide.globals` object.

For example, if you run the code `x = [3, 4]` in Python global scope,
you can access the global variable `x` from JavaScript in your browser's
developer console with `pyodide.globals.get("x")`. The same goes for functions
and imports. See {ref}`type-translations` for more details.

You can try it yourself in the browser console. Go to the [Pyodide REPL
URL](../console.html){.external} and type the following into the browser
console:

```pyodide
pyodide.runPython(`
  x = [3, 4]
`);
pyodide.globals.get('x').toJs();
// >>> [ 3, 4 ]
```

You can assign new values to Python global variables or create new ones from
Javascript.

```pyodide
// re-assign a new value to an existing variable
pyodide.globals.set("x", 'x will be now string');

// add the js "alert" function to the Python global scope
// this will show a browser alert if called from Python
pyodide.globals.set("alert", alert);

// add a "square" function to Python global scope
pyodide.globals.set("square", x => x*x);

// Test the new "square" Python function
pyodide.runPython("square(3)");
```

## Accessing JavaScript scope from Python

The JavaScript scope can be accessed from Python using the `js` module (see
{ref}`type-translations_using-js-obj-from-py`). We can use it to access global
variables and functions from Python. For instance, we can directly manipulate the DOM:

```python
import js

div = js.document.createElement("div")
div.innerHTML = "<h1>This element was created from Python</h1>"
js.document.body.prepend(div)
```
