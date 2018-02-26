#ifndef PYLOCALS_H
#define PYLOCALS_H

#include <Python.h>

int PyLocals_Ready();

extern PyObject *locals;
extern PyObject *globals;
extern PyObject *original_globals;

#endif /* PYLOCALS_H */
