#ifndef JS2PYTHON_H
#define JS2PYTHON_H

#include <emscripten.h>
#include <emscripten/bind.h>
#include <emscripten/val.h>
#include <Python.h>

PyObject *jsToPython(emscripten::val x);
PyObject *jsToPythonArgs(emscripten::val args);
PyObject *jsToPythonKwargs(emscripten::val kwargs);
int jsToPython_Ready();

#endif /* JS2PYTHON_H */
