import * as fs from "fs";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import * as os from "os";
import * as path from "path";

import {
  ensureDirNode,
  getLoadScriptForRuntimeEnv,
  initNodeModules,
} from "../../compat";
import type { RuntimeEnv } from "../../environments";

function makeRuntimeEnv(partial: Partial<RuntimeEnv> = {}): RuntimeEnv {
  return {
    IN_NODE: false,
    IN_BUN: false,
    IN_DENO: false,
    IN_SAFARI: false,
    IN_SHELL: false,
    IN_NODE_COMMONJS: false,
    IN_NODE_ESM: false,
    IN_BROWSER: false,
    IN_BROWSER_MAIN_THREAD: false,
    IN_BROWSER_WEB_WORKER: false,
    ...partial,
  };
}

describe("ensureDirNode", () => {
  it("Should create the dir if it does not exist", async () => {
    await initNodeModules();

    const baseDir = fs.mkdtempSync(path.join(os.tmpdir(), "foo-"));

    const notExistDir = path.join(baseDir, "notExistDir");

    assert.ok(!fs.existsSync(notExistDir));

    await ensureDirNode(notExistDir);

    assert.ok(fs.existsSync(notExistDir));
  });

  it("Should not throw if the dir already exists", async () => {
    await initNodeModules();

    const baseDir = fs.mkdtempSync(path.join(os.tmpdir(), "foo-"));

    assert.ok(fs.existsSync(baseDir));

    await ensureDirNode(baseDir);

    assert.ok(fs.existsSync(baseDir));
  });
});

describe("getLoadScriptForRuntimeEnv", () => {
  it("should not throw for browser-ambiguous runtime state", () => {
    const env = makeRuntimeEnv({
      // Some module-evaluation environments can set IN_BROWSER=true while
      // browser thread probes are false at evaluation time.
      IN_BROWSER: true,
      IN_BROWSER_MAIN_THREAD: false,
      IN_BROWSER_WEB_WORKER: false,
    });
    const getLoader = () => getLoadScriptForRuntimeEnv(env);
    assert.doesNotThrow(getLoader);
    assert.equal(typeof getLoader(), "function");
  });

  it("should not throw when process.browser shim disables IN_NODE", () => {
    const env = makeRuntimeEnv({
      IN_NODE: false,
      IN_BROWSER: true,
      IN_BROWSER_MAIN_THREAD: false,
      IN_BROWSER_WEB_WORKER: false,
    });
    assert.doesNotThrow(() => getLoadScriptForRuntimeEnv(env));
  });

  it("should throw when no runtime branch matches", () => {
    const env = makeRuntimeEnv();
    assert.throws(() => getLoadScriptForRuntimeEnv(env));
  });
});
