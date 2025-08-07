/**
 * @hidden
 */
export function withTrailingSlash<T extends string | undefined>(path: T): T {
  if (path === undefined) {
    return path;
  }

  if (path.endsWith("/")) {
    return path;
  }
  return (path + "/") as T;
}
