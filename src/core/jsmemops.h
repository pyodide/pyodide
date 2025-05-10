// Macros to access memory from JavaScript

#define DEREF_U8(addr, offset) HEAPU8[addr + offset]
#define DEREF_I8(addr, offset) HEAP8[addr + offset]

#define DEREF_U16(addr, offset) HEAPU16[(addr >> 1) + offset]
#define DEREF_I16(addr, offset) HEAP16[(addr >> 1) + offset]

#define DEREF_U32(addr, offset) HEAPU32[(addr >> 2) + offset]
#define DEREF_I32(addr, offset) HEAP32[(addr >> 2) + offset]

#define DEREF_F32(addr, offset) HEAPF32[(addr >> 2) + offset]
#define DEREF_F64(addr, offset) HEAPF64[(addr >> 3) + offset]

#define ASSIGN_U8(addr, offset, value) DEREF_U8(addr, offset) = value
#define ASSIGN_U16(addr, offset, value) DEREF_U16(addr, offset) = value
#define ASSIGN_U32(addr, offset, value) DEREF_U32(addr, offset) = value
#if WASM_BIGINT
// We have HEAPU64 / HEAPI64 in this case.
#define DEREF_U64(addr, offset) HEAPU64[(addr >> 3) + offset]
#define DEREF_I64(addr, offset) HEAP64[(addr >> 3) + offset]

#define LOAD_U64(addr, offset) DEREF_U64(addr, offset)
#define LOAD_I64(addr, offset) DEREF_I64(addr, offset)

#define STORE_U64(addr, offset, val) (DEREF_U64(addr, offset) = val)
#define STORE_I64(addr, offset, val) (DEREF_U64(addr, offset) = val)

#else

// No BigUint64Array, have to manually split / join lower and upper byte
//
#define BIGINT_LOWER(x) (Number((x) & BigInt(0xffffffff)) | 0)
#define BIGINT_UPPER(x) (Number((x) >> BigInt(32)) | 0)
#define UBIGINT_FROM_PAIR(lower, upper)                                        \
  (BigInt(lower) | (BigInt(upper) << BigInt(32)))

#define IBIGINT_FROM_PAIR(lower, upper)                                        \
  (BigInt(lower) | (BigInt(upper + 2 * (upper & 0x80000000)) << BigInt(32)))

#define LOAD_U64(addr, offset)                                                 \
  UBIGINT_FROM_PAIR(DEREF_U32(addr, offset * 2),                               \
                    DEREF_U32(addr, offset * 2 + 1))
#define LOAD_I64(addr, offset)                                                 \
  IBIGINT_FROM_PAIR(DEREF_U32(addr, offset * 2),                               \
                    DEREF_U32(addr, offset * 2 + 1))

#define STORE_U64(addr, offset, val)                                           \
  ((DEREF_U32(addr, offset * 2) = BIGINT_LOWER(val)),                          \
   (DEREF_U32(addr, offset * 2 + 1) = BIGINT_UPPER(val)))
#define STORE_I64 STORE_U64
#endif
