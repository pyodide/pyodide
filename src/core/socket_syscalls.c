#include "emscripten.h"
#include <stdint.h>

// Socket syscall overrides for NodeSockFS.
//
// Uses the same WebAssembly.Suspending pattern as CPython 3.14's
// Python/emscripten_syscalls.c to suspend WASM execution while awaiting
// async socket operations.
//
// For non-NodeSock fds, the EM_JS functions return null and the C code calls
// the original Emscripten SOCKFS logic inline (we cannot import the original
// JS syscall functions via __import_name__ because defining them in C causes
// Emscripten to drop the JS versions entirely).
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
extern int syscall_syncify(__externref_t promise);

// clang-format off

// Returns a Promise for NodeSock fds, null for everything else.
// When null, C code runs the original Emscripten SOCKFS connect inline.
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
    var n = Math.min(result.bytesRead, len);
    Module.HEAPU8.set(result.buffer.subarray(0, n), buf);
    return n;
  });
})

// Original Emscripten SOCKFS connect logic (synchronous).
// Called for non-NodeSock fds (regular Emscripten sockets).
EM_JS(int, _emscripten_syscall_connect, (int fd, intptr_t addr, int addrlen), {
  try {
    var sock = getSocketFromFD(fd);
    var info = getSocketAddress(addr, addrlen);
    sock.sock_ops.connect(sock, info.addr, info.port);
    return 0;
  } catch (e) {
    if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
    return -e.errno;
  }
})

// Original Emscripten SOCKFS recvfrom logic (synchronous).
EM_JS(int, _emscripten_syscall_recvfrom, (int fd, intptr_t buf, int len,
                                          int flags, intptr_t addr,
                                          int addrlen), {
  try {
    var sock = getSocketFromFD(fd);
    var msg = sock.sock_ops.recvmsg(sock, len);
    if (!msg) return 0;
    if (addr) {
      var errno = writeSockaddr(addr, sock.family,
        DNS.lookup_name(msg.addr), msg.port, addrlen);
    }
    HEAPU8.set(msg.buffer, buf);
    return msg.buffer.byteLength;
  } catch (e) {
    if (typeof FS == "undefined" || !(e.name === "ErrnoError")) throw e;
    return -e.errno;
  }
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
    return _emscripten_syscall_connect(fd, addr, addrlen);
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
    return _emscripten_syscall_recvfrom(fd, buf, len, flags, addr, addrlen);
  }
  return syscall_syncify(p);
}