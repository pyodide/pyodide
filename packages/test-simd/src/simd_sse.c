#include <xmmintrin.h>

float simd_sse_add4_sum(float a0,float a1,float a2,float a3,
                        float b0,float b1,float b2,float b3){
  __m128 va = _mm_set_ps(a3,a2,a1,a0);
  __m128 vb = _mm_set_ps(b3,b2,b1,b0);
  __m128 vc = _mm_add_ps(va,vb);
  float out[4]; _mm_storeu_ps(out, vc);
  return out[0]+out[1]+out[2]+out[3];
}

float simd_sse_dot4(float a0,float a1,float a2,float a3,
                    float b0,float b1,float b2,float b3){
  __m128 va = _mm_set_ps(a3,a2,a1,a0);
  __m128 vb = _mm_set_ps(b3,b2,b1,b0);
  __m128 vm = _mm_mul_ps(va,vb);
  float out[4]; _mm_storeu_ps(out, vm);
  return out[0]+out[1]+out[2]+out[3];
}