#ifndef RUNPYTHON_H
#define RUNPYTHON_H

/** The primary entry point function that runs Python code.
 */

#include <string>

#include <emscripten.h>
#include <emscripten/bind.h>
#include <emscripten/val.h>

/** The primary entry point function that runs Python code.
 */
emscripten::val runPython(std::wstring code);

#endif /* RUNPYTHON_H */
