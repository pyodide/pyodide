self.languagePluginUrl = '{{ PYODIDE_BASE_URL }}'
importScripts('./pyodide.js')

onmessage = async function(e) {
  await languagePluginLoader;
  const data = e.data;
  for (let key of Object.keys(data)) {
    if (key !== 'python') {
      // Keys other than python must be arguments for the python script.
      // Set them on self, so that `from js import key` works.
      self[key] = data[key];
    }
  }

  try {
    self.postMessage(
        {results : await self.pyodide.runPythonAsync(data.python)});
  } catch (e) {
    // if you prefer messages with the error
    self.postMessage({error : e.message});
    // if you prefer onerror events
    // setTimeout(() => { throw err; });
  }
}
