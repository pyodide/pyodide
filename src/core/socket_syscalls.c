#include "emscripten.h"
#include <stdint.h>

// Socket syscall overrides for NodeSockFS.
//
// Overrides __syscall_connect, __syscall_recvfrom, and __syscall_sendto to
// intercept NodeSock file descriptors and route them through async JSPI
// operations. Non-NodeSock fds fall through to the original Emscripten SOCKFS
// implementations for compatibility.
//
// GIL handling
// ────────────
// At the syscall level, CPython's socketmodule.c has already released the GIL.
// syscall_syncify() reacquires the GIL, delegates to JsvPromise_Syncify for the
// full state save/suspend/restore cycle.
// See suspenders.c syscall_syncify() for details.

extern int
syscall_syncify(__externref_t promise);

int
_orig_syscall_connect(int fd,
                      intptr_t addr,
                      int addrlen,
                      int d1,
                      int d2,
                      int d3)
  __attribute__((__import_module__("env"),
                 __import_name__("__syscall_connect"),
                 __warn_unused_result__));

int
_orig_syscall_recvfrom(int fd,
                       intptr_t buf,
                       int len,
                       int flags,
                       intptr_t addr,
                       int addrlen)
  __attribute__((__import_module__("env"),
                 __import_name__("__syscall_recvfrom"),
                 __warn_unused_result__));

int
_orig_syscall_sendto(int fd,
                     intptr_t message,
                     int length,
                     int flags,
                     intptr_t addr,
                     int addrlen)
  __attribute__((__import_module__("env"),
                 __import_name__("__syscall_sendto"),
                 __warn_unused_result__));

// clang-format off

// Returns a Promise for NodeSock fds, null for everything else.
// When null, C code falls through to the original Emscripten implementation.
EM_JS(__externref_t, _maybe_connect_async, (int fd, intptr_t addr, int addrlen), {
  var sock = Module.SOCKFS.getSocket(fd);

  // Will return null for non-NodeSock fds.
  if (!sock || !sock.sock_ops || !sock.sock_ops.connectAsync) return null;

  var info = Module.getSocketAddress(addr, addrlen);
  return sock.sock_ops.connectAsync(sock, info.addr, info.port);
})

// Returns a Promise for NodeSock fds, null for everything else.
EM_JS(__externref_t, _maybe_recvfrom_async, (int fd, intptr_t buf, int len), {
  var sock = Module.SOCKFS.getSocket(fd);

  // Will return null for non-NodeSock fds.
  if (!sock || !sock.sock_ops || !sock.sock_ops.recvmsgAsync) return null;

  return sock.sock_ops.recvmsgAsync(sock, len).then(function(result) {
    if (result === null) return 0;
    Module.HEAPU8.set(result, buf);
    return result.length;
  });
})

// Returns a Promise for NodeSock fds, null for everything else.
EM_JS(__externref_t, _maybe_sendto_async, (int fd, intptr_t message, int length), {
  var sock = Module.SOCKFS.getSocket(fd);

  // Will return null for non-NodeSock fds.
  if (!sock || !sock.sock_ops || !sock.sock_ops.sendmsgAsync) return null;

  // Copy data out of HEAPU8 before the async boundary — memory may grow.
  var data = Module.HEAPU8.slice(message, message + length);
  return sock.sock_ops.sendmsgAsync(sock, data);
})

// clang-format on

int
__syscall_connect(int fd, intptr_t addr, int addrlen, int d1, int d2, int d3)
{
  __externref_t p = _maybe_connect_async(fd, addr, addrlen);
  if (__builtin_wasm_ref_is_null_extern(p)) {
    return _orig_syscall_connect(fd, addr, addrlen, d1, d2, d3);
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

int
__syscall_sendto(int fd,
                 intptr_t message,
                 int length,
                 int flags,
                 intptr_t addr,
                 int addr_len)
{
  __externref_t p = _maybe_sendto_async(fd, message, length);
  if (__builtin_wasm_ref_is_null_extern(p)) {
    return _orig_syscall_sendto(fd, message, length, flags, addr, addr_len);
  }
  return syscall_syncify(p);
}
