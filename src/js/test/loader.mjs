/**
 *  An import hook to respond to .wat imports with something degenerate. We
 *  don't currently unit test the functions that use .wat imports. This is good
 *  enough for now to keep node from crashing.
 */
export function load(url, context, nextLoad) {
	if (url.endsWith(".wat")) {
		return {
			format: "json",
			source: "null",
			shortCircuit: true,
		};
	}
	return nextLoad(url);
}
