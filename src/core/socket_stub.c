#include "emscripten.h"
#include "stdio.h"

// Bind original setsockopt syscall to syscall_setsockopt_orig().
int
syscall_setsockopt_orig(int sockfd,
                        int level,
                        int optname,
                        intptr_t optval,
                        size_t optlen,
                        int dummy)
  __attribute__((__import_module__("env"),
                 __import_name__("__syscall_setsockopt"),
                 __warn_unused_result__));

// clang-format off

EM_JS(int, _apply_sockopt_js, (int fd, int level, int optname, int optval), {
  var SOCKFS = Module.SOCKFS;
  if (!SOCKFS || !SOCKFS.getSocket) {
    return 0;
  }

  var sock = SOCKFS.getSocket(fd);
  if (!sock) {
    return 0;
  }

  if (!sock.sockOpts) {
    sock.sockOpts = {};
  }
  sock.sockOpts[optname] = optval;

  var inner = sock.wcgSocket && sock.wcgSocket.innerSocket;
  if (!inner) {
    return 0;
  }

  if (level === 6 /* IPPROTO_TCP */ && optname === 1 /* TCP_NODELAY */) {
    if (typeof inner.setNoDelay === "function") {
      inner.setNoDelay(!!optval);
    }
  } else if (level === 1 /* SOL_SOCKET */ && optname === 9 /* SO_KEEPALIVE */) {
    if (typeof inner.setKeepAlive === "function") {
      inner.setKeepAlive(!!optval);
    }
  } else if (level === 6 /* IPPROTO_TCP */ && optname === 4 /* TCP_KEEPIDLE */) {
    if (typeof inner.setKeepAlive === "function") {
      // seconds → milliseconds
      inner.setKeepAlive(!!(1), optval * 1000);
    }
  }

  return 0;
});

EM_JS(int, _get_sockopt_js, (int fd, int level, int optname), {
  var SOCKFS = Module.SOCKFS;
  if (!SOCKFS || !SOCKFS.getSocket) {
    return -1;
  }

  var sock = SOCKFS.getSocket(fd);
  if (!sock || !sock.sockOpts) {
    return -1;
  }

  var val = sock.sockOpts[optname];
  if (val === undefined) {
    return -1;
  }
  return val;
});

// clang-format on

int
__syscall_setsockopt(int sockfd,
                     int level,
                     int optname,
                     intptr_t optval,
                     size_t optlen,
                     int dummy)
{
  int val = 0;
  if (optval && optlen >= sizeof(int)) {
    val = *(int*)optval;
  }

  _apply_sockopt_js(sockfd, level, optname, val);

  return 0;
}

int
__syscall_getsockopt(int sockfd,
                     int level,
                     int optname,
                     intptr_t optval,
                     intptr_t optlen,
                     int dummy)
{
  if (!optval || !optlen) {
    return 0;
  }

  int stored = _get_sockopt_js(sockfd, level, optname);
  if (stored == -1) {
    stored = 0;
  }

  size_t len = *(size_t*)optlen;
  if (len >= sizeof(int)) {
    *(int*)optval = stored;
    *(size_t*)optlen = sizeof(int);
  }

  return 0;
}
