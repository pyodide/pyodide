#include "Python.h"
#include "error_handling.h"
#include "js2python.h"
#include "jsbind.h"
#include "jslib.h"
#include "pyproxy.h"
#include "python2js.h"

Js_static_string(PYPROXY_DESTROYED_AT_END_OF_FUNCTION_CALL,
                 "This borrowed proxy was automatically destroyed at the "
                 "end of a function call. Try using "
                 "create_proxy or create_once_callable.");

/**
 * Prepare arguments from a `METH_FASTCALL | METH_KEYWORDS` Python function to a
 * JavaScript call. We call `python2js` on each argument. Any PyProxy *created*
 * by `python2js` is stored into the `proxies` list to be destroyed later (if
 * the argument is a PyProxy created with `create_proxy` it won't be recorded
 * for destruction).
 */
static JsVal
JsMethod_ConvertArgs(PyObject* const* pyargs,
                     Py_ssize_t nargs,
                     PyObject* kwnames,
                     JsVal proxies)
{
  JsVal jsargs = JS_NULL;
  JsVal kwargs;

  jsargs = JsvArray_New();
  for (Py_ssize_t i = 0; i < nargs; ++i) {
    JsVal arg = python2js_track_proxies(pyargs[i], proxies, false);
    FAIL_IF_JS_NULL(arg);
    JsvArray_Push(jsargs, arg);
  }

  bool has_kwargs = false;
  if (kwnames != NULL) {
    // There were kwargs? But maybe kwnames is the empty tuple?
    PyObject* kwname = PyTuple_GetItem(kwnames, 0); /* borrowed!*/
    // Clear IndexError
    PyErr_Clear();
    if (kwname != NULL) {
      has_kwargs = true;
    }
  }
  if (!has_kwargs) {
    goto finally;
  }

  // store kwargs into an object which we'll use as the last argument.
  kwargs = JsvObject_New();
  FAIL_IF_JS_NULL(kwargs);
  Py_ssize_t nkwargs = PyTuple_Size(kwnames);
  for (Py_ssize_t i = 0, k = nargs; i < nkwargs; ++i, ++k) {
    PyObject* pyname = PyTuple_GET_ITEM(kwnames, i); /* borrowed! */
    JsVal jsname = python2js(pyname);
    JsVal arg = python2js_track_proxies(pyargs[k], proxies, false);
    FAIL_IF_JS_NULL(arg);
    FAIL_IF_MINUS_ONE(JsvObject_SetAttr(kwargs, jsname, arg));
  }
  JsvArray_Push(jsargs, kwargs);

finally:
  return jsargs;
}

/**
 * __call__ overload for methods. Controlled by IS_CALLABLE.
 */
PyObject*
JsMethod_Vectorcall_impl(JsVal target,
                         JsVal thisarg,
                         PyObject* const* pyargs,
                         size_t nargsf,
                         PyObject* kwnames)
{
  bool success = false;
  JsVal jsresult = JS_NULL;
  PyObject* pyresult = NULL;
  JsVal proxies = JsvArray_New();

  // Recursion error?
  FAIL_IF_NONZERO(Py_EnterRecursiveCall(" while calling a JavaScript object"));
  JsVal jsargs =
    JsMethod_ConvertArgs(pyargs, PyVectorcall_NARGS(nargsf), kwnames, proxies);
  FAIL_IF_JS_NULL(jsargs);
  jsresult = JsvFunction_CallBound(target, thisarg, jsargs);
  FAIL_IF_JS_NULL(jsresult);
  pyresult = Js2Py_func_default_call_result(NULL, jsresult, proxies);
  FAIL_IF_NULL(pyresult);

  success = true;
finally:
  Py_LeaveRecursiveCall(/* " in JsMethod_Vectorcall" */);
  if (!success) {
    // If we succeeded and the result was a promise then we destroy the
    // arguments in async_done_callback instead of here. Otherwise, destroy the
    // arguments and return value now.
    if (!JsvNull_Check(jsresult) && pyproxy_Check(jsresult)) {
      // TODO: don't destroy proxies with roundtrip = true?
      JsvArray_Push(proxies, jsresult);
    }
    destroy_proxies(proxies, &PYPROXY_DESTROYED_AT_END_OF_FUNCTION_CALL);
  }
  if (!success) {
    Py_CLEAR(pyresult);
  }
  return pyresult;
}

/**
 * jsproxy.new implementation. Controlled by IS_CALLABLE.
 *
 * This does Reflect.construct(this, args). In other words, this treats the
 * JsMethod as a JavaScript class, constructs a new JavaScript object of that
 * class and returns a new JsProxy wrapping it. Similar to `new this(args)`.
 */
PyObject*
JsMethod_Construct_impl(JsVal target,
                        PyObject* const* pyargs,
                        Py_ssize_t nargs,
                        PyObject* kwnames)
{
  bool success = false;
  PyObject* pyresult = NULL;
  JsVal proxies = JsvArray_New();

  // Recursion error?
  FAIL_IF_NONZERO(Py_EnterRecursiveCall(" in JsMethod_Construct"));

  JsVal jsargs = JsMethod_ConvertArgs(pyargs, nargs, kwnames, proxies);
  FAIL_IF_JS_NULL(jsargs);
  JsVal jsresult = JsvFunction_Construct(target, jsargs);
  FAIL_IF_JS_NULL(jsresult);
  pyresult = js2python(jsresult);
  FAIL_IF_NULL(pyresult);

  success = true;
finally:
  Py_LeaveRecursiveCall(/* " in JsMethod_Construct" */);
  Js_static_string(msg,
                   "This borrowed proxy was automatically destroyed. Try using "
                   "create_proxy or create_once_callable.");
  destroy_proxies(proxies, &msg);
  if (!success) {
    Py_CLEAR(pyresult);
  }
  return pyresult;
}
