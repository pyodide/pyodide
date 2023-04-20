from hypothesis import HealthCheck, given, settings
from hypothesis.strategies import binary, integers
from pytest_pyodide import run_in_pyodide
from pytest_pyodide.fixture import selenium_context_manager


@run_in_pyodide(packages=["cryptography"])
def test_cryptography(selenium):
    import base64

    from cryptography.fernet import Fernet, MultiFernet

    f1 = Fernet(base64.urlsafe_b64encode(b"\x00" * 32))
    f2 = Fernet(base64.urlsafe_b64encode(b"\x01" * 32))
    f = MultiFernet([f1, f2])

    assert f1.decrypt(f.encrypt(b"abc")) == b"abc"


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
