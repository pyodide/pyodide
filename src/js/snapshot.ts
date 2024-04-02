declare var Module: any;

const getAccessorList = Symbol("getAccessorList");
const illegalOperation = "Illegal operation while taking memory snapshot: ";
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
    // has, ownKeys, isExtensible left alone
    apply() {
      throw new Error(illegalOperation + "apply " + accessorList.join("."));
    },
    construct() {
      throw new Error(illegalOperation + "construct " + accessorList.join("."));
    },
    defineProperty(target, prop, val) {
      if (prop === "__all__") {
        // @ts-ignore
        return Reflect.defineProperty(...arguments);
      }
      throw new Error(
        illegalOperation + "defineProperty " + accessorList.join("."),
      );
    },
    deleteProperty() {
      throw new Error(
        illegalOperation + "deleteProperty " + accessorList.join("."),
      );
    },
    getOwnPropertyDescriptor() {
      throw new Error(
        illegalOperation + "getOwnPropertyDescriptor " + accessorList.join("."),
      );
    },
    preventExtensions() {
      throw new Error(
        illegalOperation + "preventExtensions " + accessorList.join("."),
      );
    },
    set() {
      throw new Error(illegalOperation + "set " + accessorList.join("."));
    },
    setPrototypeOf() {
      throw new Error(
        illegalOperation + "setPrototypeOf " + accessorList.join("."),
      );
    },
  });
}

export type SnapshotConfig = {
  hiwireKeys: (string[] | null)[];
};

const SNAPSHOT_MAGIC = 0x706e7300; // "\x00snp"
// TODO: Make SNAPSHOT_BUILD_ID distinct for each build of pyodide.asm.js / pyodide.asm.wasm
const SNAPSHOT_BUILD_ID = 0;
const HEADER_SIZE = 4 * 4;

API.makeSnapshot = function (): Uint8Array {
  if (!API.config._makeSnapshot) {
    throw new Error(
      "makeSnapshot only works if you passed the makeSnapshot option to loadPyodide",
    );
  }
  const hiwireKeys: (string[] | null)[] = [];
  for (let i = 0; ; i++) {
    let value;
    try {
      value = Module.__hiwire_get(i);
    } catch (e) {
      break;
    }
    console.log("value", value, value?.[getAccessorList] || null);
    hiwireKeys.push(value?.[getAccessorList] || null);
  }
  const snapshotConfig: SnapshotConfig = {
    hiwireKeys,
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
