# Test Deno

Tests for running pyodide under Deno

## Maintaining deno.lock

The `deno.lock` file verifies the integrity of existing dependency resolutions.

If the tests are updated to include new dependencies or update existing dependencies then the `cache:validate` check may fail unless the `deno.lock` is updated.

To update `deno.lock`, run the `cache:update` task, i.e. `deno task cache:update`.

## Leveraging a local build

Deno does not support local [file: packages](https://github.com/denoland/deno/issues/18474) or [workspace packages](https://github.com/denoland/deno/issues/18546).
To leverage the local build of pyodide the `test` task follows the [`--node-modules-dir` workflow](https://deno.com/manual@v1.33.3/node/npm_specifiers#--node-modules-dir-flag) discussed in Deno summarized as follows:

1. Use the `--node-modules-dir` flag so a local `node_modules` folder is created based on currently published npm packages.
2. Replace the contents of the pyodide package in `node_modules` with the local build.
3. Run the tests which should now use the local build.
