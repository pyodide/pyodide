#ifndef DOCSTRING_H
#define DOCSTRING_H

int
set_method_docstring(PyMethodDef* method, PyObject* parent);

int
add_methods_and_set_docstrings(PyObject* module,
                               PyMethodDef* methods,
                               PyObject* docstring_source);

int
docstring_init();

#endif /* DOCSTRING_H */
