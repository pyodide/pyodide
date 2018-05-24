#ifndef PYPROXY_H
#define PYPROXY_H

/** Makes Python objects usable from Javascript.
 */

#include <emscripten.h>
#include <emscripten/bind.h>
#include <emscripten/val.h>
#include <Python.h>

#include "js2python.hpp"
#include "python2js.hpp"

// This implements the Javascript Proxy handler interface as defined here:
//     https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Proxy

class Py {
public:
  static emscripten::val makeProxy(PyObject *obj);

  static bool isExtensible(
      emscripten::val obj, emscripten::val proxy);
  static bool has(
      emscripten::val obj, emscripten::val idx);
  static emscripten::val get(
      emscripten::val obj, emscripten::val idx, emscripten::val proxy);
  static emscripten::val set(
      emscripten::val obj, emscripten::val idx, emscripten::val value,
      emscripten::val proxy);
  static emscripten::val deleteProperty(
      emscripten::val obj, emscripten::val idx);
  static emscripten::val ownKeys(
      emscripten::val obj);
  static emscripten::val enumerate(
      emscripten::val obj);
};

class PyCallable {
public:
  PyObject *x;

  PyCallable(PyObject *x_) : x(x_) {
    Py_INCREF(x);
  }

  PyCallable(const PyCallable& o) : x(o.x) {
    Py_INCREF(x);
  }

  ~PyCallable() {
    Py_DECREF(x);
  }

  emscripten::val call(
      emscripten::val args, emscripten::val kwargs);

  static emscripten::val makeCallableProxy(PyObject *obj);
};

#endif /* PYPROXY_H */
