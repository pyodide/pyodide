#ifndef MY_TYPES_H
#define MY_TYPES_H
// https://elixir.bootlin.com/linux/latest/source/arch/powerpc/boot/types.h#L9

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef unsigned long long u64;
typedef signed char i8;
typedef short i16;
typedef int i32;
typedef long long i64;

typedef float f32;
typedef double f64;

typedef int bool;

#ifndef true
#define true 1
#endif

#ifndef false
#define false 0
#endif

// //
// http://notanumber.net/archives/33/newtype-in-c-a-touch-of-strong-typing-using-compound-literals
// /* this can be used for type safety, to avoid accidental casting of values
// from
//  * one type to another and allowing alias analysis by the compiler to
//  * distinguish otherwise identical types
//  *
//  * NEWTYPE(new_type,old_type); declares new_type to be an alias for the
//  already
//  * exsiting old_type TO_NT(new_type,val)  converts a value to its newtype
//  * representation FROM_NT(new_val)  opens up a newtyped value to get at its
//  * internal representation
//  */

// #define NEWTYPE(nty, oty)                                                      \
//   typedef struct                                                               \
//   {                                                                            \
//     oty v;                                                                     \
//   } nty
// #define FROM_NT(ntv) ((ntv).v)
// #define TO_NT(nty, val) ((nty){ .v = (val) })

#endif /* MY_LINUX_TYPES_H */
