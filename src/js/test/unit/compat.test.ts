import * as fs from "fs";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import * as os from "os";
import * as path from "path";

import { ensureDirNode, initNodeModules } from "../../compat";

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
