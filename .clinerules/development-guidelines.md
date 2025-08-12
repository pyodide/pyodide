## Brief overview
These guidelines are for the development process of the project, based on the contents of the `docs/development/` directory.

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
