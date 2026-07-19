/**
 * Minimal pure POSIX path helpers, so package extraction does not depend on
 * Emscripten's `Module.PATH` (which keeps it unit-testable).
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
export function resolvePosix(base: string, relative: string): string {
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
