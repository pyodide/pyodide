import * as chai from "chai";
import { createLock } from "../../../common/lock";

describe("createLock", () => {
	it("should create a lock", () => {
		const lock = createLock();
		chai.assert.isFunction(lock);
	});

	it("should acquire the lock", async () => {
		const lock = createLock();
		const release = await lock();
		chai.assert.isFunction(release);
	});

	it("should release the lock", async () => {
		const lock = createLock();
		const release = await lock();
		release();
	});

	it("should acquire the lock in order", async () => {
		const lock = createLock();
		let released = false;
		const release = await lock();

		setTimeout(() => {
			chai.assert.isFalse(released);
			release();
			released = true;
		}, 100);

		chai.assert.isFalse(released);
		const release2 = await lock();
		chai.assert.isTrue(released);

		release2();
	});
});
