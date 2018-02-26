#ifndef PYTHON2JS_H
#define PYTHON2JS_H

#include <emscripten.h>
#include <emscripten/bind.h>
#include <emscripten/val.h>
#include <Python.h>

emscripten::val pythonExcToJS();
emscripten::val pythonToJs(PyObject *x);
int pythonToJs_Ready();

#endif /* PYTHON2JS_H */
