import { expectType, expectAssignable, expectDeprecated } from "tsd";
import {
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
  PyProxyDict,
  TypedArray,
} from "pyodide";

// Have to @ts-ignore these or we get "only refers to a type, but is being used
// as a value here."
// They will still fail if not deprecated properly.
//
// A bunch of these don't work so they are commented out. This seems to be due
// to limitations in tsd. It works as expected on interfaces and types, but fails
// on classes...

// @ts-ignore
// expectDeprecated(PyProxy);
// // @ts-ignore
// expectDeprecated(PyProxyWithHas);
// // @ts-ignore
// expectDeprecated(PyProxyWithGet);
// // @ts-ignore
// expectDeprecated(PyProxyWithSet);
// // @ts-ignore
// expectDeprecated(PyProxyWithLength);
// @ts-ignore
expectDeprecated(PyProxyIterable);
// @ts-ignore
expectDeprecated(PyProxyIterator);
// @ts-ignore
expectDeprecated(PyProxyAwaitable);
// @ts-ignore
expectDeprecated(PyProxyCallable);
// @ts-ignore
expectDeprecated(PyProxyDict);
// // @ts-ignore
// expectDeprecated(PyProxyBuffer);
// // @ts-ignore
// expectDeprecated(PyBuffer);
// @ts-ignore
expectDeprecated(TypedArray);

let px: PyProxy = {} as PyProxy;
expectDeprecated(px.isAwaitable);
expectDeprecated(px.isBuffer);
expectDeprecated(px.isCallable);
expectDeprecated(px.isIterable);
expectDeprecated(px.isIterator);
expectDeprecated(px.supportsGet);
expectDeprecated(px.supportsSet);
expectDeprecated(px.supportsHas);
expectDeprecated(px.supportsLength);

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
