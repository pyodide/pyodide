from pathlib import Path
import os

EMSDK = Path(__file__).resolve().parents[1] / "emsdk"

path = [
    str(EMSDK / "node" / "12.18.1_64bit" / "bin"),
    str(EMSDK / "binaryen" / "bin"),
    str(EMSDK / "fastcomp" / "emscripten"),
]

env = {
    "PATH": ":".join(path) + ":" + os.environ["PATH"],
    "EMSDK": str(EMSDK),
    "EM_CONFIG": str(EMSDK / ".emscripten"),
    "EM_CACHE": str(EMSDK / ".emscripten_cache"),
    "BINARYEN_ROOT": str(EMSDK / "binaryen"),
}

MAIN_C = """
#include <stdio.h>
#include <dlfcn.h>

int main() {
  puts("hello from main");
  void *handle = dlopen("library.wasm", RTLD_NOW);
  if (!handle) {
    puts("cannot load side module");
    puts(dlerror());
    return 1;
  }
  typedef void (*type_v)();
  type_v side_func = (type_v) dlsym(handle, "foo");
  if (!side_func) {
    puts("cannot load side function");
    puts(dlerror());
    return 1;
  } else {
    side_func();
  }
  return 0;
}
"""
