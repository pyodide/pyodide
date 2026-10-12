#include "emscripten.h"
#include "error_handling.h"
#include "jslib.h"
#include <stddef.h>
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
syscall_syncify(JsVal promise);

// Returns a Promise for NodeSock fds, null for everything else.
// When null, C code falls through to the original Emscripten implementation.
EM_JS(JsVal, _maybe_connect_async, (int fd, intptr_t addr, int addrlen), {
  var sock = Module.SOCKFS.getSocket(fd);

  // Will return null for non-NodeSock fds.
  if (!sock?.sock_ops?.connectAsync)
    return null;

  var info = Module.getSocketAddress(addr, addrlen);
  return sock.sock_ops.connectAsync(sock, info.addr, info.port);
})

// Returns a Promise for NodeSock fds, null for everything else.
// recvmsgAsync may return:
//   Uint8Array — data received
//   0       — connection closed (EOF)
//   number < 0 — errno (e.g. -EAGAIN for non-blocking with no data)
EM_JS(JsVal, _maybe_recvfrom_async, (int fd, intptr_t buf, int len), {
  var sock = Module.SOCKFS.getSocket(fd);

  // Will return null for non-NodeSock fds.
  if (!sock?.sock_ops?.recvmsgAsync)
    return null;

  return (async function() {
    var result = await sock.sock_ops.recvmsgAsync(sock, len);
    // clang-format off
    if (typeof result === "number")
      return result;
    // clang-format on
    Module.HEAPU8.set(result, buf);
    return result.length;
  })();
})

// Returns a Promise for NodeSock fds, null for everything else.
EM_JS(JsVal, _maybe_sendto_async, (int fd, intptr_t message, int length), {
  var sock = Module.SOCKFS.getSocket(fd);

  // Will return null for non-NodeSock fds.
  if (!sock?.sock_ops?.sendmsgAsync)
    return null;

  // Copy data out of HEAPU8 before the async boundary — memory may grow.
  var data = Module.HEAPU8.slice(message, message + length);
  return sock.sock_ops.sendmsgAsync(sock, data);
})

// Emscripten's __syscall_fcntl64(F_SETFL) is noop for F_GETFL and F_SETFL
// but we would like to allow setting and getting the flags
// The return value indicates whether the operation was handled by this function
// If true, the result is stored in *result
EM_JS(bool, _try_fcntl64, (int fd, int cmd, int arg, int* result), {
  var sock = Module.SOCKFS.getSocket(fd);

  if (!sock?.sock_ops?.fcntl64)
    return false;

  Module.HEAP32[result >> 2] = sock.sock_ops.fcntl64(sock, cmd, arg);
  if (Module.HEAP32[result >> 2] < 0)
    return false;

  // other commands are fallback to emscripten's implementation
  return true;
})

// Returns a Promise for NodeSock fds, null for everything else.
// CPython socket timeouts call poll() before recv(). Emscripten's poll is
// synchronous, but NodeSock readiness depends on the async receive pump.
EM_JS(JsVal, _maybe_poll_async, (intptr_t fds, int nfds, int timeout), {
  if (!Module.SOCKFS.pollAsync) {
    return null;
  }

  // Check if there is any NodeSock fd
  // If not, return null to use emscripten's poll
  for (var i = 0; i < nfds; i++) {
    var pollfd = fds + 8 * i; // 8 == POLLFD_SIZE
    var fd = Module.HEAP32[pollfd >> 2];
    var stream = Module.FS.getStream(fd);
    if (!stream) {
      continue;
    }
    var sock = Module.SOCKFS.getSocket(fd);
    if (!sock?.sock_ops?.pollAsync) {
      return null;
    }
  }
  return Module.SOCKFS.pollAsync(fds, nfds, timeout);
})

// Try to handle shutdown syscall for NodeSock fds.
// Returns true if the operation was handled, false otherwise.
// If true, the result is stored in *result
EM_JS(bool, _try_shutdown, (int fd, int how, int* result), {
  var sock = Module.SOCKFS.getSocket(fd);

  if (!sock?.sock_ops?.shutdown)
    return false;

  Module.HEAP32[result >> 2] = sock.sock_ops.shutdown(sock, how);
  return true;
})

// clang-format off

int __real___syscall_connect(int fd, intptr_t addr, int addrlen, int d1, int d2, int d3);

int __real___syscall_recvfrom(int fd, intptr_t buf, int len, int flags, intptr_t addr, int addrlen);

int __real___syscall_sendto(int fd, intptr_t message, int length, int flags, intptr_t addr, int addrlen);

int __real___syscall_shutdown(int fd, int how, int d1, int d2, int d3, int d4);

int __real___syscall_fcntl64(int fd, int cmd, intptr_t varargs);

int __real___syscall_poll(intptr_t fds, int nfds, int timeout);


int __wrap___syscall_connect(int fd, intptr_t addr, int addrlen, int d1, int d2, int d3)
{
  JsVal p = _maybe_connect_async(fd, addr, addrlen);
  if (__builtin_wasm_ref_is_null_extern(p)) {
    return __real___syscall_connect(fd, addr, addrlen, d1, d2, d3);
  }
  return syscall_syncify(p);
}

int __wrap___syscall_recvfrom(int fd, intptr_t buf, int len, int flags, intptr_t addr, int addrlen)
{
  JsVal p = _maybe_recvfrom_async(fd, buf, len);
  if (__builtin_wasm_ref_is_null_extern(p)) {
    return __real___syscall_recvfrom(fd, buf, len, flags, addr, addrlen);
  }
  return syscall_syncify(p);
}

int __wrap___syscall_sendto(int fd, intptr_t message, int length, int flags, intptr_t addr, int addr_len)
{
  JsVal p = _maybe_sendto_async(fd, message, length);
  if (__builtin_wasm_ref_is_null_extern(p)) {
    return __real___syscall_sendto(fd, message, length, flags, addr, addr_len);
  }
  return syscall_syncify(p);
}

int __wrap___syscall_fcntl64(int fd, int cmd, intptr_t varargs)
{
  int result = 0;
  bool handled = _try_fcntl64(fd, cmd, varargs, &result);
  if (!handled) {
    return __real___syscall_fcntl64(fd, cmd, varargs);
  }
  return result;
}

int __wrap___syscall_poll(intptr_t fds, int nfds, int timeout)
{
  JsVal p = _maybe_poll_async(fds, nfds, timeout);
  if (__builtin_wasm_ref_is_null_extern(p)) {
    return __real___syscall_poll(fds, nfds, timeout);
  }
  return syscall_syncify(p);
}

int __wrap___syscall_shutdown(int fd, int how, int d1, int d2, int d3, int d4)
{
  int result = 0;
  bool handled = _try_shutdown(fd, how, &result);
  if (!handled) {
    // Emscripten does not support shutdown so this would fail anyways, but
    // we still want to return a meaningful error code
    // https://github.com/emscripten-core/emscripten/issues/13393
    return __real___syscall_shutdown(fd, how, d1, d2, d3, d4);
  }
  return result;
}

// clang-format on

int
__syscall_setsockopt(int sockfd,
                     int level,
                     int optname,
                     intptr_t optval,
                     size_t optlen,
                     int dummy)
{
  // Emscripten's stub setsockopt returns ENOPROTOOPT without doing anything,
  // which is considered as an error by applications.
  // We cannot support any useful setsockopt for now, but we return success
  // to avoid breaking applications.
  // TODO: Replace with a more appropriate error code.
  return 0;
}
