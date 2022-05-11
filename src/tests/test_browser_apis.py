from pyodide_test_runner import run_in_pyodide


@run_in_pyodide
async def test_set_timeout_succeeded():
    success = False

    def foo():
        nonlocal success
        success = True

    import asyncio

    from pyodide import set_timeout

    set_timeout(foo, 500)
    await asyncio.sleep(1)

    assert success


@run_in_pyodide
async def test_clear_timeout_succeeded():
    success = False

    def foo():
        nonlocal success
        success = True

    import asyncio

    from pyodide import clear_timeout, set_timeout

    timeout_id = set_timeout(foo, 500)
    await asyncio.sleep(0.2)
    clear_timeout(timeout_id)

    assert not success


@run_in_pyodide
async def test_clear_timeout_destroyable_noop():
    success = False

    def foo():
        nonlocal success
        success = True

    import asyncio

    from pyodide import clear_timeout, set_timeout

    timeout_id = set_timeout(foo, 500)
    await asyncio.sleep(1)
    # This shouldn't crash
    clear_timeout(timeout_id)

    assert success


@run_in_pyodide
async def test_start_multiple_timeouts_and_clear_one():
    success1 = False
    success2 = False
    success3 = False

    def foo1():
        nonlocal success1
        success1 = True

    def foo2():
        nonlocal success2
        success2 = True

    def foo3():
        nonlocal success3
        success3 = True

    import asyncio

    from pyodide import clear_timeout, set_timeout

    timeout_id1 = set_timeout(foo1, 500)
    timeout_id2 = set_timeout(foo2, 500)
    set_timeout(foo3, 500)

    await asyncio.sleep(0.2)

    clear_timeout(timeout_id1)
    clear_timeout(timeout_id2)

    await asyncio.sleep(1)

    assert not success1
    assert not success2
    assert success3


@run_in_pyodide
async def test_trigger_event_listener():
    from pyodide import run_js

    x = run_js(
        """
class MockObject {
    constructor() {
        this.listeners = {};
    }
    addEventListener(event, handler) {
        if (event in this.listeners) {
            this.listeners[event].push(handler);
        }
        else {
            this.listeners[event] = [handler];
        }
    }
    removeEventListener(event, handler) {
        if (event in this.listeners) {
            this.listeners[event] = this.listeners[event].filter(
                (existingHandler) => existingHandler !== handler
            )
        }
    }
    triggerEvent(event) {
        if (this.listeners[event]) {
            for (const handler of this.listeners[event]) {
                handler({});
            }
        }
    }
}
let x = new MockObject();
x;
    """
    )
    triggered = False

    def foo(obj):
        nonlocal triggered
        triggered = True

    from pyodide import add_event_listener, remove_event_listener

    add_event_listener(x, "click", foo)
    x.triggerEvent("click")

    assert triggered

    remove_event_listener(x, "click", foo)


@run_in_pyodide
async def test_remove_event_listener():
    from pyodide import run_js

    x = run_js(
        """
class MockObject {
    constructor() {
        this.listeners = {};
    }
    addEventListener(event, handler) {
        if (event in this.listeners) {
            this.listeners[event].push(handler);
        }
        else {
            this.listeners[event] = [handler];
        }
    }
    removeEventListener(event, handler) {
        if (event in this.listeners) {
            this.listeners[event] = this.listeners[event].filter(
                (existingHandler) => existingHandler !== handler
            )
        }
    }
    triggerEvent(event) {
        if (this.listeners[event]) {
            for (const handler of this.listeners[event]) {
                handler({});
            }
        }
    }
}
let x = new MockObject();
x;
    """
    )
    triggered = False

    def foo(obj):
        nonlocal triggered
        triggered = True

    from pyodide import add_event_listener, remove_event_listener

    add_event_listener(x, "click", foo)
    remove_event_listener(x, "click", foo)
    x.triggerEvent("click")
    assert not triggered


@run_in_pyodide
async def test_trigger_some_of_multiple_event_listeners():
    from pyodide import run_js

    x = run_js(
        """
class MockObject {
    constructor() {
        this.listeners = {};
    }
    addEventListener(event, handler) {
        if (event in this.listeners) {
            this.listeners[event].push(handler);
        }
        else {
            this.listeners[event] = [handler];
        }
    }
    removeEventListener(event, handler) {
        if (event in this.listeners) {
            this.listeners[event] = this.listeners[event].filter(
                (existingHandler) => existingHandler !== handler
            )
        }
    }
    triggerEvent(event) {
        if (this.listeners[event]) {
            for (const handler of this.listeners[event]) {
                handler({});
            }
        }
    }
}
let x = new MockObject();
x;
    """
    )
    triggered1 = False
    triggered2 = False
    triggered3 = False

    def foo1(obj):
        nonlocal triggered1
        triggered1 = True

    def foo2(obj):
        nonlocal triggered2
        triggered2 = True

    def foo3(obj):
        nonlocal triggered3
        triggered3 = True

    from pyodide import add_event_listener, remove_event_listener

    add_event_listener(x, "click", foo1)
    add_event_listener(x, "click", foo2)
    add_event_listener(x, "click", foo3)

    remove_event_listener(x, "click", foo1)
    x.triggerEvent("click")

    assert not triggered1
    assert triggered2
    assert triggered3

    remove_event_listener(x, "click", foo2)
    remove_event_listener(x, "click", foo3)


@run_in_pyodide
async def test_remove_event_listener_twice():
    from pyodide import run_js

    x = run_js(
        """
class MockObject {
    constructor() {
        this.listeners = {};
    }
    addEventListener(event, handler) {
        if (event in this.listeners) {
            this.listeners[event].push(handler);
        }
        else {
            this.listeners[event] = [handler];
        }
    }
    removeEventListener(event, handler) {
        if (event in this.listeners) {
            this.listeners[event] = this.listeners[event].filter(
                (existingHandler) => existingHandler !== handler
            )
        }
    }
    triggerEvent(event) {
        if (this.listeners[event]) {
            for (const handler of this.listeners[event]) {
                handler({});
            }
        }
    }
}
let x = new MockObject();
x;
    """
    )
    triggered = False
    error_raised = False

    def foo(obj):
        nonlocal triggered
        triggered = True

    from pyodide import add_event_listener, remove_event_listener

    add_event_listener(x, "click", foo)
    remove_event_listener(x, "click", foo)

    try:
        remove_event_listener(x, "click", foo)
    except KeyError:
        error_raised = True

    assert error_raised


@run_in_pyodide
async def test_nonexistant_remove_event_listener():
    from pyodide import run_js

    x = run_js(
        """
class MockObject {
    constructor() {
        this.listeners = {};
    }
    addEventListener(event, handler) {
        if (event in this.listeners) {
            this.listeners[event].push(handler);
        }
        else {
            this.listeners[event] = [handler];
        }
    }
    removeEventListener(event, handler) {
        if (event in this.listeners) {
            this.listeners[event] = this.listeners[event].filter(
                (existingHandler) => existingHandler !== handler
            )
        }
    }
    triggerEvent(event) {
        if (this.listeners[event]) {
            for (const handler of this.listeners[event]) {
                handler({});
            }
        }
    }
}
let x = new MockObject();
x;
    """
    )
    triggered = False
    error_raised = False

    def foo(obj):
        nonlocal triggered
        triggered = True

    from pyodide import remove_event_listener

    try:
        remove_event_listener(x, "click", foo)
    except KeyError:
        error_raised = True

    assert error_raised
