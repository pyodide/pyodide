import { _PropagatePythonError as PropagateError } from "generated/error_handling";

function js2python_string(value) {
  // The general idea here is to allocate a Python string and then
  // have JavaScript write directly into its buffer.  We first need
  // to determine if is needs to be a 1-, 2- or 4-byte string, since
  // Python handles all 3.
  let max_code_point = 0;
  const code_points = [];
  for (let c of value) {
    let code_point = c.codePointAt(0);
    code_points.push(code_point);
    max_code_point = code_point > max_code_point ? code_point : max_code_point;
  }

  let num_code_points = code_points.length;
  let result = _PyUnicode_New(num_code_points, max_code_point);
  if (result === 0) {
    throw new PropagateError();
  }

  let ptr = _PyUnicode_Data(result);
  if (max_code_point > 0xffff) {
    for (let i = 0; i < num_code_points; i++) {
      ASSIGN_U32(ptr, 0, code_points[i]);
      ptr += 4;
    }
  } else if (max_code_point > 0xff) {
    for (let i = 0; i < num_code_points; i++) {
      ASSIGN_U16(ptr, 0, code_points[i]);
      ptr += 2;
    }
  } else {
    for (let i = 0; i < num_code_points; i++) {
      ASSIGN_U8(ptr, 0, code_points[i]);
      ptr += 1;
    }
  }

  return result;
}

function js2python_bigint(value) {
  let value_orig = value;
  let length = 0;
  if (value < 0) {
    value = -value;
  }
  value <<= BigInt(1);
  while (value) {
    length++;
    value >>= BigInt(32);
  }
  const orig = stackSave();
  const ptr = stackAlloc(length * 4);
  value = value_orig;
  for (let i = 0; i < length; i++) {
    ASSIGN_U32(ptr, i, Number(value & BigInt(0xffffffff)));
    value >>= BigInt(32);
  }
  const res = __PyLong_FromByteArray(
    ptr,
    length * 4 /* length in bytes */,
    true /* little endian */,
    true /* signed? */,
  );
  stackRestore(orig);
  return res;
}

/**
 * This function converts immutable types. numbers, bigints, strings,
 * booleans, undefined, and null are converted. PyProxies are unwrapped.
 *
 * If `value` is of any other type then `undefined` is returned.
 *
 * If `value` is one of those types but an error is raised during conversion,
 * we throw a PropagateError to propagate the error out to C. This causes
 * special handling in the EM_JS wrapper.
 */
function js2python_convertImmutable(value) {
  let result = js2python_convertImmutableInner(value);
  if (result === 0) {
    throw new PropagateError();
  }
  return result;
}
// js2python_convertImmutable is used from js2python.c so we need to add it
// to Module.
Module.js2python_convertImmutable = js2python_convertImmutable;

/**
 * Returns a pointer to a Python object, 0, or undefined.
 *
 * If we return 0 it means we tried to convert but an error occurred, if we
 * return undefined, no conversion was attempted.
 */
function js2python_convertImmutableInner(value) {
  let type = typeof value;
  if (type === "string") {
    return js2python_string(value);
  } else if (type === "number") {
    if (Number.isSafeInteger(value)) {
      return _PyLong_FromDouble(value);
    } else {
      return _PyFloat_FromDouble(value);
    }
  } else if (type === "bigint") {
    return js2python_bigint(value);
  } else if (value === undefined || value === null) {
    return __js2python_none();
  } else if (value === true) {
    return __js2python_true();
  } else if (value === false) {
    return __js2python_false();
  } else if (API.isPyProxy(value)) {
    const { props, shared } = Module.PyProxy_getAttrs(value);
    if (props.roundtrip) {
      return _JsProxy_create(value);
    } else {
      return __js2python_pyproxy(shared.ptr);
    }
  }
  return undefined;
}

function js2python_convertList(obj, context) {
  let list = _PyList_New(obj.length);
  if (list === 0) {
    return 0;
  }
  let item = 0;
  try {
    context.cache.set(obj, list);
    for (let i = 0; i < obj.length; i++) {
      item = js2python_convert_with_context(obj[i], context);
      // PyList_SetItem steals a reference to item no matter what
      _Py_IncRef(item);
      if (_PyList_SetItem(list, i, item) === -1) {
        throw new PropagateError();
      }
      _Py_DecRef(item);
      item = 0;
    }
  } catch (e) {
    _Py_DecRef(item);
    _Py_DecRef(list);
    throw e;
  }

  return list;
}

function js2python_convertMap(obj, entries, context) {
  let dict = _PyDict_New();
  if (dict === 0) {
    return 0;
  }
  let key_py = 0;
  let value_py = 0;
  try {
    context.cache.set(obj, dict);
    for (let [key_js, value_js] of entries) {
      key_py = js2python_convertImmutable(key_js);
      if (key_py === undefined) {
        let key_type =
          (key_js.constructor && key_js.constructor.name) || typeof key_js;
        throw new Error(
          `Cannot use key of type ${key_type} as a key to a Python dict`,
        );
      }
      value_py = js2python_convert_with_context(value_js, context);

      if (_PyDict_SetItem(dict, key_py, value_py) === -1) {
        throw new PropagateError();
      }
      _Py_DecRef(key_py);
      key_py = 0;
      _Py_DecRef(value_py);
      value_py = 0;
    }
  } catch (e) {
    _Py_DecRef(key_py);
    _Py_DecRef(value_py);
    _Py_DecRef(dict);
    throw e;
  }
  return dict;
}

function js2python_convertSet(obj, context) {
  let set = _PySet_New(0);
  if (set === 0) {
    return 0;
  }
  let key_py = 0;
  try {
    context.cache.set(obj, set);
    for (let key_js of obj) {
      key_py = js2python_convertImmutable(key_js);
      if (key_py === undefined) {
        let key_type =
          (key_js.constructor && key_js.constructor.name) || typeof key_js;
        throw new Error(
          `Cannot use key of type ${key_type} as a key to a Python set`,
        );
      }
      const err = _PySet_Add(set, key_py);
      if (err === -1) {
        throw new PropagateError();
      }
      _Py_DecRef(key_py);
      key_py = 0;
    }
  } catch (e) {
    _Py_DecRef(key_py);
    _Py_DecRef(set);
    throw e;
  }
  return set;
}

function checkBoolIntCollision(obj, ty) {
  if (obj.has(1) && obj.has(true)) {
    throw new Error(
      `Cannot faithfully convert ${ty} into Python since it ` +
        "contains both 1 and true as keys.",
    );
  }
  if (obj.has(0) && obj.has(false)) {
    throw new Error(
      `Cannot faithfully convert ${ty} into Python since it ` +
        "contains both 0 and false as keys.",
    );
  }
}

/**
 * Convert mutable types: Array, Map, Set, and Objects whose prototype is
 * either null or the default. Anything else is wrapped in a Proxy. This
 * should only be used on values for which js2python_convertImmutable
 * returned `undefined`.
 */
function js2python_convertOther(value, context) {
  let typeTag = getTypeTag(value);
  if (
    Array.isArray(value) ||
    value === "[object HTMLCollection]" ||
    value === "[object NodeList]"
  ) {
    return js2python_convertList(value, context);
  }
  if (typeTag === "[object Map]" || value instanceof Map) {
    checkBoolIntCollision(value, "Map");
    return js2python_convertMap(value, value.entries(), context);
  }
  if (typeTag === "[object Set]" || value instanceof Set) {
    checkBoolIntCollision(value, "Set");
    return js2python_convertSet(value, context);
  }
  if (
    typeTag === "[object Object]" &&
    (value.constructor === undefined || value.constructor.name === "Object")
  ) {
    return js2python_convertMap(value, Object.entries(value), context);
  }
  if (typeTag === "[object ArrayBuffer]" || ArrayBuffer.isView(value)) {
    let [format_utf8, itemsize] = Module.get_buffer_datatype(value);
    return _JsBuffer_CopyIntoMemoryView(
      value,
      value.byteLength,
      format_utf8,
      itemsize,
    );
  }
  return undefined;
}

/**
 * Convert a JavaScript object to Python to a given depth.
 */
function js2python_convert_with_context(value, context) {
  let result = js2python_convertImmutable(value);
  if (result !== undefined) {
    return result;
  }
  if (context.depth === 0) {
    return _JsProxy_create(value);
  }
  result = context.cache.get(value);
  if (result !== undefined) {
    return result;
  }
  context.depth--;
  try {
    result = js2python_convertOther(value, context);
    if (result !== undefined) {
      return result;
    }
    if (!context.defaultConverter) {
      return _JsProxy_create(value);
    }
    let result_js = context.defaultConverter(
      value,
      context.converter,
      context.cacheConversion,
    );
    result = js2python_convertImmutable(result_js);
    if (API.isPyProxy(result_js)) {
      Module.pyproxy_destroy(result_js, "", false);
    }
    if (result !== undefined) {
      return result;
    }
    return _JsProxy_create(result_js);
  } finally {
    context.depth++;
  }
}

/**
 * Convert a JavaScript object to Python to a given depth.
 */
function js2python_convert(val, { depth, defaultConverter }) {
  let context = {
    cache: new Map(),
    depth,
    defaultConverter,
    // arguments for defaultConverter
    converter: (x) =>
      Module.pyproxy_new(js2python_convert_with_context(x, context)),
    cacheConversion(input, output) {
      if (API.isPyProxy(output)) {
        context.cache.set(input, Module.PyProxy_getPtr(output));
      } else {
        throw new Error("Second argument should be a PyProxy!");
      }
    },
  };
  return js2python_convert_with_context(val, context);
}

Module.js2python_convert = js2python_convert;
