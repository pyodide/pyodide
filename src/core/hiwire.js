JS_FILE(hiwire_init, () => {
  0, 0; /* Magic, see include_js_file.h */

  let _hiwire = {
    objects: [null],
    slotInfo: new Uint32Array(0),
    slotInfoSize: 0,
    freeHead: 1,
    // The reverse of the object maps, needed to deduplicate keys so that key
    // equality is object identity.
    obj_to_key: new Map(),
    stack: [],
    // Actual 0 is reserved for NULL so we have to leave a space for it.
    immortals: [null],
  };
  HIWIRE_INIT_CONSTS();

  DEBUG_INIT(() => {
    Hiwire._hiwire = _hiwire;
  });
  Hiwire.new_stack = function (jsval) {
    const idx = _hiwire.stack.push(jsval) - 1;
    TRACEREFS("hw.new_stack", (idx << 2) | 2, idx, jsval);
    return (idx << 2) | 2;
  };

  Hiwire.new_value = function (jsval) {
    const index = _hiwire.freeHead;
    const info = _hiwire.slotInfo[index];
    _hiwire.objects[index] = jsval;
    _hiwire.freeHead =
      (info & INDEX_REFCOUNT_MASK) >> 1 || _hiwire.objects.length;
    if (index >= _hiwire.slotInfoSize) {
      _hiwire.slotInfoSize += 1 << 10;
      const old = _hiwire.slotInfo;
      _hiwire.slotInfo = new Uint32Array(_hiwire.slotInfoSize);
      _hiwire.slotInfo.set(old);
    }
    _hiwire.slotInfo[index] = (info & ~INDEX_REFCOUNT_MASK) | 3;
    const version = info >> VERSION_SHIFT;
    const idval = (version << VERSION_SHIFT) | (index << 1) | 1;
    TRACEREFS("hw.new_value", index, idval, jsval);
    return idval;
  };

  Hiwire.intern_object = function (obj) {
    const id = (_hiwire.immortals.push(obj) - 1) << 2;
    _hiwire.obj_to_key.set(obj, id);
    return id;
  };

  // clang-format off
  // for testing purposes.
  Hiwire.num_keys = function () {
    return Object.keys(_hiwire.objects).length;
  };

  Hiwire.stack_length = () => _hiwire.stack.length;

  Hiwire.get_value = function (idval) {
    if (!idval) {
      API.fail_test = true;
      // This might have happened because the error indicator is set. Let's
      // check.
      if (_PyErr_Occurred()) {
        // This will lead to a more helpful error message.
        let exc = _wrap_exception();
        let e = Hiwire.pop_value(exc);
        console.error(
          `Pyodide internal error: Argument '${idval}' to hiwire.get_value is falsy. ` +
            "This was probably because the Python error indicator was set when get_value was called. " +
            "The Python error that caused this was:",
          e,
        );
        throw e;
      } else {
        const msg =
          `Pyodide internal error: Argument '${idval}' to hiwire.get_value is falsy` +
          " (but error indicator is not set).";
        console.error(msg);
        throw new Error(msg);
      }
    }
    if ((idval & 3) === 0) {
      // immortal reference
      return _hiwire.immortals[idval >> 2];
    }
    if ((idval & 3) === 2) {
      // stack reference
      const idx = idval >> 2;
      if (idx >= _hiwire.stack.length) {
        API.fail_test = true;
        const msg = `Pyodide internal error : Invalid stack reference handling`;
        console.error(msg);
        throw new Error(msg);
      }
      return _hiwire.stack[idval >> 2];
    }
    const index = (idval & INDEX_REFCOUNT_MASK) >> 1;
    const idversion = idval >> VERSION_SHIFT;
    const info = _hiwire.slotInfo[index];
    const slotVersion = info >> VERSION_SHIFT;
    if (!(info & OCCUPIED_BIT) || idversion !== slotVersion) {
      API.fail_test = true;
      console.error(`Pyodide internal error: Undefined id ${idval}`);
      throw new Error(`Undefined id ${idval}`);
    }
    return _hiwire.objects[index];
  };
  // clang-format on

  Hiwire.decref = function (idval) {
    // clang-format off
    if ((idval & 3) === 0) {
      // immortal reference
      return;
    }
    if ((idval & 3) === 2) {
      // stack reference
      const idx = idval >> 2;
      TRACEREFS("hw.decref.stack", idval, idx, _hiwire.stack[idx]);
      if (idx + 1 !== _hiwire.stack.length) {
        API.fail_test = true;
        const msg = `Pyodide internal error: Invalid stack reference handling: decref index ${idx} stack size ${_hiwire.stack.length}`;
        console.error(msg);
        throw new Error(msg);
      }
      _hiwire.stack.pop();
      return;
    }
    // heap reference
    const index = (idval & INDEX_REFCOUNT_MASK) >> 1;
    TRACEREFS("hw.decref", index, idval, _hiwire.objects[index]);
    const idversion = idval >> VERSION_SHIFT;
    let info = _hiwire.slotInfo[index];
    const slotVersion = info >> VERSION_SHIFT;
    if (!(info & OCCUPIED_BIT) || idversion !== slotVersion) {
      API.fail_test = true;
      console.error(`Pyodide internal error: Undefined id ${idval}`);
      throw new Error(`Undefined id ${idval}`);
    }
    info -= 2;
    if ((info & INDEX_REFCOUNT_MASK) === 0) {
      delete _hiwire.objects[index];
      info = ((slotVersion + 1) << VERSION_SHIFT) | (_hiwire.freeHead << 1);
      _hiwire.freeHead = index;
    }
    _hiwire.slotInfo[index] = info;
  };

  Hiwire.incref = function (idval) {
    if ((idval & 3) === 0) {
      // immortal reference
      return idval;
    }
    if ((idval & 3) === 2) {
      TRACEREFS("hw.incref.stack", idval, idval >> 2, _hiwire.stack[idval]);
      // stack reference ==> move to heap
      return Hiwire.new_value(_hiwire.stack[idval >> 2]);
    }
    // heap reference
    const index = (idval & INDEX_REFCOUNT_MASK) >> 1;
    TRACEREFS("hw.incref", index, idval, _hiwire.objects[index]);
    const idversion = idval >> VERSION_SHIFT;
    let info = _hiwire.slotInfo[index];
    const slotVersion = info >> VERSION_SHIFT;
    if (!(info & OCCUPIED_BIT) || idversion !== slotVersion) {
      API.fail_test = true;
      console.error(`Pyodide internal error: Undefined id ${idval}`);
      throw new Error(`Undefined id ${idval}`);
    }
    _hiwire.slotInfo[index] += 2;
    return idval;
  };
  // clang-format on

  Hiwire.pop_value = function (idval) {
    let result = Hiwire.get_value(idval);
    Hiwire.decref(idval);
    return result;
  };

  // This is factored out primarily for testing purposes.
  Hiwire.isPromise = function (obj) {
    try {
      // clang-format off
      return !!obj && typeof obj.then === "function";
      // clang-format on
    } catch (e) {
      return false;
    }
  };

  /**
   * Turn any ArrayBuffer view or ArrayBuffer into a Uint8Array.
   *
   * This respects slices: if the ArrayBuffer view is restricted to a slice of
   * the backing ArrayBuffer, we return a Uint8Array that shows the same slice.
   */
  API.typedArrayAsUint8Array = function (arg) {
    // clang-format off
    if (ArrayBuffer.isView(arg)) {
      // clang-format on
      return new Uint8Array(arg.buffer, arg.byteOffset, arg.byteLength);
    } else {
      return new Uint8Array(arg);
    }
  };

  {
    let dtypes_str = ["b", "B", "h", "H", "i", "I", "f", "d"].join(
      String.fromCharCode(0),
    );
    let dtypes_ptr = stringToNewUTF8(dtypes_str);
    let dtypes_map = {};
    for (let [idx, val] of Object.entries(dtypes_str)) {
      dtypes_map[val] = dtypes_ptr + Number(idx);
    }

    let buffer_datatype_map = new Map([
      ["Int8Array", [dtypes_map["b"], 1, true]],
      ["Uint8Array", [dtypes_map["B"], 1, true]],
      ["Uint8ClampedArray", [dtypes_map["B"], 1, true]],
      ["Int16Array", [dtypes_map["h"], 2, true]],
      ["Uint16Array", [dtypes_map["H"], 2, true]],
      ["Int32Array", [dtypes_map["i"], 4, true]],
      ["Uint32Array", [dtypes_map["I"], 4, true]],
      ["Float32Array", [dtypes_map["f"], 4, true]],
      ["Float64Array", [dtypes_map["d"], 8, true]],
      // These last two default to Uint8. They have checked : false to allow use
      // with other types.
      ["DataView", [dtypes_map["B"], 1, false]],
      ["ArrayBuffer", [dtypes_map["B"], 1, false]],
    ]);

    /**
     * This gets the dtype of a ArrayBuffer or ArrayBuffer view. We return a
     * triple: [char* format_ptr, int itemsize, bool checked] If argument is
     * untyped (a DataView or ArrayBuffer) then we say it's a Uint8, but we set
     * the flag checked to false in that case so we allow assignment to/from
     * anything.
     *
     * This is the API for use from JavaScript, there's also an EM_JS
     * hiwire_get_buffer_datatype wrapper for use from C. Used in js2python and
     * in jsproxy.c for buffers.
     */
    Module.get_buffer_datatype = function (jsobj) {
      return buffer_datatype_map.get(jsobj.constructor.name) || [0, 0, false];
    };
  }

  Module.iterObject = function* (object) {
    for (let k in object) {
      if (Object.prototype.hasOwnProperty.call(object, k)) {
        yield k;
      }
    }
  };
  return 0;
});
