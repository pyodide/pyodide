import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.requires_dynamic_linking
@run_in_pyodide(packages=["test-simd"])
def test_simd_functions(selenium):
    import pytest
    from test_simd import simd_wrapper  # type: ignore[attr-defined]

    a = (1.0, 2.0, 3.0, 4.0)
    b = (10.0, 20.0, 30.0, 40.0)

    sum4 = sum(a) + sum(b)
    dot4 = sum(x * y for x, y in zip(a, b, strict=False))
    sum2 = sum(a[:2]) + sum(b[:2])
    dot2 = sum(x * y for x, y in zip(a[:2], b[:2], strict=False))

    # WASM / SSE f32x4
    assert simd_wrapper.wasm_add4_sum(*a, *b) == pytest.approx(sum4)
    assert simd_wrapper.sse_add4_sum(*a, *b) == pytest.approx(sum4)
    assert simd_wrapper.wasm_dot4(*a, *b) == pytest.approx(dot4)
    assert simd_wrapper.sse_dot4(*a, *b) == pytest.approx(dot4)

    # SSE2 f64x2
    assert simd_wrapper.sse2_add2_sum(*a[:2], *b[:2]) == pytest.approx(sum2)
    assert simd_wrapper.sse2_dot2(*a[:2], *b[:2]) == pytest.approx(dot2)

    # AVX f32x8 → duplicated 128b halves → 2× result
    assert simd_wrapper.avx_add8_sum(*a, *b) == pytest.approx(2 * sum4)
    assert simd_wrapper.avx_dot8(*a, *b) == pytest.approx(2 * dot4)
