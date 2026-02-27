#include "emscripten.h"
#include <stdint.h>

// Socket syscall overrides for NodeSockFS.
//
// Overrides __syscall_connect and __syscall_recvfrom to intercept NodeSock
// file descriptors and route them through async JSPI operations. Non-NodeSock
// fds fall through to the original Emscripten SOCKFS implementations.
//
// Ideally we'd bind the originals via __import_name__ (as CPython 3.14 does
// in Python/emscripten_syscalls.c), but Pyodide builds with EXPORT_ALL=1
// which causes every C function to appear in WASM_EXPORTS. Emscripten's
// jsifier.mjs skips emitting JS library functions that already exist as WASM
// exports, so the JS originals get dropped and the __import_name__ import
// becomes unsatisfiable at instantiation time.
//
// Instead, the original SOCKFS logic is reimplemented via EM_JS under
// different names (_orig_syscall_connect / _orig_syscall_recvfrom).
//
// GIL handling
// ────────────
// At the syscall level, CPython's socketmodule.c has already released the GIL
// via Py_BEGIN_ALLOW_THREADS (PyThreadState is NULL). syscall_syncify()
// reacquires the GIL via PyGILState_Ensure(), then delegates to
// JsvPromise_Syncify for the full state save/suspend/restore cycle.
// See suspenders.c syscall_syncify() for details.

// Defined in stack_switching/suspenders.c — syncify a promise from syscall
// context where the GIL is not held. Reacquires GIL, delegates to
// JsvPromise_Syncify, converts result to int, re-releases GIL.
extern int
syscall_syncify(__externref_t promise);

// Original Emscripten SOCKFS connect — reimplemented via EM_JS since the
// JS library version gets dropped when EXPORT_ALL=1 is active.
EM_JS(int, _orig_syscall_connect, (int fd, intptr_t addr, int addrlen), {
  var sock = Module.getSocketFromFD(fd);
  var info = Module.getSocketAddress(addr, addrlen);
  sock.sock_ops.connect(sock, info.addr, info.port);
  return 0;
})

// Original Emscripten SOCKFS recvfrom — reimplemented via EM_JS.
EM_JS(int, _orig_syscall_recvfrom, (int fd, intptr_t buf, int len, int flags, intptr_t addr, int addrlen), {
  var sock = Module.getSocketFromFD(fd);
  var msg = sock.sock_ops.recvmsg(sock, len);
  if (!msg) return 0;
  if (addr) {
    var errno = Module.writeSockaddr(
      addr, sock.family, Module.DNS.lookup_name(msg.addr), msg.port, addrlen
    );
  }
  Module.HEAPU8.set(msg.buffer, buf);
  return msg.buffer.byteLength;
})

// clang-format off

// Returns a Promise for NodeSock fds, null for everything else.
// When null, C code falls through to the original Emscripten implementation.
EM_JS(__externref_t, _maybe_connect_async, (int fd, intptr_t addr, int addrlen), {
  var SOCKFS = Module.SOCKFS;
  if (!SOCKFS || !SOCKFS.getSocket) return null;
  var sock = SOCKFS.getSocket(fd);
  if (!sock || !sock.sock_ops || !sock.sock_ops.connectAsync) return null;
  var info = Module.getSocketAddress(addr, addrlen);
  return sock.sock_ops.connectAsync(sock, info.addr, info.port);
})

// Returns a Promise for NodeSock fds, null for everything else.
EM_JS(__externref_t, _maybe_recvfrom_async, (int fd, intptr_t buf, int len), {
  var SOCKFS = Module.SOCKFS;
  if (!SOCKFS || !SOCKFS.getSocket) return null;
  var sock = SOCKFS.getSocket(fd);
  if (!sock || !sock.sock_ops || !sock.sock_ops.recvmsgAsync) return null;
  return sock.sock_ops.recvmsgAsync(sock, len).then(function(result) {
    if (result === null) return 0;
    Module.HEAPU8.set(result, buf);
    return result.length;
  });
})

// clang-format on

int
__syscall_connect(int fd,
                  intptr_t addr,
                  int addrlen,
                  int d1,
                  int d2,
                  int d3)
{
  __externref_t p = _maybe_connect_async(fd, addr, addrlen);
  if (__builtin_wasm_ref_is_null_extern(p)) {
    return _orig_syscall_connect(fd, addr, addrlen);
  }
  return syscall_syncify(p);
}

int
__syscall_recvfrom(int fd,
                   intptr_t buf,
                   int len,
                   int flags,
                   intptr_t addr,
                   int addrlen)
{
  __externref_t p = _maybe_recvfrom_async(fd, buf, len);
  if (__builtin_wasm_ref_is_null_extern(p)) {
    return _orig_syscall_recvfrom(fd, buf, len, flags, addr, addrlen);
  }
  return syscall_syncify(p);
}