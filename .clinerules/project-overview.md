## Brief overview
This document provides a high-level overview of the Pyodide project, based on the introductory materials. It is intended to help new contributors get started.

## Contribution Areas
- **Compiler:** Work on the CPython compilation to WebAssembly, including LLVM and Emscripten.
- **Python:** Improve the Python interpreter, including standard library compatibility, performance, and size.
- **Package Support:** Add support for new packages, including those with C, C++, Fortran, or Rust extensions.
- **Packaging and Distribution:** Improve the packaging and distribution of Pyodide and its packages.
- **Browser Integration:** Enhance the interaction between the Python and JavaScript runtimes.
- **JS Runtimes:** Improve support for different JavaScript runtimes, such as Node.js, Deno, and Bun.
- **Tooling:** Improve the build system, package installer, and testing infrastructure.
- **Documentation:** Improve the existing documentation and add new content.
- **Application Development:** Build new applications using Pyodide.

## Development Environment
- The development environment is Linux-based.
- For Windows users, WSL or GitHub Codespaces is recommended.
- Follow the instructions in the documentation to build Pyodide from source.

## Project Structure
- **cpython/:** Contains the CPython source code, patches, and build scripts.
- **src/:** Contains the JavaScript and Python APIs, as well as the Foreign Function Interface (FFI).
- **packages/:** Contains the recipes for building Python packages.
- **pyodide-build/:** Contains the build system for Pyodide.

## Key Technologies
- **WebAssembly:** The compilation target for the CPython interpreter and native extensions.
- **Emscripten:** The compiler toolchain used to build WebAssembly modules for the browser.
- **LLVM:** The underlying compiler infrastructure used by Emscripten.
