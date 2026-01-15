#include "emscripten.h"
#include "stdio.h"

// Bind original poll syscall to syscall_poll_orig().
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
  return 0;
}
