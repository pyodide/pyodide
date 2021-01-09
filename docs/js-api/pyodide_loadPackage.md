(js_api_pyodide_loadpackage)=
# pyodide.loadPackage(names, messageCallback, errorCallback)

Load a package or a list of packages over the network.

This makes the files for the package available in the virtual filesystem.
The package needs to be imported from Python before it can be used.

*Parameters*

| name              | type            | description                           |
|-------------------|-----------------|---------------------------------------|
| *names*           | {String, Array} | package name, or URL. Can be either a single element, or an array.          |

*Returns*

Loading is asynchronous, therefore, this returns a `Promise`.
