// SSE2 path (f64x2, 2 lanes)
#include <emmintrin.h>

#if !defined(__wasm_simd128__) || !defined(__SSE2__)
#error "Requires -msimd128 and -msse2"
#endif

double
simd_sse2_add2_sum(double a0, double a1, double b0, double b1)
{
  __m128d va = _mm_set_pd(a1, a0);
  __m128d vb = _mm_set_pd(b1, b0);
  __m128d vc = _mm_add_pd(va, vb);
  double out[2];
  _mm_storeu_pd(out, vc);
  return out[0] + out[1];
}

double
simd_sse2_dot2(double a0, double a1, double b0, double b1)
{
  __m128d va = _mm_set_pd(a1, a0);
  __m128d vb = _mm_set_pd(b1, b0);
  __m128d vm = _mm_mul_pd(va, vb);
  double out[2];
  _mm_storeu_pd(out, vm);
  return out[0] + out[1];
}
