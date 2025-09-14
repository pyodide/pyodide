// WebAssembly SIMD intrinsics path (f32x4, 4 lanes)
#include <wasm_simd128.h>

#ifndef __wasm_simd128__
#error "Requires -msimd128"
#endif

float
simd_wasm_add4_sum(float a0,
                   float a1,
                   float a2,
                   float a3,
                   float b0,
                   float b1,
                   float b2,
                   float b3)
{
  v128_t va = wasm_f32x4_make(a0, a1, a2, a3);
  v128_t vb = wasm_f32x4_make(b0, b1, b2, b3);
  v128_t vc = wasm_f32x4_add(va, vb);
  float out[4];
  wasm_v128_store(out, vc);
  return out[0] + out[1] + out[2] + out[3];
}

float
simd_wasm_dot4(float a0,
               float a1,
               float a2,
               float a3,
               float b0,
               float b1,
               float b2,
               float b3)
{
  v128_t va = wasm_f32x4_make(a0, a1, a2, a3);
  v128_t vb = wasm_f32x4_make(b0, b1, b2, b3);
  v128_t vm = wasm_f32x4_mul(va, vb);
  float out[4];
  wasm_v128_store(out, vm);
  return out[0] + out[1] + out[2] + out[3];
}
