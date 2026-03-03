from setuptools import Extension, setup

module = Extension(
    "test_simd.simd_wrapper",
    sources=[
        "test_simd/simd_wrapper.c",
        "test_simd/simd_wasm.c",
        "test_simd/simd_sse.c",
        "test_simd/simd_sse2.c",
        "test_simd/simd_avx.c",
    ],
    extra_compile_args=["-msimd128", "-msse2", "-mavx"],
)
setup(name="test-simd", version="0.1.0", ext_modules=[module], packages=["test_simd"])
