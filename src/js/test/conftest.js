import express from "express";
import path from "node:path";
import { after, before } from "node:test";
import puppeteer from "puppeteer";

const __ROOT = path.resolve(__dirname, "../../../", "dist");

const { loadPyodide } = require(path.resolve(__ROOT, "pyodide"));

const app = express();
app.use(express.static(__ROOT));

const NODE = process.env.TEST_NODE;
const BROWSER = !NODE;

let browser = null;
let server = null;
let hostUrl = "";

before(async () => {
  globalThis.path = path;

  if (BROWSER) {
    browser = await puppeteer.launch(/*{ headless: false, devtools: true }*/);
    const page = await browser.newPage();
    await new Promise((resolve) => {
      server = app.listen(() => resolve(""));
      hostUrl = `http://localhost:${server.address().port}/`;
    });
    await page.goto(`${hostUrl}test.html`);
    globalThis.page = page;
  } else {
    globalThis.page = {
      title: () => Promise.resolve("pyodide"),
      goto: () => Promise.resolve(),
      evaluate: (fn, ...args) => fn(...args),
    };
  }
  await page.evaluate(
    async (indexURL) => {
      globalThis.pyodide = await loadPyodide({
        indexURL,
      });
      return globalThis.pyodide;
    },
    BROWSER ? undefined : __ROOT,
  );
});

after(async function () {
  if (BROWSER) {
    await browser.close();
    server.close();
  }
});
