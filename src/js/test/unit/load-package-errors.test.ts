import assert from "node:assert/strict";
import { describe, it, type TestContext } from "node:test";
import { PackageManager } from "../../load-package.ts";
import type { LockfilePackage, PackageLoadMetadata } from "../../types.ts";
import { genMockAPI, genMockModule } from "./test-helper.ts";

function makePackage(name: string, depends: string[] = []): LockfilePackage {
  return {
    name,
    version: "1.0.0",
    file_name: `${name}-1.0.0-py3-none-any.whl`,
    package_type: "package",
    install_dir: "site",
    sha256: "00",
    imports: [name],
    depends,
  };
}

function makePackageManager(packages: LockfilePackage[]) {
  const api = genMockAPI();
  api.lockfile_packages = Object.fromEntries(
    packages.map((pkg) => [pkg.name, pkg]),
  );
  return new PackageManager(api, genMockModule());
}

type InstallMock = (
  metadata: PackageLoadMetadata,
  toLoad: Map<string, PackageLoadMetadata>,
  loaded: Set<LockfilePackage>,
  failed: Map<string, Error>,
) => Promise<void>;

function mockInstall(
  t: TestContext,
  pm: PackageManager,
  implementation: InstallMock,
) {
  t.mock.method(pm as any, "downloadAndInstall", implementation);
}

function markLoaded(
  pm: PackageManager,
  metadata: PackageLoadMetadata,
  loaded: Set<LockfilePackage>,
) {
  loaded.add(metadata.packageData);
  pm.loadedPackages[metadata.name] = metadata.channel;
}

describe("loadPackage installation errors", () => {
  it("rejects when a lockfile package cannot be downloaded", async (t) => {
    const pm = makePackageManager([makePackage("broken")]);
    const downloadError = new Error("wheel is unavailable");
    mockInstall(t, pm, async (metadata, _toLoad, _loaded, failed) => {
      failed.set(metadata.name, downloadError);
    });

    await assert.rejects(
      () => pm.loadPackage("broken"),
      (error: AggregateError) => {
        assert(error instanceof AggregateError);
        assert.match(error.message, /Failed to load broken/);
        assert.deepEqual(error.errors, [downloadError]);
        return true;
      },
    );
    assert.equal(pm.loadedPackages.broken, undefined);
  });

  it("reports a URL failure through the error callback", async (t) => {
    const pm = makePackageManager([]);
    const downloadError = new Error("wheel is unavailable");
    mockInstall(t, pm, async (metadata, _toLoad, _loaded, failed) => {
      failed.set(metadata.name, downloadError);
    });

    const errors: string[] = [];
    await assert.rejects(
      () =>
        pm.loadPackage(
          "https://invalid.example/broken-1.0.0-py3-none-any.whl",
          {
            errorCallback: (message) => errors.push(message),
          },
        ),
      (error: AggregateError) => {
        assert.deepEqual(error.errors, [downloadError]);
        return true;
      },
    );
    assert.deepEqual(errors, [
      "The following error occurred while loading broken:",
      "wheel is unavailable",
    ]);
  });

  it("still resolves after installing packages successfully", async (t) => {
    const pkg = makePackage("working");
    const pm = makePackageManager([pkg]);
    mockInstall(t, pm, async (metadata, _toLoad, loaded) => {
      markLoaded(pm, metadata, loaded);
    });

    const result = await pm.loadPackage("working");

    assert.deepEqual(result, [
      {
        name: "working",
        version: "1.0.0",
        fileName: "working-1.0.0-py3-none-any.whl",
        packageType: "package",
      },
    ]);
    assert.equal(pm.loadedPackages.working, "default channel");
  });

  it("installs independent packages before reporting a partial failure", async (t) => {
    const pm = makePackageManager([
      makePackage("working"),
      makePackage("broken"),
    ]);
    mockInstall(t, pm, async (metadata, _toLoad, loaded, failed) => {
      if (metadata.name === "broken") {
        failed.set(metadata.name, new Error("wheel is unavailable"));
        return;
      }
      markLoaded(pm, metadata, loaded);
    });

    await assert.rejects(
      () => pm.loadPackage(["working", "broken"]),
      /Failed to load broken/,
    );
    assert.equal(pm.loadedPackages.working, "default channel");
    assert.equal(pm.loadedPackages.broken, undefined);
  });

  it("can retry after a failed installation", async (t) => {
    const pkg = makePackage("flaky");
    const pm = makePackageManager([pkg]);
    let attempts = 0;
    mockInstall(t, pm, async (metadata, _toLoad, loaded, failed) => {
      attempts++;
      if (attempts === 1) {
        failed.set(metadata.name, new Error("temporary failure"));
        return;
      }
      markLoaded(pm, metadata, loaded);
    });

    await assert.rejects(() => pm.loadPackage("flaky"), /Failed to load flaky/);
    const result = await pm.loadPackage("flaky");

    assert.equal(attempts, 2);
    assert.equal(result[0].name, "flaky");
    assert.equal(pm.loadedPackages.flaky, "default channel");
  });

  it("serializes concurrent attempts and lets a later call retry", async (t) => {
    const pkg = makePackage("flaky");
    const pm = makePackageManager([pkg]);
    let attempts = 0;
    mockInstall(t, pm, async (metadata, _toLoad, loaded, failed) => {
      attempts++;
      if (attempts === 1) {
        failed.set(metadata.name, new Error("temporary failure"));
        return;
      }
      markLoaded(pm, metadata, loaded);
    });

    const results = await Promise.allSettled([
      pm.loadPackage("flaky"),
      pm.loadPackage("flaky"),
    ]);

    assert.equal(results[0].status, "rejected");
    assert(results[0].reason instanceof AggregateError);
    assert.equal(results[1].status, "fulfilled");
    assert.equal(results[1].value[0].name, "flaky");
    assert.equal(attempts, 2);
  });
});
