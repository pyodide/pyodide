import pytest

@pytest.mark.requires_dynamic_linking
def test_simd_functions(selenium):
    assert selenium.run_js(
        """
        await pyodide.loadPackage("test-simd");
        const wasm = pyodide._module.LDSO.loadedLibsByName["/usr/lib/simd-wasm.so"].exports;
        const sse  = pyodide._module.LDSO.loadedLibsByName["/usr/lib/simd-sse.so"].exports;
        const a = [1,2,3,4], b = [10,20,30,40];
        const sum_wasm = wasm.simd_wasm_add4_sum(...a, ...b);
        const sum_sse  = sse.simd_sse_add4_sum(...a, ...b);
        const dot_wasm = wasm.simd_wasm_dot4(...a, ...b);
        const dot_sse  = sse.simd_sse_dot4(...a, ...b);
        return { sum_wasm, sum_sse, dot_wasm, dot_sse };
        """
    ) == {
        "sum_wasm": pytest.approx(sum([1,2,3,4,10,20,30,40])),
        "sum_sse": pytest.approx(sum([1,2,3,4,10,20,30,40])),
        "dot_wasm": pytest.approx(1*10+2*20+3*30+4*40),
        "dot_sse": pytest.approx(1*10+2*20+3*30+4*40),
    }