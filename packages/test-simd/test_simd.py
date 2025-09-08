import pytest


@pytest.mark.requires_dynamic_linking
def test_simd_functions(selenium):
    # Compute expected scalars for readability
    a = [1, 2, 3, 4]
    b = [10, 20, 30, 40]
    sum4 = sum(a) + sum(b)
    dot4 = sum(x * y for x, y in zip(a, b, strict=False))
    sum2 = sum(a[:2]) + sum(b[:2])
    dot2 = a[0] * b[0] + a[1] * b[1]

    assert selenium.run_js(
        """
        await pyodide.loadPackage("test-simd");
        const wasm = pyodide._module.LDSO.loadedLibsByName["/usr/lib/simd-wasm.so"].exports;
        const sse  = pyodide._module.LDSO.loadedLibsByName["/usr/lib/simd-sse.so"].exports;
        const sse2 = pyodide._module.LDSO.loadedLibsByName["/usr/lib/simd-sse2.so"]?.exports;
        const avx  = pyodide._module.LDSO.loadedLibsByName["/usr/lib/simd-avx.so"]?.exports;

        const a = [1,2,3,4], b = [10,20,30,40];
        const sum_wasm = wasm.simd_wasm_add4_sum(...a, ...b);
        const sum_sse  = sse.simd_sse_add4_sum(...a, ...b);
        const dot_wasm = wasm.simd_wasm_dot4(...a, ...b);
        const dot_sse  = sse.simd_sse_dot4(...a, ...b);

        const sum_sse2 = sse2 ? sse2.simd_sse2_add2_sum(1,2,10,20) : null;
        const dot_sse2 = sse2 ? sse2.simd_sse2_dot2(1,2,10,20) : null;
        const sum_avx = avx ? avx.simd_avx_add8_sum(...a, ...b) : null;
        const dot_avx = avx ? avx.simd_avx_dot8(...a, ...b) : null;

        return { sum_wasm, sum_sse, dot_wasm, dot_sse, sum_sse2, dot_sse2, sum_avx, dot_avx };
        """
    ) == {
        "sum_wasm": pytest.approx(sum4),
        "sum_sse": pytest.approx(sum4),
        "dot_wasm": pytest.approx(dot4),
        "dot_sse": pytest.approx(dot4),
        "sum_sse2": pytest.approx(sum2),
        "dot_sse2": pytest.approx(dot2),
        "sum_avx": pytest.approx(2 * sum4),
        "dot_avx": pytest.approx(2 * dot4),
    }
