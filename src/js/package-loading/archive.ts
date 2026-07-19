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
 * Unpack an archive, dispatching on the file extension.
 *
 * @param buffer The archive contents.
 * @param filename The archive file name, used to select the format.
 * @private
 */
export function unpackArchive(
  buffer: Uint8Array,
  filename: string,
): ArchiveEntry[] {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".whl") || lower.endsWith(".zip")) {
    return unpackZip(buffer);
  }
  if (lower.endsWith(".tar")) {
    return unpackTar(buffer);
  }

  throw new Error(`Unsupported archive format: ${filename}`);
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

const TAR_BLOCK_SIZE = 512;
let tarTextDecoder: TextDecoder | undefined;


// Cache TextDecoder to avoid creating new instances
// We cannot use global TextDecoder because it may not be available in all environments (e.g. D8)
function getTarTextDecoder(): TextDecoder {
  if (!tarTextDecoder) {
    tarTextDecoder = new TextDecoder();
  }
  return tarTextDecoder;
}

/**
 * Unpack an uncompressed tar archive into a flat list of entries.
 *
 * TODO: This is a temporary implementation to handle unvendored-tests in Pyodide lockfile
 *       that are stored as uncompressed tar archive. Maybe replace it to zip or something else
 *       so we don't need to maintain this implementation.
 *
 * Handles ustar `name`/`prefix` fields plus GNU (`L`) and PAX (`x`) long-name
 * headers so deep paths are decoded correctly. Entry names use `/` separators;
 * directory entries end with `/` and carry empty data.
 *
 * @param buffer The archive contents.
 * @private
 */
export function unpackTar(buffer: Uint8Array): ArchiveEntry[] {
  const entries: ArchiveEntry[] = [];
  let offset = 0;
  let longName: string | undefined;

  while (offset + TAR_BLOCK_SIZE <= buffer.length) {
    const header = buffer.subarray(offset, offset + TAR_BLOCK_SIZE);
    // Two consecutive zero blocks mark the end of the archive.
    if (header[0] === 0) {
      break;
    }

    const size = readOctal(header, 124, 12);
    const typeflag = String.fromCharCode(header[156] || 0x30);
    const dataStart = offset + TAR_BLOCK_SIZE;
    const data = buffer.subarray(dataStart, dataStart + size);
    offset = dataStart + Math.ceil(size / TAR_BLOCK_SIZE) * TAR_BLOCK_SIZE;

    if (typeflag === "L") {
      // GNU long name: this block's data is the name of the next entry.
      longName = stripNull(getTarTextDecoder().decode(data));
      continue;
    }
    if (typeflag === "x") {
      // PAX extended header: a `path=` record overrides the next entry's name.
      const path = parsePaxPath(getTarTextDecoder().decode(data));
      if (path !== undefined) {
        longName = path;
      }
      continue;
    }
    if (typeflag === "g") {
      continue;
    }

    const name = longName ?? readTarName(header);
    longName = undefined;

    if (typeflag === "5") {
      entries.push({ name: name.endsWith("/") ? name : name + "/", data });
      continue;
    }
    if (typeflag === "0" || typeflag === "\0") {
      entries.push({ name, data });
    }
  }

  return entries;
}

function readTarName(header: Uint8Array): string {
  const name = stripNull(getTarTextDecoder().decode(header.subarray(0, 100)));
  const prefix = stripNull(getTarTextDecoder().decode(header.subarray(345, 500)));
  return prefix ? `${prefix}/${name}` : name;
}

function readOctal(header: Uint8Array, start: number, length: number): number {
  const text = getTarTextDecoder().decode(header.subarray(start, start + length));
  const trimmed = text.replace(/[\0 ]+$/, "").trim();
  return trimmed ? parseInt(trimmed, 8) : 0;
}

function stripNull(value: string): string {
  const end = value.indexOf("\0");
  return end === -1 ? value : value.slice(0, end);
}

function parsePaxPath(record: string): string | undefined {
  // PAX records have the form "<len> <key>=<value>\n".
  for (const line of record.split("\n")) {
    const eq = line.indexOf("=");
    if (eq === -1) {
      continue;
    }
    const key = line.slice(0, eq).split(" ").pop();
    if (key === "path") {
      return line.slice(eq + 1);
    }
  }
  return undefined;
}
