#include "jsproxy.h"

#include "hiwire.h"
#include "js2python.h"
#include "python2js.h"

static PyObject *JsBoundMethod_cnew(int this_, const char *name);

////////////////////////////////////////////////////////////
// JsProxy
//
// This is a Python object that provides ideomatic access to a Javascript object.

typedef struct {
  PyObject_HEAD
  int js;
} JsProxy;

static void JsProxy_dealloc(JsProxy *self) {
  hiwire_decref(self->js);
  Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *JsProxy_Repr(PyObject *o) {
  JsProxy *self = (JsProxy *)o;
  int jsrepr = hiwire_to_string(self->js);
  PyObject *pyrepr = jsToPython(jsrepr);
  return pyrepr;
}

static PyObject *JsProxy_GetAttr(PyObject *o, PyObject *attr_name) {
  JsProxy *self = (JsProxy *)o;

  PyObject *str = PyObject_Str(attr_name);
  if (str == NULL) {
    return NULL;
  }

  char *key = PyUnicode_AsUTF8(str);

  if (strncmp(key, "new", 4) == 0) {
    Py_DECREF(str);
    return PyObject_GenericGetAttr(o, attr_name);
  }

  int v = hiwire_get_member_string(self->js, (int)key);
  Py_DECREF(str);

  if (hiwire_is_function(v)) {
    hiwire_decref(v);
    return JsBoundMethod_cnew(self->js, key);
  }

  PyObject *result = jsToPython(v);
  hiwire_decref(v);
  return result;
}

static int JsProxy_SetAttr(PyObject *o, PyObject *attr_name, PyObject *value) {
  JsProxy *self = (JsProxy *)o;

  PyObject *attr_name_py_str = PyObject_Str(attr_name);
  if (attr_name_py_str == NULL) {
    return -1;
  }
  char *key = PyUnicode_AsUTF8(attr_name_py_str);
  int jsvalue = pythonToJs(value);
  hiwire_set_member_string(self->js, (int)key, jsvalue);
  hiwire_decref(jsvalue);
  Py_DECREF(attr_name_py_str);

  return 0;
}

static PyObject* JsProxy_Call(PyObject *o, PyObject *args, PyObject *kwargs) {
  JsProxy *self = (JsProxy *)o;

  Py_ssize_t nargs = PyTuple_Size(args);

  int jsargs = hiwire_array();

  for (Py_ssize_t i; i < nargs; ++i) {
    int jsarg = pythonToJs(PyTuple_GET_ITEM(args, i));
    hiwire_push_array(jsargs, jsarg);
    hiwire_decref(jsarg);
  }

  int jsresult = hiwire_call(self->js, jsargs);
  hiwire_decref(jsargs);
  PyObject *result = jsToPython(jsresult);
  hiwire_decref(jsresult);
  return result;
}

static PyObject* JsProxy_New(PyObject *o, PyObject *args, PyObject *kwargs) {
  JsProxy *self = (JsProxy *)o;

  Py_ssize_t nargs = PyTuple_Size(args);

  int jsargs = hiwire_array();

  for (Py_ssize_t i; i < nargs; ++i) {
    int jsarg = pythonToJs(PyTuple_GET_ITEM(args, i));
    hiwire_push_array(jsargs, jsarg);
    hiwire_decref(jsarg);
  }

  int jsresult = hiwire_new(self->js, jsargs);
  hiwire_decref(jsargs);
  PyObject *result = jsToPython(jsresult);
  hiwire_decref(jsresult);
  return result;
}

Py_ssize_t JsProxy_length(PyObject *o) {
  JsProxy *self = (JsProxy *)o;

  return hiwire_length(self->js);
}

PyObject* JsProxy_item(PyObject *o, Py_ssize_t idx) {
  JsProxy *self = (JsProxy *)o;

  int v = hiwire_get_member_int(self->js, idx);
  PyObject *result = jsToPython(v);
  hiwire_decref(v);
  return result;
}

int JsProxy_ass_item(PyObject *o, Py_ssize_t idx, PyObject *value) {
  JsProxy *self = (JsProxy *)o;
  int js_value = pythonToJs(value);
  hiwire_set_member_int(self->js, idx, js_value);
  hiwire_decref(js_value);
  return 0;
}

static PySequenceMethods JsProxy_SequenceMethods = {
  JsProxy_length,
  NULL,
  NULL,
  JsProxy_item,
  NULL,
  JsProxy_ass_item,
  NULL,
  NULL,
  NULL,
  NULL
};

static PyMethodDef JsProxy_Methods[] = {
  {"new", (PyCFunction)JsProxy_New, METH_VARARGS|METH_KEYWORDS, "Construct a new instance"},
  { NULL }
};

static PyTypeObject JsProxyType = {
  .tp_name = "JsProxy",
  .tp_basicsize = sizeof(JsProxy),
  .tp_dealloc = (destructor)JsProxy_dealloc,
  .tp_call = JsProxy_Call,
  .tp_getattro = JsProxy_GetAttr,
  .tp_setattro = JsProxy_SetAttr,
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_doc = "A proxy to make a Javascript object behave like a Python object",
  .tp_methods = JsProxy_Methods,
  .tp_as_sequence = &JsProxy_SequenceMethods,
  .tp_repr = JsProxy_Repr
};

PyObject *JsProxy_cnew(int v) {
  JsProxy *self;
  self = (JsProxy *)JsProxyType.tp_alloc(&JsProxyType, 0);
  self->js = hiwire_incref(v);
  return (PyObject *)self;
}

////////////////////////////////////////////////////////////
// JsBoundMethod
//
// A special class for bound methods

const size_t BOUND_METHOD_NAME_SIZE = 256;

typedef struct {
  PyObject_HEAD
  int this_;
  char name[BOUND_METHOD_NAME_SIZE];
} JsBoundMethod;

static void JsBoundMethod_dealloc(JsBoundMethod *self) {
  hiwire_decref(self->this_);
  Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject* JsBoundMethod_Call(PyObject *o, PyObject *args, PyObject *kwargs) {
  JsBoundMethod *self = (JsBoundMethod *)o;

  Py_ssize_t nargs = PyTuple_Size(args);

  int jsargs = hiwire_array();

  for (Py_ssize_t i = 0; i < nargs; ++i) {
    int jsarg = pythonToJs(PyTuple_GET_ITEM(args, i));
    hiwire_push_array(jsargs, jsarg);
    hiwire_decref(jsarg);
  }

  int jsresult = hiwire_call_member(self->this_, (int)self->name, jsargs);
  hiwire_decref(jsargs);
  PyObject *result = jsToPython(jsresult);
  hiwire_decref(jsresult);
  return result;
}

static PyTypeObject JsBoundMethodType = {
  .tp_name = "JsBoundMethod",
  .tp_basicsize = sizeof(JsBoundMethod),
  .tp_dealloc = (destructor)JsBoundMethod_dealloc,
  .tp_call = JsBoundMethod_Call,
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_doc = "A proxy to make it possible to call Javascript bound methods from Python."
};

static PyObject *JsBoundMethod_cnew(int this_, const char *name) {
  JsBoundMethod *self;
  self = (JsBoundMethod *)JsBoundMethodType.tp_alloc(&JsBoundMethodType, 0);
  self->this_ = hiwire_incref(this_);
  strncpy(self->name, name, BOUND_METHOD_NAME_SIZE);
  return (PyObject *)self;
}

////////////////////////////////////////////////////////////
// Public functions

int JsProxy_Check(PyObject *x) {
  return (PyObject_TypeCheck(x, &JsProxyType) ||
          PyObject_TypeCheck(x, &JsBoundMethodType));
}

int JsProxy_AsJs(PyObject *x) {
  JsProxy *js_proxy = (JsProxy *)x;
  return hiwire_incref(js_proxy->js);
}

int JsProxy_Ready() {
  return (PyType_Ready(&JsProxyType) ||
          PyType_Ready(&JsBoundMethodType));
}
