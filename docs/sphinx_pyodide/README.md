# Sphinx-Pyodide

This package is a special sphinx extension for Pyodide's documentation.
The three separate files do three unrelated tasks:

## packages

Adds a custom directive which makes a table of the Pyodide packages

## lexers

Adds custom pyodide Pygments lexers that provides syntax highlighting for
Javascript with embedded Python code, and for HTML with embedded Javascript that
itself contains embedded Python.

e.g., in

```pyodide
await pyodide.loadPackage(numpy);
pyodide.runPython(`
    def f(y):
        return y + ${x}
    f(7)
`);
```

the code inside of `pyodide.runPython` is highlighted as Python, the other code
is highlighted as Javascript. Similarly with `html-pyodide`:

```html-pyodide
<div></div>
<script type="text/javascript">
console.log(pyodide.runPython(`
    import sys
    sys.version
`));
</script>
```

## jsdoc

This extends `sphinx-js` for our purposes. This contains a mix of missing
features that could ideally be upstreamed into `sphinx-js` and custom code that
can't be upstreamed.

### TsAnalyzer monkey patches

We monkey patch `TsAnalyzer._type_name` to fill in formatting of types that were
left as TODOs by `sphinx-js` (this could probably be upstreamed).

We monkey patch `TsAnalyzer._convert_node` to fix two crashes (could be
upstreamed) and to turn a destructured object argument into a list of argument docs:

```js
/**
* @param options
*/
function f({x , y } : {
    /** The x value */
    x : number,
    /** The y value */
    y : string
}){ ... }
```

should be documented like:

```
options.x (number) The x value
options.y (number) The y value
```

### `js:function`

We update the `js:function` directive to display `async` in front of async
functions.

### `PyodideAnalyzer`

We compose `TsAnalyzer` into `PyodideAnalyzer`. This prunes out private
functions, marks functions as `async` so we can display `async` in front of
them, and organizes functions into our three categories:

- `globalThis`: globaly exposed functions
- `pyodide`: pyodide APIs
- `PyProxy`: `PyProxy` APIs

It also classifies them into three types: function, class, or attribute so we
can separate them out in the summary.

### js-autodoc

`sphinx-js` doesn't include full recursive layout features by default. This adds
a `js-doc-summary` directive and a `js-doc-content` directive. `js-doc-summary`
makes a summary table for any category (`globalThis`, `pyodide` or `PyProxy`)
and `js-doc-content` formats the main documentation content. These are used in
`js-api.md`. A lot of this code is similar to the `autosummary` package, but
there are enough differences that it was easier to copy the code in.

## autodoc_submodules

This makes autodoc recursively document submodules, mixed in with the top level
docs. For instance, `pyfetch` is defined in `pyodide.html`. This adds an entry
called `http.pyfetch` to the list of documented APIs for `pyodide`.
