const API = Module.API;
const Hiwire = {};
const Tests = {};
API.tests = Tests;
API.version = "0.24.0.dev0";
Module.hiwire = Hiwire;

function sleep(ms) {
  return new Promise((res) => setTimeout(res, ms));
}

function decodeHexString(s) {
  const result = new Uint8Array(s.length / 2);
  for (let i = 0; i < s.length / 2; i++) {
    result[i] = Number.parseInt(s.slice(2 * i, 2 * i + 2), 16);
  }
  return result;
}

function getTypeTag(x) {
  try {
    return Object.prototype.toString.call(x);
  } catch (e) {
    return "";
  }
}
API.getTypeTag = getTypeTag;

/**
 * Safe property check
 *
 * Observe whether a property exists or not without invoking getters.
 * Should never throw as long as arguments have the correct types.
 *
 * obj: an object
 * prop: a string or symbol
 */
function hasProperty(obj, prop) {
  try {
    while (obj) {
      if (Object.getOwnPropertyDescriptor(obj, prop)) {
        return true;
      }
      obj = Object.getPrototypeOf(obj);
    }
  } catch (e) {}
  return false;
}

/**
 * Observe whether a method exists or not
 *
 * Invokes getters but catches any error produced by a getter and throws it away.
 * Never throws an error
 *
 * obj: an object
 * prop: a string or symbol
 */
function hasMethod(obj, prop) {
  try {
    return typeof obj[prop] === "function";
  } catch (e) {
    return false;
  }
}
