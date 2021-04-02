JS_FILE(python2js_buffer_init, () => {
  0, 0; /* Magic, see include_js_file.h */

  /**
   * Determine type and endianness of data from format. This is a helper
   * function for converting buffers from Python to Javascript, used in
   * PyProxyBufferMethods and in `toJs` on a buffer.
   *
   * To understand this function it will be helpful to look at the tables here:
   * https://docs.python.org/3/library/struct.html#format-strings
   *
   * @arg format {String} A Python format string (caller must convert it to a
   *      Javascript string).
   * @arg errorMessage {String} Extra stuff to append to an error message if
   *      thrown. Should be a complete sentence.
   * @returns A pair, an appropriate TypedArray constructor and a boolean which
   *      is true if the format suggests a big endian array.
   * @private
   */
  Module.processBufferFormatString = function(formatStr, errorMessage = "") {
    if (formatStr.length > 2) {
      throw new Error("Expected format string to have length <= 2, " +
                      `got '${formatStr}'.` + errorMessage);
    }
    let formatChar = formatStr.slice(-1);
    let alignChar = formatStr.slice(0, -1);
    let bigEndian;
    switch (alignChar) {
    case "!":
    case ">":
      bigEndian = true;
      break;
    case "<":
    case "@":
    case "=":
    case "":
      bigEndian = false;
      break;
    default:
      throw new Error(`Unrecognized alignment character ${alignChar}.` +
                      errorMessage);
    }
    let arrayType;
    switch (formatChar) {
    case 'b':
      arrayType = Int8Array;
      break;
    case 's':
    case 'p':
    case 'c':
    case 'B':
    case '?':
      arrayType = Uint8Array;
      break;
    case 'h':
      arrayType = Int16Array;
      break;
    case 'H':
      arrayType = Uint16Array;
      break;
    case 'i':
    case 'l':
    case 'n':
      arrayType = Int32Array;
      break;
    case 'I':
    case 'L':
    case 'N':
    case 'P':
      arrayType = Uint32Array;
      break;
    case 'q':
      // clang-format off
            if (globalThis.BigInt64Array === undefined) {
        // clang-format on
        throw new Error("BigInt64Array is not supported on this browser." +
                        errorMessage);
      }
      arrayType = BigInt64Array;
      break;
    case 'Q':
      // clang-format off
            if (globalThis.BigUint64Array === undefined) {
        // clang-format on
        throw new Error("BigUint64Array is not supported on this browser." +
                        errorMessage);
      }
      arrayType = BigUint64Array;
      break;
    case 'f':
      arrayType = Float32Array;
      break;
    case 'd':
      arrayType = Float64Array;
      break;
    case "e":
      throw new Error("Javascript has no Float16 support.");
    default:
      throw new Error(`Unrecognized format character '${formatChar}'.` +
                      errorMessage);
    }
    return [ arrayType, bigEndian ];
  };

  Module.python2js_buffer_1d_contiguous = function(ptr, stride, n, converter) {
    "use strict";
    let byteLength = stride * n;
    let backing = HEAP8.slice(ptr, ptr + byteLength).buffer;
    return converter(backing);
  };

  Module.python2js_buffer_1d_noncontiguous = function(ptr, stride, suboffset, n,
                                                      itemsize, converter) {
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

  Module._python2js_buffer_recursive = function(ptr, curdim, bufferData) {
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
        return Module.python2js_buffer_1d_contiguous(ptr, stride, n,
                                                     bufferData.converter);
      } else {
        return Module.python2js_buffer_1d_noncontiguous(ptr, stride, suboffset,
                                                        n, bufferData.itemsize,
                                                        bufferData.converter);
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

  Module.get_converter = function(format, itemsize) {
    "use strict";
    let formatStr = UTF8ToString(format);
    let [ArrayType, bigEndian] = Module.processBufferFormatString(formatStr);
    let formatChar = formatStr.slice(-1);
    // clang-format off
    switch (formatChar) {
      case "c":
        let decoder = new TextDecoder("utf8");
        return (buff) => decoder.decode(buff);
      case "?":
        return (buff) => Array.from(new Uint8Array(buff)).map(x => !!x);
    }
    // clang-format on

    if (!bigEndian) {
      // clang-format off
      return buff => new ArrayType(buff);
      // clang-format on
    }
    let getFuncName;
    let setFuncName;
    switch (itemsize) {
    case 2:
      getFuncName = "getUint16";
      setFuncName = "setUint16";
      break;
    case 4:
      getFuncName = "getUint32";
      setFuncName = "setUint32";
      break;
    case 8:
      getFuncName = "getFloat64";
      setFuncName = "setFloat64";
      break;
    default:
      // clang-format off
        throw new Error(`Unexpected size ${ itemsize }`);
      // clang-format on
    }
    function swapFunc(buff) {
      let dataview = new DataView(buff);
      let getFunc = dataview[getFuncName].bind(dataview);
      let setFunc = dataview[setFuncName].bind(dataview);
      for (let byte = 0; byte < dataview.byteLength; byte += itemsize) {
        // Get value as little endian, set back as big endian.
        setFunc(byte, getFunc(byte, true), false);
      }
      return buff;
    }
    // clang-format off
    return buff => new ArrayType(swapFunc(buff));
    // clang-format on
  };
});
