#ifndef MY_TYPES_H
#define MY_TYPES_H
// https://elixir.bootlin.com/linux/latest/source/arch/powerpc/boot/types.h#L9
#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "stdbool.h"
#include "stdint.h"

#undef false
#undef true
// These work for both C and javascript.
// In C !!0 ==> 0 and in javascript !!0 ==> false
// In C !!1 ==> 1 and in javascript !!1 ==> true
// clang-format off
#define false (!!0)
#define true (!!1)
// clang-format on

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef int8_t i8;
typedef int16_t i16;
typedef int32_t i32;
typedef int64_t i64;

typedef float f32;
typedef double f64;

#endif /* MY_LINUX_TYPES_H */
