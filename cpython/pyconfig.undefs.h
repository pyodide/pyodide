#undef HAVE_EPOLL
#undef HAVE_EPOLL_CREATE1
#undef HAVE_LINUX_VM_SOCKETS_H
#undef HAVE_SOCKETPAIR
#undef HAVE_UTIMENSAT
#undef HAVE_SIGACTION

/* Untested syscalls in emscripten */
#undef HAVE_OPENAT
#undef HAVE_MKDIRAT
#undef HAVE_FCHOWNAT
#undef HAVE_RENAMEAT
#undef HAVE_LINKAT
#undef HAVE_SYMLINKAT
#undef HAVE_READLINKAT
#undef HAVE_FCHMODAT
#undef HAVE_DUP3

/* Syscalls not implemented in emscripten */
#undef HAVE_PREADV
#undef HAVE_PWRITEV
#undef HAVE_PIPE2
#undef HAVE_NICE

/* Syscalls that resulted in a segfault */
#undef HAVE_UTIMENSAT
#undef HAVE_SYS_SOCKET_H
#undef HAVE_SYS_IOCTL_H

/* Unsupported functionality */
#undef HAVE_PTHREAD_H

#define CONFIG_32
#define ANSI
