The biggest issue that comes up in building scipy is that we don't have a good
fortran to wasm compiler. Some version of flang classic might work.

Instead of compiling from fortran directly, we rely on f2c to cross compile
the code to C and then compile C to wasm. We rely on f2c both directly and via
CLAPACK which is f2c'd LAPACK.

Unfortunately, f2c only handles fortran 77 code and it doesn't work perfectly
even on that. After LAPACK version 3.2 (released in 2008), LAPACK started
adding methods that use newer fortran features, so they cannot be f2c'd. Hence
it's unlikely that new versions of CLAPACK will be released and we can't use
any newer version of CLAPACK.

Scipy is built based on a newer version of CLAPACK and I couldn't figure out
how to remove the newer functions. They cause dynamic linking errors when
scipy is imported. To find the list of problem functions I used:

```sh
wasm-objdump clapack_all.so -d | sed -n 's/.*func.*<\(.*\)>:/\1/p' | sort -u > clapack_exports.txt
```

to list the symbols exported from our clapack and

```
wasm-objdump _flapack.so -d | sed -E -n 's/.*global.get [0-9]* <([a-z]*_?)>/\1/p' | sort -u > symbols.txt
```

to list the symbols that `_flapack.so` expects to see. There are 36 symbols in
this list. Conveniently, LAPACK defines one function per file, so I just
download a copy of LAPACK and cat these functions into
`scipy/linalg/src/lapack_deprecations/cgegv.f` which is chosen arbitrarily from
the `.f` source files that are linked into `_flapack.so` (there aren't that many
options though). Using an existing file allows us to avoid fiddling with build
scripts. Of the 36 missing symbol, 32 of them are written in Fortran 77 and work
fine. The remaining 4 need removing but I couldn't figure out how to take them
out in any sensible way (I can't understand all the layers of codegen that
happen in scipy), so I give them do-nothing definitions, and then in the build
script remove lines containing them with `sed`.

Another big problem with f2c is that it cannot handle implicit casts of function
arguments, because it tries to guess the types of the arguments of the function
being called based on the types of the arguments at the call site. There are two
distinct versions of this:

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
