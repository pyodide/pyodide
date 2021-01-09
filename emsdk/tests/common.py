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
