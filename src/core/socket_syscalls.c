#include "emscripten.h"
#include <stdint.h>

// Socket syscall overrides for NodeSockFS.
//
// Overrides __syscall_connect, __syscall_recvfrom, and __syscall_sendto to
// intercept NodeSock file descriptors and route them through async JSPI
// operations. Non-NodeSock fds fall through to the original Emscripten SOCKFS
// fds fall through to the original Emscripten SOCKFS implementations for
// compatibility.
//
// Note that the original SOCKFS logic is reimplemented via EM_JS as
// Emscripten's jsifier.mjs drops the JS library functions when we link our
// JSPI version of the function with the same name.
//
// GIL handling
// ────────────
// At the syscall level, CPython's socketmodule.c has already released the GIL.
// syscall_syncify() reacquires the GIL, delegates to JsvPromise_Syncify for the
// full state save/suspend/restore cycle.
// See suspenders.c syscall_syncify() for details.

extern int
syscall_syncify(__externref_t promise);

// Original Emscripten SOCKFS connect
// https://github.com/emscripten-core/emscripten/blob/af01558779231dcf3524438e904b688a5576432c/src/lib/libsyscall.js#L374
EM_JS(int, _orig_syscall_connect, (int fd, intptr_t addr, int addrlen), {
  var sock = Module.getSocketFromFD(fd);
  var info = Module.getSocketAddress(addr, addrlen);
  sock.sock_ops.connect(sock, info.addr, info.port);
  return 0;
})

// Original Emscripten SOCKFS recvfrom
// https://github.com/emscripten-core/emscripten/blob/af01558779231dcf3524438e904b688a5576432c/src/lib/libsyscall.js#L411
EM_JS(int,
      _orig_syscall_recvfrom,
      (int fd, intptr_t buf, int len, int flags, intptr_t addr, int addrlen),
      {
        var sock = Module.getSocketFromFD(fd);
        var msg = sock.sock_ops.recvmsg(sock, len);
        if (!msg)
          return 0;
        if (addr) {
          var errno = Module.writeSockaddr(addr,
                                           sock.family,
                                           Module.DNS.lookup_name(msg.addr),
                                           msg.port,
                                           addrlen);
        }
        Module.HEAPU8.set(msg.buffer, buf);
        return msg.buffer.byteLength;
      })

// Original Emscripten SOCKFS sendto
// https://github.com/emscripten-core/emscripten/blob/af01558779231dcf3524438e904b688a5576432c/src/lib/libsyscall.js#L425
EM_JS(int,
      _orig_syscall_sendto,
      (int fd,
       intptr_t message,
       int length,
       int flags,
       intptr_t addr,
       int addr_len),
      {
        var sock = Module.getSocketFromFD(fd);
        if (!addr) {
          return sock.sock_ops.sendmsg(sock, Module.HEAP8, message, length);
        }
        var dest = Module.getSocketAddress(addr, addr_len);
        return sock.sock_ops.sendmsg(
          sock, Module.HEAP8, message, length, dest.addr, dest.port);
      })

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
