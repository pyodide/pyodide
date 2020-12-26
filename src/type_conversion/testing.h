#ifndef TEST_H
#define TEST_H
#ifdef TEST

#include "Python.h"
#include <stdio.h>

int
testing_init();

// For use in tests.
// If the assertion is false, malloc an explanation and return it.
#define ASSERT(assertion...)                                                   \
  do {                                                                         \
    printf("asserted: %s\n", #assertion);                                      \
    if (!(assertion)) {                                                        \
      printf("Assertion failed!");                                             \
      char* failure_msg;                                                       \
      asprintf(&failure_msg,                                                   \
               "Assertion failed on line %d:\nASSERT(%s);",                    \
               __LINE__,                                                       \
               #assertion);                                                    \
      printf("%s\n", failure_msg);                                             \
      return failure_msg;                                                      \
    }                                                                          \
    printf("Assertion passed!");                                               \
  } while (0)

/**
 * We define two macros to make tests:
 * DEFINE_TEST(name, body):
 *   Defines a test with given name and body. Test should use ASSERT macro
 * above. DEFINE_TEST_EXPECT_FAIL(name, match, body): This variant expects the
 * test to fail with a message that matches js regex "match".
 *
 * Implementation details:
 * We define a C function called inner_test_<name-of-test>. This inner function
 * returns NULL on success and a pointer to a heap-allocated string on fail.
 * The body of this inner_test function is exactly the body provided by to
 * DEFINE_TEST. (This is _DEFINE_TEST_INNER)
 *
 * We also define an EM_JS wrapper called test_<name-of-test>, this either calls
 * Module.Tests._expect_success or Module.Tests._expect_fail. We need an extra
 * layer of indirection first (_DEFINE_TEST_HELPER) so that macros __LINE__ and
 * __FILE__ will get expanded. The EM_JS macro stringifies its arguments so any
 * macros inside will not be expanded. See testing_init for the
 * definitions of _expect_success and _expect_fail
 *
 */
#define DEFINE_TEST(name, body...)                                             \
  _DEFINE_TEST_INNER(name, body)                                               \
  _DEFINE_TEST_HELPER(_expect_success, name, #body, __LINE__, __FILE__)

#define DEFINE_TEST_EXPECT_FAIL(name, match, body...)                          \
  _DEFINE_TEST_INNER(name, body)                                               \
  _DEFINE_TEST_HELPER(_expect_fail, name, match, #body, __LINE__, __FILE__)

#define _DEFINE_TEST_INNER(name, ...)                                          \
  char* inner_test_##name()                                                    \
  {                                                                            \
    __VA_ARGS__                                                                \
    return NULL;                                                               \
  }

// We need this helper function because EM_JS blocks expansion of macros
// inside its body, so we need to expand out the inner macros first
// Remember: C macros expand their arguments exactly once.
#define _DEFINE_TEST_HELPER(fn, name, args...)                                 \
  EM_JS(void, test_##name, (), {                                               \
    return Module.Tests.fn(_inner_test_##name(), #name, args);                 \
  })

// clang-format on

#endif // TEST
#endif // TEST_H
