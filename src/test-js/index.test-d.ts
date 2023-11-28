import { expectType, expectAssignable } from "tsd";
import { version, loadPyodide, PackageData } from "pyodide";

import {
  PyProxy,
  PyProxyWithLength,
  PyProxyWithGet,
  PyProxyWithSet,
  PyProxyWithHas,
  PyIterable,
  PyIterator,
  PyAwaitable,
  PyBuffer,
  PyCallable,
  PyBufferView,
  PyDict,
  TypedArray,
} from "pyodide/ffi";

import "./test-deprecated";

// TODO: check that these are exported only as types not as values
// Currently tsd doesn't do this:
// ✖   Module "pyodide/ffi" declares TypedArray locally, but it is not exported.
// ✖   Expected an error, but found none.
// expectError(new PyProxy());

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
    }),
  );

  expectType<PyProxy>(pyodide.globals);

  let x: any;
  expectType<boolean>(pyodide.isPyProxy(x));
  if (x instanceof pyodide.ffi.PyProxy) {
    expectType<PyProxy>(x);
  } else {
    expectType<any>(x);
  }

  let px: PyProxy = <PyProxy>{};

  expectType<any>(pyodide.runPython("1+1"));
  expectType<any>(pyodide.runPython("1+1", { globals: px }));
  expectType<Promise<any>>(pyodide.runPythonAsync("1+1"));
  expectType<Promise<any>>(pyodide.runPythonAsync("1+1", { globals: px }));

  expectType<Promise<Array<PackageData>>>(
    pyodide.loadPackagesFromImports("import some_pkg"),
  );
  expectType<Promise<Array<PackageData>>>(
    pyodide.loadPackagesFromImports("import some_pkg", {
      messageCallback: (x: any) => console.log(x),
    }),
  );
  expectType<Promise<Array<PackageData>>>(
    pyodide.loadPackagesFromImports("import some_pkg", {
      messageCallback: (x: any) => console.log(x),
      errorCallback: (x: any) => console.warn(x),
    }),
  );

  expectType<Promise<Array<PackageData>>>(pyodide.loadPackage("blah"));
  expectType<Promise<Array<PackageData>>>(
    pyodide.loadPackage(["blah", "blah2"]),
  );
  expectType<Promise<Array<PackageData>>>(
    pyodide.loadPackage("blah", {
      messageCallback: (x: any) => console.log(x),
    }),
  );
  expectType<Promise<Array<PackageData>>>(
    pyodide.loadPackage(["blah", "blah2"], {
      messageCallback: (x: any) => console.log(x),
      errorCallback: (x: any) => console.warn(x),
    }),
  );
  expectType<Promise<Array<PackageData>>>(pyodide.loadPackage(px));

  expectType<PyProxy>(pyodide.pyodide_py);
  expectType<void>(pyodide.registerJsModule("blah", { a: 7 }));
  expectType<void>(pyodide.unregisterJsModule("blah"));

  pyodide.setInterruptBuffer(new Int32Array(1));
  expectType<any>(pyodide.toPy({}));
  expectType<string>(pyodide.version);

  expectType<any>(px.x);
  expectType<PyProxy>(px.copy());
  expectType<void>(px.destroy({ message: "blah" }));
  expectType<void>(px.destroy({ destroyRoundtrip: false }));
  expectType<void>(px.destroy());
  expectType<any>(px.toJs());
  expectType<any>(px.toJs({}));
  expectType<any>(px.toJs({ depth: 10 }));
  expectType<any>(px.toJs({ create_pyproxies: false }));
  expectType<any>(px.toJs({ create_pyproxies: true }));
  expectType<any>(px.toJs({ pyproxies: [] }));
  expectType<string>(px.toString());
  expectType<string>(px.type);

  if (px instanceof pyodide.ffi.PyProxyWithGet) {
    expectType<PyProxyWithGet>(px);
    expectType<(x: any) => any>(px.get);
  }

  if (px instanceof pyodide.ffi.PyProxyWithHas) {
    expectType<PyProxyWithHas>(px);
    expectType<(x: any) => boolean>(px.has);
  }

  if (px instanceof pyodide.ffi.PyProxyWithLength) {
    expectType<PyProxyWithLength>(px);
    expectType<number>(px.length);
  }

  if (px instanceof pyodide.ffi.PyProxyWithSet) {
    expectType<PyProxyWithSet>(px);
    expectType<(x: any, y: any) => void>(px.set);
  }

  if (px instanceof pyodide.ffi.PyDict) {
    expectAssignable<PyProxyWithHas>(px);
    expectAssignable<PyProxyWithGet>(px);
    expectAssignable<PyProxyWithSet>(px);
    expectAssignable<PyProxyWithLength>(px);
    expectAssignable<PyIterable>(px);
  }

  if (px instanceof pyodide.ffi.PyAwaitable) {
    expectType<PyAwaitable>(px);
    expectType<any>(await px);
  }

  if (px instanceof pyodide.ffi.PyBuffer) {
    expectType<PyBuffer>(px);
    let buf = px.getBuffer();
    expectType<PyBufferView>(buf);
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

  if (px instanceof pyodide.ffi.PyCallable) {
    expectType<PyCallable>(px);
    expectType<any>(px(1, 2, 3));
    expectAssignable<(...args: any[]) => any>(px);
  }

  if (px instanceof pyodide.ffi.PyIterable) {
    expectType<PyIterable>(px);
    for (let x of px) {
      expectType<any>(x);
    }
    let it = px[Symbol.iterator]();
    expectAssignable<{ done?: any; value: any }>(it.next());
  }

  if (px instanceof pyodide.ffi.PyIterator) {
    expectType<PyIterator>(px);
    expectAssignable<{ done?: any; value: any }>(px.next());
    expectAssignable<{ done?: any; value: any }>(px.next(22));
  }

  pyodide.unpackArchive(new Uint8Array(40), "tar");
  pyodide.unpackArchive(new Uint8Array(40), "tar", {
    extractDir: "/some/path",
  });
}
