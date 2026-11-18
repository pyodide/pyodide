import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.requires_dynamic_linking
@run_in_pyodide(packages=["test-buffer"])
def test_zerod_buffers(selenium):
    from buffer_test import ZeroDBuffer

    from pyodide.ffi import to_js

    int8Buf = ZeroDBuffer("b", bytes([((~18) & 255) + 1]))
    jsInt8Buf = to_js(int8Buf)
    assert jsInt8Buf.constructor.name == "Int8Array"
    assert jsInt8Buf.length == 1
    assert jsInt8Buf.byteLength == 1
    assert jsInt8Buf[0] == -18

    uint8Buf = ZeroDBuffer("B", bytes([130]))
    jsUint8Buf = to_js(uint8Buf)
    assert jsUint8Buf.constructor.name == "Uint8Array"
    assert jsUint8Buf.length == 1
    assert jsUint8Buf.byteLength == 1
    assert jsUint8Buf[0] == 130

    int16Buf = ZeroDBuffer("h", bytes([18, 2]))
    jsInt16Buf = to_js(int16Buf)
    assert jsInt16Buf.constructor.name == "Int16Array"
    assert jsInt16Buf.length == 1
    assert jsInt16Buf.byteLength == 2
    assert jsInt16Buf[0] == 18 + 2 * 256

    uint16Buf = ZeroDBuffer("H", bytes([18, 2]))
    jsUint16Buf = to_js(uint16Buf)
    assert jsUint16Buf.constructor.name == "Uint16Array"
    assert jsUint16Buf.length == 1
    assert jsUint16Buf.byteLength == 2
    assert jsUint16Buf[0] == 18 + 2 * 256

    int32Buf = ZeroDBuffer("i", bytes([18, 2, 0, 1]))
    jsInt32Buf = to_js(int32Buf)
    assert jsInt32Buf.constructor.name == "Int32Array"
    assert jsInt32Buf.length == 1
    assert jsInt32Buf.byteLength == 4
    assert jsInt32Buf[0] == 18 + 2 * 256 + 1 * 256 * 256 * 256

    uint32Buf = ZeroDBuffer("I", bytes([18, 2, 0, 1]))
    jsUint32Buf = to_js(uint32Buf)
    assert jsUint32Buf.constructor.name == "Uint32Array"
    assert jsUint32Buf.length == 1
    assert jsUint32Buf.byteLength == 4
    assert jsUint32Buf[0] == 18 + 2 * 256 + 1 * 256 * 256 * 256

    int64Buf = ZeroDBuffer("q", bytes([18, 2, 0, 1, 0, 0, 0, 1]))
    jsInt64Buf = to_js(int64Buf)
    assert jsInt64Buf.constructor.name == "BigInt64Array"
    assert jsInt64Buf.length == 1
    assert jsInt64Buf.byteLength == 8
    assert jsInt64Buf[0] == 18 + 2 * 256 + 1 * 256 * 256 * 256 + pow(256, 7)

    uint64Buf = ZeroDBuffer("Q", bytes([18, 2, 0, 1, 0, 0, 0, 1]))
    jsUint64Buf = to_js(uint64Buf)
    assert jsUint64Buf.constructor.name == "BigUint64Array"
    assert jsUint64Buf.length == 1
    assert jsUint64Buf.byteLength == 8
    assert jsUint64Buf[0] == 18 + 2 * 256 + 1 * 256 * 256 * 256 + pow(256, 7)

    float16Buf = ZeroDBuffer("e", bytes([0, 71]))
    jsFloat16Buf = to_js(float16Buf)
    assert jsFloat16Buf.constructor.name == "Float16Array"
    assert jsFloat16Buf.length == 1
    assert jsFloat16Buf.byteLength == 2
    assert jsFloat16Buf[0] == 7

    float32Buf = ZeroDBuffer("f", bytes([0, 0, 224, 64]))
    jsFloat32Buf = to_js(float32Buf)
    assert jsFloat32Buf.constructor.name == "Float32Array"
    assert jsFloat32Buf.length == 1
    assert jsFloat32Buf.byteLength == 4
    assert jsFloat32Buf[0] == 7

    float64Buf = ZeroDBuffer("d", bytes([0, 0, 0, 0, 0, 0, 28, 64]))
    jsFloat64Buf = to_js(float64Buf)
    assert jsFloat64Buf.constructor.name == "Float64Array"
    assert jsFloat64Buf.length == 1
    assert jsFloat64Buf.byteLength == 8
    assert jsFloat64Buf[0] == 7
