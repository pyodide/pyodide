# JavaScript Promise Integration (JSPI) in Pyodide

This document explains how Pyodide implements JavaScript Promise Integration (JSPI) to enable synchronous-style code in Python to await JavaScript promises.

## Overview

JSPI is a WebAssembly feature that allows WebAssembly code to suspend execution while waiting for a JavaScript promise to resolve, then resume from where it left off. Pyodide uses this to implement `run_sync()`, which lets Python code synchronously wait for async operations.

### Key APIs

- **`WebAssembly.Suspending`**: Wraps a JavaScript async function so it can suspend the WebAssembly stack when called from WebAssembly
- **`WebAssembly.promising`** (or the older `WebAssembly.Function` with `{ promising: "first" }`): Wraps a WebAssembly function so that calling it returns a Promise that resolves when the function completes (including any suspensions)

## Architecture

The JSPI implementation spans several files:

```
src/core/stack_switching/
├── stack_switching.mjs    # Entry point, feature detection
├── suspenders.mjs         # JavaScript side: createPromising, promisingApply
├── suspenders.c           # C side: syncifyHandler, JsvPromise_Syncify
├── stack_state.mjs        # Manages WebAssembly argument stack state
└── pystate.c              # Manages Python thread state during suspension
```

## Feature Detection

In `stack_switching.mjs`:

```javascript
export const newJspiSupported = canConstructWasm && "Suspending" in WebAssembly;
export const oldJspiSupported = canConstructWasm && "Suspender" in WebAssembly;
export const jspiSupported = newJspiSupported || oldJspiSupported;
```

The code supports both the new JSPI API (`WebAssembly.Suspending`/`WebAssembly.promising`) and the older API (`WebAssembly.Suspender`/`WebAssembly.Function` with suspending options).

## Core Components

### 1. Creating a Promising Function (`createPromising`)

The `createPromising` function in `suspenders.mjs` wraps a WebAssembly function so it returns a Promise:

```javascript
export function createPromising(wasm_func) {
  if (Module.newJspiSupported) {
    const promisingFunc = WebAssembly.promising(wasm_func);
    async function wrapper(...args) {
      const orig = validSuspender.value;
      validSuspender.value = true;
      try {
        return await promisingFunc(null, ...args);
      } finally {
        validSuspender.value = orig;
      }
    }
    return wrapper;
  }
  // Fallback to old API...
}
```

### 2. The Syncify Handler (`syncifyHandler`)

In `suspenders.c`, the `syncifyHandler` is a JavaScript function wrapped with `WebAssembly.Suspending`:

```javascript
async function inner(x, y) {
  // In the old JSPI API, we get the promise as first argument.
  // In the new JSPI API we get it as the second argument.
  try {
    return await (x ?? y);
  } catch (e) {
    if (e && e.pyodide_fatal_error) {
      throw e;
    }
    Module.syncify_error = e;
    return Module.error;
  }
}
if (newJspiSupported) {
  syncifyHandler = new WebAssembly.Suspending(inner);
}
```

This handler:
1. Receives a promise to await
2. Suspends the WebAssembly stack
3. Waits for the promise to resolve
4. Returns the result (or captures errors)

### 3. Global State Management

Two important global variables track suspension state:

- **`suspenderGlobal`**: Stores the current suspender object (used internally by JSPI)
- **`validSuspender`**: A flag indicating whether suspension is currently allowed

```javascript
export let suspenderGlobal = { value: null };
export let validSuspender = { value: false };
```

## Data Flow

### Calling Python with Stack Switching (`callPromising`)

When JavaScript calls a Python function with stack switching enabled:

```
JavaScript                          WebAssembly/C                      Python
    │                                    │                                │
    │  pyFunc.callPromising(args)        │                                │
    │ ──────────────────────────────────>│                                │
    │                                    │                                │
    │  promisingApply(...)               │                                │
    │ ──────────────────────────────────>│                                │
    │    (sets validSuspender = true)    │                                │
    │    (records stackStop)             │                                │
    │                                    │                                │
    │                                    │  _pyproxy_apply_promising()    │
    │                                    │ ──────────────────────────────>│
    │                                    │    (sets suspender)            │
    │                                    │                                │
    │                                    │                                │ Python code runs
    │                                    │                                │
    │                                    │<────────────────────────────── │ returns result
    │<────────────────────────────────── │                                │
    │  Promise resolves                  │                                │
```

### Python Awaiting a JS Promise (`run_sync`)

When Python code calls `run_sync(promise)`:

```
Python                              C/WebAssembly                      JavaScript
    │                                    │                                │
    │  run_sync(promise)                 │                                │
    │ ──────────────────────────────────>│                                │
    │                                    │                                │
    │                                    │  JsvPromise_Syncify(promise)   │
    │                                    │ ──────────────────────────────>│
    │                                    │                                │
    │                                    │  saveState()                   │
    │                                    │    - StackState captures       │
    │                                    │      argument stack            │
    │                                    │    - captureThreadState()      │
    │                                    │      saves Python state        │
    │                                    │                                │
    │                                    │  syncifyHandler(suspender,     │
    │                                    │                 promise)       │
    │                                    │ ──────────────────────────────>│
    │                                    │                                │
    │                                    │    ┌─────────────────────────┐ │
    │                                    │    │ WebAssembly SUSPENDS    │ │
    │                                    │    │ (stack is saved)        │ │
    │                                    │    └─────────────────────────┘ │
    │                                    │                                │
    │                                    │                                │ await promise
    │                                    │                                │
    │                                    │    ┌─────────────────────────┐ │
    │                                    │    │ WebAssembly RESUMES     │ │
    │                                    │    │ (stack is restored)     │ │
    │                                    │    └─────────────────────────┘ │
    │                                    │                                │
    │                                    │  restoreState()               │
    │                                    │    - StackState.restore()     │
    │                                    │    - restoreThreadState()     │
    │                                    │                                │
    │<────────────────────────────────── │                                │
    │  result returned                   │                                │
```

## Stack State Management

The `StackState` class in `stack_state.mjs` manages the WebAssembly argument stack during suspension:

```
               |     ^^^       |
               |  older data   |
               |               |
  stack_stop . |_______________|
        .      |               |
        .      |     data      |
        .      |   in stack    |
        .    * |_______________| . .  _____________  stack_start + _copy.length
        .      |               |     |             |
        .      |     data      |     |  data saved |
        .      |   for next    |     |  in _copy   |
               | continuation  |     |             |
 stack_start . |               | . . |_____________| stack_start
               |               |
               |  newer data   |
               |     vvv       |
```

Key operations:
- **`constructor()`**: Captures current stack pointer (`start`) and the entry point (`stop`)
- **`restore()`**: Restores the argument stack data and stack pointers
- **`_save()`/`_save_up_to()`**: Saves stack data to `_copy` when another continuation needs the space

## Python Thread State Management

The `pystate.c` file handles Python's thread state during suspension:

### `captureThreadState()`
1. Saves asyncio state (current event loop and task)
2. Calls `_leave_task` to properly exit the current asyncio task
3. Creates a new `PyThreadState` for the continuation
4. Swaps to the new thread state

### `restoreThreadState()`
1. Calls `_enter_task` to re-enter the asyncio task
2. Swaps back to the original thread state
3. Manages a freelist of thread states for efficiency

## Error Handling

Errors during suspension are handled specially:

1. **JavaScript errors**: Caught in `syncifyHandler`, stored in `Module.syncify_error`
2. **Python errors**: Saved via `PyErr_GetRaisedException()` in `_pyproxy_apply_promising`
3. **No valid suspender**: Returns `Module.error` and sets appropriate Python exception

```c
JsVal JsvPromise_Syncify(JsVal promise) {
  JsVal state = saveState();
  if (JsvError_Check(state)) {
    return JS_ERROR;  // No valid suspender
  }
  JsVal suspender = get_suspender();
  JsVal result = syncifyHandler(suspender, promise);
  restoreState(state);
  if (JsvError_Check(result)) {
    JsvPromise_Syncify_handleError();
  }
  return result;
}
```

## Public API

### Python Side

```python
from pyodide.ffi import run_sync, can_run_sync

# Check if stack switching is available
if can_run_sync():
    # Synchronously wait for an async operation
    result = run_sync(some_js_promise)
    result = run_sync(some_async_coroutine())
```

### JavaScript Side

```javascript
// Call a Python function with stack switching enabled
const result = await pyFunc.callPromising(arg1, arg2);

// With keyword arguments
const result = await pyFunc.callPromisingKwargs(arg1, { kwarg1: value1 });
```

## Initialization

JSPI is initialized during Pyodide startup if supported:

```javascript
// In stack_switching.mjs
if (jspiSupported) {
  Module.preRun.push(initSuspenders);
}

// initSuspenders creates the promising wrappers
export function initSuspenders() {
  promisingApplyHandler = createPromising(wasmExports._pyproxy_apply_promising);
  if (wasmExports.run_main_promising) {
    promisingRunMainHandler = createPromising(wasmExports.run_main_promising);
  }
}
```

## Limitations

1. **Runtime support required**: JSPI must be supported by the JavaScript runtime
2. **Entry point requirement**: `run_sync` only works when Python was entered via an async path (`callPromising`, `runPythonAsync`, etc.)
3. **Single suspension point**: Only one suspension can be active at a time per call chain

## Browser/Runtime Support

- **Chrome/Chromium**: Supported (with flags in older versions)
- **Firefox**: Supported in recent versions
- **Safari**: Not yet supported
- **Node.js**: Supported with `--experimental-wasm-stack-switching` flag
- **Deno**: Supported in recent versions

## Related Files

- `src/core/pyproxy.ts`: `callPyObjectKwargsPromising()` - JavaScript entry point
- `src/core/pyproxy.c`: `_pyproxy_apply_promising()` - C entry point
- `src/core/jsproxy.c`: `run_sync()` - Python entry point, `JsvPromise_Syncify()`
- `src/tests/test_stack_switching.py`: Test suite for JSPI functionality
