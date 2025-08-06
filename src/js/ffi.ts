export type {
	PyProxy,
	PyProxyWithLength,
	PyProxyWithGet,
	PyProxyWithSet,
	PyProxyWithHas,
	PyDict,
	PyIterable,
	PyAsyncIterable,
	PyIterator,
	PyAsyncIterator,
	PyGenerator,
	PyAsyncGenerator,
	PyAwaitable,
	PyCallable,
	PyBuffer,
	PyBufferView,
	PySequence,
	PyMutableSequence,
} from "generated/pyproxy";
export type { PythonError } from "generated/error_handling";
// These need to be imported for their side effects at startup
import "generated/js2python";
import "generated/python2js_buffer";

export type { TypedArray } from "./types";

import {
	PyProxy,
	PyProxyWithLength,
	PyProxyWithGet,
	PyProxyWithSet,
	PyProxyWithHas,
	PyDict,
	PyIterable,
	PyAsyncIterable,
	PyIterator,
	PyAsyncIterator,
	PyGenerator,
	PyAsyncGenerator,
	PyAwaitable,
	PyCallable,
	PyBuffer,
	PyBufferView,
	PySequence,
	PyMutableSequence,
} from "generated/pyproxy";

import { PythonError } from "../core/error_handling";

/**
 * Foreign function interface classes. Can be used for typescript type
 * annotations or at runtime for `instanceof` checks.
 * @summaryLink :ref:`ffi <js-api-pyodide-ffi>`
 * @hidetype
 * @omitFromAutoModule
 */
export const ffi = {
	PyProxy,
	PyProxyWithLength,
	PyProxyWithGet,
	PyProxyWithSet,
	PyProxyWithHas,
	PyDict,
	PyIterable,
	PyAsyncIterable,
	PyIterator,
	PyAsyncIterator,
	PyGenerator,
	PyAsyncGenerator,
	PyAwaitable,
	PyCallable,
	PyBuffer,
	PyBufferView,
	PythonError,
	PySequence,
	PyMutableSequence,
};
