import { expectType, expectAssignable } from "tsd";
import {
  loadPyodide,
  PyProxy,
  PyProxyWithLength,
  PyProxyWithGet,
  PyProxyWithSet,
  PyProxyWithHas,
  PyProxyIterable,
  PyProxyIterator,
  PyProxyAwaitable,
  PyProxyBuffer,
  PyProxyCallable,
  PyBuffer,
  TypedArray,
} from "./pyodide";

async function main() {
  let pyodide = await loadPyodide();
  expectType<Promise<typeof pyodide>>(loadPyodide({ indexURL: "blah" }));
  expectType<Promise<typeof pyodide>>(loadPyodide({ fullStdLib: true }));

  expectType<Promise<typeof pyodide>>(
    loadPyodide({
      indexURL: "blah",
      fullStdLib: true,
      stdin: () => "a string",
      stdout: (x: string) => {},
      stderr: (err: string) => {},
    })
  );

  expectType<PyProxy>(pyodide.globals);

  let x: any;
  expectType<boolean>(pyodide.isPyProxy(x));
  if (pyodide.isPyProxy(x)) {
    expectType<PyProxy>(x);
  } else {
    expectType<any>(x);
  }

  let px: PyProxy = <PyProxy>{};

  expectType<any>(pyodide.runPython("1+1"));
  expectType<any>(pyodide.runPython("1+1", { globals: px }));
  expectType<Promise<any>>(pyodide.runPythonAsync("1+1"));
  expectType<Promise<any>>(pyodide.runPythonAsync("1+1", { globals: px }));

  expectType<Promise<void>>(pyodide.loadPackagesFromImports("import some_pkg"));
  expectType<Promise<void>>(
    pyodide.loadPackagesFromImports("import some_pkg", (x: any) =>
      console.log(x)
    )
  );
  expectType<Promise<void>>(
    pyodide.loadPackagesFromImports(
      "import some_pkg",
      (x: any) => console.log(x),
      (x: any) => console.warn(x)
    )
  );

  expectType<Promise<void>>(pyodide.loadPackage("blah"));
  expectType<Promise<void>>(pyodide.loadPackage(["blah", "blah2"]));
  expectType<Promise<void>>(
    pyodide.loadPackage("blah", (x: any) => console.log(x))
  );
  expectType<Promise<void>>(
    pyodide.loadPackage(
      ["blah", "blah2"],
      (x: any) => console.log(x),
      (x: any) => console.warn(x)
    )
  );
  expectType<Promise<void>>(pyodide.loadPackage(px));

  expectType<PyProxy>(pyodide.pyodide_py);
  expectType<void>(pyodide.registerJsModule("blah", { a: 7 }));
  expectType<void>(pyodide.unregisterJsModule("blah"));

  pyodide.setInterruptBuffer(new Int32Array(1));
  expectType<any>(pyodide.toPy({}));
  expectType<string>(pyodide.version);

  expectType<any>(px.x);
  expectType<PyProxy>(px.copy());
  expectType<void>(px.destroy("blah"));
  expectType<void>(px.destroy());
  expectType<any>(px.toJs());
  expectType<any>(px.toJs({}));
  expectType<any>(px.toJs({ depth: 10 }));
  expectType<any>(px.toJs({ create_pyproxies: false }));
  expectType<any>(px.toJs({ create_pyproxies: true }));
  expectType<any>(px.toJs({ pyproxies: [] }));
  expectType<string>(px.toString());
  expectType<string>(px.type);

  if (px.supportsGet()) {
    expectType<PyProxyWithGet>(px);
    expectType<(x: any) => any>(px.get);
  }

  if (px.supportsHas()) {
    expectType<PyProxyWithHas>(px);
    expectType<(x: any) => boolean>(px.has);
  }

  if (px.supportsLength()) {
    expectType<PyProxyWithLength>(px);
    expectType<number>(px.length);
  }

  if (px.supportsSet()) {
    expectType<PyProxyWithSet>(px);
    expectType<(x: any, y: any) => void>(px.set);
  }

  if (px.isAwaitable()) {
    expectType<PyProxyAwaitable>(px);
    expectType<any>(await px);
  }

  if (px.isBuffer()) {
    expectType<PyProxyBuffer>(px);
    let buf = px.getBuffer();
    expectType<PyBuffer>(buf);
    expectType<boolean>(buf.c_contiguous);
    expectType<TypedArray>(buf.data);
    expectType<boolean>(buf.f_contiguous);
    expectType<string>(buf.format);
    expectType<number>(buf.itemsize);
    expectType<number>(buf.nbytes);
    expectType<number>(buf.ndim);
    expectType<number>(buf.offset);
    expectType<boolean>(buf.readonly);
    expectType<() => void>(buf.release);
    expectType<number[]>(buf.shape);
    expectType<number[]>(buf.strides);
  }

  if (px.isCallable()) {
    expectType<PyProxyCallable>(px);
    expectType<any>(px(1, 2, 3));
    expectAssignable<(...args: any[]) => any>(px);
  }

  if (px.isIterable()) {
    expectType<PyProxyIterable>(px);
    for (let x of px) {
      expectType<any>(x);
    }
    let it = px[Symbol.iterator]();
    expectAssignable<{ done?: any; value: any }>(it.next());
  }

  if (px.isIterator()) {
    expectType<PyProxyIterator>(px);
    expectAssignable<{ done?: any; value: any }>(px.next());
    expectAssignable<{ done?: any; value: any }>(px.next(22));
  }
}
