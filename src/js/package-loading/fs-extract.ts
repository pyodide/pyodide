/**
 * Write unpacked archive entries into the Emscripten filesystem.
 *
 * @private
 */

import type { FSType } from "../types";
import type { ArchiveEntry } from "./archive";
import { shouldLoadDynlib } from "./dynlib-detect";
import type { DynlibEntry } from "./dynlib-preload";
import { dirname, resolve } from "./posix-path";

/** @private */
export interface ExtractResult {
  dynlibs: DynlibEntry[];
  distInfoDir?: string;
  dataDir?: string;
}

/**
 * Extract archive entries into `installDir`.
 *
 * @param fs The Emscripten filesystem (`Module.FS`).
 * @param entries The unpacked archive entries.
 * @param installDir The absolute directory to extract into.
 * @param extensionTags The compatible extension tags used to detect dynlibs.
 * @returns The detected `.dist-info`/`.data` directory names and the resolved
 * paths of shared libraries to load.
 * @private
 */
export function extractArchiveToFS(
  fs: FSType,
  entries: readonly ArchiveEntry[],
  installDir: string,
  extensionTags: readonly string[],
): ExtractResult {
  const dynlibs: DynlibEntry[] = [];
  let distInfoDir: string | undefined;
  let dataDir: string | undefined;

  for (const { name, data } of entries) {
    const firstComponent = name.split("/", 1)[0];
    if (!distInfoDir && firstComponent.endsWith(".dist-info")) {
      distInfoDir = firstComponent;
    }
    if (!dataDir && firstComponent.endsWith(".data")) {
      dataDir = firstComponent;
    }

    const fullPath = resolve(installDir, name);
    // Guard against zip-slip: a malicious archive must not escape installDir.
    if (fullPath !== installDir && !fullPath.startsWith(installDir)) {
      throw new Error(
        `Refusing to extract '${name}': path escapes '${installDir}'`,
      );
    }

    if (name.endsWith("/")) {
      fs.mkdirTree(fullPath);
      continue;
    }

    fs.mkdirTree(dirname(fullPath));
    fs.writeFile(fullPath, data, { canOwn: true });

    if (shouldLoadDynlib(name, extensionTags)) {
      dynlibs.push({ path: fullPath, size: data.byteLength });
    }
  }

  return { dynlibs, distInfoDir, dataDir };
}
