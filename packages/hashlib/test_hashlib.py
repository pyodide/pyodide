from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["test", "hashlib"], pytest_assert_rewrites=False)
def test_hashlib(selenium):
    from test import libregrtest  # type:ignore[attr-defined]

    name = "test_hashlib"
    ignore_tests = [
        "*threaded*",
    ]

    try:
        libregrtest.main([name], ignore_tests=ignore_tests, verbose=True, verbose3=True)
    except SystemExit as e:
        if e.code != 0:
            raise RuntimeError(f"Failed with code: {e.code}") from None


@run_in_pyodide(packages=["hashlib"])
def test_hashlib_algorithms(selenium):
    import hashlib
    from hashlib import algorithms_available

    python_algorithms = {
        "md5",
        "blake2s",
        "sha3_256",
        "sha256",
        "sha384",
        "sha224",
        "sha3_384",
        "sha512",
        "blake2b",
        "sha3_224",
        "shake_256",
        "sha1",
        "sha3_512",
        "shake_128",
    }
    openssl_algorithms = {
        "whirlpool",
        "shake_128",
        "shake_256",
        "sha3_384",
        "sha256",
        "sha3_512",
        "sha512",
        "mdc2",
        "ripemd160",
        "md5-sha1",
        "sm3",
        "sha512_256",
        "md5",
        "md4",
        "sha3_224",
        "sha1",
        "sha224",
        "blake2s",
        "sha384",
        "sha512_224",
        "sha3_256",
        "blake2b",
    } - python_algorithms

    for python_algorithm in python_algorithms:
        assert python_algorithm in algorithms_available
    for openssl_algorithm in openssl_algorithms:
        assert openssl_algorithm in algorithms_available

    for algorithm in algorithms_available:
        hashlib.new(algorithm).digest_size
