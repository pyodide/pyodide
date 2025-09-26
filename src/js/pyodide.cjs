// CommonJS wrapper for ESM pyodide
// This file provides CommonJS compatibility for tools like pytest_pyodide
// while maintaining "type": "module" in package.json

const { createRequire } = require('module');
const nodeRequire = createRequire(__filename);

// Set global require for pyodide.asm.js compatibility
if (typeof globalThis.require === 'undefined') {
  globalThis.require = nodeRequire;
}

// Load pyodide.mjs as ESM
let loadPyodideModule;

// Since we can't use top-level await in CommonJS, we provide an async loadPyodide
const loadPyodide = async function(...args) {
  if (!loadPyodideModule) {
    // Dynamic import of the ESM module
    const mod = await import('./pyodide.mjs');
    loadPyodideModule = mod.loadPyodide;
  }
  return loadPyodideModule(...args);
};

// Export for CommonJS
module.exports = {
  loadPyodide,
  version: '0.29.0-dev.0'
};