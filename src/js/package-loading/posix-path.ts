/**
 * Minimal pure POSIX path helpers.
 *
 * Note: These helper functions already exist in Emscripten's FS / PATH utilities,
 * but we define them here to avoid dependencies on Emscripten.
 * This helps keep the package extraction logic self-contained and testable.
 *
 * @private
 */

/** @private */
export function basename(path: string): string {
  const idx = path.lastIndexOf("/");
  return idx === -1 ? path : path.slice(idx + 1);
}

/** @private */
export function dirname(path: string): string {
  const idx = path.lastIndexOf("/");
  if (idx === -1) {
    return "";
  }
  return idx === 0 ? "/" : path.slice(0, idx);
}

/**
 * Resolve `relative` against the absolute directory `base`, collapsing `.` and
 * `..` segments. The result is always absolute.
 *
 * @private
 */
export function resolve(base: string, relative: string): string {
  const combined = relative.startsWith("/") ? relative : `${base}/${relative}`;
  const out: string[] = [];
  for (const segment of combined.split("/")) {
    if (segment === "" || segment === ".") {
      continue;
    }
    if (segment === "..") {
      out.pop();
      continue;
    }
    out.push(segment);
  }
  return "/" + out.join("/");
}
