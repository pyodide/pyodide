# Test Deno

Tests for running pyodide under Deno

## Maintaining deno.lock

The `deno.lock` file verifies the integrity of existing dependency resolutions.

If the tests are updated to include new dependencies or update existing dependencies then the `cache:validate` check may fail unless the `deno.lock` is updated.

To update `deno.lock`, run the `cache:update` task, i.e. `deno task cache:update`.
