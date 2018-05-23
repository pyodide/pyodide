#ifndef PYIMPORT_H
#define PYIMPORT_H

/** Makes `var foo = pyodide.pyimport('foo')` work in Javascript.
 */

int pyimport(char *name);
int pyimport_Ready();

#endif /* PYIMPORT_H */
