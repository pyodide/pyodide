const API = Module.API;
const Hiwire = {};
const Tests = {};
API.tests = Tests;
API.version = "0.22.0.dev0";
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
