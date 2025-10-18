(adding-packages-into-pyodide-distribution)=

# Adding Packages into Pyodide Distribution

> [!NOTE]
> Please check {ref}`building-packages-from-source` first if you want to build a package
> from source. This document is for adding packages into the Pyodide distribution.

As of 2025/04, PyPI does not support Emscripten/wasm32 wheels, so it is not
easy to distribute your package to Pyodide users.
Therefore, Pyodide currently releases a set of packages that are
precompiled and included in the Pyodide distribution.
This document describes how to add a package to the Pyodide distribution.

## Writing a recipe

To add a package to the Pyodide distribution,
you need to write a recipe for that package.

See {ref}`building-packages-using-recipe` for more information on how to write a recipe.

## Adding a recipe to the Pyodide distribution

Once you have written a recipe, you need to add it to the
[`pyodide-recipes`](https://github.com/pyodide/pyodide-recipes) repository.

Once the recipe is added to the `pyodide-recipes` repository,
the Pyodide maintainers will regularly apply the updated recipes to the next Pyodide release.

Alternatively, you can download the prebuilt packages from the `pyodide-recipes` repository,
host them on your own server, and use them in your Pyodide distribution.

```{eval-rst}
.. toctree::
   :hidden:

   building-packages-using-recipe.md
   meta-yaml.md
```
