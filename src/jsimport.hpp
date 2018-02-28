#ifndef JSIMPORT_H
#define JSIMPORT_H

#include <Python.h>

int JsImport_Ready();
extern PyObject *globals;
extern PyObject *original_globals;

#endif /* JSIMPORT_H */
