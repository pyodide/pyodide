"""SIMD test package.

Provides access to the CPython C-extension module `simd_wrapper`.
"""

from . import simd_wrapper

wasm_add4_sum = simd_wrapper.wasm_add4_sum
wasm_dot4 = simd_wrapper.wasm_dot4
sse_add4_sum = simd_wrapper.sse_add4_sum
sse_dot4 = simd_wrapper.sse_dot4
sse2_add2_sum = simd_wrapper.sse2_add2_sum
sse2_dot2 = simd_wrapper.sse2_dot2
avx_add8_sum = simd_wrapper.avx_add8_sum
avx_dot8 = simd_wrapper.avx_dot8

__all__ = [
    "simd_wrapper",
    "wasm_add4_sum",
    "wasm_dot4",
    "sse_add4_sum",
    "sse_dot4",
    "sse2_add2_sum",
    "sse2_dot2",
    "avx_add8_sum",
    "avx_dot8",
]
