JS_FILE(python2js_buffer_init, () => {
  0, 0; /* Magic, see include_js_file.h */

  /**
   * Determine type and endianness of data from format. This is a helper
   * function for converting buffers from Python to JavaScript, used in
   * PyProxyBufferMethods and in `toJs` on a buffer.
   *
   * To understand this function it will be helpful to look at the tables here:
   * https://docs.python.org/3/library/struct.html#format-strings
   *
   * @arg format {String} A Python format string (caller must convert it to a
   *      JavaScript string).
   * @arg errorMessage {String} Extra stuff to append to an error message if
   *      thrown. Should be a complete sentence.
   * @returns A pair, an appropriate TypedArray constructor and a boolean which
   *      is true if the format suggests a big endian array.
   * @private
   */
  Module.processBufferFormatString = function (formatStr, errorMessage = "") {
    if (formatStr.length > 2) {
      throw new Error(
        "Expected format string to have length <= 2, " +
          `got '${formatStr}'.` +
          errorMessage
      );
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
        throw new Error(
          `Unrecognized alignment character ${alignChar}.` + errorMessage
        );
    }
    let arrayType;
    switch (formatChar) {
      case "b":
        arrayType = Int8Array;
        break;
      case "s":
      case "p":
      case "c":
      case "B":
      case "?":
        arrayType = Uint8Array;
        break;
      case "h":
        arrayType = Int16Array;
        break;
      case "H":
        arrayType = Uint16Array;
        break;
      case "i":
      case "l":
      case "n":
        arrayType = Int32Array;
        break;
      case "I":
      case "L":
      case "N":
      case "P":
        arrayType = Uint32Array;
        break;
      case "q":
        if (globalThis.BigInt64Array === undefined) {
          throw new Error(
            "BigInt64Array is not supported on this browser." + errorMessage
          );
        }
        arrayType = BigInt64Array;
        break;
      case "Q":
        if (globalThis.BigUint64Array === undefined) {
          throw new Error(
            "BigUint64Array is not supported on this browser." + errorMessage
          );
        }
        arrayType = BigUint64Array;
        break;
      case "f":
        arrayType = Float32Array;
        break;
      case "d":
        arrayType = Float64Array;
        break;
      case "e":
        throw new Error("Javascript has no Float16 support.");
      default:
        throw new Error(
          `Unrecognized format character '${formatChar}'.` + errorMessage
        );
    }
    return [arrayType, bigEndian];
  };

  /**
   * Convert a 1-dimensional contiguous buffer to JavaScript.
   *
   * In this case we can just slice the memory out of the wasm HEAP.
   * @param {number} ptr A pointer to the start of the buffer in wasm memory
   * @param {number} stride The size of the entries in bytes
   * @param {number} n The number of entries
   * @returns A new ArrayBuffer with the appropriate data in it (not a view of
   *  the WASM heap)
   * @private
   */
  Module.python2js_buffer_1d_contiguous = function (ptr, stride, n) {
    "use strict";
    let byteLength = stride * n;
    // Note: slice here is a copy (as opposed to subarray which is not)
    return HEAP8.slice(ptr, ptr + byteLength).buffer;
  };

  /**
   * Convert a 1d noncontiguous buffer to JavaScript.
   *
   * Since the buffer is not contiguous we have to copy it in chunks.
   * @param {number} ptr The WAM memory pointer to the start of the buffer.
   * @param {number} stride The stride in bytes between each entry.
   * @param {number} suboffset The suboffset from the Python Buffer protocol.
   *  Negative if no suboffsets. (see
   *  https://docs.python.org/3/c-api/buffer.html#c.Py_buffer.suboffsets)
   * @param {number} n The number of entries.
   * @param {number} itemsize The size in bytes of each entry.
   * @returns A new ArrayBuffer with the appropriate data in it (not a view of
   *  the WASM heap)
   * @private
   */
  Module.python2js_buffer_1d_noncontiguous = function (
    ptr,
    stride,
    suboffset,
    n,
    itemsize
  ) {
    "use strict";
    let byteLength = itemsize * n;
    // Make new memory of the appropriate size
    let buffer = new Uint8Array(byteLength);
    for (let i = 0; i < n; ++i) {
      let curptr = ptr + i * stride;
      if (suboffset >= 0) {
        curptr = DEREF_U32(curptr, 0) + suboffset;
      }
      buffer.set(HEAP8.subarray(curptr, curptr + itemsize), i * itemsize);
    }
    return buffer.buffer;
  };

  /**
   * Convert an ndarray to a nested JavaScript array, the main function.
   *
   * This is called by _python2js_buffer_inner (defined in python2js_buffer.c).
   * There are two layers of setup that need to be done to get the base case of
   * the recursion right.
   *
   * The last dimension of the array is handled by the appropriate 1d array
   * converter: python2js_buffer_1d_contiguous or
   * python2js_buffer_1d_noncontiguous.
   *
   * @param {number} ptr The pointer into the buffer
   * @param {number} curdim What dimension are we currently working on? 0 <=
   * curdim < ndim.
   * @param {number} bufferData All of the data out of the Py_buffer, plus the
   * converter function: ndim, format, itemsize, shape (a ptr), strides (a ptr),
   * suboffsets (a ptr), converter,
   * @returns A nested JavaScript array, the result of the conversion.
   * @private
   */
  Module._python2js_buffer_recursive = function (ptr, curdim, bufferData) {
    "use strict";
    // Stride and suboffset are signed, n is unsigned.
    let n = DEREF_U32(bufferData.shape, curdim);
    let stride = DEREF_I32(bufferData.strides, curdim);
    let suboffset = -1;
    if (bufferData.suboffsets !== 0) {
      suboffset = DEREF_I32(bufferData.suboffsets, curdim);
    }
    if (curdim === bufferData.ndim - 1) {
      // Last dimension, use appropriate 1d converter
      let arraybuffer;
      if (stride === bufferData.itemsize && suboffset < 0) {
        arraybuffer = Module.python2js_buffer_1d_contiguous(ptr, stride, n);
      } else {
        arraybuffer = Module.python2js_buffer_1d_noncontiguous(
          ptr,
          stride,
          suboffset,
          n,
          bufferData.itemsize
        );
      }
      return bufferData.converter(arraybuffer);
    }

    let result = [];
    for (let i = 0; i < n; ++i) {
      // See:
      // https://docs.python.org/3/c-api/buffer.html#pil-style-shape-strides-and-suboffsets
      let curPtr = ptr + i * stride;
      if (suboffset >= 0) {
        curptr = DEREF_U32(curptr, 0) + suboffset;
      }
      result.push(
        Module._python2js_buffer_recursive(curPtr, curdim + 1, bufferData)
      );
    }
    return result;
  };

  /**
   * Get the appropriate converter function.
   *
   * The converter function takes an ArrayBuffer and returns an appropriate
   * TypedArray. If the buffer is big endian, the converter will convert the
   * data to little endian.
   *
   * The converter function does something special if the format character is
   * "?" or "s". If it's "?" we return an array of booleans, if it's "s" we
   * return a string.
   *
   * @param {string} format The format character of the buffer.
   * @param {number} itemsize Should be one of 1, 2, 4, 8. Used for big endian
   * conversion.
   * @returns A converter function ArrayBuffer => TypedArray
   * @private
   */
  Module.get_converter = function (format, itemsize) {
    "use strict";
    let formatStr = UTF8ToString(format);
    let [ArrayType, bigEndian] = Module.processBufferFormatString(formatStr);
    let formatChar = formatStr.slice(-1);
    switch (formatChar) {
      case "s":
        let decoder = new TextDecoder("utf8", { ignoreBOM: true });
        return (buff) => decoder.decode(buff);
      case "?":
        return (buff) => Array.from(new Uint8Array(buff), (x) => !!x);
    }

    if (!bigEndian) {
      return (buff) => new ArrayType(buff);
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
        throw new Error(`Unexpected size ${itemsize}`);
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
    return (buff) => new ArrayType(swapFunc(buff));
  };
});
