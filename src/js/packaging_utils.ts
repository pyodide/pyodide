/**
 * Utility functions for packaging.
 * This file contains some TypeScript port of Python's packaging library and some other functions.
 **/

const canonicalizeNameRegex = /[-_.]+/g;

/**
 * Normalize a package name. Port of Python's packaging.utils.canonicalize_name.
 * @param package_name The package name to normalize.
 * @returns The normalized package name.
 */
export function canonicalizePackageName(name: string): string {
    return name.replace(canonicalizeNameRegex, '-').toLowerCase();
}

// Regexp for validating package name and URI
const packageUriRegex = /^.*?([^\/]*)\.whl$/;

/**
 * Extract package name from a wheel URI.
 * TODO: validate if the URI is a valid wheel URI.
 * @param packageUri The wheel URI.
 * @returns The package name.
 */
export function uriToPackageName(packageUri: string): string | undefined {
  let match = packageUriRegex.exec(packageUri);
  if (match) {
    let wheel_name = match[1].toLowerCase();
    return wheel_name.split("-").slice(0, -4).join("-");
  }
}