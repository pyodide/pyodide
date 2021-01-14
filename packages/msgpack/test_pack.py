from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(standalone=True, packages=["msgpack"])
def test_pack():
    from msgpack import packb, unpackb, Unpacker, Packer, pack

    def check(data, use_list=False):
        re = unpackb(packb(data), use_list=use_list, strict_map_key=False)
        assert re == data

    test_data = [
        0,
        1,
        127,
        128,
        255,
        256,
        65535,
        65536,
        4294967295,
        4294967296,
        -1,
        -32,
        -33,
        -128,
        -129,
        -32768,
        -32769,
        -4294967296,
        -4294967297,
        1.0,
        b"",
        b"a",
        b"a" * 31,
        b"a" * 32,
        None,
        True,
        False,
        (),
        ((),),
        ((), None),
        {None: 0},
        (1 << 23),
    ]
    for td in test_data:
        check(td)
