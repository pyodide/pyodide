#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"
#include "python2js_buffer.h"
#include "types.h"

#include <endian.h>
#include <stdint.h>

#include "hiwire.h"

// This file handles the conversion of Python buffer objects (which loosely
// represent Numpy arrays) to Javascript.

//   Converts everything to nested Javascript arrays, where the scalars are
//   standard Javascript numbers (python2js_buffer_recursive)

// clang-format off
EM_JS_REF(JsRef, _python2js_buffer_inner, (
  void* buf,
  Py_ssize_t itemsize,
  int ndim,
  char* format,
  Py_ssize_t* shape,
  Py_ssize_t* strides,
  Py_ssize_t* suboffsets
), {
  let converter = Module.get_converter(format, itemsize);
  let result = Module._python2js_buffer_recursive(buf, 0, {
    ndim,
    format,
    itemsize,
    shape,
    strides,
    suboffsets,
    converter,
  });
  return Module.hiwire.new_value(result);
});
// clang-format on

JsRef
_python2js_buffer(PyObject* x)
{
  Py_buffer view;
  if (PyObject_GetBuffer(x, &view, PyBUF_FULL_RO) == -1) {
    return NULL;
  }
  // clang-format off
  JsRef result = _python2js_buffer_inner(
    view.buf,
    view.itemsize,
    view.ndim,
    view.format,
    view.shape,
    view.strides,
    view.suboffsets
  );
  // clang-format on
  PyBuffer_Release(&view);
  return result;
}

EM_JS_NUM(errcode, python2js_buffer_init, (), {
  Module.python2js_buffer_1d_contiguous = function(ptr, stride, n, converter)
  {
    "use strict";
    let byteLength = stride * n;
    let backing = HEAP8.slice(ptr, ptr + byteLength).buffer;
    return converter(backing);
  };

  Module.python2js_buffer_1d_noncontiguous =
    function(ptr, stride, suboffset, n, itemsize, converter)
  {
    "use strict";
    let byteLength = itemsize * n;
    let buffer = new Uint8Array(byteLength);
    for (i = 0; i < n; ++i) {
      let curptr = ptr + i * stride;
      if (suboffset >= 0) {
        curptr = HEAP32[curptr / 4] + suboffset;
      }
      buffer.set(HEAP8.subarray(curptr, curptr + itemsize), i * itemsize);
    }
    return converter(buffer.buffer);
  };

  Module._python2js_buffer_recursive = function(ptr, curdim, bufferData)
  {
    "use strict";
    let n = HEAP32[bufferData.shape / 4 + curdim];
    let stride = HEAP32[bufferData.strides / 4 + curdim];
    let suboffset = -1;
    // clang-format off
    if (bufferData.suboffsets !== 0) {
      suboffset = HEAP32[bufferData.suboffsets / 4 + curdim];
    }
    if (curdim === bufferData.ndim - 1) {
      if (stride === bufferData.itemsize && suboffset < 0) {
        // clang-format on
        return Module.python2js_buffer_1d_contiguous(
          ptr, stride, n, bufferData.converter);
      } else {
        return Module.python2js_buffer_1d_noncontiguous(
          ptr, stride, suboffset, n, bufferData.itemsize, bufferData.converter);
      }
    }

    let result = [];
    for (let i = 0; i < n; ++i) {
      let curPtr = ptr + i * stride;
      if (suboffset >= 0) {
        curptr = HEAP32[curptr / 4] + suboffset;
      }
      result.push(
        Module._python2js_buffer_recursive(curPtr, curdim + 1, bufferData));
    }
    return result;
  };

  Module.get_converter = function(format, itemsize)
  {
    "use strict";
    let formatStr = UTF8ToString(format);
    if (formatStr.length > 2) {
      throw new Error(
        `Expected format string to have length <= 2, got '${formatStr}'`);
    }
    let formatChar = formatStr.slice(-1);
    let alignChar = formatStr.slice(0, -1);
    // clang-format off
    let swap = alignChar === "!" || alignChar === ">";
    // clang-format on
    let swapFunc;
    if (!swap) {
      // clang-format off
      swapFunc = buff => buff;
      // clang-format on
    } else {
      let getFuncName;
      let setFuncName;
      switch (itemsize) {
        case 2:
          getFuncName = "getUint16";
          setFuncName = "setUint16";
        case 4:
          getFuncName = "getUint32";
          setFuncName = "setUint32";
        case 8:
          getFuncName = "getFloat64";
          setFuncName = "setFloat64";
      }
      swapFunc = function(buff, size)
      {
        let dataview = new DataView(buff);
        let getFunc = dataview[getFuncName];
        let setFunc = dataview[setFuncName];
        for (let byte = 0; byte < dataview.byteLength; byte += itemsize) {
          // Get value as little endian, set back as big endian.
          setFunc(byte, getFunc(byte, true), false);
        }
        return buff;
      }
    }
    // clang-format off
    switch (formatChar) {
      case 'c':
        let decoder = new TextDecoder("utf8");
        return (buff) => decoder.decode(buff);
      case 'b':
        return (buff) => new Int8Array(buff);
      case 'B':
        return (buff) => new Uint8Array(buff);
      case '?':
        return (buff) => Array.from(new Uint8Array(buff)).map(x => !!x);
      case 'h':
        return (buff) => new Int16Array(swapFunc(buff));
      case 'H':
        return (buff) => new Uint16Array(swapFunc(buff));
      case 'i':
      case 'l':
      case 'n':
        return (buff) => new Int32Array(swapFunc(buff));
        return "getInt32";
      case 'I':
      case 'L':
      case 'N':
        return (buff) => new Uint32Array(swapFunc(buff));
      case 'q':
        return (buff) => new BigInt64Array(swapFunc(buff));
      case 'Q':
        return (buff) => new BigUint64Array(swapFunc(buff));
      case 'f':
        return (buff) => new Float32Array(swapFunc(buff));
      case 'd':
        return (buff) => new Float64Array(swapFunc(buff));
      default:
        throw new Error(`Unrecognized format character '${formatChar}'`);
    }
    // clang-format on
  };
});
