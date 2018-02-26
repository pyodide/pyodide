#ifndef RUNPYTHON_H
#define RUNPYTHON_H

#include <string>

#include <emscripten.h>
#include <emscripten/bind.h>
#include <emscripten/val.h>

emscripten::val runPython(std::wstring code);

#endif /* RUNPYTHON_H */
