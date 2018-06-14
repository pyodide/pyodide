#include <Python.h>
#include <pythread.h>

/* A set of mock-ups for thread lock functionality that is required for
   Cython-generated modules to work.

   It is compiled into the main module, as if it came from Python itself.
*/

PyThread_type_lock
PyThread_allocate_lock(void)
{
  return (PyThread_type_lock)0x1;
}

void
PyThread_free_lock(PyThread_type_lock _)
{}

int
PyThread_acquire_lock(PyThread_type_lock _, int __)
{
  return PY_LOCK_ACQUIRED;
}
