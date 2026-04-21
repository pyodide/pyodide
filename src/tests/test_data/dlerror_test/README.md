Use the following command to compile the `main_func.c` file into a shared library:

The resulting shared library is intentionally broken to test the error message stored in the `dlerror` function.

```bash
emcc side.c -o libside.so -shared -sSIDE_MODULE=1
emcc main_func.c -o main_func.so -shared -sSIDE_MODULE=1 -L. -lside
rm -f libside.so  # remove side so that loading main_func.so will fail
```
