#ifdef TEST
#include "testing.h"
#include "emscripten.h"

EM_JS(int, testing_init, (), {
  Module.Tests = {};
  Module.Tests.test_entrypoints = function() { return "It works!"; };

  // msg_utf8 is either a heap allocated string or null.
  // If it's a heap allocated string, convert to a js string, free it, and
  // return the js string. Otherwise return js false.
  function c_string_to_js_string(s_utf8)
  {
    let s = false;
    if (s_utf8) {
      s = UTF8ToString(s_utf8);
      _free(s_utf8);
    }
    return s;
  };

  function js_string_to_c_string(s)
  {
    if (!s) {
      return 0;
    }
    return allocate(intArrayFromString(s), "i8", ALLOC_NORMAL);
  }

  function _expect_success_helper(msg_utf8, name, test_body, line, file)
  {
    let msg = c_string_to_js_string(msg_utf8);
    if (msg) {
      let result = [
        `Test "${name}" failed(defined on line ${ line } in ${ file }):`,
        `${ msg }`,
      ].join("\n");
      return result;
    }
    // Test succeeded
    return undefined;
  }

  function _expect_fail_helper(msg_utf8, name, match, test_body, line, file)
  {
    let msg = c_string_to_js_string(msg_utf8);
    let re = new RegExp(match);
    if (!msg) {
      let result = [
        `Test "${name}" failed (defined on line ${ line } in ${ file }):`,
        `Expected an assertion failure, but all assertions passed.`,
      ].join("\n");
      return result;
    } else if (!re.test(msg)) {
      let result = [
        `Test "${name}" failed (defined on line ${ line } in ${ file }):`,
        `Expected an assertion failure matching pattern "${match}".`,
        `Assertion failed, but pattern not found in resulting message:`,
        `${msg}`,
      ].join("\n");
      return result;
    }
    // Test suceeded
    return undefined;
  }

  Module.Tests._expect_success = function(... args)
  {
    return js_string_to_c_string(_expect_success_helper(... args));
  };

  Module.Tests._expect_fail = function(... args)
  {
    return js_string_to_c_string(_expect_fail_helper(... args));
  };

  // The entries in pyodide._module are not enumerable.
  // So "Object.keys()" or directly using "for(let name in pyodide._module)"
  // do not work.
  for (let name of Object.getOwnPropertyNames(Module)) {
    if (name.startsWith("_test_")) {
      Module.Tests[name.slice("_test_".length)] = function()
      {
        return c_string_to_js_string(Module[name]());
      };
    }
  }
  return 0;
});

// Passing tests
DEFINE_TEST(c_tests_expect_success_success, {
  ASSERT(1);
  ASSERT(1 > -7);
})

DEFINE_TEST_EXPECT_FAIL(c_tests_expect_fail_fail, "88", {
  ASSERT(0 * (1 + 1 - 88));
})

// Different ways for tests to fail
DEFINE_TEST(c_tests_expect_success_fails, { ASSERT(0 * (1 + 1 - 88)); })

DEFINE_TEST_EXPECT_FAIL(c_tests_expect_fail_succeeds, "88", {
  ASSERT(1);
  ASSERT(1 > -7);
})

DEFINE_TEST_EXPECT_FAIL(c_tests_expect_fail_wrong_message, "77", {
  ASSERT(0 * (1 + 1 - 88));
})

#endif // TEST
