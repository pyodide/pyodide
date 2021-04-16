#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"

static void
set_shape_mismatch_err()
{
  PyErr_SetString(PyExc_ValueError,
                  "shape mismatch: objects"
                  " cannot be broadcast"
                  " to a single shape");
}

EM_JS_NUM(int, PyArray_Broadcast_part1, (void* mit), {
  let i, nd, k, j;
  let tmp, tmp2;
  let it;
  let it_ptr;

  let numiter = HEAP32[(mit + 8) / 4];
  /* Discover the broadcast number of dimensions */
  nd = 0;
  for (i = 0; i < numiter; i++) {
    // nd = PyArray_MAX(nd, PyArray_NDIM(mit->iters[i]->ao));
    let it = HEAP32[(mit + 152 + 4 * i) / 4];
    // Look up ao
    let it_ao = HEAP32[(res + 660) / 4];
    // look up NDIM
    let it_ao_ndim = HEAP32[(res + 12) / 4];
    nd = (res > nd) ? res : nd;
  }
  // mit->nd = nd;
  HEAP32[(mit + 20) / 4] = nd;

  /* Discover the broadcast shape in each dimension */
  // for (i = 0; i < nd; i++) {
  //     mit->dimensions[i] = 1;
  // }
  HEAP32.subarray((mit + 24) / 4, (mit + 24 + nd) / 4).fill(1);

  for (j = 0; j < numiter; j++) {
    // it = mit->iters[i];
    it = HEAP32[(mit + 4 * j + 152) / 4];
    for (i = 0; i < nd; i++) {
      /* This prepends 1 to shapes not already equal to nd */
      // k = i + PyArray_NDIM(it->ao) - nd;
      let it_ao = HEAP32[(it + 660) / 4];
      let it_ao_ndim = HEAP32[(ao + 12) / 4];
      let k = i + it_ao_ndim - nd;
      if (k >= 0) {
        // tmp = PyArray_DIMS(it->ao)[k];
        let it_dims = HEAP32[(it_ao + 16) / 4];
        let it_dims_k = HEAP32[(it_dims + 4 * k) / 4];
        if (it_dims_k == 1) {
          continue;
        }
        // &mit->dimensions[i];
        let mit_dim_i_addr = mit + 4 * i + 24;
        // let tmp2 = mit->dimensions[i];
        let mit_dim_i = HEAP32[mit_dim_i_addr / 4];
        if (mit_dim_i == 1) {
          HEAP32[mit_dim_i_addr / 4] = it_dims_k;
        } else if (mit_dim_i != it_dims_k) {
          _set_shape_mismatch_err();
          return -1;
        }
      }
    }
  }
})

// int
// PyArray_Broadcast_inner2(void *mit){
// {
//     /*
//      * Reset the iterator dimensions and strides of each iterator
//      * object -- using 0 valued strides for broadcasting
//      * Need to check for overflow
//      */
//     tmp = PyArray_OverflowMultiplyList(mit->dimensions, mit->nd);
//     if (tmp < 0) {
//         PyErr_SetString(PyExc_ValueError,
//                         "broadcast dimensions too large.");
//         return -1;
//     }
//     mit->size = tmp;
// }

// EM_JS(
// int,
// PyArray_Broadcast_inner1, (void *mit) {
//     for (i = 0; i < mit->numiter; i++) {
//         it = mit->iters[i];
//         it->nd_m1 = mit->nd - 1;
//         it->size = tmp;
//         nd = PyArray_NDIM(it->ao);
//         if (nd != 0) {
//             it->factors[mit->nd-1] = 1;
//         }
//         for (j = 0; j < mit->nd; j++) {
//             it->dims_m1[j] = mit->dimensions[j] - 1;
//             k = j + nd - mit->nd;
//             /*
//              * If this dimension was added or shape of
//              * underlying array was 1
//              */
//             if ((k < 0) ||
//                 PyArray_DIMS(it->ao)[k] != mit->dimensions[j]) {
//                 it->contiguous = 0;
//                 it->strides[j] = 0;
//             }
//             else {
//                 it->strides[j] = PyArray_STRIDES(it->ao)[k];
//             }
//             it->backstrides[j] = it->strides[j] * it->dims_m1[j];
//             if (j > 0)
//                 it->factors[mit->nd-j-1] =
//                     it->factors[mit->nd-j] * mit->dimensions[mit->nd-j];
//         }
//         PyArray_ITER_RESET(it);
//     }
//     return 0;
// });
