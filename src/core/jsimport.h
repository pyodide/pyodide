#ifndef JSIMPORT_H
#define JSIMPORT_H

/** Support "from js import …" from Python. */
#define PY_SSIZE_T_CLEAN
#include "Python.h"

/** Install the import hook to support "from js import …". */
int
JsImport_init();

#endif /* JSIMPORT_H */
