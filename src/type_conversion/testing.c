#ifdef TEST
#include "testing.h"
#include "emscripten.h"

EM_JS(int, testing_init, (), {
  Module.Tests = {};
  Module.Tests.test_entrypoints = function() { return "It works!"; };
  Module.Tests.UTF8ToString = UTF8ToString;

  Module.Tests._convert_message = function(msg_utf8)
  {
    // message is heap allocated or null
    let msg = false;
    if (msg_utf8) {
      msg = UTF8ToString(msg_utf8);
      _free(msg_utf8);
    }
    return msg;
  };

  Module.Tests._expect_success = function(msg_utf8, name, test_body, line, file)
  {
    let msg = Module.Tests._convert_message(msg_utf8);
    console.log(msg, name, test_body, line, file);
    if (msg) {
      console.log("  Failed");
      let result = [
        `Test "${name}" failed(defined on line ${ line } in ${ file }):`,
        `${ msg }`,
      ].join("\n");
      console.log(result);
      return result;
    }
    console.log("  Succeeded");
    // Test suceeded
    return undefined;
  };

  Module.Tests._expect_fail =
    function(msg_utf8, name, match, test_body, line, file)
  {
    let msg = Module.Tests._convert_message(msg_utf8);
    console.log("_expect_fail");
    console.log(msg, name, match, test_body, line, file);
    let re = new RegExp(match);
    if (!msg) {
      console.log("  Failed: no assert fail");
      let result = [
        `Test "${name}" failed (defined on line ${ line } in ${ file }):`,
        `Expected an assertion failure, but all assertions passed.`,
      ].join("\n");
      console.log(result);
      return result;
    } else if (!re.test(msg)) {
      console.log("  Failed: assert fail doesn't match");
      let result = [
        `Test "${name}" failed (defined on line ${ line } in ${ file }):`,
        `Expected an assertion failure matching pattern "${match}".`,
        `Assertion failed, but pattern not found in resulting message:`,
        `${msg}`,
      ].join("\n");
      console.log(result);
      return result;
    }
    console.log("  Succeeded");
    // Test suceeded
    return undefined;
  };

  Module.Tests.c_tests_expect_success_success =
    _test_c_tests_expect_success_success;
  Module.Tests.c_tests_expect_fail_fail = _test_c_tests_expect_fail_fail;
  Module.Tests.c_tests_expect_success_fails =
    _test_c_tests_expect_success_fails;
  Module.Tests.c_tests_expect_fail_succeeds =
    _test_c_tests_expect_fail_succeeds;
  Module.Tests.c_tests_expect_fail_wrong_message =
    _test_c_tests_expect_fail_wrong_message;
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
