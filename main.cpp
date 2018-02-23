#include <string>
#include <codecvt>
#include <locale>

#include <emscripten.h>
#include <emscripten/bind.h>
#include <emscripten/val.h>
#include <Python.h>
#include <node.h>

// TODO: Bound methods should probably have their own class, rather than using
// JsProxy for everything

using emscripten::val;

////////////////////////////////////////////////////////////
// Forward declarations

val pythonToJs(PyObject *x);
PyObject *jsToPython(val x, val *parent=NULL, const char *name=NULL);
static PyObject *locals = NULL;
static PyObject *globals = NULL;
static PyObject *original_globals = NULL;
static PyObject *JsProxy_cnew(val v, val *parent=NULL, const char *name=NULL);
static val *undefined;

////////////////////////////////////////////////////////////
// JsProxy
//
// This is a Python object that provides ideomatic access to a Javascript object.

typedef struct {
  PyObject_HEAD
  val *js;
  val *parent;
  char *name;
} JsProxy;

static void JsProxy_dealloc(JsProxy *self) {
  delete self->js;
  if (self->parent) {
    delete self->parent;
  }
  if (self->name) {
    free(self->name);
  }
  Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *JsProxy_GetAttr(PyObject *o, PyObject *attr_name) {
  JsProxy *self = (JsProxy *)o;

  PyObject *str = PyObject_Str(attr_name);
  if (str == NULL) {
    return NULL;
  }

  std::string s(PyUnicode_AsUTF8(str));
  val v = (*self->js)[s];
  Py_DECREF(str);

  return jsToPython(v, self->js, s.c_str());
}

static int JsProxy_SetAttr(PyObject *o, PyObject *attr_name, PyObject *value) {
  JsProxy *self = (JsProxy *)o;

  PyObject *attr_name_py_str = PyObject_Str(attr_name);
  if (attr_name_py_str == NULL) {
    return NULL;
  }
  std::string attr_name_str(PyUnicode_AsUTF8(attr_name_py_str));

  val value_js = pythonToJs(value);

  (*self->js).set(attr_name_str, value_js);
  Py_DECREF(attr_name_py_str);

  return 0;
}
static PyObject* JsProxy_Call(PyObject *o, PyObject *args, PyObject *kwargs) {
  JsProxy *self = (JsProxy *)o;

  Py_ssize_t nargs = PyTuple_Size(args);

  // TODO: There's probably some way to not have to explicitly expand arguments
  // here.

  if (self->parent) {
    switch (nargs) {
    case 0:
      return jsToPython((*self->parent).call<val>(self->name));
    case 1:
      return jsToPython((*self->parent).call<val>(
                            self->name,
                            pythonToJs(PyTuple_GET_ITEM(args, 0))));
    case 2:
      return jsToPython((*self->parent).call<val>(
                            self->name,
                            pythonToJs(PyTuple_GET_ITEM(args, 0)),
                            pythonToJs(PyTuple_GET_ITEM(args, 1))));
    case 3:
      return jsToPython((*self->parent).call<val>(
                            self->name,
                            pythonToJs(PyTuple_GET_ITEM(args, 0)),
                            pythonToJs(PyTuple_GET_ITEM(args, 1)),
                            pythonToJs(PyTuple_GET_ITEM(args, 2))));
    case 4:
      return jsToPython((*self->parent).call<val>(
                            self->name,
                            pythonToJs(PyTuple_GET_ITEM(args, 0)),
                            pythonToJs(PyTuple_GET_ITEM(args, 1)),
                            pythonToJs(PyTuple_GET_ITEM(args, 2)),
                            pythonToJs(PyTuple_GET_ITEM(args, 3))));
    }
  } else {
    switch (nargs) {
    case 0:
      return jsToPython((*self->js)());
    case 1:
      return jsToPython((*self->js)(
                            pythonToJs(PyTuple_GET_ITEM(args, 0))));
    case 2:
      return jsToPython((*self->js)(
                          pythonToJs(PyTuple_GET_ITEM(args, 0)),
                          pythonToJs(PyTuple_GET_ITEM(args, 1))));
    case 3:
      return jsToPython((*self->js)(
                            pythonToJs(PyTuple_GET_ITEM(args, 0)),
                            pythonToJs(PyTuple_GET_ITEM(args, 1)),
                            pythonToJs(PyTuple_GET_ITEM(args, 2))));
    case 4:
      return jsToPython((*self->js)(
                            pythonToJs(PyTuple_GET_ITEM(args, 0)),
                            pythonToJs(PyTuple_GET_ITEM(args, 1)),
                            pythonToJs(PyTuple_GET_ITEM(args, 2)),
                            pythonToJs(PyTuple_GET_ITEM(args, 3))));
    }
  }
  // TODO: Handle exception here
  return NULL;
}

static PyTypeObject JsProxyType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "JsProxy",             /* tp_name */
    sizeof(JsProxy),             /* tp_basicsize */
    0,                         /* tp_itemsize */
    (destructor)JsProxy_dealloc, /* tp_dealloc */
    0,                         /* tp_print */
    0,                         /* tp_getattr */
    0,                         /* tp_setattr */
    0,                         /* tp_reserved */
    0,                         /* tp_repr */
    0,                         /* tp_as_number */
    0,                         /* tp_as_sequence */
    0,                         /* tp_as_mapping */
    0,                         /* tp_hash  */
    JsProxy_Call,              /* tp_call */
    0,                         /* tp_str */
    JsProxy_GetAttr,           /* tp_getattro */
    JsProxy_SetAttr,           /* tp_setattro */
    0,                         /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT,
    "A proxy to make a Javascript object behave like a Python object",
    0,                         /* tp_traverse */
    0,                         /* tp_clear */
    0,                         /* tp_richcompare */
    0,                         /* tp_weaklistoffset */
    0,                         /* tp_iter */
    0,                         /* tp_iternext */
    0,                         /* tp_methods */
    0,                         /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,                         /* tp_init */
    0,                         /* tp_alloc */
    0,                         /* tp_new */
};

static PyObject *JsProxy_cnew(val v, val *parent, const char *name) {
  JsProxy *self;
  self = (JsProxy *)JsProxyType.tp_alloc(&JsProxyType, 0);
  self->js = new val(v);
  if (parent) {
    self->parent = new val(*parent);
    size_t n = strnlen(name, 256);
    char *copy = (char *)malloc(n + 1);
    strncpy(copy, name, n + 1);
    self->name = copy;
  } else {
    self->parent = NULL;
  }
  return (PyObject *)self;
}

////////////////////////////////////////////////////////////
// LocalsProxy
//
// This is an object designed to be used as a "locals" namespace dictionary.
// It first looks for things in its own internal dictionary, and failing that,
// looks in the Javascript global namespace.  This is a way of merging the
// Python and Javascript namespaces without fullying copying either one.

typedef struct {
  PyObject_HEAD
  PyObject *locals;
} LocalsProxy;

static void LocalsProxy_dealloc(LocalsProxy *self) {
  Py_DECREF(self->locals);
  Py_TYPE(self)->tp_free((PyObject *)self);
}

static Py_ssize_t LocalsProxy_length(PyObject *o) {
  LocalsProxy *self = (LocalsProxy *)o;

  return PyDict_Size(self->locals);
}

PyObject* LocalsProxy_get(PyObject *o, PyObject *key) {
  LocalsProxy *self = (LocalsProxy *)o;

  {
    PyObject *str = PyObject_Str(key);
    if (str == NULL) {
      return NULL;
    }
    char *c = PyUnicode_AsUTF8(str);
    Py_DECREF(str);
  }

  PyObject *py_val = PyDict_GetItem(self->locals, key);
  if (py_val != NULL) {
    Py_INCREF(py_val);
    return py_val;
  }

  PyObject *str = PyObject_Str(key);
  if (str == NULL) {
    return NULL;
  }
  char *c = PyUnicode_AsUTF8(str);
  val v = val::global(c);
  Py_DECREF(str);
  return jsToPython(v);
}

int LocalsProxy_set(PyObject *o, PyObject *k, PyObject *v) {
  LocalsProxy *self = (LocalsProxy *)o;

  if (v == NULL) {
    // TODO: This might not actually be here to delete...
    return PyDict_DelItem(self->locals, k);
  } else {
    return PyDict_SetItem(self->locals, k, v);
  }
}

static PyMappingMethods LocalsProxy_as_mapping = {
  LocalsProxy_length,
  LocalsProxy_get,
  LocalsProxy_set
};

static PyTypeObject LocalsProxyType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "LocalsProxy",             /* tp_name */
    sizeof(LocalsProxy),             /* tp_basicsize */
    0,                         /* tp_itemsize */
    (destructor)LocalsProxy_dealloc, /* tp_dealloc */
    0,                         /* tp_print */
    0,                         /* tp_getattr */
    0,                         /* tp_setattr */
    0,                         /* tp_reserved */
    0,                         /* tp_repr */
    0,                         /* tp_as_number */
    0,                         /* tp_as_sequence */
    &LocalsProxy_as_mapping,    /* tp_as_mapping */
    0,                         /* tp_hash  */
    0,                         /* tp_call */
    0,                         /* tp_str */
    0,                         /* tp_getattro */
    0,                         /* tp_setattro */
    0,                         /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT,
    "A proxy that looks in a dict first, otherwise the JS global namespace.",
    0,                         /* tp_traverse */
    0,                         /* tp_clear */
    0,                         /* tp_richcompare */
    0,                         /* tp_weaklistoffset */
    0,                         /* tp_iter */
    0,                         /* tp_iternext */
    0,                         /* tp_methods */
    0,                         /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,                         /* tp_init */
    0,                         /* tp_alloc */
    0,                         /* tp_new */
};

static PyObject *LocalsProxy_cnew(PyObject *d)
{
  LocalsProxy *self;
  self = (LocalsProxy *)LocalsProxyType.tp_alloc(&LocalsProxyType, 0);
  if (self != NULL) {
    Py_INCREF(d);
    self->locals = d;
  }

  return (PyObject *)self;
}

////////////////////////////////////////////////////////////
// Conversions

val pythonExcToJS() {
  PyObject *type;
  PyObject *value;
  PyObject *traceback;
  PyObject *str;

  PyErr_Fetch(&type, &value, &traceback);

  str = PyObject_Str(value);
  // TODO: Return a JS Error object rather than a string here...?
  val result = pythonToJs(str);

  Py_DECREF(str);
  Py_DECREF(type);
  Py_DECREF(value);
  Py_DECREF(traceback);

  return result;
}

val pythonToJs(PyObject *x) {
  // TODO: bool, None
  if (x == Py_None) {
    return val(*undefined);
  } else if (x == Py_True) {
    return val(true);
  } else if (x == Py_False) {
    return val(false);
  } else if (PyLong_Check(x)) {
    long x_long = PyLong_AsLongLong(x);
    if (x_long == -1 && PyErr_Occurred()) {
      return pythonExcToJS();
    }
    return val(x_long);
  } else if (PyFloat_Check(x)) {
    double x_double = PyFloat_AsDouble(x);
    if (x_double == -1.0 && PyErr_Occurred()) {
      return pythonExcToJS();
    }
    return val(x_double);
  } else if (PyUnicode_Check(x)) {
    // TODO: Not clear whether this is UTF-16 or UCS2
    // TODO: This is doing two copies.  Can we reduce?
    Py_ssize_t length;
    wchar_t *chars = PyUnicode_AsWideCharString(x, &length);
    if (chars == NULL) {
      return pythonExcToJS();
    }
    std::wstring x_str(chars, length);
    PyMem_Free(chars);
    return val(x_str);
  } else if (PyBytes_Check(x)) {
    // TODO: This is doing two copies.  Can we reduce?
    char *x_buff;
    Py_ssize_t length;
    PyBytes_AsStringAndSize(x, &x_buff, &length);
    std::string x_str(x_buff, length);
    return val(x_str);
  } else if (PyObject_TypeCheck(x, &JsProxyType)) {
    JsProxy *js_proxy = (JsProxy *)x;
    return val(*(js_proxy->js));
  } else if (PySequence_Check(x)) {
    val array = val::global("Array");
    val x_array = array.new_();
    size_t length = PySequence_Size(x);
    for (size_t i = 0; i < length; ++i) {
      PyObject *item = PySequence_GetItem(x, i);
      if (item == NULL) {
        return pythonExcToJS();
      }
      x_array.call<int>("push", pythonToJs(item));
      Py_DECREF(item);
    }
    return x_array;
  } else if (PyDict_Check(x)) {
    val object = val::global("Object");
    val x_object = object.new_();
    PyObject *k, *v;
    Py_ssize_t pos = 0;
    while (PyDict_Next(x, &pos, &k, &v)) {
      x_object.set(pythonToJs(k), pythonToJs(v));
    }
    return x_object;
  } else {
    return val(x);
  }
}

PyObject *jsToPython(val x, val *parent, const char *name) {
  val xType = x.typeOf();

  if (xType.equals(val("string"))) {
    std::wstring x_str = x.as<std::wstring>();
    return PyUnicode_FromWideChar(&*x_str.begin(), x_str.size());
  } else if (xType.equals(val("number"))) {
    double x_double = x.as<double>();
    return PyFloat_FromDouble(x_double);
  } else if (xType.equals(val("undefined"))) {
    Py_INCREF(Py_None);
    return Py_None;
  } else {
    return JsProxy_cnew(x, parent, name);
  }
}

static bool is_whitespace(char x) {
  switch (x) {
  case ' ':
  case '\n':
  case '\r':
  case '\t':
    return true;
  default:
    return false;
  }
}

val runPython(std::wstring code) {
  std::wstring_convert<std::codecvt_utf8<wchar_t>> conv;
  std::string code_utf8 = conv.to_bytes(code);
  std::string::iterator last_line = code_utf8.end();

  PyCompilerFlags cf;
  cf.cf_flags = PyCF_SOURCE_IS_UTF8;
  PyEval_MergeCompilerFlags(&cf);

  // Find the last non-whitespace-only line since that will provide the result
  // TODO: This way to find the last line will probably break in many ways
  if (code_utf8.size() == 0) {
    return val(*undefined);
  }
  last_line--;
  for (; last_line != code_utf8.begin() && is_whitespace(*last_line); last_line--) {}
  for (; last_line != code_utf8.begin() && *last_line != '\n'; last_line--) {}

  int do_eval_line = 1;
  _node *co;
  co = PyParser_SimpleParseStringFlags(&*last_line, Py_eval_input, cf.cf_flags);
  if (co == NULL) {
    do_eval_line = 0;
    PyErr_Clear();
  }
  PyNode_Free(co);

  PyObject *ret;
  if (do_eval_line == 0 || last_line != code_utf8.begin()) {
    if (do_eval_line) {
      *last_line = 0;
      last_line++;
    }
    ret = PyRun_StringFlags(&*code_utf8.begin(), Py_file_input, globals, locals, &cf);
    if (ret == NULL) {
      return pythonExcToJS();
    }
    Py_DECREF(ret);
  }

  switch (do_eval_line) {
  case 0:
    Py_INCREF(Py_None);
    ret = Py_None;
    break;
  case 1:
    ret = PyRun_StringFlags(&*last_line, Py_eval_input, globals, locals, &cf);
    break;
  case 2:
    ret = PyRun_StringFlags(&*last_line, Py_file_input, globals, locals, &cf);
    break;
  }

  if (ret == NULL) {
    return pythonExcToJS();
  }

  // Now copy all the variables over to the Javascript side
  {
    val js_globals = val::global("window");
    PyObject *k, *v;
    Py_ssize_t pos = 0;

    while (PyDict_Next(globals, &pos, &k, &v)) {
      if (!PyDict_Contains(original_globals, k)) {
        js_globals.set(pythonToJs(k), pythonToJs(v));
      }
    }
  }

  val result = pythonToJs(ret);
  Py_DECREF(ret);
  return result;
}

EMSCRIPTEN_BINDINGS(python) {
  emscripten::function("runPython", &runPython);
  emscripten::class_<PyObject>("PyObject");
}

extern "C" {
  int main(int argc, char** argv) {
    setenv("PYTHONHOME", "/", 0);

    Py_InitializeEx(0);

    if (PyType_Ready(&JsProxyType) < 0)
      return 1;

    if (PyType_Ready(&LocalsProxyType) < 0)
      return 1;

    PyObject *m = PyImport_AddModule("__main__");
    if (m == NULL)
      return 1;
    globals = PyModule_GetDict(m);

    m = PyImport_AddModule("builtins");
    PyDict_Update(globals, PyModule_GetDict(m));

    original_globals = PyDict_Copy(globals);

    locals = LocalsProxy_cnew(globals);
    if (locals == NULL)
      return 1;

    undefined = new val(val::global("undefined"));

    emscripten_exit_with_live_runtime();
    return 0;
  }
}
