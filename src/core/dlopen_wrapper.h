#ifndef DLOPEN_WRAPPER_H
#define DLOPEN_WRAPPER_H

// This function is a wrapper around emscripten_dlopen that is called
// inside pyodide.loadPackage to load shraed libraries.
void
emscripten_dlopen_wrapper(const char* filename, int flags);

#endif /* DLOPEN_WRAPPER_H */
