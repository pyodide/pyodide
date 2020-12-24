def test_blosc(selenium_standalone):
    selenium = selenium_standalone
    selenium.load_package(["numcodes", "numpy"])
    cmd = """
        import numpy as np
        from numcodecs import blosc
        from numcodecs.blosc import Blosc
        from numcodecs.tests.common import check_encode_decode

        # mix of dtypes: integer, float, bool, string
        # mix of shapes: 1D, 2D, 3D
        # mix of orders: C, F
        arrays = [
            np.arange(1000, dtype='i4'),
            # np.linspace(1000, 1001, 1000, dtype='f8'),
            # np.random.normal(loc=1000, scale=1, size=(100, 10)),
            # np.random.randint(0, 2, size=1000, dtype=bool).reshape(100, 10, order='F'),
            # np.random.choice([b'a', b'bb', b'ccc'], size=1000).reshape(10, 10, 10),
            # np.random.randint(0, 2**60, size=1000, dtype='u8').view('M8[ns]'),
            # np.random.randint(0, 2**60, size=1000, dtype='u8').view('m8[ns]'),
            # np.random.randint(0, 2**25, size=1000, dtype='u8').view('M8[m]'),
            # np.random.randint(0, 2**25, size=1000, dtype='u8').view('m8[m]'),
            # np.random.randint(-2**63, -2**63 + 20, size=1000, dtype='i8').view('M8[ns]'),
            # np.random.randint(-2**63, -2**63 + 20, size=1000, dtype='i8').view('m8[ns]'),
            # np.random.randint(-2**63, -2**63 + 20, size=1000, dtype='i8').view('M8[m]'),
            # np.random.randint(-2**63, -2**63 + 20, size=1000, dtype='i8').view('m8[m]'),
        ]

        codecs = [
            # Blosc(shuffle=Blosc.SHUFFLE),
            # Blosc(clevel=0, shuffle=Blosc.SHUFFLE),
            # Blosc(cname='lz4', shuffle=Blosc.SHUFFLE),
            # Blosc(cname='lz4', clevel=1, shuffle=Blosc.NOSHUFFLE),
            # Blosc(cname='lz4', clevel=5, shuffle=Blosc.SHUFFLE),
            # Blosc(cname='lz4', clevel=9, shuffle=Blosc.BITSHUFFLE),
            # Blosc(cname='zlib', clevel=1, shuffle=0),
            Blosc(cname='zstd', clevel=1, shuffle=1),
            # Blosc(cname='blosclz', clevel=1, shuffle=2),
            # Blosc(cname='snappy', clevel=1, shuffle=2),
            # Blosc(shuffle=Blosc.SHUFFLE, blocksize=0),
            # Blosc(shuffle=Blosc.SHUFFLE, blocksize=2**8),
            # Blosc(cname='lz4', clevel=1, shuffle=Blosc.NOSHUFFLE, blocksize=2**8),
        ]
        # for codec in codecs:
        #     for array in arrays:
        #         check_encode_decode(array, codec)
        """

    selenium.run(cmd)
