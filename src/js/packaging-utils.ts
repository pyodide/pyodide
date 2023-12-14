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

type ParsedPackageData = {
  name: string;
  version: string;
  fileName: string;
};

// Regexp for validating package name and URI
const packageUriRegex = /^.*?([^\/]*)\.whl$/;

/**
 * Extract package name from a wheel URI.
 * TODO: validate if the URI is a valid wheel URI.
 * @param packageUri The wheel URI.
 * @returns The package name.
 * @private
 */
export function uriToPackageData(
  packageUri: string,
): ParsedPackageData | undefined {
  const match = packageUriRegex.exec(packageUri);
  if (match) {
    let wheelName = match[1].toLowerCase().split("-");
    return {
      name: wheelName[0],
      version: wheelName[1],
      fileName: wheelName.join("-") + ".whl",
    };
  }
}
