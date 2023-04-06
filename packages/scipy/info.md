The biggest issue that comes up in building scipy is that we don't have a good
fortran to wasm compiler. Some version of flang classic might work.

Instead of compiling from fortran directly, we rely on f2c to cross compile
the code to C and then compile C to wasm. We rely on f2c both directly and via
OpenBLAS which has f2c'd its Fortran files and then modified the generated C
files by hand.

A big problem with f2c is that it cannot handle implicit casts of function
arguments, because it tries to guess the types of the arguments of the function
being called based on the types of the arguments at the call site. There are
two distinct versions of this:

1. casts between number types -- we deal with this automatically in
   `fix_inconsistent_decls` in `_f2c_fixes.py`
2. casts between char\* and int -- this is too annoying to deal with
   automatically, so we write manual patches.

Type 1: the fortran equivalent of the following C code:

```C
double f(double x){
  return x + 5;
}

double g(int x){
  return f(x);
}
```

gets f2c'd to

```C
double f(double x){
  return x + 5;
}

double g(int x){
  double f(int);
  return f(x);
}
```

When we try to compile this, we get an error saying that f has been declared
with two different types.

Type 2: For each string argument, the Fortran ABI adds arguments at the end of
the argument list. LAPACK never declares functions as taking strings, preferring
to call them integers:

```C
int some_lapack_func(int *some_string, int *some_string_length){
 // ...
}
```

But then when we call it: `some_lapack_func("a string here", 14);` the f2c'd
version looks like:

```C
int str_len = 14;
int some_lapack_func(int *some_string, int *some_string_length, fortranlen some_string_length_again);
some_lapack_func("a string here", &str_len, 14);
```

When changing `packages/scipy/meta.yaml`, rebuilding scipy takes time, it can
be convenient to only build a few sub-packages to reduce iteration time. You
can add something like this to `packages/scipy/meta.yaml`:

```bash
# Define which sub-packages to keep
TO_KEEP='linalg|sparse|_lib|_build_utils'
# Update scipy/setup.py
perl -pi -e "s@(config.add_subpackage\(')(?!$TO_KEEP)@# \1\2@" scipy/setup.py
# delete unwanted folders to avoid unneeded cythonization
folders_to_delete=$(find scipy -mindepth 1 -maxdepth 1 -type d | grep -vP "$TO_KEEP")
rm -rf $folders_to_delete
```

Building only `scipy.(linalg|sparse|_lib|_build_utils)` takes ~4 minutes on my
machine compared to ~10-15 minutes for a full scipy build.
