import chai from "chai";

it("should pass a basic truthy sanity test (node)", async () => {
  await chai.assert.isFulfilled(Promise.resolve());
});

it("should pass a basic sanity test in browser (puppeteer)", async () => {
  const title = await chai.assert.isFulfilled(page.title());
  chai.assert.isString(title);
  chai.assert.equal(title, "pyodide");
});
