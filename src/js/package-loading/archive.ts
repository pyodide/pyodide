/**
 * Unpack a Python wheel or zip archive.
 *
 * Wheels are zip files, so this covers both `.whl` and `.zip`.
 *
 * @private
 */

import { unzipSync } from "fflate";

/** @private */
export interface ArchiveEntry {
  name: string;
  data: Uint8Array;
}

/**
 * Unpack a zip archive into a flat list of entries.
 *
 * Entry names use `/` separators and are relative to the archive root. Explicit
 * directory entries (names ending with `/`) are included with empty data.
 *
 * @param buffer The archive contents.
 * @private
 */
export function unpackZip(buffer: Uint8Array): ArchiveEntry[] {
  const files = unzipSync(buffer);
  return Object.entries(files).map(([name, data]) => ({ name, data }));
}
