#include "Python.h"

inline PyGILState_STATE PyGILState_Ensure(void) { return PyGILState_UNLOCKED; }

inline void PyGILState_Release(PyGILState_STATE state) { }
