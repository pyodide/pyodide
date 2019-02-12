self.languagePluginUrl = '{{DEPLOY}}'
importScripts('./pyodide.js')

var onmessage = function(e) { // eslint-disable-line no-unused-vars
  languagePluginLoader.then(() => {
    const data = e.data;
    const keys = Object.keys(data);
    for (let key of keys) {
      if (key !== 'python') {
        // Keys other than python must be arguments for the python script.
        // Set them on self, so that `from js import key` works.
        self[key] = data[key];
      }
    }

    self.pyodide.runPythonAsync(data.python, () => {})
        .then((results) => { self.postMessage({results}); })
        .catch((err) => {
          // if you prefer messages with the error
          self.postMessage({error : err.message});
          // if you prefer onerror events
          // setTimeout(() => { throw err; });
        });
  });
}
