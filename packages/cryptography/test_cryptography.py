from hypothesis import HealthCheck, given, settings
from hypothesis.strategies import binary, integers

from conftest import selenium_context_manager
from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(packages=["cryptography"])
def test_cryptography():
    import base64

    from cryptography.fernet import Fernet, MultiFernet

    f1 = Fernet(base64.urlsafe_b64encode(b"\x00" * 32))
    f2 = Fernet(base64.urlsafe_b64encode(b"\x01" * 32))
    f = MultiFernet([f1, f2])

    assert f1.decrypt(f.encrypt(b"abc")) == b"abc"


@run_in_pyodide(packages=["cryptography", "pytest"])
def test_der_reader_basic():
    import pytest
    from cryptography.hazmat._der import DERReader

    reader = DERReader(b"123456789")
    assert reader.read_byte() == ord(b"1")
    assert reader.read_bytes(1).tobytes() == b"2"
    assert reader.read_bytes(4).tobytes() == b"3456"

    with pytest.raises(ValueError):
        reader.read_bytes(4)

    assert reader.read_bytes(3).tobytes() == b"789"

    # The input is now empty.
    with pytest.raises(ValueError):
        reader.read_bytes(1)
    with pytest.raises(ValueError):
        reader.read_byte()


@run_in_pyodide(packages=["cryptography", "pytest"])
def test_der():
    import pytest
    from cryptography.hazmat._der import (
        INTEGER,
        NULL,
        OCTET_STRING,
        SEQUENCE,
        DERReader,
        encode_der,
        encode_der_integer,
    )

    # This input is the following structure, using
    # https://github.com/google/der-ascii
    #
    # SEQUENCE {
    #   SEQUENCE {
    #     NULL {}
    #     INTEGER { 42 }
    #     OCTET_STRING { "hello" }
    #   }
    # }
    der = b"\x30\x0e\x30\x0c\x05\x00\x02\x01\x2a\x04\x05\x68\x65\x6c\x6c\x6f"
    reader = DERReader(der)
    with pytest.raises(ValueError):
        reader.check_empty()

    with pytest.raises(ValueError):
        with reader:
            pass

    with pytest.raises(ZeroDivisionError):
        with DERReader(der):
            raise ZeroDivisionError

    # Parse the outer element.
    outer = reader.read_element(SEQUENCE)
    reader.check_empty()
    assert outer.data.tobytes() == der[2:]

    # Parse the outer element with read_any_element.
    reader = DERReader(der)
    tag, outer2 = reader.read_any_element()
    reader.check_empty()
    assert tag == SEQUENCE
    assert outer2.data.tobytes() == der[2:]

    # Parse the outer element with read_single_element.
    outer3 = DERReader(der).read_single_element(SEQUENCE)
    assert outer3.data.tobytes() == der[2:]

    # read_single_element rejects trailing data.
    with pytest.raises(ValueError):
        DERReader(der + der).read_single_element(SEQUENCE)

    # Continue parsing the structure.
    inner = outer.read_element(SEQUENCE)
    outer.check_empty()

    # Parsing a missing optional element should work.
    assert inner.read_optional_element(INTEGER) is None

    null = inner.read_element(NULL)
    null.check_empty()

    # Parsing a present optional element should work.
    integer = inner.read_optional_element(INTEGER)
    assert integer.as_integer() == 42

    octet_string = inner.read_element(OCTET_STRING)
    assert octet_string.data.tobytes() == b"hello"

    # Parsing a missing optional element should work when the input is empty.
    inner.check_empty()
    assert inner.read_optional_element(INTEGER) is None

    # Re-encode the same structure.
    der2 = encode_der(
        SEQUENCE,
        encode_der(
            SEQUENCE,
            encode_der(NULL),
            encode_der(INTEGER, encode_der_integer(42)),
            encode_der(OCTET_STRING, b"hello"),
        ),
    )
    assert der2 == der


@run_in_pyodide(packages=["cryptography"])
def test_der_lengths():

    from cryptography.hazmat._der import OCTET_STRING, DERReader, encode_der

    for [length, header] in [
        # Single-byte lengths.
        (0, b"\x04\x00"),
        (1, b"\x04\x01"),
        (2, b"\x04\x02"),
        (127, b"\x04\x7f"),
        # Long-form lengths.
        (128, b"\x04\x81\x80"),
        (129, b"\x04\x81\x81"),
        (255, b"\x04\x81\xff"),
        (0x100, b"\x04\x82\x01\x00"),
        (0x101, b"\x04\x82\x01\x01"),
        (0xFFFF, b"\x04\x82\xff\xff"),
        (0x10000, b"\x04\x83\x01\x00\x00"),
    ]:
        body = length * b"a"
        der = header + body

        reader = DERReader(der)
        element = reader.read_element(OCTET_STRING)
        reader.check_empty()
        assert element.data.tobytes() == body

        assert encode_der(OCTET_STRING, body) == der


@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(data=binary())
def test_fernet(selenium_module_scope, data):
    sbytes = list(data)
    with selenium_context_manager(selenium_module_scope) as selenium:
        selenium.load_package("cryptography")
        selenium.run(
            f"""
            from cryptography.fernet import Fernet
            data = bytes({sbytes})
            f = Fernet(Fernet.generate_key())
            ct = f.encrypt(data)
            assert f.decrypt(ct) == data
            """
        )


@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(block_size=integers(min_value=1, max_value=255), data=binary())
def test_pkcs7(selenium_module_scope, block_size, data):
    sbytes = list(data)
    with selenium_context_manager(selenium_module_scope) as selenium:
        selenium.load_package("cryptography")
        selenium.run(
            f"""
            from cryptography.hazmat.primitives.padding import ANSIX923, PKCS7
            block_size = {block_size}
            data = bytes({sbytes})
            # Generate in [1, 31] so we can easily get block_size in bits by
            # multiplying by 8.
            p = PKCS7(block_size=block_size * 8)
            padder = p.padder()
            unpadder = p.unpadder()

            padded = padder.update(data) + padder.finalize()

            assert unpadder.update(padded) + unpadder.finalize() == data
            """
        )


@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(block_size=integers(min_value=1, max_value=255), data=binary())
def test_ansix923(selenium_module_scope, block_size, data):
    sbytes = list(data)
    with selenium_context_manager(selenium_module_scope) as selenium:
        selenium.load_package("cryptography")
        selenium.run(
            f"""
            from cryptography.hazmat.primitives.padding import ANSIX923, PKCS7
            block_size = {block_size}
            data = bytes({sbytes})
            a = ANSIX923(block_size=block_size * 8)
            padder = a.padder()
            unpadder = a.unpadder()

            padded = padder.update(data) + padder.finalize()

            assert unpadder.update(padded) + unpadder.finalize() == data
            """
        )
