## Brief overview

These are general guidelines for working in this workspace.

## Communication style

- Be direct and concise in your responses.
- Provide clear explanations for your actions.

## Development workflow

- Use the `docs/` directory for all documentation.
- Follow the existing structure of the project when adding new files.
- Use the `Makefile` to build the project.

## Coding best practices

- Follow the coding style of the existing code.
- Write tests for new features.

## Project context

- This project is a Python distribution for the browser and Node.js based on WebAssembly.
- The project is hosted on GitHub at https://github.com/pyodide/pyodide.

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
- **pyodide-build/:** Contains the build system for Pyodide. pyodide-build is a submodule and we do not directly modify the source code in this repository. All the pyodide-build-related changes should be dealt separately in pyodide-build repository.

## Key Technologies

- **WebAssembly:** The compilation target for the CPython interpreter and native extensions.
- **Emscripten:** The compiler toolchain used to build WebAssembly modules for the browser.
- **LLVM:** The underlying compiler infrastructure used by Emscripten.

## Building the project

- Use `make` to build the project.
- For a streamlined build process, use the provided Docker image.
- When building from source, follow the specific instructions for your operating system (Linux, macOS).

## Package Management

- Python packages are built using recipes defined in `meta.yaml` files.
- To add a new package, create a recipe and add it to the `pyodide-recipes` repository.
- Use `pyodide build` to build individual packages from source.

## Contributing

- Follow the development workflow outlined in `docs/development/contributing.md`.
- Adhere to the Code of Conduct.
- Use `pre-commit` to ensure code style consistency.

## Core C Code Development

- When modifying the core C code in `src/core`, follow the guidelines in `docs/development/core.md`.
- Use the provided error handling macros for consistency.
- Follow the specified function structure for clarity and correct resource management.

## Testing and Debugging

- Use `pytest` for the Python test suite and `npm test` for the JavaScript tests.
- Refer to `docs/development/debugging.md` for tips on debugging, including how to handle linker errors and build with symbols.

## Documentation Structure

- All documentation is located in the `docs/` directory.
- The documentation is organized into three main sections: `usage`, `development`, and `project`.
- New documentation should be added to the appropriate section.

## Tooling and Dependencies

- The documentation is built using Sphinx.
- The required Python packages for building the documentation are listed in `docs/requirements-doc.txt`.
- When adding new dependencies, update `docs/requirements-doc.txt`.

## Content and Style

- The main entry point for the documentation is `docs/index.rst`.
- We only use markdown except for the index.rst file.
- JavaScript and TypeScript documentation is handled via `sphinx-js`.

## Building the Documentation

- The `Makefile` and `make.bat` files in the `docs/` directory are used to build the documentation.
- Use `make help` to see available build targets.
