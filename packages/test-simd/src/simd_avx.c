// AVX path (f32x8, 8 lanes)
// WebAssembly SIMD only supports 128-bit vectors.
// When compiling AVX intrinsics, Emscripten lowers each 256-bit op into two 128-bit ops.
// Here we duplicate the lower 128b so result = 2 × SSE (shows upper half is active).
#include <immintrin.h>

#if !defined(__wasm_simd128__) || !defined(__AVX__)
#error "Requires -msimd128 and -mavx"
#endif

float simd_avx_add8_sum(
  float a0, float a1, float a2, float a3,
  float b0, float b1, float b2, float b3
) {
  __m256 va = _mm256_set_ps(a3, a2, a1, a0, a3, a2, a1, a0);
  __m256 vb = _mm256_set_ps(b3, b2, b1, b0, b3, b2, b1, b0);
  __m256 vc = _mm256_add_ps(va, vb);
  float out[8];
  _mm256_storeu_ps(out, vc);
  // Collapse 8-lane vector to scalar for JS/Python assertions
  float s = 0.0f;
  for (int i = 0; i < 8; i++) {
    s += out[i];
  }
  return s;
}

float simd_avx_dot8(
  float a0, float a1, float a2, float a3,
  float b0, float b1, float b2, float b3
) {
  __m256 va = _mm256_set_ps(a3, a2, a1, a0, a3, a2, a1, a0);
  __m256 vb = _mm256_set_ps(b3, b2, b1, b0, b3, b2, b1, b0);
  __m256 vm = _mm256_mul_ps(va, vb);
  float out[8];
  _mm256_storeu_ps(out, vm);
  // Collapse 8-lane vector to scalar for JS/Python assertions
  float s = 0.0f;
  for (int i = 0; i < 8; i++) {
    s += out[i];
  }
  return s;
}


