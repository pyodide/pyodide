#ifndef RUNPYTHON_H
#define RUNPYTHON_H
#include "Python.h"

/** The primary entry point function that runs Python code.
 */

int
runpython_init(PyObject* core_module);

#endif /* RUNPYTHON_H */
