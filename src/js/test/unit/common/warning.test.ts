import * as chai from "chai";
import sinon from "sinon";
import { makeWarnOnce } from "../../../common/warning";

describe("makeWarnOnce", () => {
  it("should return a function", () => {
    const warn = makeWarnOnce("warning");
    chai.assert.isFunction(warn);
  });

  it("should warn once", () => {
    const warn = makeWarnOnce("warning");
    const spy = sinon.spy(console, "warn");
    warn();
    warn();

    chai.assert.isTrue(spy.calledOnce);
  });
});
