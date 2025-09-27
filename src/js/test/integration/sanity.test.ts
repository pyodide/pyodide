import { expect, test } from "./fixture";

test("should pass a basic truthy sanity test (node)", async () => {
  expect(await Promise.resolve("success")).toStrictEqual("success");
});

test("should pass a basic sanity test in browser (playwright)", async ({
  page,
}) => {
  await expect(page).toHaveTitle("pyodide");
});
