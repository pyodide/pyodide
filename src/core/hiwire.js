JS_FILE(hiwire_init, () => {
  0, 0; /* Magic, see include_js_file.h */

  // See the macros and extensive comment in hiwire.c for more info.
  const _hiwire = {
    // next free = 0 means that all slots are full, so we don't use slot 0.
    objects: [null],
    slotInfo: new Uint32Array(0),
    slotInfoSize: 0,
    freeHead: 1,
    numKeys: 0,
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
    TRACEREFS("hw.new_stack", STACK_INDEX_TO_REF(idx), idx, jsval);
    return STACK_INDEX_TO_REF(idx);
  };

  Hiwire.new_value = function (jsval) {
    const index = _hiwire.freeHead;
    const info = _hiwire.slotInfo[index];
    _hiwire.objects[index] = jsval;
    // if nextfree is 0 then we'll add a new entry to the list next
    _hiwire.freeHead = HEAP_INFO_TO_NEXTFREE(info) || _hiwire.objects.length;
    if (index >= _hiwire.slotInfoSize) {
      // we ran out of space in the slotInfo map, reallocate.
      _hiwire.slotInfoSize += 1024;
      const old = _hiwire.slotInfo;
      _hiwire.slotInfo = new Uint32Array(_hiwire.slotInfoSize);
      _hiwire.slotInfo.set(old);
    }
    _hiwire.slotInfo[index] = HEAP_NEW_OCCUPIED_INFO(info);
    const idval = HEAP_NEW_REF(index, info);
    _hiwire.numKeys++;
    TRACEREFS("hw.new_value", index, idval, jsval);
    return idval;
  };

  /**
   * Increase the reference count on an object and return a JsRef which is unique
   * to the object.
   *
   * I.e., if `Hiwire.get_value(id1) === Hiwire.get_value(id2)` then
   * hiwire_incref_deduplicate(id1) == hiwire_incref_deduplicate(id2).
   *
   * This is used for the id for JsProxies so that equality checks work correctly.
   */
  Hiwire.incref_deduplicate = function (idval) {
    const obj = Hiwire.get_value(idval);
    let result = _hiwire.obj_to_key.get(obj);
    if (result) {
      if (!IS_IMMORTAL(result)) {
        HEAP_INCREF(_hiwire.slotInfo[HEAP_REF_TO_INDEX(result)]);
      }
      return result;
    }
    // Either not present or key is out of date.
    // Use incref to force possible stack reference to heap reference.
    result = Hiwire.incref(idval);
    _hiwire.obj_to_key.set(obj, result);
    // Record that we need to remove this entry from obj_to_key when the
    // reference is freed. (Touching a map is expensive, avoid if possible!)
    _hiwire.slotInfo[HEAP_REF_TO_INDEX(result)] |= DEDUPLICATED_BIT;
    return result;
  };

  Hiwire.intern_object = function (obj) {
    const id = IMMORTAL_INDEX_TO_REF(_hiwire.immortals.push(obj) - 1);
    _hiwire.obj_to_key.set(obj, id);
    return id;
  };

  // for testing purposes.
  Hiwire.num_keys = function () {
    return _hiwire.numKeys;
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
    if (IS_IMMORTAL(idval)) {
      return _hiwire.immortals[IMMORTAL_REF_TO_INDEX(idval)];
    }
    if (IS_STACK(idval)) {
      const idx = STACK_REF_TO_INDEX(idval);
      if (idx >= _hiwire.stack.length) {
        API.fail_test = true;
        const msg = `Pyodide internal error : Invalid stack reference handling`;
        console.error(msg);
        throw new Error(msg);
      }
      return _hiwire.stack[idx];
    }
    const index = HEAP_REF_TO_INDEX(idval);
    const info = _hiwire.slotInfo[index];
    if (HEAP_REF_IS_OUT_OF_DATE(idval, info)) {
      API.fail_test = true;
      console.error(`Pyodide internal error: Undefined id ${idval}`);
      throw new Error(`Undefined id ${idval}`);
    }
    return _hiwire.objects[index];
  };

  Hiwire.decref = function (idval) {
    if (IS_IMMORTAL(idval)) {
      return;
    }
    if (IS_STACK(idval)) {
      const idx = STACK_REF_TO_INDEX(idval);
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
    const index = HEAP_REF_TO_INDEX(idval);
    TRACEREFS("hw.decref", index, idval, _hiwire.objects[index]);
    let info = _hiwire.slotInfo[index];
    if (HEAP_REF_IS_OUT_OF_DATE(idval, info)) {
      API.fail_test = true;
      console.error(`Pyodide internal error: Undefined id ${idval}`);
      throw new Error(`Undefined id ${idval}`);
    }
    HEAP_DECREF(info);
    if (HEAP_IS_REFCNT_ZERO(info)) {
      if (HEAP_IS_DEDUPLICATED(info)) {
        _hiwire.obj_to_key.delete(_hiwire.objects[index]);
      }
      // Note: it's 100x faster to set the value to `undefined` than to `delete` it.
      _hiwire.objects[index] = undefined;
      _hiwire.numKeys--;
      info = FREE_LIST_INFO(info, _hiwire.freeHead);
      _hiwire.freeHead = index;
    }
    _hiwire.slotInfo[index] = info;
  };

  Hiwire.incref = function (idval) {
    if (IS_IMMORTAL(idval)) {
      return idval;
    }
    if (IS_STACK(idval)) {
      const idx = STACK_REF_TO_INDEX(idx);
      TRACEREFS("hw.incref.stack", idval, idx, _hiwire.stack[idx]);
      // stack reference ==> move to heap
      return Hiwire.new_value(_hiwire.stack[idx]);
    }
    // heap reference
    const index = HEAP_REF_TO_INDEX(idval);
    TRACEREFS("hw.incref", index, idval, _hiwire.objects[index]);
    const info = _hiwire.slotInfo[index];
    if (HEAP_REF_IS_OUT_OF_DATE(idval, info)) {
      API.fail_test = true;
      console.error(`Pyodide internal error: Undefined id ${idval}`);
      throw new Error(`Undefined id ${idval}`);
    }
    HEAP_INCREF(_hiwire.slotInfo[index]);
    return idval;
  };

  Hiwire.pop_value = function (idval) {
    let result = Hiwire.get_value(idval);
    Hiwire.decref(idval);
    return result;
  };

  // This is factored out primarily for testing purposes.
  Hiwire.isPromise = function (obj) {
    try {
      return !!obj && typeof obj.then === "function";
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
    if (ArrayBuffer.isView(arg)) {
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
