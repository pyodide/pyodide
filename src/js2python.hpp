#ifndef JS2PYTHON_H
#define JS2PYTHON_H

#include <emscripten.h>
#include <emscripten/bind.h>
#include <emscripten/val.h>
#include <Python.h>

PyObject *jsToPython(emscripten::val x,
                     emscripten::val *parent = NULL,
                     const char *name = NULL);

#endif /* JS2PYTHON_H */
