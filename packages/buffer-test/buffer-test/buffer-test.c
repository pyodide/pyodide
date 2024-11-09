#define PY_SSIZE_T_CLEAN
#include <Python.h>

// clang-format off
typedef struct
{
  PyObject_HEAD
  Py_ssize_t byteLength; // invariant: byteLength should be equal to length * itemsize
  Py_ssize_t length;
  char data[16];
  char format[2];
  Py_ssize_t itemsize;
} ZeroDBufferObject;
// clang-format on

static int
ZeroDBuffer_init(PyObject* o, PyObject* args, PyObject* kwds)
{
  ZeroDBufferObject* self = (ZeroDBufferObject*)o;
  Py_buffer buf;
  int fmt;
  if (!PyArg_ParseTuple(args, "Cy*", &fmt, &buf)) {
    return -1;
  }
  for (int i = 0; i < buf.len && i < 16; i++) {
    self->data[i] = ((char*)buf.buf)[i];
  }
  self->itemsize = buf.len;
  PyBuffer_Release(&buf);
  self->format[0] = fmt;
  self->format[1] = 0;
  return 0;
}

static void
ZeroDBuffer_dealloc(PyObject* self)
{
}

static int
ZeroDBuffer_GetBuffer(PyObject* obj, Py_buffer* view, int flags)
{
  ZeroDBufferObject* self = (ZeroDBufferObject*)obj;
  view->obj = NULL;
  // This gets decremented automatically by PyBuffer_Release (even though
  // bf_releasebuffer is NULL)
  Py_INCREF(self);

  view->buf = &self->data;
  view->obj = (PyObject*)self;
  view->len = 1;
  view->readonly = 0;
  view->itemsize = self->itemsize;
  view->format = self->format;
  view->ndim = 0;
  view->shape = NULL;
  view->strides = NULL;
  view->suboffsets = NULL;

  return 0;
}

static PyBufferProcs ZeroDBuffer_BufferProcs = {
  .bf_getbuffer = ZeroDBuffer_GetBuffer,
  .bf_releasebuffer = NULL,
};

static PyTypeObject ZeroDBufferType = {
  .tp_name = "ZeroDBuffer",
  .tp_basicsize = sizeof(ZeroDBufferObject),
  .tp_dealloc = ZeroDBuffer_dealloc,
  .tp_as_buffer = &ZeroDBuffer_BufferProcs,
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_doc = PyDoc_STR("An internal helper buffer"),
  .tp_init = ZeroDBuffer_init,
  .tp_new = PyType_GenericNew,
};

static struct PyModuleDef module = {
  PyModuleDef_HEAD_INIT,
  "buffer_test",       /* name of module */
  "Tests for buffers", /* module documentation, may be NULL */
  -1,                  /* size of per-interpreter state of the module,
                          or -1 if the module keeps state in global variables. */
};

PyMODINIT_FUNC
PyInit_buffer_test(void)
{
  PyObject* module_object = PyModule_Create(&module);
  if (module_object == NULL) {
    return NULL;
  }
  if (PyModule_AddType(module_object, &ZeroDBufferType) == -1) {
    return NULL;
  }
  return module_object;
}
