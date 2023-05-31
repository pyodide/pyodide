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
  TypedArray,
} from "./pyproxy.gen";

export type { PythonError } from "./error_handling.gen";

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
} from "./pyproxy.gen";

import { PythonError } from "./error_handling.gen";

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
