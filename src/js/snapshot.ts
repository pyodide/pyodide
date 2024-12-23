import { jsFinderHook } from "./api";
import { scheduleCallback } from "./scheduler";

declare var Module: any;

/** @private */
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

type SerializedHiwireValue = { path: string[] } | { serialized: any } | null;

/**
 * @hidden
 */
export type SnapshotConfig = {
  hiwireKeys: SerializedHiwireValue[];
  immortalKeys: string[];
};

const SNAPSHOT_MAGIC = 0x706e7300; // "\x00snp"
const HEADER_SIZE_IN_BYTES =
  4 /* magic */ +
  4 /* offset to binary */ +
  4 /* json length */ +
  4 /* padding */ +
  32; /* build id */

function encodeBuildId(buildId: string, buffer: Uint32Array): void {
  if (buffer.length !== 8) {
    throw new Error("Expected 256 bit buffer");
  }
  for (let i = 0; i < 32; i++) {
    buffer[i] = parseInt(buildId.slice(i * 8, (i + 1) * 8), 16);
  }
}

function decodeBuildId(buffer: Uint32Array): string {
  if (buffer.length !== 8) {
    throw new Error("Expected 256 bit buffer");
  }
  return Array.from(buffer, (n) => n.toString(16).padStart(8, "0")).join("");
}

// The expected index of the deduplication map in the immortal externref table.
// We double check that this is still right in makeSnapshot (when creating the
// snapshot) and in syncUpSnapshotLoad1 (when using it).
const MAP_INDEX = 5;

API.makeSnapshot = function (serializer?: (obj: any) => any): Uint8Array {
  if (!API.config._makeSnapshot) {
    throw new Error(
      "makeSnapshot only works if you passed the makeSnapshot option to loadPyodide",
    );
  }
  const hiwireKeys: SerializedHiwireValue[] = [];
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
    const path = value[getAccessorList];
    if (path) {
      hiwireKeys.push({ path });
      continue;
    }
    if (serializer) {
      const serialized = serializer(value);
      try {
        JSON.stringify(serialized);
      } catch (e) {
        console.warn(
          `Serializer returned result that cannot be JSON.stringify'd at index ${i}.`,
        );
        console.warn("  Input: ", value);
        console.warn("  Output:", serialized);
        throw new Error(
          `Serializer returned result that cannot be JSON.stringify'd at index ${i}.`,
        );
      }
      hiwireKeys.push({ serialized });
      continue;
    }
    throw new Error(`Can't serialize object at index ${i}`);
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
  let snapshotOffset = HEADER_SIZE_IN_BYTES + 2 * snapshotConfigString.length;
  // align to 16 bytes
  snapshotOffset = Math.ceil(snapshotOffset / 16) * 16;
  const snapshot = new Uint8Array(snapshotOffset + Module.HEAP8.length);
  const encoder = new TextEncoder();
  const { written: jsonLength } = encoder.encodeInto(
    snapshotConfigString,
    snapshot.subarray(HEADER_SIZE_IN_BYTES),
  );
  const uint32View = new Uint32Array(snapshot.buffer);
  uint32View[0] = SNAPSHOT_MAGIC;
  uint32View[1] = snapshotOffset;
  uint32View[2] = jsonLength!;
  uint32View[3] = 0; // padding
  encodeBuildId(API.config.BUILD_ID, uint32View.subarray(4, 4 + 8));
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
  const snapshotOffset = uint32View[1];
  const jsonLength = uint32View[2];
  const buildId = decodeBuildId(uint32View.subarray(4, 4 + 8));
  if (buildId !== API.config.BUILD_ID) {
    throw new Error(
      "Snapshot build id mismatch\n" +
        `expected: ${API.config.BUILD_ID}\n` +
        `got     : ${buildId}\n`,
    );
  }
  const jsonBuf = snapshot.subarray(
    HEADER_SIZE_IN_BYTES,
    HEADER_SIZE_IN_BYTES + jsonLength,
  );
  snapshot = snapshot.subarray(snapshotOffset);
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
 * @private
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
 * @private
 */
export function syncUpSnapshotLoad2(
  jsglobals: any,
  snapshotConfig: SnapshotConfig,
  deserializer?: (serialized: any) => any,
) {
  const expectedKeys = getExpectedKeys();
  expectedKeys.forEach((v, idx) => tableSet(idx, v));
  snapshotConfig.hiwireKeys.forEach((e, idx) => {
    let x;
    if (!e) {
      x = e;
    } else if ("path" in e) {
      x = e.path.reduce((x, y) => x[y], jsglobals) || null;
    } else {
      if (!deserializer) {
        throw new Error(
          "You must pass an appropriate deserializer as _snapshotDeserializer",
        );
      }
      x = deserializer(e.serialized);
    }
    // @ts-ignore
    tableSet(expectedKeys.length + idx, x);
  });
  snapshotConfig.immortalKeys.forEach((v) => Module.__hiwire_immortal_add(v));
}
