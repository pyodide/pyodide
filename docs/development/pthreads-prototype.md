# Experimental pthreads build (prototype)

This branch carries an opt-in, experimental build of Pyodide with CPython
threading (pthreads) enabled, investigating the state of Emscripten's
pthreads + dynamic-linking support (see issue
[#237](https://github.com/pyodide/pyodide/issues/237)). It is a prototype:
not ABI-stable, not CI-tested, and not intended to ship as-is.

## Building

```sh
PYODIDE_PTHREADS=1 make all-but-packages
PYODIDE_PTHREADS=1 PYODIDE_PACKAGES="tag:pytest,tag:pyodide.test,numpy,!test-rust-abi,!test-rust-panic" make -C packages
```

Everything is guarded by `ifdef PYODIDE_PTHREADS`, so the default build is
unchanged. The flag adds `-pthread` to `CFLAGS_BASE`/`LDFLAGS_BASE` (which
pyodide-build also picks up, so package side modules need no extra
configuration), passes `--enable-wasm-pthreads` to CPython's configure,
builds sqlite threadsafe, adds `-pthread` to every vendored static library
(wasm-ld refuses `--shared-memory` if any object lacks the atomics and
bulk-memory features), and links the main module with
`-sPTHREAD_POOL_SIZE=8 -sPTHREAD_POOL_SIZE_STRICT=0`.

Testing:

```sh
# Node (no special setup needed)
PYODIDE_PTHREADS=1 pytest src/tests/test_core_python.py --runtime node -m long_running -k thread

# Browser: SharedArrayBuffer requires cross-origin isolation, so the regular
# `python -m http.server` is not enough:
python tools/serve_coi.py 8000 --directory dist
# then check `crossOriginIsolated === true` in devtools.
```

The pytest fixtures in `conftest.py` automatically serve COOP/COEP headers
and skip memory snapshots when `PYODIDE_PTHREADS=1` is set.

## Results (Emscripten 5.0.3, Pyodide 314.1.0.dev0, June 2026)

| Rung | Node 26 | Chrome (headless, COI) |
| --- | --- | --- |
| Boot, `sys._emscripten_info.pthreads == True` | pass | pass |
| `threading.Thread` start/run/join | pass | pass |
| Locks, `queue`, `ThreadPoolExecutor` | pass | pass |
| CPython stdlib: `test_thread`, `test_threading`, `test_threading_local`, `test_threadedtempfile`, `test_thread_local_bytecode`, `test_importlib.test_threaded_import` | pass | not run |
| dlopen numpy before threads (baseline) | pass | pass |
| dlopen numpy **while a Python thread runs** | pass | not run |
| import numpy **inside a spawned thread** (per-thread dylib table sync) | pass | not run |
| re-dlopen of an already-loaded library (ctypes) | pass | not run |
| 48 numpy matmuls on 12 threads (pool size 8, deferred spawn) | pass (0.6 s) | pass (4 threads) |

Stdlib failures, both platform gaps rather than threading bugs (annotated in
`src/tests/python_tests.yaml`): `test_concurrent_futures.test_thread_pool`
(imports `InterpreterPoolExecutor`, needs the `_interpreters` module) and
`test_threadsignals` (`signal.alarm` does not exist on Emscripten).

## Bugs found and fixed along the way

1. **CPython's wasm-gc call trampoline is incompatible with pthreads**
   (`cpython/patches/0010-Disable-wasm-gc-trampoline-in-pthreads-builds.patch`).
   Two independent problems, both worth reporting upstream to CPython:
   - The hardcoded trampoline wasm binary imports `env.memory` without the
     shared flag, so instantiation fails at boot in a shared-memory build
     ("LinkError: mismatch in shared state of memory, declared = 0,
     imported = 1").
   - Worse: the trampoline function pointer is created with `addFunction` on
     the main thread and stored in (shared) `_PyRuntimeState`. Every pthread
     has its **own** `WebAssembly.Table`, and Emscripten only mirrors
     dlopen'd libraries between thread tables, not `addFunction` entries.
     The first Python call on a spawned thread crashes with
     "RuntimeError: table index is out of bounds" in `_PyEM_TrampolineCall`.
     The crash is nearly invisible: the worker dies, sets
     `crashed_thread_id`, and the main thread later throws the cryptic
     `Error: unwind` from `_emscripten_yield` the next time it enters wasm.
   The patch falls back to the JS trampoline (which resolves the function
   pointer through the calling thread's own table) whenever `wasmMemory` is
   a `SharedArrayBuffer`. A proper fix could instantiate the trampoline once
   per thread instead.

2. **Pyodide's injected JS runs in every pthread worker.** The
   `pyodide_pre.gen.dat` tail (`pre.js`, `stack_switching.out.js`,
   `pyodide_js_init()`) executes at module-evaluation time, which includes
   pthread workers, where `Module.API` and `Module.preRun` do not exist. The
   recipe now defines `IS_PYODIDE_PTHREAD` (via `ENVIRONMENT_IS_PTHREAD`)
   and skips `pyodide_js_init()` on workers; `pre.js` and
   `stack_switching.mjs` got matching guards.

3. **`JSEvents` needs native code from `libhtml5` under pthreads**
   (`_emscripten_run_callback_on_thread`), but `AUTO_NATIVE_LIBRARIES=0`
   keeps it out of the link and `MAIN_MODULE=1` whole-archive linking of
   `-lhtml5` drags in `emscripten_wget.c` and unwanted JS library deps. The
   Makefile compiles just `system/lib/html5/callback.c` into the link.

4. **`embuilder build libgl --pthreads` no longer exists** in Emscripten
   5.x; the multithreaded port variant is the named target
   `libGL-mt-getprocaddr`.

5. **Memory snapshots are incompatible with shared memory** (the snapshot
   code copies `Module.HEAP8`, which views a `SharedArrayBuffer`). The
   conftest skips snapshots under `PYODIDE_PTHREADS=1`; `make all` (which
   builds `dist/snapshot.bin`) has not been adapted — use
   `make all-but-packages` + `make -C packages`.

## Upstream issues we expected to hit but did not (on 5.0.3)

- [emscripten#26913](https://github.com/emscripten-core/emscripten/issues/26913)
  (`_emscripten_dlsync_threads` deadlock): a regression introduced by the
  futex rework in 5.0.7 and fixed post-5.0.7 — 5.0.3 predates it, which is
  presumably why dlopen-with-live-threads worked here. An Emscripten upgrade
  should re-run probe 2 (`/tmp` probes are reproduced in the issue-comment
  draft below).
- [emscripten#26227](https://github.com/emscripten-core/emscripten/issues/26227)
  (re-dlopen deadlock): not reproduced via the ctypes re-dlopen path.

## Known gaps / follow-up work

- **FFI is not thread-safe.** Hiwire/JsProxy state and the `js` module exist
  per JS realm; touching them from a spawned thread is undefined behavior.
  Threads must stick to pure-Python/native compute. A real design (proxying
  to the main thread, or per-thread hiwire state) is the largest open item.
- **jsverror wiring is main-thread-only**: workers get no-op stubs from
  `src/core/libjsverror.js`, so JS-error funneling into wasm is degraded off
  the main thread.
- **ABI**: `-pthread` changes the ABI; every package wheel must be rebuilt.
  A shipped threaded Pyodide means a second ABI tag / build matrix.
- **Deployment**: COOP/COEP cross-origin isolation breaks header-less hosts
  and CDN loading without CORP/CORS — a threaded build can only be opt-in.
- **PYODIDE_SYMBOLS=1 + pthreads breaks boot** (`API._pyodide` undefined in
  `finalizeBootstrap`) — the RUNTIME_DEBUG instrumentation appears to
  interact with the EM_JS injection; debug with `EXTRA_LDFLAGS=-g2` instead.
- **Snapshots** (above), `test_snapshots.py` should be skipped.
- The default (non-pthread) build is expected to be unchanged but was not
  re-verified after the Makefile edits; run normal CI before merging
  anything from this branch.
- Stress areas not yet probed: JSPI/stack-switching × threads
  (`test_stack_switching.py`), `ALLOW_MEMORY_GROWTH` view-staleness under
  growth on a worker, Firefox/Safari, fs access from threads.
