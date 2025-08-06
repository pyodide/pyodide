import * as chai from "chai";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";

import { ensureDirNode, initNodeModules } from "../../compat";

describe("ensureDirNode", () => {
      it("Should create the dir if it does not exist", async () => {
            await initNodeModules();

            const baseDir = fs.mkdtempSync(path.join(os.tmpdir(), "foo-"));

            const notExistDir = path.join(baseDir, "notExistDir");

            chai.assert.isFalse(fs.existsSync(notExistDir));

            await ensureDirNode(notExistDir);

            chai.assert.isTrue(fs.existsSync(notExistDir));
      });

      it("Should not throw if the dir already exists", async () => {
            await initNodeModules();

            const baseDir = fs.mkdtempSync(path.join(os.tmpdir(), "foo-"));

            chai.assert.isTrue(fs.existsSync(baseDir));

            await ensureDirNode(baseDir);

            chai.assert.isTrue(fs.existsSync(baseDir));
      });
});
