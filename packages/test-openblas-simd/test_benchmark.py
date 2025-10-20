"""
OpenBLAS vs OpenBLAS-SIMD performance comparison benchmark.

Verification goals:
- libopenblas_og.so: legacy build without explicit SIMD flags
- libopenblas.so: default build with explicit -msimd128 flags
- libopenblas_simd_o3.so: extra-aggressive SIMD build

Expected outcomes:
- SIMD expected to be 1.5-3x faster on large datasets
- Small datasets may see minimal gains or slight overhead
"""

import os
import pytest
from pytest_pyodide import run_in_pyodide


RUN_BENCHMARKS = os.environ.get("PYODIDE_RUN_OPENBLAS_BENCH") == "1"

pytestmark = pytest.mark.skipif(
    not RUN_BENCHMARKS,
    reason="OpenBLAS benchmarks run only when PYODIDE_RUN_OPENBLAS_BENCH=1",
)

@pytest.mark.requires_dynamic_linking
@run_in_pyodide(packages=["libopenblas", "libopenblas-og", "libopenblas-simd-o3"])
def test_benchmark_sdot(selenium):
    """cblas_sdot benchmark (single-precision vector dot product)."""
    import time
    from collections import OrderedDict
    from ctypes import CDLL, c_int, c_float, POINTER

    libs = OrderedDict(
        [
            ("baseline", CDLL("/usr/lib/libopenblas_og.so")),
            ("simd", CDLL("/usr/lib/libopenblas.so")),
            ("simd_o3", CDLL("/usr/lib/libopenblas_simd_o3.so")),
        ]
    )

    # Configure signatures
    for lib in libs.values():
        lib.cblas_sdot.argtypes = [c_int, POINTER(c_float), c_int, POINTER(c_float), c_int]
        lib.cblas_sdot.restype = c_float

    sizes = [10_000, 50_000, 307_200, 921_600, 2_073_600]
    iterations = 25

    timings = {name: {} for name in libs}

    for size in sizes:
        a = (c_float * size)(*[float(i % 1000) for i in range(size)])
        b = (c_float * size)(*[float((i * 2) % 1000) for i in range(size)])

        outputs = {}
        for name, lib in libs.items():
            sample_times = []
            for _ in range(iterations):
                start = time.perf_counter()
                res = lib.cblas_sdot(size, a, 1, b, 1)
                sample_times.append(time.perf_counter() - start)
            timings[name][size] = sum(sample_times) / len(sample_times) * 1000
            outputs[name] = res

        base_res = outputs["baseline"]
        for variant, res in outputs.items():
            if variant == "baseline":
                continue
            assert abs(base_res - res) < 1.0, f"Results differ: baseline={base_res}, {variant}={res}"

    # Pretty print summary
    print("\n" + "=" * 90)
    print("cblas_sdot Benchmark Results (Vector Dot Product)")
    print("=" * 90)
    header = (
        f"{'Size':<12} {'Baseline (ms)':<15} {'SIMD (ms)':<15} "
        f"{'SIMD-O3 (ms)':<15} {'Speedup SIMD':<12} {'Speedup O3':<12}"
    )
    print(header)
    print("-" * 90)
    for size in sizes:
        baseline_time = timings["baseline"][size]
        simd_time = timings["simd"][size]
        o3_time = timings["simd_o3"][size]
        ratio_simd = baseline_time / simd_time if simd_time > 0 else 0.0
        ratio_o3 = baseline_time / o3_time if o3_time > 0 else 0.0
        print(
            f"{size:<12} "
            f"{baseline_time:<15.6f} "
            f"{simd_time:<15.6f} "
            f"{o3_time:<15.6f} "
            f"{ratio_simd:<12.2f} "
            f"{ratio_o3:<12.2f}"
        )
    print("=" * 90)

    largest = max(sizes)
    assert timings["simd"][largest] <= timings["baseline"][largest] * 1.2
    assert timings["simd_o3"][largest] <= timings["baseline"][largest] * 1.5


@pytest.mark.requires_dynamic_linking
@run_in_pyodide(packages=["libopenblas", "libopenblas-og", "libopenblas-simd-o3"])
def test_benchmark_sgemm(selenium):
    """cblas_sgemm benchmark (single-precision matrix multiplication)."""
    import time
    from collections import OrderedDict
    from ctypes import CDLL, c_int, c_float, POINTER

    libs = OrderedDict(
        [
            ("baseline", CDLL("/usr/lib/libopenblas_og.so")),
            ("simd", CDLL("/usr/lib/libopenblas.so")),
            ("simd_o3", CDLL("/usr/lib/libopenblas_simd_o3.so")),
        ]
    )

    for lib in libs.values():
        lib.cblas_sgemm.argtypes = [
            c_int,
            c_int,
            c_int,
            c_int,
            c_int,
            c_int,
            c_float,
            POINTER(c_float),
            c_int,
            POINTER(c_float),
            c_int,
            c_float,
            POINTER(c_float),
            c_int,
        ]
        lib.cblas_sgemm.restype = None

    gemm_cases = [
        {"shape": (128, 128, 128), "iterations": 8},
        {"shape": (256, 256, 256), "iterations": 6},
        {"shape": (384, 384, 384), "iterations": 5},
        {"shape": (512, 512, 512), "iterations": 4},
    ]

    timings = {name: {} for name in libs}

    for case in gemm_cases:
        m, k, n = case["shape"]
        size_key = f"{m}x{k} @ {k}x{n}"

        a = (c_float * (m * k))(*[float(i % 100) / 100.0 for i in range(m * k)])
        b = (c_float * (k * n))(*[float(i % 100) / 100.0 for i in range(k * n)])
        c_buffers = {
            name: (c_float * (m * n))(*[0.0 for _ in range(m * n)]) for name in libs
        }

        order = 101  # CblasRowMajor
        trans = 111  # CblasNoTrans
        alpha = 1.0
        beta = 0.0
        lda = k
        ldb = n
        ldc = n

        for name, lib in libs.items():
            sample_times = []
            buffer = c_buffers[name]
            for _ in range(case["iterations"]):
                start = time.perf_counter()
                lib.cblas_sgemm(
                    order,
                    trans,
                    trans,
                    m,
                    n,
                    k,
                    alpha,
                    a,
                    lda,
                    b,
                    ldb,
                    beta,
                    buffer,
                    ldc,
                )
                sample_times.append(time.perf_counter() - start)
            timings[name][size_key] = sum(sample_times) / len(sample_times) * 1000

        base_buf = c_buffers["baseline"]
        for variant, buf in c_buffers.items():
            if variant == "baseline":
                continue
            max_diff = max(
                abs(base_buf[i] - buf[i]) for i in range(min(10, m * n))
            )
            assert max_diff < 0.01, f"Results differ too much ({variant}): max_diff={max_diff}"

    print("\n" + "=" * 90)
    print("cblas_sgemm Benchmark Results (Matrix-Matrix Multiplication)")
    print("=" * 90)
    header = (
        f"{'Shape':<20} {'Baseline (ms)':<15} {'SIMD (ms)':<15} "
        f"{'SIMD-O3 (ms)':<15} {'Speedup SIMD':<12} {'Speedup O3':<12}"
    )
    print(header)
    print("-" * 90)
    for size_key in timings["baseline"]:
        baseline_time = timings["baseline"][size_key]
        simd_time = timings["simd"][size_key]
        o3_time = timings["simd_o3"][size_key]
        ratio_simd = baseline_time / simd_time if simd_time > 0 else 0.0
        ratio_o3 = baseline_time / o3_time if o3_time > 0 else 0.0
        print(
            f"{size_key:<20} "
            f"{baseline_time:<15.6f} "
            f"{simd_time:<15.6f} "
            f"{o3_time:<15.6f} "
            f"{ratio_simd:<12.2f} "
            f"{ratio_o3:<12.2f}"
        )
    print("=" * 90)

    largest = list(timings["baseline"].keys())[-1]
    baseline_time = timings["baseline"][largest]
    simd_time = timings["simd"][largest]
    o3_time = timings["simd_o3"][largest]
    assert simd_time <= baseline_time * 1.35, (
        f"SIMD build slower than expected at {largest}: "
        f"{simd_time:.2f} ms vs baseline {baseline_time:.2f} ms"
    )
    assert o3_time <= baseline_time * 1.5, (
        f"SIMD-O3 build slower than expected at {largest}: "
        f"{o3_time:.2f} ms vs baseline {baseline_time:.2f} ms"
    )


@pytest.mark.requires_dynamic_linking
@run_in_pyodide(packages=["libopenblas", "libopenblas-og", "libopenblas-simd-o3"])
def test_verify_simd_instructions(selenium):
    """SIMD build verification: ensure outputs match the baseline"""
    from collections import OrderedDict
    from ctypes import CDLL, c_int, c_float, POINTER

    libs = OrderedDict(
        [
            ("baseline", CDLL("/usr/lib/libopenblas_og.so")),
            ("simd", CDLL("/usr/lib/libopenblas.so")),
            ("simd_o3", CDLL("/usr/lib/libopenblas_simd_o3.so")),
        ]
    )

    for lib in libs.values():
        lib.cblas_sdot.argtypes = [c_int, POINTER(c_float), c_int, POINTER(c_float), c_int]
        lib.cblas_sdot.restype = c_float

    # Simple test
    size = 4
    a = (c_float * size)(1.0, 2.0, 3.0, 4.0)
    b = (c_float * size)(5.0, 6.0, 7.0, 8.0)

    results = {name: lib.cblas_sdot(size, a, 1, b, 1) for name, lib in libs.items()}
    expected = 1*5 + 2*6 + 3*7 + 4*8  # 70.0

    print(f"\nVerification test (dot product of [1,2,3,4] and [5,6,7,8]):")
    print(f"  Expected: {expected}")
    for name in ["baseline", "simd", "simd_o3"]:
        print(f"  {name}: {results[name]}")
        assert abs(results[name] - expected) < 0.001, f"{name} result incorrect: {results[name]}"

    base_res = results["baseline"]
    for variant, res in results.items():
        if variant == "baseline":
            continue
        assert abs(base_res - res) < 0.001, f"baseline and {variant} results differ"
