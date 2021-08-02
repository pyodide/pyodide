import assert from "assert";
import { initializePackageCache, pathIsUrl } from "../load-pyodide.js";
import fs from "fs";

describe("initializePackageCache", () => {
  it("Output path exists", async () => {
    let cacheDir = await initializePackageCache("pyodide");
    assert.equal(fs.existsSync(cacheDir), true);
  });
});

describe("pathIsUrl", () => {
  it("examples", async () => {
    assert.equal(pathIsUrl("/test"), false);
    // in Node.js relative path is a path, unlike in the browser
    assert.equal(pathIsUrl("./test"), false);
    //
    assert.equal(pathIsUrl("http://test.com"), true);
    assert.equal(pathIsUrl("https://test.com"), true);
  });
});
