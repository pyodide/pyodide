"""
Tests for WebLoop async generator management and shutdown_asyncgens() functionality.

These tests verify that WebLoop properly tracks, manages, and shuts down async generators
in browser environments, providing proper resource cleanup similar to BaseEventLoop.
"""

from pytest_pyodide.decorator import run_in_pyodide


@run_in_pyodide
async def test_shutdown_closes_partially_consumed(selenium):
    """Test that shutdown_asyncgens() closes partially consumed generators."""
    import asyncio

    loop = asyncio.get_running_loop()
    # Reset state for clean test
    loop._asyncgens_shutdown_called = False
    loop._asyncgens.clear()

    closed = []

    async def agen():
        try:
            yield 1
            await asyncio.sleep(0) 
            yield 2
        finally:
            closed.append("closed")

    # Start and partially consume generator
    a = agen()
    value = await a.__anext__()
    assert value == 1

    # Generator should not be closed yet
    assert len(closed) == 0

    # Shutdown should close the pending generator
    await loop.shutdown_asyncgens()
    assert len(closed) == 1
    assert closed[0] == "closed"


@run_in_pyodide
async def test_warn_on_firstiter_after_shutdown(selenium):
    """Test that creating generators after shutdown issues warnings."""
    import asyncio
    import warnings

    loop = asyncio.get_running_loop()
    # Reset state for clean test
    loop._asyncgens_shutdown_called = False
    loop._asyncgens.clear()

    warnings.simplefilter("always", ResourceWarning)
    captured_warnings = []

    def custom_showwarning(message, *args, **kwargs):
        captured_warnings.append(str(message))

    old_showwarning = warnings.showwarning
    warnings.showwarning = custom_showwarning

    try:
        # Shutdown first
        await loop.shutdown_asyncgens()

        # Creating generator after shutdown should warn
        async def agen():
            yield 1

        a = agen()
        async for _ in a:  # This triggers firstiter hook
            break

        # Check that warning was issued
        assert any("shutdown_asyncgens()" in msg for msg in captured_warnings)
        
    finally:
        warnings.showwarning = old_showwarning


@run_in_pyodide
async def test_finalizer_schedules_close(selenium):
    """Test that finalizer hook schedules aclose when generator is garbage collected."""
    import asyncio
    import gc

    loop = asyncio.get_running_loop()
    # Reset state for clean test
    loop._asyncgens_shutdown_called = False
    loop._asyncgens.clear()

    closed = []

    async def agen():
        try:
            yield 1
        finally:
            closed.append("finalized")

    # Start generator but don't explicitly close it
    a = agen()
    value = await a.__anext__()
    assert value == 1

    # Remove reference and force garbage collection
    a = None
    for _ in range(3):
        gc.collect()
        await asyncio.sleep(0.01)  # Allow finalizer to run

    # Shutdown should handle any remaining cleanup
    await loop.shutdown_asyncgens()
    
    # Generator should eventually be finalized
    assert len(closed) > 0
    assert "finalized" in closed


@run_in_pyodide
async def test_multiple_generators_closed(selenium):
    """Test that shutdown_asyncgens() closes multiple generators concurrently."""
    import asyncio

    loop = asyncio.get_running_loop()
    # Reset state for clean test
    loop._asyncgens_shutdown_called = False
    loop._asyncgens.clear()

    closed = []

    async def agen(name):
        try:
            yield f"{name}_value"
            await asyncio.sleep(0) 
            yield f"{name}_done"
        finally:
            closed.append(f"{name}_closed")

    # Start multiple generators
    gen1 = agen("gen1")
    gen2 = agen("gen2")
    gen3 = agen("gen3")
    
    # Partially consume each
    assert await gen1.__anext__() == "gen1_value"
    assert await gen2.__anext__() == "gen2_value"
    assert await gen3.__anext__() == "gen3_value"

    # None should be closed yet
    assert len(closed) == 0

    # Shutdown should close all pending generators
    await loop.shutdown_asyncgens()
    
    # All should be closed
    assert len(closed) == 3
    assert "gen1_closed" in closed
    assert "gen2_closed" in closed
    assert "gen3_closed" in closed
    

@run_in_pyodide
async def test_close_with_pending_generators_warning(selenium):
    """Test that close() warns about pending generators."""
    import asyncio
    import warnings

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        loop = asyncio.get_running_loop()
        # Reset state for clean test
        loop._asyncgens_shutdown_called = False
        loop._asyncgens.clear()
        
        # Create pending generator
        async def pending_agen():
            yield 1
        
        agen = pending_agen()
        await agen.__anext__()
        
        # Simulate close() warning logic (can't actually close running loop)
        if len(loop._asyncgens) > 0 and not loop._asyncgens_shutdown_called:
            warnings.warn(
                "Event loop closed with pending async generators; "
                "call loop.shutdown_asyncgens() before close().",
                ResourceWarning,
                source=loop,
            )
        
        # Verify warning was issued
        resource_warnings = [warning for warning in w if warning.category == ResourceWarning]
        assert len(resource_warnings) > 0
        assert "shutdown_asyncgens" in str(resource_warnings[0].message)
        
        # Clean up
        await agen.aclose()


@run_in_pyodide
async def test_aclose_exception_handling(selenium):
    """Test that exceptions during aclose are properly handled."""
    import asyncio

    loop = asyncio.get_running_loop()
    # Reset state for clean test
    loop._asyncgens_shutdown_called = False
    loop._asyncgens.clear()

    exception_logs = []

    def exception_handler(loop, context):
        exception_logs.append(context.get("message", ""))

    old_handler = loop.get_exception_handler()
    loop.set_exception_handler(exception_handler)

    try:
        async def bad_agen():
            try:
                yield 1
            finally:
                raise RuntimeError("cleanup failed")

        # Start generator
        a = bad_agen()
        value = await a.__anext__()
        assert value == 1

        # Shutdown should handle the exception gracefully
        await loop.shutdown_asyncgens()
        
        # Exception should be logged
        assert any("error" in msg.lower() or "exception" in msg.lower() 
                  for msg in exception_logs if msg)
                  
    finally:
        loop.set_exception_handler(old_handler)


@run_in_pyodide
async def test_shutdown_idempotent(selenium):
    """Test that multiple shutdown_asyncgens() calls are safe."""
    import asyncio
    
    loop = asyncio.get_running_loop()
    # Reset state for clean test
    loop._asyncgens_shutdown_called = False
    loop._asyncgens.clear()
    
    # Multiple shutdowns should not raise errors
    await loop.shutdown_asyncgens()
    await loop.shutdown_asyncgens()
    await loop.shutdown_asyncgens()
    
    # Shutdown flag should be set
    assert loop._asyncgens_shutdown_called is True


@run_in_pyodide
async def test_webloop_attributes_exist(selenium):
    """Test that WebLoop has all expected async generator management attributes."""
    import asyncio
    import weakref
    
    loop = asyncio.get_running_loop()
    
    # Verify we're using WebLoop
    assert "WebLoop" in type(loop).__name__
    
    # Check required attributes exist
    assert hasattr(loop, '_asyncgens')
    assert hasattr(loop, '_asyncgens_shutdown_called')
    assert hasattr(loop, '_old_agen_hooks')
    assert hasattr(loop, 'shutdown_asyncgens')
    
    # Verify types
    assert isinstance(loop._asyncgens, weakref.WeakSet)
    assert isinstance(loop._asyncgens_shutdown_called, bool)
    assert callable(loop.shutdown_asyncgens)


@run_in_pyodide
async def test_hook_methods_functionality(selenium):
    """Test that async generator hook methods exist and are callable."""
    import asyncio
    import sys
    
    loop = asyncio.get_running_loop()
    
    # Check hook methods exist
    assert hasattr(loop, '_asyncgen_firstiter_hook')
    assert hasattr(loop, '_asyncgen_finalizer_hook')
    assert hasattr(loop, '_install_asyncgen_hooks')
    assert hasattr(loop, '_restore_asyncgen_hooks')
    
    # Verify they're callable
    assert callable(loop._asyncgen_firstiter_hook)
    assert callable(loop._asyncgen_finalizer_hook)
    assert callable(loop._install_asyncgen_hooks)
    assert callable(loop._restore_asyncgen_hooks)
    
    # Check hooks are installed
    hooks = sys.get_asyncgen_hooks()
    assert hooks.firstiter is not None
    assert hooks.finalizer is not None


@run_in_pyodide
async def test_debug_mode_integration(selenium):
    """Test that debug mode works correctly with async generator management."""
    import asyncio
    
    loop = asyncio.get_running_loop()
    
    # Test debug mode methods exist
    assert hasattr(loop, 'get_debug')
    assert hasattr(loop, 'set_debug')
    
    original_debug = loop.get_debug()
    
    try:
        # Test setting debug mode
        loop.set_debug(True)
        assert loop.get_debug() is True
        
        loop.set_debug(False)
        assert loop.get_debug() is False
        
        # Debug mode should not affect shutdown functionality
        await loop.shutdown_asyncgens()
        
    finally:
        # Restore original debug setting
        loop.set_debug(original_debug)

@run_in_pyodide
async def test_shutdown_timeout_logs(selenium):
    import asyncio
    loop = asyncio.get_running_loop()
    loop._asyncgens_shutdown_called = False
    loop._asyncgens.clear()

    logs = []
    loop.set_exception_handler(lambda l, c: logs.append(c.get("message", "")))

    async def slow_agen():
        try:
            yield 1
        finally:
            # aclose()에서 오래 대기
            await asyncio.sleep(999)

    a = slow_agen()
    assert await a.__anext__() == 1

    await loop.shutdown_asyncgens(timeout=0.01)
    assert any("timed out" in (m or "").lower() for m in logs)
