#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"

// Stuff copied from ndarraytypes.h to check offsets
// First we need a couple of things.
typedef int npy_intp;
typedef void PyArray_Descr; // makes it opaque
typedef bool npy_bool;

#if true /* begin copied from numpy */

#define NPY_MAXDIMS 32
#define NPY_MAXARGS 32

/*
 * The main array object structure.
 *
 * It has been recommended to use the inline functions defined below
 * (PyArray_DATA and friends) to access fields here for a number of
 * releases. Direct access to the members themselves is deprecated.
 * To ensure that your code does not use deprecated access,
 * #define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
 * (or NPY_1_8_API_VERSION or higher as required).
 */
/* This struct will be moved to a private header in a future release */
typedef struct tagPyArrayObject_fields
{
  PyObject_HEAD
    /* Pointer to the raw data buffer */
    char* data;
  /* The number of dimensions, also called 'ndim' */
  int nd;
  /* The size in each dimension, also called 'shape' */
  npy_intp* dimensions;
  /*
   * Number of bytes to jump to get to the
   * next element in each dimension
   */
  npy_intp* strides;
  /*
   * This object is decref'd upon
   * deletion of array. Except in the
   * case of WRITEBACKIFCOPY which has
   * special handling.
   *
   * For views it points to the original
   * array, collapsed so no chains of
   * views occur.
   *
   * For creation from buffer object it
   * points to an object that should be
   * decref'd on deletion
   *
   * For WRITEBACKIFCOPY flag this is an
   * array to-be-updated upon calling
   * PyArray_ResolveWritebackIfCopy
   */
  PyObject* base;
  /* Pointer to type structure */
  PyArray_Descr* descr;
  /* Flags describing array -- see below */
  int flags;
  /* For weak references */
  PyObject* weakreflist;
} PyArrayObject_fields;

/*
 * Can't put this in npy_deprecated_api.h like the others.
 * PyArrayObject field access is deprecated as of NumPy 1.7.
 */
typedef PyArrayObject_fields PyArrayObject;

/* FWD declaration */
typedef struct PyArrayIterObject_tag PyArrayIterObject;

/*
 * type of the function which translates a set of coordinates to a
 * pointer to the data
 */
typedef char* (*npy_iter_get_dataptr_t)(PyArrayIterObject* iter, npy_intp*);

struct PyArrayIterObject_tag
{
  PyObject_HEAD int nd_m1; /* number of dimensions - 1 */
  npy_intp index, size;
  npy_intp coordinates[NPY_MAXDIMS]; /* N-dimensional loop */
  npy_intp dims_m1[NPY_MAXDIMS];     /* ao->dimensions - 1 */
  npy_intp strides[NPY_MAXDIMS];     /* ao->strides or fake */
  npy_intp backstrides[NPY_MAXDIMS]; /* how far to jump back */
  npy_intp factors[NPY_MAXDIMS];     /* shape factors */
  PyArrayObject* ao;
  char* dataptr; /* pointer to current item*/
  npy_bool contiguous;

  npy_intp bounds[NPY_MAXDIMS][2];
  npy_intp limits[NPY_MAXDIMS][2];
  npy_intp limits_sizes[NPY_MAXDIMS];
  npy_iter_get_dataptr_t translate;
};

typedef struct
{
  PyObject_HEAD int numiter;             /* number of iters */
  npy_intp size;                         /* broadcasted size */
  npy_intp index;                        /* current index */
  int nd;                                /* number of dims */
  npy_intp dimensions[NPY_MAXDIMS];      /* dimensions */
  PyArrayIterObject* iters[NPY_MAXARGS]; /* iterators */
} PyArrayMultiIterObject;

#endif /* end copied from numpy */

// To minimize change of confusion, make sure variables in here don't match any
// variables used in PyArray_Broadcast_part1
#define offset_Array_nd 12
#define offset_Array_dimensions 16

#define offset_Iter_ao 660

#define offset_MultIter_numiter 8
#define offset_MultIter_nd 20
#define offset_MultIter_dimensions 24
#define offset_MultIter_iters 152

/**
 * Check that our offsets match the numpy declarations.
 */
// clang-format off
int numpy_patch_init(){
  assert(offset_Array_nd         == offsetof(PyArrayObject, nd));
  assert(offset_Array_dimensions == offsetof(PyArrayObject, dimensions));

  assert(offset_Iter_ao == offsetof(PyArrayIterObject, ao));

  assert(offset_MultIter_numiter    == offsetof(PyArrayMultiIterObject, numiter));
  assert(offset_MultIter_nd         == offsetof(PyArrayMultiIterObject, nd));
  assert(offset_MultIter_dimensions == offsetof(PyArrayMultiIterObject, dimensions));
  assert(offset_MultIter_iters      == offsetof(PyArrayMultiIterObject, iters));
  return 0;
}
// clang-format on

// clang-format off
#define LOAD(ptr)            HEAP32[(ptr)/4]
#define LOAD_ARRAY(ptr, idx) LOAD(ptr + 4*idx)

#define Array_nd(ptr)                 LOAD(ptr + offset_Array_nd)
#define Array_dimensions(ptr)         LOAD(ptr + offset_Array_dimensions)

#define Iter_array(ptr)               LOAD(ptr + offset_Iter_ao)

#define MultiIter_numiter(ptr)          LOAD(ptr + offset_MultIter_numiter)
#define MultiIter_nd(ptr)               LOAD(ptr + offset_MultIter_nd)
#define MultiIter_iter(ptr, index)      LOAD_ARRAY(ptr + offset_MultIter_iters, index)
#define MultiIter_dimension(ptr, index) LOAD_ARRAY(ptr + offset_MultIter_dimensions, index)
// clang-format on

/**
 * It's annoying to set errors from Javascript.
 */
void
set_shape_mismatch_err()
{
  PyErr_SetString(
    PyExc_ValueError,
    "shape mismatch: objects cannot be broadcast to a single shape");
}

/**
 * This is basically a 1-1 port of the first segment of PyArray_Broadcast.
 * I rearranged the code a small amount to save effort.
 * Pretty much all that happened is that we destroyed type information, replaced
 * declarations with "let", and had to make special macros to do most memory
 * access which is much more annoying than in Javascript.
 *
 * See below for the C equivalent.
 */
EM_JS_NUM(int, PyArray_Broadcast_part1, (void* mit), {
  let numiter = MultiIter_numiter(mit);
  /* Discover the broadcast number of dimensions */
  let nd = 0;
  for (let i = 0; i < numiter; i++) {
    let cur_nd = Array_nd(Iter_array(MultiIter_iter(mit, i)));
    nd = (cur_nd > nd) ? cur_nd : nd;
  }
  MultiIter_nd(mit) = nd;

  /* Discover the broadcast shape in each dimension */
  let start_offset = (mit + offset_MultIter_dimensions) / 4;
  HEAP32.subarray(start_offset, start_offset + nd).fill(1);

  for (let j = 0; j < numiter; j++) {
    let it = MultiIter_iter(mit, j);
    for (i = 0; i < nd; i++) {
      /* This prepends 1 to shapes not already equal to nd */
      let cur_array = Iter_array(it);
      let cur_nd = Array_nd(cur_array);
      let k = i + cur_nd - nd;
      if (k >= 0) {
        let tmp = LOAD_ARRAY(Array_dimensions(cur_array), k);
        if (tmp == 1) {
          continue;
        }
        let mit_dim_i = MultiIter_dimension(mit, i);
        if (mit_dim_i == 1) {
          MultiIter_dimension(mit, i) = tmp;
        } else if (mit_dim_i != tmp) {
          _set_shape_mismatch_err();
          return -1;
        }
      }
    }
  }
})

// Here is the C code I based the above function on.
// This is lightly reorganized from the original definition.
/*
NPY_NO_EXPORT int
PyArray_Broadcast(PyArrayMultiIterObject *mit)
{
    int i, nd, k, j;
    npy_intp tmp, tmp2;
    PyArrayIterObject *it;
    PyArrayIterObject **it_ptr;

    / * Discover the broadcast number of dimensions * /
    for (i = 0, nd = 0; i < mit->numiter; i++) {
        nd = PyArray_MAX(nd, PyArray_NDIM(mit->iters[i]->ao));
    }
    mit->nd = nd;

    / * Discover the broadcast shape in each dimension * /
    for (i = 0; i < nd; i++) {
        mit->dimensions[i] = 1;
    }

    for (j = 0; j < mit->numiter; j++) {
        it = mit->iters[j];
        for (i = 0; i < nd; i++) {
            / * This prepends 1 to shapes not already equal to nd * /
            k = i + PyArray_NDIM(it->ao) - nd;
            if (k >= 0) {
                tmp = PyArray_DIMS(it->ao)[k];
                if (tmp == 1) {
                    continue;
                }
                if (mit->dimensions[i] == 1) {
                    mit->dimensions[i] = tmp;
                }
                else if (mit->dimensions[i] != tmp) {
                    PyErr_SetString(PyExc_ValueError,
                                    "shape mismatch: objects" \
                                    " cannot be broadcast" \
                                    " to a single shape");
                    return -1;
                }
            }
        }
    }

  // Rest of function skipped
}
*/
