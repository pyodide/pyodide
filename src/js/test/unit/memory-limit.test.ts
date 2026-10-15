import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { createLimitedMemory } from "../../memory-limit";

const MiB = 1024 * 1024;
const PAGE = 65536;

describe("createLimitedMemory", () => {
  it("cannot grow past the limit", () => {
    const memory = createLimitedMemory(2 * PAGE, 4 * PAGE);
    assert.equal(memory.buffer.byteLength, 2 * PAGE);
    memory.grow(2);
    assert.equal(memory.buffer.byteLength, 4 * PAGE);
    assert.throws(() => memory.grow(1), RangeError);
  });

  it("rounds the limit down to a whole page", () => {
    const memory = createLimitedMemory(PAGE, 3 * PAGE + 100);
    memory.grow(2);
    assert.throws(() => memory.grow(1), RangeError);
  });

  it("caps the limit at the largest heap Emscripten allows", () => {
    const memory = createLimitedMemory(PAGE, 2 ** 40);
    assert.equal(memory.buffer.byteLength, PAGE);
  });

  it("rejects a limit below the initial size", () => {
    for (const bad of [0, -1, NaN, 16 * MiB]) {
      assert.throws(() => createLimitedMemory(32 * MiB, bad), RangeError);
    }
  });

  it("also stops growth by the wasm memory.grow instruction", () => {
    // (module
    //   (import "env" "memory" (memory 0))
    //   (func (export "grow") (param i32) (result i32)
    //     (memory.grow (local.get 0))))
    // memory.grow in wasm never goes through Memory.prototype.grow in JS.
    const bytes = new Uint8Array([
      0x00, 0x61, 0x73, 0x6d, 0x01, 0x00, 0x00, 0x00, 0x01, 0x06, 0x01, 0x60,
      0x01, 0x7f, 0x01, 0x7f, 0x02, 0x0f, 0x01, 0x03, 0x65, 0x6e, 0x76, 0x06,
      0x6d, 0x65, 0x6d, 0x6f, 0x72, 0x79, 0x02, 0x00, 0x00, 0x03, 0x02, 0x01,
      0x00, 0x07, 0x08, 0x01, 0x04, 0x67, 0x72, 0x6f, 0x77, 0x00, 0x00, 0x0a,
      0x08, 0x01, 0x06, 0x00, 0x20, 0x00, 0x40, 0x00, 0x0b,
    ]);
    const memory = createLimitedMemory(PAGE, 3 * PAGE);
    const { grow } = new WebAssembly.Instance(new WebAssembly.Module(bytes), {
      env: { memory },
    }).exports as { grow: (pages: number) => number };
    assert.equal(grow(1), 1); // returns the previous size in pages
    assert.equal(grow(1), 2);
    assert.equal(grow(1), -1); // refused, the limit is 3 pages
    assert.equal(memory.buffer.byteLength, 3 * PAGE);
  });
});
