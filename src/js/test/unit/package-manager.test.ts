import * as chai from "chai";
import sinon from "sinon";
import { PackageManager, toStringArray } from "../../load-package.ts";
import { genMockAPI, genMockModule } from "./test-helper.ts";

describe("PackageManager", () => {
  it("should initialize with API and Module", () => {
    const mockApi = genMockAPI();
    const mockMod = genMockModule();
    const _ = new PackageManager(mockApi, mockMod);
  });
});

describe("logStdout and logStderr", () => {
  it("Should use console.log and console.error if no logger is provided", () => {
    const mockApi = genMockAPI();
    const mockMod = genMockModule();

    const pm = new PackageManager(mockApi, mockMod);

    const logSpy = sinon.spy(pm, "stdout");
    const errorSpy = sinon.spy(pm, "stderr");

    pm.logStdout("stdout");
    pm.logStderr("stderr");

    chai.assert.isTrue(logSpy.calledOnce);
    chai.assert.isTrue(errorSpy.calledOnce);
    chai.assert.isTrue(logSpy.calledWith("stdout"));
    chai.assert.isTrue(errorSpy.calledWith("stderr"));

    logSpy.restore();
    errorSpy.restore();
  });

  it("Should be overwrited when setCallbacks is called", () => {
    const mockApi = genMockAPI();
    const mockMod = genMockModule();

    const pm = new PackageManager(mockApi, mockMod);

    const stdoutLogger = sinon.spy();
    const stderrLogger = sinon.spy();

    pm.setCallbacks(stdoutLogger, stderrLogger)(() => {
      pm.logStdout("stdout");
      pm.logStderr("stderr");
    })()

    chai.assert.isTrue(stdoutLogger.calledOnce);
    chai.assert.isTrue(stderrLogger.calledOnce);
    chai.assert.isTrue(stdoutLogger.calledWith("stdout"));
    chai.assert.isTrue(stderrLogger.calledWith("stderr"));
  });
});

describe("toStringArray", () => {
  it("Should convert string to array of strings", () => {
    chai.assert.deepEqual(toStringArray("hello"), ["hello"]);
  });

  it("Should return the array if it is already an array", () => {
    chai.assert.deepEqual(toStringArray(["hello", "world"]), [
      "hello",
      "world",
    ]);
  });

  it("Should convert PyProxy to array of strings", () => {
    // TODO: use real PyProxy
    const pyProxyMock = {
      toJs: () => ["hello", "world"],
    };

    chai.assert.deepEqual(toStringArray(pyProxyMock), ["hello", "world"]);
  });
});

describe("getLoadedPackageChannel", () => {
  it("Should return the loaded package from loadedPackages obj", () => {
    const mockApi = genMockAPI();
    const mockMod = genMockModule();

    const pm = new PackageManager(mockApi, mockMod);
    pm.loadedPackages = {
      package: "channel",
    };

    const loadedPackage = pm.getLoadedPackageChannel("package");
    chai.assert.equal(loadedPackage, "channel");

    const notLoadedPackage = pm.getLoadedPackageChannel("notLoadedPackage");
    chai.assert.equal(notLoadedPackage, null);
  });
});
