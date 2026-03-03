"""
Stub implementation of _ssl module for Pyodide.

Provides stub implementations of the _ssl C extension module so that code
importing from _ssl does not fail. Actual SSL operations are not supported.
"""

# Version information (stub values)
# Use 1.1.1w as a reference
# Some packages may check for specific versions of OpenSSL, so we need to provide
# consistent version info.
# TODO: This might be an issue if openssl version linked to the side modules are different
# from this version. But I don't see a good way to sync them right now.
OPENSSL_VERSION_NUMBER = 269488511
OPENSSL_VERSION_INFO = (1, 1, 1, 23, 15)
OPENSSL_VERSION = "OpenSSL (stub)"
_OPENSSL_API_VERSION = (1, 1, 1, 23, 15)

PROTO_MINIMUM_SUPPORTED = -2
PROTO_SSLv3 = 768
PROTO_TLSv1 = 769
PROTO_TLSv1_1 = 770
PROTO_TLSv1_2 = 771
PROTO_TLSv1_3 = 772
PROTO_MAXIMUM_SUPPORTED = -1

PROTOCOL_SSLv23 = 2
PROTOCOL_TLS = 2
PROTOCOL_TLS_CLIENT = 16
PROTOCOL_TLS_SERVER = 17
PROTOCOL_TLSv1 = 3
PROTOCOL_TLSv1_1 = 4
PROTOCOL_TLSv1_2 = 5

CERT_NONE = 0
CERT_OPTIONAL = 1
CERT_REQUIRED = 2

SSL_ERROR_ZERO_RETURN = 6
SSL_ERROR_WANT_READ = 2
SSL_ERROR_WANT_WRITE = 3
SSL_ERROR_WANT_X509_LOOKUP = 4
SSL_ERROR_SYSCALL = 5
SSL_ERROR_SSL = 1
SSL_ERROR_WANT_CONNECT = 7
SSL_ERROR_EOF = 8
SSL_ERROR_INVALID_ERROR_CODE = 10

OP_ALL = -0x7FFFFFAC
OP_NO_SSLv2 = 0x01000000
OP_NO_SSLv3 = 0x02000000
OP_NO_TLSv1 = 0x04000000
OP_NO_TLSv1_1 = 0x10000000
OP_NO_TLSv1_2 = 0x08000000
OP_NO_TLSv1_3 = 0x20000000
OP_NO_COMPRESSION = 0x00020000
OP_CIPHER_SERVER_PREFERENCE = 0x00400000
OP_SINGLE_DH_USE = 0x00100000
OP_SINGLE_ECDH_USE = 0x00080000
OP_ENABLE_MIDDLEBOX_COMPAT = 0x00000400
OP_LEGACY_SERVER_CONNECT = 0x00000004
OP_NO_TICKET = 0x00004000
OP_ENABLE_KTLS = 0x00000800
OP_IGNORE_UNEXPECTED_EOF = 0x00000200
OP_NO_RENEGOTIATION = 0x00000100

VERIFY_DEFAULT = 0
VERIFY_CRL_CHECK_LEAF = 0x4
VERIFY_CRL_CHECK_CHAIN = 0xC
VERIFY_X509_STRICT = 0x20
VERIFY_X509_PARTIAL_CHAIN = 0x80000
VERIFY_X509_TRUSTED_FIRST = 0x8000
VERIFY_ALLOW_PROXY_CERTS = 0x10

ALERT_DESCRIPTION_CLOSE_NOTIFY = 0
ALERT_DESCRIPTION_UNEXPECTED_MESSAGE = 10
ALERT_DESCRIPTION_BAD_RECORD_MAC = 20
ALERT_DESCRIPTION_HANDSHAKE_FAILURE = 40
ALERT_DESCRIPTION_BAD_CERTIFICATE = 42
ALERT_DESCRIPTION_BAD_CERTIFICATE_HASH_VALUE = 43
ALERT_DESCRIPTION_BAD_CERTIFICATE_STATUS_RESPONSE = 44
ALERT_DESCRIPTION_CERTIFICATE_EXPIRED = 45
ALERT_DESCRIPTION_CERTIFICATE_UNKNOWN = 46
ALERT_DESCRIPTION_ILLEGAL_PARAMETER = 47
ALERT_DESCRIPTION_UNKNOWN_CA = 48
ALERT_DESCRIPTION_ACCESS_DENIED = 49
ALERT_DESCRIPTION_CERTIFICATE_REVOKED = 50
ALERT_DESCRIPTION_CERTIFICATE_UNOBTAINABLE = 51
ALERT_DESCRIPTION_DECODE_ERROR = 52
ALERT_DESCRIPTION_DECOMPRESSION_FAILURE = 53
ALERT_DESCRIPTION_RECORD_OVERFLOW = 54
ALERT_DESCRIPTION_DECRYPT_ERROR = 55
ALERT_DESCRIPTION_INSUFFICIENT_SECURITY = 56
ALERT_DESCRIPTION_UNKNOWN_PSK_IDENTITY = 57
ALERT_DESCRIPTION_UNSUPPORTED_CERTIFICATE = 58
ALERT_DESCRIPTION_UNSUPPORTED_EXTENSION = 110
ALERT_DESCRIPTION_UNRECOGNIZED_NAME = 112
ALERT_DESCRIPTION_USER_CANCELLED = 90
ALERT_DESCRIPTION_NO_RENEGOTIATION = 100
ALERT_DESCRIPTION_PROTOCOL_VERSION = 70
ALERT_DESCRIPTION_INTERNAL_ERROR = 80

HAS_SNI = True
HAS_ECDH = False
HAS_NPN = False
HAS_ALPN = True
HAS_SSLv2 = False
HAS_SSLv3 = False
HAS_TLSv1 = True
HAS_TLSv1_1 = True
HAS_TLSv1_2 = True
HAS_TLSv1_3 = False
HAS_PSK = True
HAS_PHA = False

HOSTFLAG_NEVER_CHECK_SUBJECT = 0x4
ENCODING_PEM = 1
ENCODING_DER = 1
_DEFAULT_CIPHERS = "DEFAULT"


class SSLError(OSError):
    def __str__(self) -> str:
        return str(self.args[1]) if len(self.args) > 1 else ""


class SSLZeroReturnError(SSLError):
    pass


class SSLWantReadError(SSLError):
    pass


class SSLWantWriteError(SSLError):
    pass


class SSLSyscallError(SSLError):
    pass


class SSLEOFError(SSLError):
    pass


class SSLCertVerificationError(SSLError):
    pass


class _SSLContext:
    def __init__(self, protocol):
        raise NotImplementedError("SSL is not supported in Pyodide")


class SSLSession:
    def __init__(self):
        raise NotImplementedError("SSL is not supported in Pyodide")


class MemoryBIO:
    def __init__(self):
        self._buffer = bytearray()
        self._eof = False

    def write(self, data):
        if isinstance(data, str):
            raise TypeError("a bytes-like object is required, not 'str'")
        if data is None:
            raise TypeError("a bytes-like object is required, not 'NoneType'")
        if isinstance(data, (bool, int)):
            raise TypeError(
                f"a bytes-like object is required, not '{type(data).__name__}'"
            )
        if isinstance(data, memoryview):
            if not data.c_contiguous:
                raise BufferError("memoryview must be contiguous")
            data = data.tobytes()
        self._buffer.extend(data)
        return len(data)

    def read(self, n=-1):
        if n == -1 or n >= len(self._buffer):
            data = bytes(self._buffer)
            self._buffer.clear()
        else:
            data = bytes(self._buffer[:n])
            del self._buffer[:n]
        return data

    @property
    def eof(self):
        return self._eof and len(self._buffer) == 0

    def write_eof(self):
        self._eof = True

    @property
    def pending(self):
        return len(self._buffer)


def txt2obj(txt, name=False):
    raise NotImplementedError("SSL is not supported in Pyodide")


def nid2obj(nid):
    raise NotImplementedError("SSL is not supported in Pyodide")


def RAND_status():
    return 1


def RAND_add(string, entropy):
    pass


def RAND_bytes(n):
    import secrets

    return secrets.token_bytes(n)


def get_default_verify_paths():
    return ("SSL_CERT_FILE", None, "SSL_CERT_DIR", None)


def enum_certificates(store_name):
    return []


def enum_crls(store_name):
    return []
