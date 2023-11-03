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

export type { TypedArray } from "./types";

export type { PythonError } from "../core/error_handling";

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
 * See :ref:`js-api-pyodide-ffi`
 * @hidetype
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
