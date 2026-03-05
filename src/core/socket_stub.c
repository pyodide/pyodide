#include <stddef.h>
#include <stdint.h>

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
