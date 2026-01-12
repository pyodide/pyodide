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
  printf("[C:__syscall_setsockopt] fd=%d, level=%d, optname=%d\n",
         sockfd,
         level,
         optname);
  // Emscripten's stub setsockopt returns ENOPROTOOPT without doing anything,
  // which is considered as an error by applications.
  // For now, we just log the call and return success.
  // FIXME(before merge): do something more useful here if needed, and merge it
  // with the patches in emscripten-settings.ts
  return 0;
}
