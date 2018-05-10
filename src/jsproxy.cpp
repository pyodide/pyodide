#include "jsproxy.hpp"

#include "js2python.hpp"
#include "python2js.hpp"

using emscripten::val;

static PyObject *JsBoundMethod_cnew(val this_, const char *name);

////////////////////////////////////////////////////////////
// JsProxy
//
// This is a Python object that provides ideomatic access to a Javascript object.

typedef struct {
  PyObject_HEAD
  val *js;
} JsProxy;

static void JsProxy_dealloc(JsProxy *self) {
  delete self->js;
  Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *JsProxy_GetAttr(PyObject *o, PyObject *attr_name) {
  JsProxy *self = (JsProxy *)o;

  PyObject *str = PyObject_Str(attr_name);
  if (str == NULL) {
    return NULL;
  }

  std::string s(PyUnicode_AsUTF8(str));

  if (s == "new") {
    Py_DECREF(str);
    return PyObject_GenericGetAttr(o, attr_name);
  }

  val v = (*self->js)[s];
  Py_DECREF(str);

  if (v.typeof().equals(val("function"))) {
    return JsBoundMethod_cnew(*self->js, s.c_str());
  }

  return jsToPython(v);
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

  switch (nargs) {
  case 0:
    return jsToPython((*self->js)());
  case 1:
    return jsToPython((*self->js)
                      (pythonToJs(PyTuple_GET_ITEM(args, 0))));
  case 2:
    return jsToPython((*self->js)
                      (pythonToJs(PyTuple_GET_ITEM(args, 0)),
                       pythonToJs(PyTuple_GET_ITEM(args, 1))));
  case 3:
    return jsToPython((*self->js)
                      (pythonToJs(PyTuple_GET_ITEM(args, 0)),
                       pythonToJs(PyTuple_GET_ITEM(args, 1)),
                       pythonToJs(PyTuple_GET_ITEM(args, 2))));
  case 4:
    return jsToPython((*self->js)
                      (pythonToJs(PyTuple_GET_ITEM(args, 0)),
                       pythonToJs(PyTuple_GET_ITEM(args, 1)),
                       pythonToJs(PyTuple_GET_ITEM(args, 2)),
                       pythonToJs(PyTuple_GET_ITEM(args, 3))));
  case 5:
    return jsToPython((*self->js)
                      (pythonToJs(PyTuple_GET_ITEM(args, 0)),
                       pythonToJs(PyTuple_GET_ITEM(args, 1)),
                       pythonToJs(PyTuple_GET_ITEM(args, 2)),
                       pythonToJs(PyTuple_GET_ITEM(args, 3)),
                       pythonToJs(PyTuple_GET_ITEM(args, 4))));
  }
  PyErr_SetString(PyExc_TypeError, "Too many arguments to function");
  return NULL;
}

static PyObject* JsProxy_New(PyObject *o, PyObject *args, PyObject *kwargs) {
  JsProxy *self = (JsProxy *)o;

  Py_ssize_t nargs = PyTuple_Size(args);

  // TODO: There's probably some way to not have to explicitly expand arguments
  // here.

  switch (nargs) {
  case 0:
    return jsToPython((*self->js).new_());
  case 1:
    return jsToPython((*self->js)
                      .new_(pythonToJs(PyTuple_GET_ITEM(args, 0))));
  case 2:
    return jsToPython((*self->js)
                      .new_(pythonToJs(PyTuple_GET_ITEM(args, 0)),
                            pythonToJs(PyTuple_GET_ITEM(args, 1))));
  case 3:
    return jsToPython((*self->js)
                      .new_(pythonToJs(PyTuple_GET_ITEM(args, 0)),
                            pythonToJs(PyTuple_GET_ITEM(args, 1)),
                            pythonToJs(PyTuple_GET_ITEM(args, 2))));
  case 4:
    return jsToPython((*self->js)
                      .new_(pythonToJs(PyTuple_GET_ITEM(args, 0)),
                            pythonToJs(PyTuple_GET_ITEM(args, 1)),
                            pythonToJs(PyTuple_GET_ITEM(args, 2)),
                            pythonToJs(PyTuple_GET_ITEM(args, 3))));
  case 5:
    return jsToPython((*self->js)
                      .new_(pythonToJs(PyTuple_GET_ITEM(args, 0)),
                            pythonToJs(PyTuple_GET_ITEM(args, 1)),
                            pythonToJs(PyTuple_GET_ITEM(args, 2)),
                            pythonToJs(PyTuple_GET_ITEM(args, 3)),
                            pythonToJs(PyTuple_GET_ITEM(args, 4))));
  }
  PyErr_SetString(PyExc_TypeError, "Too many arguments to function");
  return NULL;
}

Py_ssize_t JsProxy_length(PyObject *o) {
  JsProxy *self = (JsProxy *)o;

  return (*self->js)["length"].as<Py_ssize_t>();
}

PyObject* JsProxy_item(PyObject *o, Py_ssize_t idx) {
  JsProxy *self = (JsProxy *)o;

  val v = (*self->js)[idx];

  return jsToPython(v);
}

int JsProxy_ass_item(PyObject *o, Py_ssize_t idx, PyObject *value) {
  JsProxy *self = (JsProxy *)o;
  val js_value = pythonToJs(value);

  (*self->js).set(idx, js_value);

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
  .tp_as_sequence = &JsProxy_SequenceMethods
};

PyObject *JsProxy_cnew(val v) {
  JsProxy *self;
  self = (JsProxy *)JsProxyType.tp_alloc(&JsProxyType, 0);
  self->js = new val(v);
  return (PyObject *)self;
}


////////////////////////////////////////////////////////////
// JsBoundMethod
//
// A special class for bound methods

const size_t BOUND_METHOD_NAME_SIZE = 256;

typedef struct {
  PyObject_HEAD
  val *this_;
  char name[BOUND_METHOD_NAME_SIZE];
} JsBoundMethod;

static void JsBoundMethod_dealloc(JsBoundMethod *self) {
  delete self->this_;
  Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject* JsBoundMethod_Call(PyObject *o, PyObject *args, PyObject *kwargs) {
  JsBoundMethod *self = (JsBoundMethod *)o;

  Py_ssize_t nargs = PyTuple_Size(args);

  // TODO: There's probably some way to not have to explicitly expand arguments
  // here.

  switch (nargs) {
  case 0:
    return jsToPython((*self->this_).call<val>(self->name));
  case 1:
    return jsToPython((*self->this_).call<val>
                      (self->name,
                       pythonToJs(PyTuple_GET_ITEM(args, 0))));
  case 2:
    return jsToPython((*self->this_).call<val>
                      (self->name,
                       pythonToJs(PyTuple_GET_ITEM(args, 0)),
                       pythonToJs(PyTuple_GET_ITEM(args, 1))));
  case 3:
    return jsToPython((*self->this_).call<val>
                      (self->name,
                       pythonToJs(PyTuple_GET_ITEM(args, 0)),
                       pythonToJs(PyTuple_GET_ITEM(args, 1)),
                       pythonToJs(PyTuple_GET_ITEM(args, 2))));
  case 4:
    return jsToPython((*self->this_).call<val>
                      (self->name,
                       pythonToJs(PyTuple_GET_ITEM(args, 0)),
                       pythonToJs(PyTuple_GET_ITEM(args, 1)),
                       pythonToJs(PyTuple_GET_ITEM(args, 2)),
                       pythonToJs(PyTuple_GET_ITEM(args, 3))));
  case 5:
    return jsToPython((*self->this_).call<val>
                      (self->name,
                       pythonToJs(PyTuple_GET_ITEM(args, 0)),
                       pythonToJs(PyTuple_GET_ITEM(args, 1)),
                       pythonToJs(PyTuple_GET_ITEM(args, 2)),
                       pythonToJs(PyTuple_GET_ITEM(args, 3)),
                       pythonToJs(PyTuple_GET_ITEM(args, 4))));
  }

  PyErr_SetString(PyExc_TypeError, "Too many arguments to function");
  return NULL;
}

static PyTypeObject JsBoundMethodType = {
  .tp_name = "JsBoundMethod",
  .tp_basicsize = sizeof(JsBoundMethod),
  .tp_dealloc = (destructor)JsBoundMethod_dealloc,
  .tp_call = JsBoundMethod_Call,
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_doc = "A proxy to make it possible to call Javascript bound methods from Python."
};

static PyObject *JsBoundMethod_cnew(val this_, const char *name) {
  JsBoundMethod *self;
  self = (JsBoundMethod *)JsBoundMethodType.tp_alloc(&JsBoundMethodType, 0);
  self->this_ = new val(this_);
  strncpy(self->name, name, BOUND_METHOD_NAME_SIZE);
  return (PyObject *)self;
}

////////////////////////////////////////////////////////////
// Public functions

int JsProxy_Check(PyObject *x) {
  return (PyObject_TypeCheck(x, &JsProxyType) ||
          PyObject_TypeCheck(x, &JsBoundMethodType));
}

val JsProxy_AsVal(PyObject *x) {
  JsProxy *js_proxy = (JsProxy *)x;
  return *(js_proxy->js);
}

int JsProxy_Ready() {
  return (PyType_Ready(&JsProxyType) ||
          PyType_Ready(&JsBoundMethodType));
}
