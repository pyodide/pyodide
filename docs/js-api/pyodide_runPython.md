(js_api_pyodide_runPython)=
# pyodide.runPython(code)

Runs a string of Python code from Javascript.

The last part of the string may be an expression, in which case, its value is returned.

**Parameters**

| name    | type   | description                    |
|---------|--------|--------------------------------|
| *code*  | String | Python code to evaluate        |


**Returns**

| name       | type    | description                     |
|------------|---------|---------------------------------|
| *jsresult* | *any*   | Result, converted to Javascript |
