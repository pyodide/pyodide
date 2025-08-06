// @ts-nocheck
// Port of https://github.com/stacktracejs/error-stack-parser
// Rewritten to ES6 and removed UMD and CommonJS support.
// Removed old opera support.

import StackFrame from "./stackframe";

declare namespace ErrorStackParser {
	export type { StackFrame };
	/**
	 * Given an Error object, extract the most information from it.
	 *
	 * @param {Error} error object
	 * @return {Array} of StackFrames
	 */
	export function parse(error: Error): StackFrame[];
}

function ErrorStackParser() {
	var CHROME_IE_STACK_REGEXP = /^\s*at .*(\S+:\d+|\(native\))/m;
	var SAFARI_NATIVE_CODE_REGEXP = /^(eval@)?(\[native code])?$/;

	return {
		/**
		 * Given an Error object, extract the most information from it.
		 *
		 * @param {Error} error object
		 * @return {Array} of StackFrames
		 */
		parse: function ErrorStackParser$$parse(error: Error): StackFrame[] {
			if (error.stack && error.stack.match(CHROME_IE_STACK_REGEXP)) {
				return this.parseV8OrIE(error);
			} else if (error.stack) {
				return this.parseFFOrSafari(error);
			} else {
				throw new Error("Cannot parse given Error object");
			}
		},

		// Separate line and column numbers from a string of the form: (URI:Line:Column)
		extractLocation: function ErrorStackParser$$extractLocation(urlLike) {
			// Fail-fast but return locations like "(native)"
			if (urlLike.indexOf(":") === -1) {
				return [urlLike];
			}

			var regExp = /(.+?)(?::(\d+))?(?::(\d+))?$/;
			var parts = regExp.exec(urlLike.replace(/[()]/g, ""));
			return [parts[1], parts[2] || undefined, parts[3] || undefined];
		},

		parseV8OrIE: function ErrorStackParser$$parseV8OrIE(error) {
			var filtered = error.stack.split("\n").filter(function (line) {
				return !!line.match(CHROME_IE_STACK_REGEXP);
			}, this);

			return filtered.map(function (line) {
				if (line.indexOf("(eval ") > -1) {
					// Throw away eval information until we implement stacktrace.js/stackframe#8
					line = line
						.replace(/eval code/g, "eval")
						.replace(/(\(eval at [^()]*)|(,.*$)/g, "");
				}
				var sanitizedLine = line
					.replace(/^\s+/, "")
					.replace(/\(eval code/g, "(")
					.replace(/^.*?\s+/, "");

				// capture and preserve the parenthesized location "(/foo/my bar.js:12:87)" in
				// case it has spaces in it, as the string is split on \s+ later on
				var location = sanitizedLine.match(/ (\(.+\)$)/);

				// remove the parenthesized location from the line, if it was matched
				sanitizedLine = location
					? sanitizedLine.replace(location[0], "")
					: sanitizedLine;

				// if a location was matched, pass it to extractLocation() otherwise pass all sanitizedLine
				// because this line doesn't have function name
				var locationParts = this.extractLocation(
					location ? location[1] : sanitizedLine,
				);
				var functionName = (location && sanitizedLine) || undefined;
				var fileName =
					["eval", "<anonymous>"].indexOf(locationParts[0]) > -1
						? undefined
						: locationParts[0];

				return new StackFrame({
					functionName: functionName,
					fileName: fileName,
					lineNumber: locationParts[1],
					columnNumber: locationParts[2],
					source: line,
				});
			}, this);
		},

		parseFFOrSafari: function ErrorStackParser$$parseFFOrSafari(error) {
			var filtered = error.stack.split("\n").filter(function (line) {
				return !line.match(SAFARI_NATIVE_CODE_REGEXP);
			}, this);

			return filtered.map(function (line) {
				// Throw away eval information until we implement stacktrace.js/stackframe#8
				if (line.indexOf(" > eval") > -1) {
					line = line.replace(
						/ line (\d+)(?: > eval line \d+)* > eval:\d+:\d+/g,
						":$1",
					);
				}

				if (line.indexOf("@") === -1 && line.indexOf(":") === -1) {
					// Safari eval frames only have function names and nothing else
					return new StackFrame({
						functionName: line,
					});
				} else {
					var functionNameRegex = /((.*".+"[^@]*)?[^@]*)(?:@)/;
					var matches = line.match(functionNameRegex);
					var functionName = matches && matches[1] ? matches[1] : undefined;
					var locationParts = this.extractLocation(
						line.replace(functionNameRegex, ""),
					);

					return new StackFrame({
						functionName: functionName,
						fileName: locationParts[0],
						lineNumber: locationParts[1],
						columnNumber: locationParts[2],
						source: line,
					});
				}
			}, this);
		},
	};
}

const errorStackParser = new ErrorStackParser();

export { StackFrame };
export default errorStackParser;
