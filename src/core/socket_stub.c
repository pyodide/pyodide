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
  return 0;
}
