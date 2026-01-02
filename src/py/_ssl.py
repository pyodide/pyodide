"""
Stub implementation of _ssl module for Pyodide.

This module provides stub implementations of the _ssl C extension module
constants, classes, and functions so that code importing from _ssl directly
does not fail. Actual SSL operations are not supported in Pyodide's browser
environment.
"""

from enum import IntEnum as _IntEnum, IntFlag as _IntFlag

# Version information
OPENSSL_VERSION_NUMBER = 0
OPENSSL_VERSION_INFO = (0, 0, 0, 0, 0)
OPENSSL_VERSION = "OpenSSL (stub)"
_OPENSSL_API_VERSION = (0, 0, 0, 0, 0)

# Protocol constants
PROTO_MINIMUM_SUPPORTED = -2
PROTO_SSLv3 = 768
PROTO_TLSv1 = 769
PROTO_TLSv1_1 = 770
PROTO_TLSv1_2 = 771
PROTO_TLSv1_3 = 772
PROTO_MAXIMUM_SUPPORTED = -1

# Protocol methods (deprecated, but still used)
PROTOCOL_SSLv23 = 2
PROTOCOL_TLS = 2
PROTOCOL_TLS_CLIENT = 16
PROTOCOL_TLS_SERVER = 17
PROTOCOL_TLSv1 = 3
PROTOCOL_TLSv1_1 = 4
PROTOCOL_TLSv1_2 = 5

# Certificate verification modes
CERT_NONE = 0
CERT_OPTIONAL = 1
CERT_REQUIRED = 2

# SSL error codes
SSL_ERROR_ZERO_RETURN = 6
SSL_ERROR_WANT_READ = 2
SSL_ERROR_WANT_WRITE = 3
SSL_ERROR_WANT_X509_LOOKUP = 4
SSL_ERROR_SYSCALL = 5
SSL_ERROR_SSL = 1
SSL_ERROR_WANT_CONNECT = 7
SSL_ERROR_EOF = 8
SSL_ERROR_INVALID_ERROR_CODE = 10

# Options (commonly used ones)
OP_ALL = -0x7fffffac
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

# Verify flags
VERIFY_DEFAULT = 0
VERIFY_CRL_CHECK_LEAF = 0x4
VERIFY_CRL_CHECK_CHAIN = 0xC
VERIFY_X509_STRICT = 0x20
VERIFY_X509_PARTIAL_CHAIN = 0x80000
VERIFY_ALLOW_PROXY_CERTS = 0x10

# Alert descriptions (commonly used)
ALERT_DESCRIPTION_CLOSE_NOTIFY = 0
ALERT_DESCRIPTION_UNEXPECTED_MESSAGE = 10
ALERT_DESCRIPTION_BAD_RECORD_MAC = 20
ALERT_DESCRIPTION_HANDSHAKE_FAILURE = 40
ALERT_DESCRIPTION_BAD_CERTIFICATE = 42
ALERT_DESCRIPTION_CERTIFICATE_EXPIRED = 45
ALERT_DESCRIPTION_CERTIFICATE_UNKNOWN = 46
ALERT_DESCRIPTION_ILLEGAL_PARAMETER = 47
ALERT_DESCRIPTION_UNKNOWN_CA = 48
ALERT_DESCRIPTION_ACCESS_DENIED = 49
ALERT_DESCRIPTION_INTERNAL_ERROR = 80

# Feature flags - all False for stub implementation
HAS_SNI = False
HAS_ECDH = False
HAS_NPN = False
HAS_ALPN = False
HAS_SSLv2 = False
HAS_SSLv3 = False
HAS_TLSv1 = False
HAS_TLSv1_1 = False
HAS_TLSv1_2 = False
HAS_TLSv1_3 = False
HAS_PSK = False

# Other flags
HOSTFLAG_NEVER_CHECK_SUBJECT = 0x4

# Encoding types
ENCODING_PEM = 1
ENCODING_DER = 1

# Default cipher string
_DEFAULT_CIPHERS = "DEFAULT"

# Exception classes
class SSLError(OSError):
    """Base class for SSL errors."""

    # The str() of a SSLError doesn't include the errno
    def __str__(self) -> str:
        return str(self.args[1]) if len(self.args) > 1 else ""


class SSLZeroReturnError(SSLError):
    """SSL/TLS session has been terminated."""
    pass


class SSLWantReadError(SSLError):
    """Non-blocking SSL socket needs to read more data."""
    pass


class SSLWantWriteError(SSLError):
    """Non-blocking SSL socket needs to write more data."""
    pass


class SSLSyscallError(SSLError):
    """System error in SSL operation."""
    pass


class SSLEOFError(SSLError):
    """EOF occurred in SSL operation."""
    pass


class SSLCertVerificationError(SSLError):
    """Certificate verification failed."""
    pass


# Stub classes
class _SSLContext:
    """Stub SSL context class."""
    def __init__(self, protocol):
        raise NotImplementedError("SSL is not supported in Pyodide")

class SSLSession:
    """Stub SSL session class."""
    def __init__(self):
        raise NotImplementedError("SSL is not supported in Pyodide")


class MemoryBIO:
    """Stub memory BIO class for buffering SSL data."""
    def __init__(self):
        self._buffer = bytearray()
        self._eof = False
    
    def write(self, data):
        """Write data to the BIO buffer.
        
        Args:
            data: bytes-like object to write
            
        Returns:
            Number of bytes written
            
        Raises:
            TypeError: if data is not bytes-like
            BufferError: if memoryview is not contiguous
        """
        if isinstance(data, str):
            raise TypeError("a bytes-like object is required, not 'str'")
        if data is None:
            raise TypeError("a bytes-like object is required, not 'NoneType'")
        if isinstance(data, bool) or isinstance(data, int):
            raise TypeError(f"a bytes-like object is required, not '{type(data).__name__}'")
        
        if isinstance(data, memoryview):
            # Check if contiguous
            if not data.c_contiguous:
                raise BufferError("memoryview must be contiguous")
            data = data.tobytes()
        
        self._buffer.extend(data)
        return len(data)
    
    def read(self, n=-1):
        """Read data from the BIO buffer.
        
        Args:
            n: number of bytes to read, -1 or omitted means read all
            
        Returns:
            bytes object with the data read
        """
        if n == -1 or n >= len(self._buffer):
            data = bytes(self._buffer)
            self._buffer.clear()
        else:
            data = bytes(self._buffer[:n])
            del self._buffer[:n]
        return data
    
    @property
    def eof(self):
        """Return True if EOF has been written and buffer is empty."""
        return self._eof and len(self._buffer) == 0
    
    def write_eof(self):
        """Mark the BIO as having reached EOF."""
        self._eof = True
    
    @property
    def pending(self):
        """Return the number of bytes available to read."""
        return len(self._buffer)


# Stub functions
def txt2obj(txt, name=False):
    """Convert text to ASN.1 object (stub)."""
    raise NotImplementedError("SSL is not supported in Pyodide")


def nid2obj(nid):
    """Convert NID to ASN.1 object (stub)."""
    raise NotImplementedError("SSL is not supported in Pyodide")


def RAND_status():
    """Return RAND status (stub - always returns 1)."""
    return 1


def RAND_add(string, entropy):
    """Add entropy to RAND (stub - no-op)."""
    pass


def RAND_bytes(n):
    """Generate random bytes (stub - uses Python's random)."""
    import random
    return bytes([random.randint(0, 255) for _ in range(n)])


def get_default_verify_paths():
    """Get default certificate verification paths (stub)."""
    return ('SSL_CERT_FILE', None, 'SSL_CERT_DIR', None)


def enum_certificates(store_name):
    """Enumerate certificates from Windows store (stub - returns empty list)."""
    return []


def enum_crls(store_name):
    """Enumerate CRLs from Windows store (stub - returns empty list)."""
    return []