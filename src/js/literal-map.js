const { get, getOwnPropertyDescriptor, ownKeys } = Reflect;

const getPropertyDescriptor = (value) => ({
  value,
  enumerable: true,
  writable: true,
  configurable: true,
});

const _ = Symbol();
const prototype = "prototype";

const handler = {
  deleteProperty: (map, k) => (map.has(k) ? map.delete(k) : delete map[k]),
  get(map, k, proxy) {
    if (k === _) return map;
    let v = map[k];
    if (typeof v === "function" && k !== "constructor") {
      v = v.bind(map);
    }
    v ||= map.get(k);
    return v;
  },
  getOwnPropertyDescriptor(map, k) {
    if (map.has(k)) return getPropertyDescriptor(map.get(k));
    if (k in map) return getOwnPropertyDescriptor(map, k);
  },
  has: (map, k) => map.has(k) || k in map,
  ownKeys: (map) =>
    [...map.keys(), ...ownKeys(map)].filter((x) =>
      ["string", "symbol"].includes(typeof x),
    ),
  set: (map, k, v) => (map.set(k, v), true),
};

API.LiteralMap = new Proxy(
  class LiteralMap extends Map {
    constructor(...args) {
      return new Proxy(super(...args), handler);
    }
  },
  {
    get(Class, k, ...rest) {
      return k !== prototype && k in Class[prototype]
        ? (proxy, ...args) => {
            const map = proxy[_];
            let value = map[k];
            if (typeof value === "function") value = value.apply(map, args);
            // prevent leaking the internal map elsewhere
            return value === map ? proxy : value;
          }
        : get(Class, k, ...rest);
    },
  },
);
