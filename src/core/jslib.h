#ifndef JSLIB_H
#define JSLIB_H
#include "hiwire/hiwire.h"

#include "types.h"

#define WARN_UNUSED __attribute__((warn_unused_result))
#define errcode int WARN_UNUSED

typedef HwRef JsRef;
typedef __externref_t JsVal;

typedef struct Js_Identifier
{
  const char* string;
  JsRef object;
} Js_Identifier;

#define Jsv_null __builtin_wasm_ref_null_extern()
#define JsvNull_Check(x) __builtin_wasm_ref_is_null_extern(x)

#define Js_static_string_init(value) { .string = value, .object = NULL }
#define Js_static_string(varname, value)                                       \
  static Js_Identifier varname = Js_static_string_init(value)
#define Js_IDENTIFIER(varname) Js_static_string(JsId_##varname, #varname)

#define hiwire_CLEAR(x)                                                        \
  do {                                                                         \
    hiwire_decref(x);                                                          \
    x = NULL;                                                                  \
  } while (0)

// Special JsRefs for singleton constants.
extern JsRef Jsr_undefined;
extern JsRef Jsr_true;
extern JsRef Jsr_false;
extern JsRef Jsr_novalue;
extern JsRef Jsr_error;


// ==================== JS_ERROR ====================

#define JS_ERROR hiwire_get(Jsr_error)

__attribute__((import_module("sentinel"), import_name("is_sentinel"))) int
JsvError_Check(JsVal val);

#define Jsv_undefined hiwire_get(Jsr_undefined)
#define Jsv_true hiwire_get(Jsr_true)
#define Jsv_false hiwire_get(Jsr_false)
#define Jsv_novalue hiwire_get(Jsr_novalue)

int JsvNoValue_Check(JsVal);

// ==================== Conversions between JsRef and JsVal ====================

JsRef
JsRef_new(JsVal v);

JsVal
JsRef_pop(JsRef ref);

JsVal
JsRef_toVal(JsRef ref);

// ==================== Primitive Conversions ====================

JsVal
JsvNum_fromInt(int x);

JsVal
JsvNum_fromDouble(double x);

JsVal
JsvNum_fromDigits(const unsigned int* digits, size_t ndigits);

bool
Jsv_to_bool(JsVal x);

JsVal
Jsv_typeof(JsVal x);

char*
Jsv_constructorName(JsVal obj);

JsVal
JsvUTF8ToString(const char*);

JsRef
JsrString_FromId(Js_Identifier* id);

JsVal
JsvString_FromId(Js_Identifier* id);

// ==================== JsvArray API  ====================

JsVal
JsvArray_New();

bool
JsvArray_Check(JsVal obj);

JsVal
JsvArray_Get(JsVal, int);

errcode
JsvArray_Set(JsVal, int, JsVal);

JsVal
JsvArray_Delete(JsVal, int);

int JsvArray_Push(JsVal, JsVal);

void JsvArray_Extend(JsVal, JsVal);

errcode
JsvArray_Insert(JsVal arr, int idx, JsVal value);

JsVal
JsvArray_ShallowCopy(JsVal obj);

JsVal
JsvArray_slice(JsVal obj, int length, int start, int stop, int step);

errcode
JsvArray_slice_assign(JsVal idobj,
                      int slicelength,
                      int start,
                      int stop,
                      int step,
                      int values_length,
                      PyObject** values);

// ==================== JsvObject API  ====================

JsVal
JsvObject_New();

JsVal JsvObject_Entries(JsVal);

JsVal JsvObject_Keys(JsVal);

JsVal JsvObject_Values(JsVal);

JsVal
JsvObject_toString(JsVal obj);

int
JsvObject_SetAttr(JsVal obj, JsVal attr, JsVal value);

JsVal
JsvObject_CallMethod(JsVal obj, JsVal meth, JsVal args);

JsVal
JsvObject_CallMethod_NoArgs(JsVal obj, JsVal meth);

JsVal
JsvObject_CallMethod_OneArg(JsVal obj, JsVal meth, JsVal arg);

JsVal
JsvObject_CallMethod_TwoArgs(JsVal obj, JsVal meth, JsVal arg1, JsVal arg2);

JsVal
JsvObject_CallMethodId(JsVal obj, Js_Identifier* meth_id, JsVal args);

JsVal
JsvObject_CallMethodId_NoArgs(JsVal obj, Js_Identifier* name_id);

JsVal
JsvObject_CallMethodId_OneArg(JsVal obj, Js_Identifier* meth_id, JsVal arg);

JsVal
JsvObject_CallMethodId_TwoArgs(JsVal obj,
                               Js_Identifier* meth_id,
                               JsVal arg1,
                               JsVal arg2);

// ==================== JsvFunction API  ====================

bool
JsvFunction_Check(JsVal obj);

JsVal
JsvFunction_Call_OneArg(JsVal func, JsVal arg);

JsVal
JsvFunction_CallBound(JsVal func, JsVal this, JsVal args);

JsVal
JsvFunction_Construct(JsVal func, JsVal args);

// ==================== Promises  ====================

bool
JsvPromise_Check(JsVal obj);

JsVal
JsvPromise_Resolve(JsVal obj);

// Defined in suspenders.c
JsVal
JsvPromise_Syncify(JsVal promise);

// ==================== Buffers  ====================

errcode
JsvBuffer_assignToPtr(JsVal buf, void* ptr);

errcode
JsvBuffer_assignFromPtr(JsVal buf, void* ptr);

errcode
JsvBuffer_readFromFile(JsVal buf, int fd);

errcode
JsvBuffer_writeToFile(JsVal buf, int fd);

errcode
JsvBuffer_intoFile(JsVal buf, int fd);

// ==================== Miscellaneous  ====================

bool
JsvGenerator_Check(JsVal obj);

bool
JsvAsyncGenerator_Check(JsVal obj);

void __attribute__((__noreturn__))
JsvError_Throw(JsVal e);

/**
 * Returns non-zero if a < b.
 */
bool
Jsv_less_than(JsVal a, JsVal b);

/**
 * Returns non-zero if a <= b.
 */
bool
Jsv_less_than_equal(JsVal a, JsVal b);

/**
 * Returns non-zero if a == b.
 */
bool
Jsv_equal(JsVal a, JsVal b);

/**
 * Returns non-zero if a != b.
 */
bool
Jsv_not_equal(JsVal x, JsVal b);

/**
 * Returns non-zero if a > b.
 */
bool
Jsv_greater_than(JsVal a, JsVal b);

/**
 * Returns non-zero if a >= b.
 */
bool
Jsv_greater_than_equal(JsVal a, JsVal b);

JsVal
JsvMap_New(void);

JsVal
JsvLiteralMap_New(void);

errcode
JsvMap_Set(JsVal map, JsVal key, JsVal val);

/**
 * Create a new Set.
 */
JsVal
JsvSet_New(void);

/**
 * Does set.add(key).
 */
errcode WARN_UNUSED
JsvSet_Add(JsVal mapid, JsVal keyid);

#endif
