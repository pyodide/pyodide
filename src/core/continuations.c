#include <Python.h>
#include <error_handling.h>
#include <js2python.h>
#include <pyproxy.h>

typedef struct
{
  CFrame* cframe;
  int use_tracing;
  int recursion_depth;
  PyFrameObject* _top_frame;
  int trash_delete_nesting;
  _PyErr_StackItem exc_info;
} P;

P*
captureThreadState()
{
  PyThreadState* tstate = PyThreadState_Get();
  P* state = (P*)malloc(sizeof(P));
  state->cframe = tstate->cframe;
  state->recursion_depth = tstate->recursion_depth;
  state->use_tracing = tstate->cframe->use_tracing;
  state->_top_frame = tstate->frame;
  Py_XINCREF(state->_top_frame);
  // All versions of Python.
  state->trash_delete_nesting = tstate->trash_delete_nesting;
  state->exc_info = *tstate->exc_info;
  tstate->exc_info->exc_type = NULL;
  tstate->exc_info->exc_value = NULL;
  tstate->exc_info->exc_traceback = NULL;
  tstate->exc_info->previous_item = NULL;
  return state;
}

void
restoreThreadState(P* state)
{
  PyThreadState* tstate = PyThreadState_Get();
  tstate->cframe = state->cframe;
  tstate->recursion_depth = state->recursion_depth;
  tstate->cframe->use_tracing = state->use_tracing;
  tstate->frame = state->_top_frame;
  tstate->trash_delete_nesting = state->trash_delete_nesting;
  *tstate->exc_info = state->exc_info;
  free(state);
}

void
setErrObject(PyObject* exc)
{
  PyErr_SetObject((PyObject*)Py_TYPE(exc), exc);
}

// clang-format off
EM_JS_REF(JsRef, continuletSwitchHelper, (JsRef idself, int iserr, JsRef idvalue, JsRef idto), {
  const self = Hiwire.get_value(idself);
  const value = idvalue ? Hiwire.get_value(idvalue) : undefined;
  const to = idto ? Hiwire.get_value(idto) : undefined;
  let result = Module.continuletSwitchMain(self, iserr, value, to);
  if(result === 0) {
    return 0;
  } else {
    return Hiwire.new_value(result);
  }
});
// clang-format on

static PyObject*
continuletSwitch(PyObject* _module, PyObject* const* args, Py_ssize_t nargs)
{
  // static PyObject* continuletSwitch(PyObject* _module, PyObject* args) {
  PyObject* self;
  PyObject* _ign;
  bool iserr;
  PyObject* value;
  PyObject* to;
  JsRef continuation = NULL;
  JsRef jsself = NULL;
  JsRef jsvalue = NULL;
  JsRef jsto = NULL;
  JsRef jsresult = NULL;
  PyObject* result = NULL;

  if (!_PyArg_ParseStack(
        args, nargs, "OOiOO:_switch", &self, &_ign, &iserr, &value, &to)) {
    return NULL;
  }

  if (iserr) {
    if (PyExceptionClass_Check(value)) {
      value = _PyObject_CallNoArg(value);
    } else if (PyExceptionInstance_Check(value)) {
      Py_INCREF(value);
    } else {
      /* Not something you can raise.  */
      PyErr_SetString(PyExc_TypeError,
                      "exceptions must derive from BaseException");
      return NULL;
    }
  }

  jsself = pyproxy_new(self);
  FAIL_IF_NULL(jsself);
  if (value != Py_None) {
    jsvalue = pyproxy_new(value);
    FAIL_IF_NULL(jsvalue);
  }
  if (to != Py_None) {
    jsto = pyproxy_new(to);
    FAIL_IF_NULL(jsto);
  }
  continuation = continuletSwitchHelper(jsself, iserr, jsvalue, jsto);
  FAIL_IF_NULL(continuation);
  jsresult = hiwire_syncify(continuation);
  FAIL_IF_ERR_OCCURRED();
  result = js2python(jsresult);
  FAIL_IF_NULL(result);
finally:
  if (iserr) {
    Py_DECREF(value);
  }
  hiwire_CLEAR(continuation);
  destroy_proxy(jsself, NULL);
  if (jsvalue != NULL) {
    destroy_proxy(jsvalue, NULL);
  }
  if (jsto != NULL) {
    destroy_proxy(jsto, NULL);
  }
  hiwire_CLEAR(jsself);
  hiwire_CLEAR(jsvalue);
  hiwire_CLEAR(jsto);
  hiwire_CLEAR(jsresult);
  return result;
}

static PyMethodDef methods[] = {
  {
    "_switch",
    (PyCFunction)continuletSwitch,
    // METH_VARARGS,
    METH_FASTCALL,
  },
  { NULL } /* Sentinel */
};

int
continuations_init(PyObject* core_module)
{
  return PyModule_AddFunctions(core_module, methods);
}
