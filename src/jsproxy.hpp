#ifndef JSPROXY_H
#define JSPROXY_H

#include <Python.h>
#include <emscripten.h>
#include <emscripten/bind.h>
#include <emscripten/val.h>

PyObject *JsProxy_cnew(emscripten::val v, emscripten::val *parent, const char *name);
int JsProxy_Check(PyObject *x);
emscripten::val JsProxy_AsVal(PyObject *x);
int JsProxy_Ready();

#endif /* JSPROXY_H */
