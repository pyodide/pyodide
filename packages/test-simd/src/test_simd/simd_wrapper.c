#include <Python.h>

// Prototypes for existing SIMD implementations
// wasm (f32x4)
extern float
simd_wasm_add4_sum(float a0,
                   float a1,
                   float a2,
                   float a3,
                   float b0,
                   float b1,
                   float b2,
                   float b3);
extern float
simd_wasm_dot4(float a0,
               float a1,
               float a2,
               float a3,
               float b0,
               float b1,
               float b2,
               float b3);

// sse (f32x4)
extern float
simd_sse_add4_sum(float a0,
                  float a1,
                  float a2,
                  float a3,
                  float b0,
                  float b1,
                  float b2,
                  float b3);
extern float
simd_sse_dot4(float a0,
              float a1,
              float a2,
              float a3,
              float b0,
              float b1,
              float b2,
              float b3);

// sse2 (f64x2)
extern double
simd_sse2_add2_sum(double a0, double a1, double b0, double b1);
extern double
simd_sse2_dot2(double a0, double a1, double b0, double b1);

// avx (f32x8)
extern float
simd_avx_add8_sum(float a0,
                  float a1,
                  float a2,
                  float a3,
                  float b0,
                  float b1,
                  float b2,
                  float b3);
extern float
simd_avx_dot8(float a0,
              float a1,
              float a2,
              float a3,
              float b0,
              float b1,
              float b2,
              float b3);

// Python wrapper functions

static PyObject*
py_simd_wasm_add4_sum(PyObject* self, PyObject* args)
{
  float a0, a1, a2, a3, b0, b1, b2, b3;
  if (!PyArg_ParseTuple(
        args, "ffffffff", &a0, &a1, &a2, &a3, &b0, &b1, &b2, &b3)) {
    return NULL;
  }
  float r = simd_wasm_add4_sum(a0, a1, a2, a3, b0, b1, b2, b3);
  return Py_BuildValue("f", r);
}

static PyObject*
py_simd_wasm_dot4(PyObject* self, PyObject* args)
{
  float a0, a1, a2, a3, b0, b1, b2, b3;
  if (!PyArg_ParseTuple(
        args, "ffffffff", &a0, &a1, &a2, &a3, &b0, &b1, &b2, &b3)) {
    return NULL;
  }
  float r = simd_wasm_dot4(a0, a1, a2, a3, b0, b1, b2, b3);
  return Py_BuildValue("f", r);
}

static PyObject*
py_simd_sse_add4_sum(PyObject* self, PyObject* args)
{
  float a0, a1, a2, a3, b0, b1, b2, b3;
  if (!PyArg_ParseTuple(
        args, "ffffffff", &a0, &a1, &a2, &a3, &b0, &b1, &b2, &b3)) {
    return NULL;
  }
  float r = simd_sse_add4_sum(a0, a1, a2, a3, b0, b1, b2, b3);
  return Py_BuildValue("f", r);
}

static PyObject*
py_simd_sse_dot4(PyObject* self, PyObject* args)
{
  float a0, a1, a2, a3, b0, b1, b2, b3;
  if (!PyArg_ParseTuple(
        args, "ffffffff", &a0, &a1, &a2, &a3, &b0, &b1, &b2, &b3)) {
    return NULL;
  }
  float r = simd_sse_dot4(a0, a1, a2, a3, b0, b1, b2, b3);
  return Py_BuildValue("f", r);
}

static PyObject*
py_simd_sse2_add2_sum(PyObject* self, PyObject* args)
{
  double a0, a1, b0, b1;
  if (!PyArg_ParseTuple(args, "dddd", &a0, &a1, &b0, &b1)) {
    return NULL;
  }
  double r = simd_sse2_add2_sum(a0, a1, b0, b1);
  return Py_BuildValue("d", r);
}

static PyObject*
py_simd_sse2_dot2(PyObject* self, PyObject* args)
{
  double a0, a1, b0, b1;
  if (!PyArg_ParseTuple(args, "dddd", &a0, &a1, &b0, &b1)) {
    return NULL;
  }
  double r = simd_sse2_dot2(a0, a1, b0, b1);
  return Py_BuildValue("d", r);
}

static PyObject*
py_simd_avx_add8_sum(PyObject* self, PyObject* args)
{
  float a0, a1, a2, a3, b0, b1, b2, b3;
  if (!PyArg_ParseTuple(
        args, "ffffffff", &a0, &a1, &a2, &a3, &b0, &b1, &b2, &b3)) {
    return NULL;
  }
  float r = simd_avx_add8_sum(a0, a1, a2, a3, b0, b1, b2, b3);
  return Py_BuildValue("f", r);
}

static PyObject*
py_simd_avx_dot8(PyObject* self, PyObject* args)
{
  float a0, a1, a2, a3, b0, b1, b2, b3;
  if (!PyArg_ParseTuple(
        args, "ffffffff", &a0, &a1, &a2, &a3, &b0, &b1, &b2, &b3)) {
    return NULL;
  }
  float r = simd_avx_dot8(a0, a1, a2, a3, b0, b1, b2, b3);
  return Py_BuildValue("f", r);
}

// Module table & init

static PyMethodDef SimdMethods[] = {
  { "wasm_add4_sum",
    py_simd_wasm_add4_sum,
    METH_VARARGS,
    "WASM f32x4 add then sum" },
  { "wasm_dot4",
    py_simd_wasm_dot4,
    METH_VARARGS,
    "WASM f32x4 dot (sum of mul)" },
  { "sse_add4_sum",
    py_simd_sse_add4_sum,
    METH_VARARGS,
    "SSE f32x4 add then sum" },
  { "sse_dot4", py_simd_sse_dot4, METH_VARARGS, "SSE f32x4 dot (sum of mul)" },
  { "sse2_add2_sum",
    py_simd_sse2_add2_sum,
    METH_VARARGS,
    "SSE2 f64x2 add then sum" },
  { "sse2_dot2",
    py_simd_sse2_dot2,
    METH_VARARGS,
    "SSE2 f64x2 dot (sum of mul)" },
  { "avx_add8_sum",
    py_simd_avx_add8_sum,
    METH_VARARGS,
    "AVX f32x8 add then sum" },
  { "avx_dot8", py_simd_avx_dot8, METH_VARARGS, "AVX f32x8 dot (sum of mul)" },
  { NULL, NULL, 0, NULL }
};

static struct PyModuleDef simdmodule = {
  PyModuleDef_HEAD_INIT,
  "simd_wrapper",                                              // m_name
  "SIMD accelerated vector operations (WASM, SSE, SSE2, AVX)", // m_doc
  -1,                                                          // m_size
  SimdMethods,                                                 // m_methods
  NULL,
  NULL,
  NULL,
  NULL
};

PyMODINIT_FUNC
PyInit_simd_wrapper(void)
{
  return PyModule_Create(&simdmodule);
}
