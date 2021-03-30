#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "python2js_buffer.h"
#include "types.h"

#include <endian.h>
#include <stdint.h>

#include "hiwire.h"

// This file handles the conversion of Python buffer objects (which loosely
// represent Numpy arrays) to Javascript.

// There are two methods here:

//   1. Converts everything to nested Javascript arrays, where the scalars are
//   standard Javascript numbers (python2js_buffer_recursive)

//   2. Converts everything to nested arrays, where the last contiguous
//   dimension is a subarray of a TypedArray that points to the original bytes
//   on the WebAssembly (Python) side. This is much faster since it doesn't
//   require copying the data, and the data is shared. In the case of a
//   one-dimensional array, the result is simply a TypedArray. Unfortunately,
//   this requires that the source array is C-contiguous and in native (little)
//   endian order. (python2js_shareable_buffer_recursive)

// Unfortunately, this also means that there are different semantics: sometimes
// the array is a copy, and other times it is a shared reference. One should
// write code that doesn't rely on either behavior, but treats this simply as
// the performance optimization that it is.

typedef JsRef(scalar_converter)(char*);

static JsRef
_convert_bool(char* data)
{
  char v = *((char*)data);
  return hiwire_bool((int)v);
}

static JsRef
_convert_int8(char* data)
{
  i8 v = *((i8*)data);
  return hiwire_int(v);
}

static JsRef
_convert_uint8(char* data)
{
  u8 v = *((u8*)data);
  return hiwire_int(v);
}

static JsRef
_convert_int16(char* data)
{
  i16 v = *((i16*)data);
  return hiwire_int(v);
}

static JsRef
_convert_int16_swap(char* data)
{
  i16 v = *((i16*)data);
  return hiwire_int(be16toh(v));
}

static JsRef
_convert_uint16(char* data)
{
  u16 v = *((u16*)data);
  return hiwire_int(v);
}

static JsRef
_convert_uint16_swap(char* data)
{
  u16 v = *((u16*)data);
  return hiwire_int(be16toh(v));
}

static JsRef
_convert_int32(char* data)
{
  i32 v = *((i32*)data);
  return hiwire_int(v);
}

static JsRef
_convert_int32_swap(char* data)
{
  i32 v = *((i32*)data);
  return hiwire_int(be32toh(v));
}

static JsRef
_convert_uint32(char* data)
{
  u32 v = *((u32*)data);
  return hiwire_int(v);
}

static JsRef
_convert_uint32_swap(char* data)
{
  u32 v = *((u32*)data);
  return hiwire_int(be32toh(v));
}

static JsRef
_convert_int64(char* data)
{
  i64 v = *((i64*)data);
  return hiwire_int(v);
}

static JsRef
_convert_int64_swap(char* data)
{
  i64 v = *((i64*)data);
  return hiwire_int(be64toh(v));
}

static JsRef
_convert_uint64(char* data)
{
  u64 v = *((u64*)data);
  return hiwire_int(v);
}

static JsRef
_convert_uint64_swap(char* data)
{
  u64 v = *((u64*)data);
  return hiwire_int(be64toh(v));
}

static JsRef
_convert_float32(char* data)
{
  float v = *((float*)data);
  return hiwire_double(v);
}

static JsRef
_convert_float32_swap(char* data)
{
  union float32_t
  {
    u32 i;
    float f;
  } v;

  v.f = *((float*)data);
  v.i = be32toh(v.i);
  return hiwire_double(v.f);
}

static JsRef
_convert_float64(char* data)
{
  double v = *((double*)data);
  return hiwire_double(v);
}

static JsRef
_convert_float64_swap(char* data)
{
  union float64_t
  {
    u64 i;
    double f;
  } v;

  v.f = *((double*)data);
  v.i = be64toh(v.i);
  return hiwire_double(v.f);
}

static scalar_converter*
_python2js_buffer_get_converter(Py_buffer* buff)
{
  // Uses Python's struct typecodes as defined here:
  // https://docs.python.org/3.8/library/array.html

  char format;
  char swap;
  if (buff->format == NULL) {
    swap = 0;
    format = 'B';
  } else {
    switch (buff->format[0]) {
      case '>':
      case '!':
        swap = 1;
        format = buff->format[1];
        break;
      case '=':
      case '<':
      case '@':
        swap = 0;
        format = buff->format[1];
        break;
      default:
        swap = 0;
        format = buff->format[0];
    }
  }

  switch (format) {
    case 'c':
    case 'b':
      return _convert_int8;
    case 'B':
      return _convert_uint8;
    case '?':
      return _convert_bool;
    case 'h':
      if (swap) {
        return _convert_int16_swap;
      } else {
        return _convert_int16;
      }
    case 'H':
      if (swap) {
        return _convert_uint16_swap;
      } else {
        return _convert_uint16;
      }
    case 'i':
    case 'l':
    case 'n':
      if (swap) {
        return _convert_int32_swap;
      } else {
        return _convert_int32;
      }
    case 'I':
    case 'L':
    case 'N':
      if (swap) {
        return _convert_uint32_swap;
      } else {
        return _convert_uint32;
      }
    case 'q':
      if (swap) {
        return _convert_int64_swap;
      } else {
        return _convert_int64;
      }
    case 'Q':
      if (swap) {
        return _convert_uint64_swap;
      } else {
        return _convert_uint64;
      }
    case 'f':
      if (swap) {
        return _convert_float32_swap;
      } else {
        return _convert_float32;
      }
    case 'd':
      if (swap) {
        return _convert_float64_swap;
      } else {
        return _convert_float64;
      }
    default:
      return NULL;
  }
}

static JsRef
_python2js_buffer_recursive(Py_buffer* buff,
                            char* ptr,
                            int dim,
                            scalar_converter* convert)
{
  // This function is basically a manual conversion of `recursive_tolist` in
  // Numpy to use the Python buffer interface and output Javascript.

  Py_ssize_t i, n, stride;
  JsRef jsarray, jsitem;

  if (dim >= buff->ndim) {
    return convert(ptr);
  }

  n = buff->shape[dim];
  stride = buff->strides[dim];

  jsarray = hiwire_array();

  for (i = 0; i < n; ++i) {
    jsitem = _python2js_buffer_recursive(buff, ptr, dim + 1, convert);
    if (jsitem == NULL) {
      hiwire_decref(jsarray);
      return NULL;
    }
    hiwire_push_array(jsarray, jsitem);
    hiwire_decref(jsitem);

    ptr += stride;
  }

  return jsarray;
}

static JsRef
_python2js_buffer_to_typed_array(Py_buffer* buff)
{
  // Uses Python's struct typecodes as defined here:
  // https://docs.python.org/3.8/library/array.html

  char format;
  if (buff->format == NULL) {
    format = 'B';
  } else {
    switch (buff->format[0]) {
      case '>':
      case '!':
        // This path can't handle byte-swapping
        return NULL;
      case '=':
      case '<':
      case '@':
        format = buff->format[1];
        break;
      default:
        format = buff->format[0];
    }
  }

  Py_ssize_t len = buff->len / buff->itemsize;
  switch (format) {
    case 'c':
    case 'b':
      return hiwire_int8array((i8*)buff->buf, len);
    case 'B':
      return hiwire_uint8array((u8*)buff->buf, len);
    case '?':
      return NULL;
    case 'h':
      return hiwire_int16array((i16*)buff->buf, len);
    case 'H':
      return hiwire_uint16array((u16*)buff->buf, len);
    case 'i':
    case 'l':
    case 'n':
      return hiwire_int32array((i32*)buff->buf, len);
    case 'I':
    case 'L':
    case 'N':
      return hiwire_uint32array((u32*)buff->buf, len);
    case 'q':
    case 'Q':
      return NULL;
    case 'f':
      return hiwire_float32array((f32*)buff->buf, len);
    case 'd':
      return hiwire_float64array((f64*)buff->buf, len);
    default:
      return NULL;
  }
}

enum shareable_enum
{
  NOT_SHAREABLE,
  CONTIGUOUS,
  NOT_CONTIGUOUS
};

static JsRef
_python2js_shareable_buffer_recursive(Py_buffer* buff,
                                      enum shareable_enum shareable,
                                      JsRef idarr,
                                      int ptr,
                                      int dim)
{
  Py_ssize_t i, n, stride;
  JsRef jsarray, jsitem;

  switch (shareable) {
    case NOT_CONTIGUOUS:
      if (dim >= buff->ndim) {
        // The last dimension isn't contiguous, so we need to output one-by-one
        return hiwire_get_member_int(idarr, ptr / buff->itemsize);
      }
      break;
    case CONTIGUOUS:
      if (dim == buff->ndim - 1) {
        // The last dimension is contiguous, so we can output a whole row at a
        // time
        return hiwire_subarray(
          idarr, ptr / buff->itemsize, ptr / buff->itemsize + buff->shape[dim]);
      }
      break;
    default:
      break;
  }

  n = buff->shape[dim];
  stride = buff->strides[dim];

  jsarray = hiwire_array();

  for (i = 0; i < n; ++i) {
    jsitem = _python2js_shareable_buffer_recursive(
      buff, shareable, idarr, ptr, dim + 1);
    if (jsitem == NULL) {
      hiwire_decref(jsarray);
      return NULL;
    }
    hiwire_push_array(jsarray, jsitem);
    hiwire_decref(jsitem);

    ptr += stride;
  }

  return jsarray;
}

static enum shareable_enum
_python2js_buffer_is_shareable(Py_buffer* buff)
{
  if (buff->ndim == 0) {
    return NOT_SHAREABLE;
  }

  char* invalid_codes = ">!qQ?";
  for (char* i = buff->format; *i != 0; ++i) {
    for (char* j = invalid_codes; *j != 0; ++j) {
      if (*i == *j) {
        return NOT_SHAREABLE;
      }
    }
  }

  for (int i = 0; i < buff->ndim; ++i) {
    if (buff->strides[i] <= 0) {
      return NOT_SHAREABLE;
    }
  }

  if (buff->itemsize != buff->strides[buff->ndim - 1]) {
    return NOT_CONTIGUOUS;
  }

  // We can use the most efficient method
  return CONTIGUOUS;
}

JsRef
_python2js_buffer(PyObject* x)
{
  PyObject* memoryview = PyMemoryView_FromObject(x);
  if (memoryview == NULL) {
    return NULL;
  }

  Py_buffer* buff;
  buff = PyMemoryView_GET_BUFFER(memoryview);

  enum shareable_enum shareable = _python2js_buffer_is_shareable(buff);
  JsRef result;

  if (shareable != NOT_SHAREABLE) {
    JsRef idarr = _python2js_buffer_to_typed_array(buff);
    if (idarr == NULL) {
      PyErr_SetString(
        PyExc_TypeError,
        "Internal error: Invalid type to convert to array buffer.");
      return NULL;
    }

    result =
      _python2js_shareable_buffer_recursive(buff, shareable, idarr, 0, 0);
    hiwire_decref(idarr);
  } else {
    scalar_converter* convert = _python2js_buffer_get_converter(buff);
    if (convert == NULL) {
      Py_DECREF(memoryview);
      return NULL;
    }

    result = _python2js_buffer_recursive(buff, buff->buf, 0, convert);
  }

  Py_DECREF(memoryview);

  return result;
}
