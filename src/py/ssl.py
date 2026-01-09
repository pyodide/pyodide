# type: ignore
"""
Stub implementation of Python's ssl module for Pyodide.

This module provides stub implementations so that code importing ssl does not fail.
Actual SSL operations are not supported in Pyodide's browser environment.
"""

import _ssl
import os
import sys
import base64
import warnings
from collections import namedtuple
from enum import Enum as _Enum, IntEnum as _IntEnum, IntFlag as _IntFlag, _simple_enum
from socket import socket, create_connection, _GLOBAL_DEFAULT_TIMEOUT

from _ssl import (
    OPENSSL_VERSION_NUMBER,
    OPENSSL_VERSION_INFO,
    OPENSSL_VERSION,
    _DEFAULT_CIPHERS,
    _SSLContext,
    MemoryBIO,
    SSLSession,
    SSLError,
    SSLZeroReturnError,
    SSLWantReadError,
    SSLWantWriteError,
    SSLSyscallError,
    SSLEOFError,
    SSLCertVerificationError,
    HAS_SNI,
    HAS_ECDH,
    HAS_NPN,
    HAS_ALPN,
    HAS_SSLv2,
    HAS_SSLv3,
    HAS_TLSv1,
    HAS_TLSv1_1,
    HAS_TLSv1_2,
    HAS_TLSv1_3,
    HAS_PSK,
    HAS_PHA,
    txt2obj as _txt2obj,
    nid2obj as _nid2obj,
    RAND_status,
    RAND_add,
    RAND_bytes,
    HOSTFLAG_NEVER_CHECK_SUBJECT,
    VERIFY_X509_PARTIAL_CHAIN,
    VERIFY_X509_STRICT,
)

CertificateError = SSLCertVerificationError

_IntEnum._convert_(
    "_SSLMethod",
    __name__,
    lambda name: name.startswith("PROTOCOL_") and name != "PROTOCOL_SSLv23",
    source=_ssl,
)

_IntFlag._convert_(
    "Options", __name__, lambda name: name.startswith("OP_"), source=_ssl
)

_IntEnum._convert_(
    "AlertDescription",
    __name__,
    lambda name: name.startswith("ALERT_DESCRIPTION_"),
    source=_ssl,
)

_IntEnum._convert_(
    "SSLErrorNumber", __name__, lambda name: name.startswith("SSL_ERROR_"), source=_ssl
)

_IntFlag._convert_(
    "VerifyFlags", __name__, lambda name: name.startswith("VERIFY_"), source=_ssl
)

_IntEnum._convert_(
    "VerifyMode", __name__, lambda name: name.startswith("CERT_"), source=_ssl
)

PROTOCOL_SSLv23 = _SSLMethod.PROTOCOL_SSLv23 = _SSLMethod.PROTOCOL_TLS
_PROTOCOL_NAMES = {value: name for name, value in _SSLMethod.__members__.items()}
_SSLv2_IF_EXISTS = None


@_simple_enum(_IntEnum)
class TLSVersion:
    MINIMUM_SUPPORTED = _ssl.PROTO_MINIMUM_SUPPORTED
    SSLv3 = _ssl.PROTO_SSLv3
    TLSv1 = _ssl.PROTO_TLSv1
    TLSv1_1 = _ssl.PROTO_TLSv1_1
    TLSv1_2 = _ssl.PROTO_TLSv1_2
    TLSv1_3 = _ssl.PROTO_TLSv1_3
    MAXIMUM_SUPPORTED = _ssl.PROTO_MAXIMUM_SUPPORTED


@_simple_enum(_IntEnum)
class _TLSContentType:
    """Content types (record layer) - RFC 8446, section B.1"""

    CHANGE_CIPHER_SPEC = 20
    ALERT = 21
    HANDSHAKE = 22
    APPLICATION_DATA = 23
    HEADER = 0x100
    INNER_CONTENT_TYPE = 0x101


@_simple_enum(_IntEnum)
class _TLSAlertType:
    """Alert types for TLSContentType.ALERT messages - RFC 8466, section B.2"""

    CLOSE_NOTIFY = 0
    UNEXPECTED_MESSAGE = 10
    BAD_RECORD_MAC = 20
    DECRYPTION_FAILED = 21
    RECORD_OVERFLOW = 22
    DECOMPRESSION_FAILURE = 30
    HANDSHAKE_FAILURE = 40
    NO_CERTIFICATE = 41
    BAD_CERTIFICATE = 42
    UNSUPPORTED_CERTIFICATE = 43
    CERTIFICATE_REVOKED = 44
    CERTIFICATE_EXPIRED = 45
    CERTIFICATE_UNKNOWN = 46
    ILLEGAL_PARAMETER = 47
    UNKNOWN_CA = 48
    ACCESS_DENIED = 49
    DECODE_ERROR = 50
    DECRYPT_ERROR = 51
    EXPORT_RESTRICTION = 60
    PROTOCOL_VERSION = 70
    INSUFFICIENT_SECURITY = 71
    INTERNAL_ERROR = 80
    INAPPROPRIATE_FALLBACK = 86
    USER_CANCELED = 90
    NO_RENEGOTIATION = 100
    MISSING_EXTENSION = 109
    UNSUPPORTED_EXTENSION = 110
    CERTIFICATE_UNOBTAINABLE = 111
    UNRECOGNIZED_NAME = 112
    BAD_CERTIFICATE_STATUS_RESPONSE = 113
    BAD_CERTIFICATE_HASH_VALUE = 114
    UNKNOWN_PSK_IDENTITY = 115
    CERTIFICATE_REQUIRED = 116
    NO_APPLICATION_PROTOCOL = 120


@_simple_enum(_IntEnum)
class _TLSMessageType:
    """Message types (handshake protocol) - RFC 8446, section B.3"""

    HELLO_REQUEST = 0
    CLIENT_HELLO = 1
    SERVER_HELLO = 2
    HELLO_VERIFY_REQUEST = 3
    NEWSESSION_TICKET = 4
    END_OF_EARLY_DATA = 5
    HELLO_RETRY_REQUEST = 6
    ENCRYPTED_EXTENSIONS = 8
    CERTIFICATE = 11
    SERVER_KEY_EXCHANGE = 12
    CERTIFICATE_REQUEST = 13
    SERVER_DONE = 14
    CERTIFICATE_VERIFY = 15
    CLIENT_KEY_EXCHANGE = 16
    FINISHED = 20
    CERTIFICATE_URL = 21
    CERTIFICATE_STATUS = 22
    SUPPLEMENTAL_DATA = 23
    KEY_UPDATE = 24
    NEXT_PROTO = 67
    MESSAGE_HASH = 254
    CHANGE_CIPHER_SPEC = 0x0101


socket_error = OSError
CHANNEL_BINDING_TYPES = ["tls-unique"]
HAS_NEVER_CHECK_COMMON_NAME = False
_RESTRICTED_SERVER_CIPHERS = _DEFAULT_CIPHERS

DefaultVerifyPaths = namedtuple(
    "DefaultVerifyPaths",
    "cafile capath openssl_cafile_env openssl_cafile openssl_capath_env openssl_capath",
)


def get_default_verify_paths():
    """Return paths to default cafile and capath."""
    parts = _ssl.get_default_verify_paths()
    cafile = os.environ.get(parts[0], parts[1])
    capath = os.environ.get(parts[2], parts[3])
    return DefaultVerifyPaths(
        cafile if cafile and os.path.isfile(cafile) else None,
        capath if capath and os.path.isdir(capath) else None,
        *parts,
    )


class _ASN1Object(namedtuple("_ASN1Object", "nid shortname longname oid")):
    """ASN.1 object identifier lookup"""

    __slots__ = ()

    def __new__(cls, oid):
        return super().__new__(cls, 0, "stub", "stub", oid)

    @classmethod
    def fromnid(cls, nid):
        return super().__new__(cls, nid, "stub", "stub", "0.0.0.0")

    @classmethod
    def fromname(cls, name):
        return super().__new__(cls, 0, name, name, "0.0.0.0")


class Purpose(_ASN1Object, _Enum):
    """SSLContext purpose flags with X509v3 Extended Key Usage objects"""

    SERVER_AUTH = "1.3.6.1.5.5.7.3.1"
    CLIENT_AUTH = "1.3.6.1.5.5.7.3.2"


class SSLContext:
    """An SSLContext holds various SSL-related configuration options and data."""

    _windows_cert_stores = ("CA", "ROOT")
    sslsocket_class = None
    sslobject_class = None

    def __init__(self, protocol=None, *args, **kwargs):
        if protocol is None:
            warnings.warn(
                "ssl.SSLContext() without protocol argument is deprecated.",
                category=DeprecationWarning,
                stacklevel=2,
            )
            protocol = PROTOCOL_TLS

        if not isinstance(protocol, int):
            raise TypeError("protocol must be an integer")

        valid_protocols = {
            PROTOCOL_TLS,
            PROTOCOL_TLS_CLIENT,
            PROTOCOL_TLS_SERVER,
        }
        for proto_name in [
            "PROTOCOL_SSLv3",
            "PROTOCOL_TLSv1",
            "PROTOCOL_TLSv1_1",
            "PROTOCOL_TLSv1_2",
        ]:
            if hasattr(_ssl, proto_name):
                valid_protocols.add(getattr(_ssl, proto_name))
        if protocol not in valid_protocols:
            raise ValueError(f"invalid protocol version {protocol}")

        self.protocol = protocol
        if protocol == PROTOCOL_TLS_CLIENT:
            self._check_hostname = True
            self._verify_mode = CERT_REQUIRED
        else:
            self._check_hostname = False
            self._verify_mode = CERT_NONE

        self._minimum_version = TLSVersion.TLSv1_2
        self._maximum_version = TLSVersion.TLSv1_3
        self._options = (
            Options.OP_ALL
            | Options.OP_NO_SSLv2
            | Options.OP_NO_SSLv3
            | Options.OP_NO_COMPRESSION
            | Options.OP_CIPHER_SERVER_PREFERENCE
            | Options.OP_SINGLE_DH_USE
            | Options.OP_SINGLE_ECDH_USE
            | Options.OP_ENABLE_MIDDLEBOX_COMPAT
        )
        self._verify_flags = VerifyFlags.VERIFY_X509_TRUSTED_FIRST
        self._host_flags = 0
        self.sni_callback = None
        self._msg_callback_inner = None
        self.keylog_filename = None
        self._num_tickets = 2
        self._cert_store = {"crl": 0, "x509_ca": 0, "x509": 0}
        self.post_handshake_auth = None

    def _encode_hostname(self, hostname):
        if hostname is None:
            return None
        elif isinstance(hostname, str):
            return hostname.encode("idna").decode("ascii")
        else:
            return hostname.decode("ascii")

    def wrap_socket(
        self,
        sock,
        server_side=False,
        do_handshake_on_connect=True,
        suppress_ragged_eofs=True,
        server_hostname=None,
        session=None,
    ):
        raise NotImplementedError("SSL is not supported in Pyodide")

    def wrap_bio(
        self, incoming, outgoing, server_side=False, server_hostname=None, session=None
    ):
        raise NotImplementedError("SSL is not supported in Pyodide")

    def set_npn_protocols(self, npn_protocols):
        warnings.warn(
            "ssl NPN is deprecated, use ALPN instead", DeprecationWarning, stacklevel=2
        )

    def set_servername_callback(self, server_name_callback):
        if server_name_callback is not None and not callable(server_name_callback):
            raise TypeError("not a callable object")
        self.sni_callback = server_name_callback

    def set_alpn_protocols(self, alpn_protocols):
        pass

    def _load_windows_store_certs(self, storename, purpose):
        pass

    def load_default_certs(self, purpose=Purpose.SERVER_AUTH):
        if not isinstance(purpose, _ASN1Object):
            raise TypeError(purpose)

    def load_verify_locations(self, cafile=None, capath=None, cadata=None):
        if cafile is None and capath is None and cadata is None:
            raise TypeError("cafile, capath and cadata cannot be all omitted")

    def load_cert_chain(self, certfile, keyfile=None, password=None):
        pass

    def set_default_verify_paths(self):
        pass

    @property
    def minimum_version(self):
        return self._minimum_version

    @minimum_version.setter
    def minimum_version(self, value):
        self._minimum_version = value

    @property
    def maximum_version(self):
        return self._maximum_version

    @maximum_version.setter
    def maximum_version(self, value):
        self._maximum_version = value

    @property
    def options(self):
        return self._options

    @options.setter
    def options(self, value):
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("'options' must be an integer")
        if value < 0:
            raise OverflowError("options must be a non-negative integer")
        if value >= 2**64:
            raise OverflowError("options value is too large")
        self._options = value

    @property
    def hostname_checks_common_name(self):
        if not HAS_NEVER_CHECK_COMMON_NAME:
            return True
        return (
            self._host_flags & HOSTFLAG_NEVER_CHECK_SUBJECT
        ) != HOSTFLAG_NEVER_CHECK_SUBJECT

    @hostname_checks_common_name.setter
    def hostname_checks_common_name(self, value):
        if not HAS_NEVER_CHECK_COMMON_NAME:
            raise AttributeError("hostname_checks_common_name")
        if value:
            self._host_flags &= ~HOSTFLAG_NEVER_CHECK_SUBJECT
        else:
            self._host_flags |= HOSTFLAG_NEVER_CHECK_SUBJECT

    @property
    def check_hostname(self):
        return self._check_hostname

    @check_hostname.setter
    def check_hostname(self, value):
        self._check_hostname = bool(value)
        if self._check_hostname and self._verify_mode == CERT_NONE:
            self._verify_mode = CERT_REQUIRED

    @property
    def _msg_callback(self):
        return self._msg_callback_inner

    @_msg_callback.setter
    def _msg_callback(self, callback):
        if callback is not None and not callable(callback):
            raise TypeError(f"{callback} is not callable.")
        self._msg_callback_inner = callback

    @property
    def verify_mode(self):
        return self._verify_mode

    @verify_mode.setter
    def verify_mode(self, value):
        if value is None:
            raise TypeError("verify_mode must be specified")
        if value not in (CERT_NONE, CERT_OPTIONAL, CERT_REQUIRED):
            raise ValueError("invalid value for verify_mode")
        if self._check_hostname and value == CERT_NONE:
            raise ValueError(
                "Cannot set verify_mode to CERT_NONE when check_hostname is enabled."
            )
        self._verify_mode = value

    @property
    def verify_flags(self):
        return self._verify_flags

    @verify_flags.setter
    def verify_flags(self, value):
        if value is None:
            raise TypeError("verify_flags must be specified")
        self._verify_flags = value

    def get_ca_certs(self, binary_form=False):
        return []

    def cert_store_stats(self):
        return self._cert_store.copy()

    def set_ciphers(self, ciphers):
        if not isinstance(ciphers, str):
            raise TypeError("ciphers must be a string")
        if not ciphers or ciphers.isspace():
            raise SSLError("No cipher can be selected.")

    def get_ciphers(self):
        return []

    def load_dh_params(self, dhfile):
        import errno

        if dhfile is None:
            raise TypeError("path is None")
        if isinstance(dhfile, str):
            if not os.path.exists(dhfile):
                raise FileNotFoundError(
                    errno.ENOENT, "No such file or directory", dhfile
                )
            try:
                with open(dhfile) as f:
                    content = f.read()
                    if (
                        "BEGIN DH PARAMETERS" not in content
                        and "BEGIN PARAMETERS" not in content
                    ):
                        raise SSLError("PEM lib")
            except (UnicodeDecodeError, OSError) as e:
                if isinstance(e, FileNotFoundError):
                    raise
                raise SSLError("PEM lib") from e
        elif isinstance(dhfile, bytes):
            if not os.path.exists(dhfile.decode()):
                raise FileNotFoundError(
                    errno.ENOENT, "No such file or directory", dhfile
                )
        if isinstance(dhfile, bytes) and not os.path.exists(dhfile.decode()):
            raise FileNotFoundError(errno.ENOENT, "No such file or directory", dhfile)

    def session_stats(self):
        return {
            "number": 0,
            "connect": 0,
            "connect_good": 0,
            "connect_renegotiate": 0,
            "accept": 0,
            "accept_good": 0,
            "accept_renegotiate": 0,
            "hits": 0,
            "misses": 0,
            "timeouts": 0,
            "cache_full": 0,
        }

    @property
    def num_tickets(self):
        return self._num_tickets

    @num_tickets.setter
    def num_tickets(self, value):
        if value is None:
            raise TypeError("num_tickets must be an integer, not None")
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("num_tickets must be an integer")
        if value < 0:
            raise ValueError("num_tickets must be a non-negative integer")
        if self.protocol == PROTOCOL_TLS_CLIENT and value != 2:
            raise ValueError("can't set num_tickets for client contexts")
        self._num_tickets = value

    def set_ecdh_curve(self, curve_name):
        pass

def create_default_context(
    purpose=Purpose.SERVER_AUTH, *, cafile=None, capath=None, cadata=None
):
    """Create a SSLContext object with default settings."""
    if not isinstance(purpose, _ASN1Object):
        raise TypeError(purpose)

    if purpose == Purpose.SERVER_AUTH:
        context = SSLContext(PROTOCOL_TLS_CLIENT)
        context.verify_mode = CERT_REQUIRED
        context.check_hostname = True
    elif purpose == Purpose.CLIENT_AUTH:
        context = SSLContext(PROTOCOL_TLS_SERVER)
    else:
        raise ValueError(purpose)

    context.verify_flags |= VERIFY_X509_PARTIAL_CHAIN | VERIFY_X509_STRICT

    if cafile or capath or cadata:
        context.load_verify_locations(cafile, capath, cadata)
    elif context.verify_mode != CERT_NONE:
        context.load_default_certs(purpose)

    if hasattr(context, "keylog_filename"):
        keylogfile = os.environ.get("SSLKEYLOGFILE")
        if keylogfile and not sys.flags.ignore_environment:
            context.keylog_filename = keylogfile
    return context


def _create_unverified_context(
    protocol=None,
    *,
    cert_reqs=CERT_NONE,
    check_hostname=False,
    purpose=Purpose.SERVER_AUTH,
    certfile=None,
    keyfile=None,
    cafile=None,
    capath=None,
    cadata=None,
):
    """Create a SSLContext object for Python stdlib modules."""
    if not isinstance(purpose, _ASN1Object):
        raise TypeError(purpose)

    if purpose == Purpose.SERVER_AUTH:
        if protocol is None:
            protocol = PROTOCOL_TLS_CLIENT
    elif purpose == Purpose.CLIENT_AUTH:
        if protocol is None:
            protocol = PROTOCOL_TLS_SERVER
    else:
        raise ValueError(purpose)

    context = SSLContext(protocol)
    context.check_hostname = check_hostname
    if cert_reqs is not None:
        context.verify_mode = cert_reqs

    if keyfile and not certfile:
        raise ValueError("certfile must be specified")
    if certfile or keyfile:
        context.load_cert_chain(certfile, keyfile)

    if cafile or capath or cadata:
        context.load_verify_locations(cafile, capath, cadata)
    elif context.verify_mode != CERT_NONE:
        context.load_default_certs(purpose)

    keylogfile = os.environ.get("SSLKEYLOGFILE")
    if keylogfile and not sys.flags.ignore_environment:
        context.keylog_filename = keylogfile
    return context


_create_default_https_context = create_default_context
_create_stdlib_context = _create_unverified_context


class SSLObject:
    """SSL object for wrapping BIO objects. Instances returned by SSLContext.wrap_bio()."""

    def __init__(self, *args, **kwargs):
        raise TypeError(
            f"{self.__class__.__name__} does not have a public constructor. "
            f"Instances are returned by SSLContext.wrap_bio()."
        )

    @classmethod
    def _create(
        cls,
        incoming,
        outgoing,
        server_side=False,
        server_hostname=None,
        session=None,
        context=None,
    ):
        raise NotImplementedError("SSL is not supported in Pyodide")

    context = property(lambda self: None)
    session = property(lambda self: None)
    session_reused = property(lambda self: None)
    server_side = property(lambda self: None)
    server_hostname = property(lambda self: None)

    def read(self, len=1024, buffer=None):
        pass

    def write(self, data):
        pass

    def getpeercert(self, binary_form=False):
        pass

    def get_verified_chain(self):
        return []

    def get_unverified_chain(self):
        return []

    def selected_npn_protocol(self):
        warnings.warn(
            "ssl NPN is deprecated, use ALPN instead", DeprecationWarning, stacklevel=2
        )

    def selected_alpn_protocol(self):
        pass

    def cipher(self):
        pass

    def shared_ciphers(self):
        pass

    def compression(self):
        pass

    def pending(self):
        pass

    def do_handshake(self):
        pass

    def unwrap(self):
        pass

    def get_channel_binding(self, cb_type="tls-unique"):
        pass

    def version(self):
        pass

    def verify_client_post_handshake(self):
        pass


class SSLSocket(socket):
    """SSL socket wrapping a socket.socket. Instances returned by SSLContext.wrap_socket()."""

    def __init__(self, *args, **kwargs):
        raise TypeError(
            f"{self.__class__.__name__} does not have a public constructor. "
            f"Instances are returned by SSLContext.wrap_socket()."
        )

    @classmethod
    def _create(
        cls,
        sock,
        server_side=False,
        do_handshake_on_connect=True,
        suppress_ragged_eofs=True,
        server_hostname=None,
        context=None,
        session=None,
    ):
        raise NotImplementedError("SSL is not supported in Pyodide")

    context = property(lambda self: None)
    session = property(lambda self: None)
    session_reused = property(lambda self: None)

    def dup(self):
        raise NotImplementedError("Can't dup() %s instances" % self.__class__.__name__)

    def read(self, len=1024, buffer=None):
        pass

    def write(self, data):
        pass

    def getpeercert(self, binary_form=False):
        pass

    def get_verified_chain(self):
        return []

    def get_unverified_chain(self):
        return []

    def selected_npn_protocol(self):
        warnings.warn(
            "ssl NPN is deprecated, use ALPN instead", DeprecationWarning, stacklevel=2
        )

    def selected_alpn_protocol(self):
        pass

    def cipher(self):
        pass

    def shared_ciphers(self):
        pass

    def compression(self):
        pass

    def send(self, data, flags=0):
        pass

    def sendto(self, data, flags_or_addr, addr=None):
        pass

    def sendmsg(self, *args, **kwargs):
        raise NotImplementedError(
            "sendmsg not allowed on instances of %s" % self.__class__
        )

    def sendall(self, data, flags=0):
        pass

    def sendfile(self, file, offset=0, count=None):
        pass

    def recv(self, buflen=1024, flags=0):
        pass

    def recv_into(self, buffer, nbytes=None, flags=0):
        pass

    def recvfrom(self, buflen=1024, flags=0):
        pass

    def recvfrom_into(self, buffer, nbytes=None, flags=0):
        pass

    def recvmsg(self, *args, **kwargs):
        raise NotImplementedError(
            "recvmsg not allowed on instances of %s" % self.__class__
        )

    def recvmsg_into(self, *args, **kwargs):
        raise NotImplementedError(
            "recvmsg_into not allowed on instances of %s" % self.__class__
        )

    def pending(self):
        pass

    def shutdown(self, how):
        pass

    def unwrap(self):
        pass

    def verify_client_post_handshake(self):
        pass

    def do_handshake(self, block=False):
        pass

    def connect(self, addr):
        pass

    def connect_ex(self, addr):
        pass

    def accept(self):
        pass

    def get_channel_binding(self, cb_type="tls-unique"):
        pass

    def version(self):
        pass


SSLContext.sslsocket_class = SSLSocket
SSLContext.sslobject_class = SSLObject


def cert_time_to_seconds(cert_time):
    """Return the time in seconds since Epoch from a certificate time string."""
    from calendar import timegm
    from time import strptime

    months = (
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    )
    time_format = " %d %H:%M:%S %Y GMT"
    try:
        month_number = months.index(cert_time[:3].title()) + 1
    except ValueError:
        raise ValueError(
            'time data %r does not match format "%%b%s"' % (cert_time, time_format)
        )
    tt = strptime(cert_time[3:], time_format)
    return timegm((tt[0], month_number) + tt[2:6])


PEM_HEADER = "-----BEGIN CERTIFICATE-----"
PEM_FOOTER = "-----END CERTIFICATE-----"


def DER_cert_to_PEM_cert(der_cert_bytes):
    """Convert a certificate from DER format to PEM format."""
    f = str(base64.standard_b64encode(der_cert_bytes), "ASCII", "strict")
    ss = [PEM_HEADER]
    ss += [f[i : i + 64] for i in range(0, len(f), 64)]
    ss.append(PEM_FOOTER + "\n")
    return "\n".join(ss)


def PEM_cert_to_DER_cert(pem_cert_string):
    """Convert a certificate from PEM format to DER format."""
    if not pem_cert_string.startswith(PEM_HEADER):
        raise ValueError("Invalid PEM encoding; must start with %s" % PEM_HEADER)
    if not pem_cert_string.strip().endswith(PEM_FOOTER):
        raise ValueError("Invalid PEM encoding; must end with %s" % PEM_FOOTER)
    d = pem_cert_string.strip()[len(PEM_HEADER) : -len(PEM_FOOTER)]
    return base64.decodebytes(d.encode("ASCII", "strict"))


def get_server_certificate(
    addr,
    ssl_version=PROTOCOL_TLS_CLIENT,
    ca_certs=None,
    timeout=_GLOBAL_DEFAULT_TIMEOUT,
):
    """Retrieve the certificate from the server at the specified address."""
    raise NotImplementedError("SSL is not supported in Pyodide")


def get_protocol_name(protocol_code):
    return _PROTOCOL_NAMES.get(protocol_code, "<unknown>")
