#ifndef PYIMPORT_H
#define PYIMPORT_H

#include <emscripten.h>
#include <emscripten/bind.h>
#include <emscripten/val.h>

/** Makes `var foo = pyodide.pyimport('foo')` work in Javascript.
 */

emscripten::val pyimport(emscripten::val name);

#endif /* PYIMPORT_H */
