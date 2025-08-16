## Brief overview
These guidelines are for maintaining the project's documentation, which is built using Sphinx.

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
