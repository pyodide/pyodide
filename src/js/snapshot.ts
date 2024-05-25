import { jsFinderHook } from "./api";
import { scheduleCallback } from "./scheduler";

declare var Module: any;

export function getExpectedKeys() {
  return [
    null,
    jsFinderHook,
    API.config.jsglobals,
    API.public_api,
    API,
    scheduleCallback,
    API,
    {},
  ];
}

const getAccessorList = Symbol("getAccessorList");
/**
 * @private
 */
export function makeGlobalsProxy(
  obj: any,
  accessorList: (string | symbol)[] = [],
): any {
  return new Proxy(obj, {
    get(target, prop, receiver) {
      if (prop === getAccessorList) {
        return accessorList;
      }
      // @ts-ignore
      const orig = Reflect.get(...arguments);
      const descr = Reflect.getOwnPropertyDescriptor(target, prop);
      // We're required to return the original value unmodified if it's an own
      // property with a non-writable, non-configurable data descriptor
      if (descr && descr.writable === false && !descr.configurable) {
        return orig;
      }
      // Or an accessor descriptor with a setter but no getter
      if (descr && descr.set && !descr.get) {
        return orig;
      }
      if (!["object", "function"].includes(typeof orig)) {
        return orig;
      }
      return makeGlobalsProxy(orig, [...accessorList, prop]);
    },
    getPrototypeOf() {
      // @ts-ignore
      return makeGlobalsProxy(Reflect.getPrototypeOf(...arguments), [
        ...accessorList,
        "[getProtoTypeOf]",
      ]);
    },
  });
}

export type SnapshotConfig = {
  hiwireKeys: (string[] | null)[];
  immortalKeys: string[];
};

const SNAPSHOT_MAGIC = 0x706e7300; // "\x00snp"
// TODO: Make SNAPSHOT_BUILD_ID distinct for each build of pyodide.asm.js / pyodide.asm.wasm
const SNAPSHOT_BUILD_ID = 0;
const HEADER_SIZE = 4 * 4;

// The expected index of the deduplication map in the immortal externref table.
// We double check that this is still right in makeSnapshot (when creating the
// snapshot) and in syncUpSnapshotLoad1 (when using it).
const MAP_INDEX = 5;

API.makeSnapshot = function (): Uint8Array {
  if (!API.config._makeSnapshot) {
    throw new Error(
      "makeSnapshot only works if you passed the makeSnapshot option to loadPyodide",
    );
  }
  const hiwireKeys: (string[] | null)[] = [];
  const expectedKeys = getExpectedKeys();
  for (let i = 0; i < expectedKeys.length; i++) {
    let value;
    try {
      value = Module.__hiwire_get(i);
    } catch (e) {
      throw new Error(`Failed to get value at index ${i}`);
    }
    let isOkay = false;
    try {
      isOkay =
        value === expectedKeys[i] ||
        JSON.stringify(value) === JSON.stringify(expectedKeys[i]);
    } catch (e) {
      // first comparison returned false and stringify raised
      console.warn(e);
    }
    if (!isOkay) {
      console.warn(expectedKeys[i], value);
      throw new Error(`Unexpected hiwire entry at index ${i}`);
    }
  }

  for (let i = expectedKeys.length; ; i++) {
    let value;
    try {
      value = Module.__hiwire_get(i);
    } catch (e) {
      break;
    }
    if (!["object", "function"].includes(typeof value)) {
      throw new Error(
        `Unexpected object of type ${typeof value} at index ${i}`,
      );
    }
    if (value === null) {
      hiwireKeys.push(value);
      continue;
    }
    const accessorList = value[getAccessorList];
    if (!accessorList) {
      throw new Error(`Can't serialize object at index ${i}`);
    }
    hiwireKeys.push(accessorList);
  }
  const immortalKeys = [];
  const shouldBeAMap = Module.__hiwire_immortal_get(MAP_INDEX);
  if (Object.prototype.toString.call(shouldBeAMap) !== "[object Map]") {
    throw new Error(`Internal error: expected a map at index ${MAP_INDEX}`);
  }
  for (let i = MAP_INDEX + 1; ; i++) {
    let v;
    try {
      v = Module.__hiwire_immortal_get(i);
    } catch (e) {
      break;
    }
    if (typeof v !== "string") {
      throw new Error("Expected a string");
    }
    immortalKeys.push(v);
  }
  const snapshotConfig: SnapshotConfig = {
    hiwireKeys,
    immortalKeys,
  };
  const snapshotConfigString = JSON.stringify(snapshotConfig);
  let snapshotOffset = HEADER_SIZE + 2 * snapshotConfigString.length;
  // align to 8 bytes
  snapshotOffset = Math.ceil(snapshotOffset / 8) * 8;
  const snapshot = new Uint8Array(snapshotOffset + Module.HEAP8.length);
  const encoder = new TextEncoder();
  const { written: jsonLength } = encoder.encodeInto(
    snapshotConfigString,
    snapshot.subarray(HEADER_SIZE),
  );
  const uint32View = new Uint32Array(snapshot.buffer);
  uint32View[0] = SNAPSHOT_MAGIC;
  uint32View[1] = SNAPSHOT_BUILD_ID;
  uint32View[2] = snapshotOffset;
  uint32View[3] = jsonLength!;
  snapshot.subarray(snapshotOffset).set(Module.HEAP8);
  return snapshot;
};

API.restoreSnapshot = function (snapshot: Uint8Array): SnapshotConfig {
  const uint32View = new Uint32Array(
    snapshot.buffer,
    snapshot.byteOffset,
    snapshot.byteLength / 4,
  );
  if (uint32View[0] !== SNAPSHOT_MAGIC) {
    throw new Error("Snapshot has invalid magic number");
  }
  if (uint32View[1] !== SNAPSHOT_BUILD_ID) {
    throw new Error("Snapshot has invalid BUILD_ID");
  }
  const snpOffset = uint32View[2];
  const jsonSize = uint32View[3];
  const jsonBuf = snapshot.subarray(HEADER_SIZE, HEADER_SIZE + jsonSize);
  snapshot = snapshot.subarray(snpOffset);
  const jsonStr = new TextDecoder().decode(jsonBuf);
  const snapshotConfig: SnapshotConfig = JSON.parse(jsonStr);
  // @ts-ignore
  Module.HEAP8.set(snapshot);
  return snapshotConfig;
};

/**
 * Set up some of the JavaScript state that is normally set up by C
 * initialization code. TODO: adjust C code to simplify.
 *
 * This is divided up into two parts: syncUpSnapshotLoad1 has to happen at the
 * beginning of finalizeBootstrap before the public API is setup,
 * syncUpSnapshotLoad2 happens near the end so that API.public_api exists.
 *
 * This code is quite sensitive to the details of our setup, so it might break
 * if we move stuff around far away in the code base. Ideally over time we can
 * structure the code to make it less brittle.
 */
export function syncUpSnapshotLoad1() {
  // hiwire init puts a null at the beginning of both the mortal and immortal tables.
  Module.__hiwire_set(0, null);
  Module.__hiwire_immortal_add(null);
  // Usually importing _pyodide_core would trigger jslib_init but we need to manually call it.
  Module._jslib_init();
  // Puts deduplication map into the immortal table.
  // TODO: Add support for snapshots to hiwire and move this to a hiwire_snapshot_init function?
  let mapIndex = Module.__hiwire_immortal_add(new Map());
  // We expect everything after this in the immortal table to be interned strings.
  // We need to know where to start looking for the strings so that we serialized correctly.
  if (mapIndex !== MAP_INDEX) {
    throw new Error(
      `Internal error: Expected mapIndex to be ${MAP_INDEX}, got ${mapIndex}`,
    );
  }
  // Set API._pyodide to a proxy of the _pyodide module.
  // Normally called by import _pyodide.
  Module._init_pyodide_proxy();
}

function tableSet(idx: number, val: any): void {
  if (Module.__hiwire_set(idx, val) < 0) {
    throw new Error("table set failed");
  }
}

/**
 * Fill in the JsRef table.
 */
export function syncUpSnapshotLoad2(
  jsglobals: any,
  snapshotConfig: SnapshotConfig,
) {
  const expectedKeys = getExpectedKeys();
  expectedKeys.forEach((v, idx) => tableSet(idx, v));
  snapshotConfig.hiwireKeys.forEach((e, idx) => {
    const x = e?.reduce((x, y) => x[y], jsglobals) || null;
    // @ts-ignore
    tableSet(expectedKeys.length + idx, x);
  });
  snapshotConfig.immortalKeys.forEach((v) => Module.__hiwire_immortal_add(v));
}
