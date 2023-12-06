/**
 * Utility functions for packaging.
 * This file contains some TypeScript port of Python's packaging library and some other functions.
 **/

const canonicalizeNameRegex = /[-_.]+/g;

/**
 * Normalize a package name. Port of Python's packaging.utils.canonicalize_name.
 * @param name The package name to normalize.
 * @returns The normalized package name.
 * @private
 */
export function canonicalizePackageName(name: string): string {
  return name.replace(canonicalizeNameRegex, "-").toLowerCase();
}

// Regexp for validating package name and URI
const packageUriRegex = /^.*?([^\/]*)\.whl$/;

/**
 * Extract package name from a wheel URI.
 * TODO: validate if the URI is a valid wheel URI.
 * @param packageUri The wheel URI.
 * @returns The package name.
 * @private
 */
export function uriToPackageName(packageUri: string): string | undefined {
  let match = packageUriRegex.exec(packageUri);
  if (match) {
    const wheelName = match[1].toLowerCase();
    const pkgName = wheelName.split("-").slice(0, -4).join("-");
    return canonicalizePackageName(pkgName);
  }
}
