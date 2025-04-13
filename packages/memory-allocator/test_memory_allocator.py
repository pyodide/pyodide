from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["memory-allocator"])
def test_memory_allocator(selenium):
    from memory_allocator.test import TestMemoryAllocator

    mem = TestMemoryAllocator()
    for i in range(12):
        ptr = mem.aligned_malloc(2**i, 4048)
        assert ptr == ptr & ~(2**i - 1)
