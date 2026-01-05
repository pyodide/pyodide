# type: ignore
# Stub implementation for Pyodide - imports from _ssl stub module

# Import from stub _ssl module
import _ssl
import os
import sys

from _ssl import OPENSSL_VERSION_NUMBER, OPENSSL_VERSION_INFO, OPENSSL_VERSION, _DEFAULT_CIPHERS
from _ssl import _SSLContext, MemoryBIO, SSLSession
from _ssl import (
    SSLError, SSLZeroReturnError, SSLWantReadError, SSLWantWriteError,
    SSLSyscallError, SSLEOFError, SSLCertVerificationError
    )
from _ssl import txt2obj as _txt2obj, nid2obj as _nid2obj
from _ssl import RAND_status, RAND_add, RAND_bytes
from collections import namedtuple
from enum import Enum as _Enum
from enum import IntEnum as _IntEnum
from enum import IntFlag as _IntFlag
from enum import _simple_enum

CertificateError = SSLCertVerificationError

# Stub protocol definitions
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
    """Content types (record layer)

    See RFC 8446, section B.1
    """

    CHANGE_CIPHER_SPEC = 20
    ALERT = 21
    HANDSHAKE = 22
    APPLICATION_DATA = 23
    # pseudo content types
    HEADER = 0x100
    INNER_CONTENT_TYPE = 0x101


@_simple_enum(_IntEnum)
class _TLSAlertType:
    """Alert types for TLSContentType.ALERT messages

    See RFC 8466, section B.2
    """

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
    """Message types (handshake protocol)

    See RFC 8446, section B.3
    """

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


# Import Windows certificate enumeration functions from _ssl

import base64  # for DER-to-PEM translation
import errno
import socket as _socket
import warnings
from socket import _GLOBAL_DEFAULT_TIMEOUT, create_connection, socket

socket_error = OSError  # keep that public name in module namespace

CHANNEL_BINDING_TYPES = ["tls-unique"]

HAS_NEVER_CHECK_COMMON_NAME = False

# Import additional constants from _ssl
from _ssl import (
    HOSTFLAG_NEVER_CHECK_SUBJECT,
    VERIFY_X509_PARTIAL_CHAIN,
    VERIFY_X509_STRICT,
)

_RESTRICTED_SERVER_CIPHERS = _DEFAULT_CIPHERS


def _dnsname_match(dn, hostname):
    """Matching according to RFC 6125, section 6.4.3

    - Hostnames are compared lower-case.
    - For IDNA, both dn and hostname must be encoded as IDN A-label (ACE).
    - Partial wildcards like 'www*.example.org', multiple wildcards, sole
      wildcard or wildcards in labels other then the left-most label are not
      supported and a CertificateError is raised.
    - A wildcard must match at least one character.
    """
    if not dn:
        return False

    wildcards = dn.count("*")
    # speed up common case w/o wildcards
    if not wildcards:
        return dn.lower() == hostname.lower()

    if wildcards > 1:
        raise CertificateError(f"too many wildcards in certificate DNS name: {dn!r}.")

    dn_leftmost, sep, dn_remainder = dn.partition(".")

    if "*" in dn_remainder:
        # Only match wildcard in leftmost segment.
        raise CertificateError(
            f"wildcard can only be present in the leftmost label: {dn!r}."
        )

    if not sep:
        # no right side
        raise CertificateError(
            f"sole wildcard without additional labels are not support: {dn!r}."
        )

    if dn_leftmost != "*":
        # no partial wildcard matching
        raise CertificateError(
            f"partial wildcards in leftmost label are not supported: {dn!r}."
        )

    hostname_leftmost, sep, hostname_remainder = hostname.partition(".")
    if not hostname_leftmost or not sep:
        # wildcard must match at least one char
        return False
    return dn_remainder.lower() == hostname_remainder.lower()


def _inet_paton(ipname):
    """Try to convert an IP address to packed binary form

    Supports IPv4 addresses on all platforms and IPv6 on platforms with IPv6
    support.
    """
    # inet_aton() also accepts strings like '1', '127.1', some also trailing
    # data like '127.0.0.1 whatever'.
    try:
        addr = _socket.inet_aton(ipname)
    except OSError:
        # not an IPv4 address
        pass
    else:
        if _socket.inet_ntoa(addr) == ipname:
            # only accept injective ipnames
            return addr
        else:
            # refuse for short IPv4 notation and additional trailing data
            raise ValueError(f"{ipname!r} is not a quad-dotted IPv4 address.")

    try:
        return _socket.inet_pton(_socket.AF_INET6, ipname)
    except OSError:
        raise ValueError(f"{ipname!r} is neither an IPv4 nor an IP6 address.")
    except AttributeError:
        # AF_INET6 not available
        pass

    raise ValueError(f"{ipname!r} is not an IPv4 address.")


def _ipaddress_match(cert_ipaddress, host_ip):
    """Exact matching of IP addresses.

    RFC 6125 explicitly doesn't define an algorithm for this
    (section 1.7.2 - "Out of Scope").
    """
    # OpenSSL may add a trailing newline to a subjectAltName's IP address,
    # commonly with IPv6 addresses. Strip off trailing \n.
    ip = _inet_paton(cert_ipaddress.rstrip())
    return ip == host_ip


DefaultVerifyPaths = namedtuple(
    "DefaultVerifyPaths",
    "cafile capath openssl_cafile_env openssl_cafile openssl_capath_env openssl_capath",
)


def get_default_verify_paths():
    """Return paths to default cafile and capath."""
    parts = _ssl.get_default_verify_paths()

    # environment vars shadow paths
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
        # Stub implementation
        return super().__new__(cls, 0, "stub", "stub", oid)

    @classmethod
    def fromnid(cls, nid):
        """Create _ASN1Object from OpenSSL numeric ID"""
        return super().__new__(cls, nid, "stub", "stub", "0.0.0.0")

    @classmethod
    def fromname(cls, name):
        """Create _ASN1Object from short name, long name or OID"""
        return super().__new__(cls, 0, name, name, "0.0.0.0")


class Purpose(_ASN1Object, _Enum):
    """SSLContext purpose flags with X509v3 Extended Key Usage objects"""

    SERVER_AUTH = "1.3.6.1.5.5.7.3.1"
    CLIENT_AUTH = "1.3.6.1.5.5.7.3.2"


class SSLContext:
    """An SSLContext holds various SSL-related configuration options and
    data, such as certificates and possibly a private key."""

    _windows_cert_stores = ("CA", "ROOT")

    sslsocket_class = None  # SSLSocket is assigned later.
    sslobject_class = None  # SSLObject is assigned later.

    def __init__(self, protocol=None, *args, **kwargs):
        if protocol is None:
            warnings.warn(
                "ssl.SSLContext() without protocol argument is deprecated.",
                category=DeprecationWarning,
                stacklevel=2,
            )
            protocol = PROTOCOL_TLS

        # Validate protocol
        if not isinstance(protocol, int):
            raise TypeError("protocol must be an integer")

        # Check for invalid protocol values
        valid_protocols = {
            PROTOCOL_TLS,
            PROTOCOL_TLS_CLIENT,
            PROTOCOL_TLS_SERVER,
            PROTOCOL_TLS.value,
        }
        # Add deprecated protocols if they exist
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
        elif protocol == PROTOCOL_TLS_SERVER:
            self._check_hostname = False
            self._verify_mode = CERT_NONE
        else:
            self._check_hostname = False
            self._verify_mode = CERT_NONE
        self._minimum_version = TLSVersion.TLSv1_2  # sensible default
        self._maximum_version = TLSVersion.TLSv1_3  # sensible default
        self._options = Options.OP_ALL | Options.OP_NO_SSLv2 | Options.OP_NO_SSLv3
        # SSLContext also enables these by default
        self._options |= (
            Options.OP_NO_COMPRESSION
            | Options.OP_CIPHER_SERVER_PREFERENCE
            | Options.OP_SINGLE_DH_USE
            | Options.OP_SINGLE_ECDH_USE
            | Options.OP_ENABLE_MIDDLEBOX_COMPAT
        )
        self._verify_flags = VerifyFlags.VERIFY_DEFAULT
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
        # Validate BIO arguments
        if not isinstance(incoming, MemoryBIO):
            raise TypeError("incoming must be a MemoryBIO instance")
        if not isinstance(outgoing, MemoryBIO):
            raise TypeError("outgoing must be a MemoryBIO instance")

        # Validate server_hostname
        if server_side and server_hostname is not None:
            raise ValueError("server_hostname can only be specified in client mode")

        if not server_side:
            if self.check_hostname and not server_hostname:
                raise ValueError("check_hostname requires server_hostname")
            if server_hostname is not None:
                if not isinstance(server_hostname, str):
                    if isinstance(server_hostname, bytes):
                        server_hostname = server_hostname.decode("ascii")
                    else:
                        raise TypeError("server_hostname must be a string or bytes")
                # Validate hostname format
                if not server_hostname or server_hostname.startswith("."):
                    raise ValueError(
                        "server_hostname cannot be empty or start with a dot"
                    )

        # Create and return a stub SSLObject
        return SSLObject._create(
            incoming=incoming,
            outgoing=outgoing,
            server_side=server_side,
            server_hostname=server_hostname,
            session=session,
            context=self,
        )

    def set_npn_protocols(self, npn_protocols):
        warnings.warn(
            "ssl NPN is deprecated, use ALPN instead", DeprecationWarning, stacklevel=2
        )

    def set_servername_callback(self, server_name_callback):
        if server_name_callback is None:
            self.sni_callback = None
        else:
            if not callable(server_name_callback):
                raise TypeError("not a callable object")
            self.sni_callback = server_name_callback

    def set_alpn_protocols(self, alpn_protocols):
        pass

    def _load_windows_store_certs(self, storename, purpose):
        # Stub - no-op for Pyodide
        pass

    def load_default_certs(self, purpose=Purpose.SERVER_AUTH):
        if not isinstance(purpose, _ASN1Object):
            raise TypeError(purpose)
        # Stub - no-op for Pyodide
        pass

    def load_verify_locations(self, cafile=None, capath=None, cadata=None):
        if cafile is None and capath is None and cadata is None:
            raise TypeError("cafile, capath and cadata cannot be all omitted")

        # Check if file exists when cafile is provided
        if cafile is not None:
            if isinstance(cafile, str):
                if not os.path.exists(cafile):
                    raise OSError(errno.ENOENT, "No such file or directory", cafile)
                # Validate it's a valid PEM file
                try:
                    with open(cafile) as f:
                        content = f.read()
                        if not (
                            "-----BEGIN CERTIFICATE-----" in content
                            and "-----END CERTIFICATE-----" in content
                        ):
                            raise _ssl.SSLError("PEM lib")
                except (UnicodeDecodeError, OSError) as e:
                    if isinstance(e, FileNotFoundError):
                        raise
                    raise _ssl.SSLError("PEM routines") from e

                # Check if this is a CA certificate by looking for CA:TRUE in the content
                # This is a simple heuristic for the stub
                if "CA:TRUE" in content or "Root CA" in content or "CA Cert" in content:
                    self._cert_store["x509_ca"] += 1
                else:
                    self._cert_store["x509"] += 1
            elif isinstance(cafile, bytes):
                if not os.path.exists(cafile.decode()):
                    raise OSError(errno.ENOENT, "No such file or directory", cafile)
                # For bytes, just increment x509
                self._cert_store["x509"] += 1

        if cadata is not None:
            if isinstance(cadata, (str, bytes)):
                if isinstance(cadata, bytes):
                    cadata_str = cadata.decode("ascii", errors="ignore")
                else:
                    cadata_str = cadata

                # Initialize the set for tracking loaded certs if needed
                if not hasattr(self, "_loaded_certs"):
                    self._loaded_certs = set()

                # Split and hash each cert to detect duplicates
                import hashlib

                certs = cadata_str.split("-----BEGIN CERTIFICATE-----")
                new_certs = 0
                for cert in certs[1:]:  # Skip first empty split
                    if "-----END CERTIFICATE-----" in cert:
                        cert_data = (
                            "-----BEGIN CERTIFICATE-----"
                            + cert.split("-----END CERTIFICATE-----")[0]
                            + "-----END CERTIFICATE-----"
                        )
                        cert_hash = hashlib.sha256(cert_data.encode()).hexdigest()
                        if cert_hash not in self._loaded_certs:
                            self._loaded_certs.add(cert_hash)
                            new_certs += 1

                self._cert_store["x509_ca"] += new_certs

    def load_cert_chain(self, certfile, keyfile=None, password=None):
        if certfile is not None:
            if isinstance(certfile, str):
                if not os.path.exists(certfile):
                    raise FileNotFoundError(
                        errno.ENOENT, "No such file or directory", certfile
                    )
                # Validate it's a valid PEM file
                try:
                    with open(certfile) as f:
                        content = f.read()
                        # Empty file or file without proper PEM markers
                        if (
                            not content.strip()
                            or "-----BEGIN CERTIFICATE-----" not in content
                        ):
                            raise _ssl.SSLError("PEM lib")
                except (UnicodeDecodeError, OSError) as e:
                    if isinstance(e, FileNotFoundError):
                        raise
                    raise _ssl.SSLError("PEM lib") from e
            elif isinstance(certfile, bytes):
                if not os.path.exists(certfile.decode()):
                    raise FileNotFoundError(
                        errno.ENOENT, "No such file or directory", certfile
                    )
        # Note: load_cert_chain does NOT add to cert_store, only load_verify_locations does

    def set_default_verify_paths(self):
        # Stub - no-op for Pyodide
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
        """Set SSL options.

        Args:
            value: Integer value with option flags

        Raises:
            TypeError: if value is not an integer
            OverflowError: if value is negative or too large
        """
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("'options' must be an integer")

        # Check for negative values
        if value < 0:
            raise OverflowError("options must be a non-negative integer")

        # Check for values that are too large (greater than unsigned long long max)
        # Using a reasonable upper bound
        if value >= 2**64:
            raise OverflowError("options value is too large")

        self._options = value

    @property
    def hostname_checks_common_name(self):
        if not HAS_NEVER_CHECK_COMMON_NAME:
            # When HAS_NEVER_CHECK_COMMON_NAME is False, always return True (checks common name)
            return True
        ncs = self._host_flags & HOSTFLAG_NEVER_CHECK_SUBJECT
        return ncs != HOSTFLAG_NEVER_CHECK_SUBJECT

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
        """Whether to match the peer cert's hostname in :meth:`SSLSocket.do_handshake`."""
        return self._check_hostname

    @check_hostname.setter
    def check_hostname(self, value):
        """Set whether to match the peer cert's hostname.

        Automatically sets verify_mode to CERT_REQUIRED when check_hostname is True.
        """
        self._check_hostname = bool(value)
        if self._check_hostname and self._verify_mode == CERT_NONE:
            self._verify_mode = CERT_REQUIRED

    @property
    def _msg_callback(self):
        """TLS message callback

        The message callback provides a debugging hook to analyze TLS
        connections. The callback is called for any TLS protocol message
        (header, handshake, alert, and more), but not for application data.
        Due to technical  limitations, the callback can't be used to filter
        traffic or to abort a connection. Any exception raised in the
        callback is delayed until the handshake, read, or write operation
        has been performed.

        def msg_cb(conn, direction, version, content_type, msg_type, data):
            pass

        conn
            :class:`SSLSocket` or :class:`SSLObject` instance
        direction
            ``read`` or ``write``
        version
            :class:`TLSVersion` enum member or int for unknown version. For a
            frame header, it's the header version.
        content_type
            :class:`_TLSContentType` enum member or int for unsupported
            content type.
        msg_type
            Either a :class:`_TLSContentType` enum number for a header
            message, a :class:`_TLSAlertType` enum member for an alert
            message, a :class:`_TLSMessageType` enum member for other
            messages, or int for unsupported message types.
        data
            Raw, decrypted message content as bytes
        """
        return self._msg_callback_inner

    @_msg_callback.setter
    def _msg_callback(self, callback):
        if callback is not None and not hasattr(callback, "__call__"):
            raise TypeError(f"{callback} is not callable.")

        self._msg_callback_inner = callback

    @property
    def verify_mode(self):
        """Get the certificate verification mode.

        Returns one of CERT_NONE, CERT_OPTIONAL, or CERT_REQUIRED.
        """
        return self._verify_mode

    @verify_mode.setter
    def verify_mode(self, value):
        """Set the certificate verification mode.

        Must be one of CERT_NONE, CERT_OPTIONAL, or CERT_REQUIRED.
        """
        if value is None:
            raise TypeError("verify_mode must be specified")

        # Validate the value
        if value not in (CERT_NONE, CERT_OPTIONAL, CERT_REQUIRED):
            raise ValueError("invalid value for verify_mode")

        # Check if check_hostname is True and trying to set verify_mode to CERT_NONE
        if (
            hasattr(self, "_check_hostname")
            and self._check_hostname
            and value == CERT_NONE
        ):
            raise ValueError(
                "Cannot set verify_mode to CERT_NONE when check_hostname is enabled."
            )

        # In the real implementation, this would set SSL_CTX_set_verify with:
        # - CERT_NONE -> SSL_VERIFY_NONE
        # - CERT_OPTIONAL -> SSL_VERIFY_PEER
        # - CERT_REQUIRED -> SSL_VERIFY_PEER | SSL_VERIFY_FAIL_IF_NO_PEER_CERT
        # For our stub, we just store the value
        self._verify_mode = value

    @property
    def verify_flags(self):
        """Get the certificate verification flags.

        Returns a VerifyFlags value.
        """
        return self._verify_flags

    @verify_flags.setter
    def verify_flags(self, value):
        """Set the certificate verification flags.

        Must be a valid VerifyFlags value, not None.
        """
        if value is None:
            raise TypeError("verify_flags must be specified")

        # In the real implementation, this would call SSL_CTX_set_verify with
        # the appropriate OpenSSL verification flags.
        # For our stub, we just store the value
        self._verify_flags = value

    def get_ca_certs(self, binary_form=False):
        # stub
        return []

    def cert_store_stats(self):
        return self._cert_store.copy()

    def set_ciphers(self, ciphers):
        if not isinstance(ciphers, str):
            raise TypeError("ciphers must be a string")

        if not ciphers or ciphers.isspace():
            raise _ssl.SSLError("No cipher can be selected.")

    def get_ciphers(self):
        # Stub
        return []

    def load_dh_params(self, dhfile):
        if dhfile is None:
            raise TypeError("path is None")

        # Check if file exists
        if isinstance(dhfile, str):
            if not os.path.exists(dhfile):
                raise FileNotFoundError(
                    errno.ENOENT, "No such file or directory", dhfile
                )
            # Validate it's actually a DH params file
            try:
                with open(dhfile) as f:
                    content = f.read()
                    # DH params files should have DH PARAMETERS marker
                    if (
                        "BEGIN DH PARAMETERS" not in content
                        and "BEGIN PARAMETERS" not in content
                    ):
                        raise _ssl.SSLError("PEM lib")
            except (UnicodeDecodeError, OSError) as e:
                if isinstance(e, FileNotFoundError):
                    raise
                raise _ssl.SSLError("PEM lib") from e
        elif isinstance(dhfile, bytes):
            if not os.path.exists(dhfile.decode()):
                raise FileNotFoundError(
                    errno.ENOENT, "No such file or directory", dhfile
                )
        # Stub - no actual DH params loading

    def session_stats(self):
        # Stub
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
        """Get the number of TLS 1.3 session tickets."""
        return self._num_tickets

    @num_tickets.setter
    def num_tickets(self, value):
        """Set the number of TLS 1.3 session tickets.

        Args:
            value: Number of tickets (non-negative integer)

        Raises:
            TypeError: if value is None
            ValueError: if value is negative or if setting on CLIENT context
        """
        if value is None:
            raise TypeError("num_tickets must be an integer, not None")

        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("num_tickets must be an integer")

        if value < 0:
            raise ValueError("num_tickets must be a non-negative integer")

        # TLS_CLIENT contexts can only have the default value
        if self.protocol == PROTOCOL_TLS_CLIENT and value != 2:
            raise ValueError("can't set num_tickets for client contexts")

        self._num_tickets = value


def create_default_context(
    purpose=Purpose.SERVER_AUTH, *, cafile=None, capath=None, cadata=None
):
    """Create a SSLContext object with default settings.

    NOTE: The protocol and settings may change anytime without prior
          deprecation. The values represent a fair balance between maximum
          compatibility and security.
    """
    if not isinstance(purpose, _ASN1Object):
        raise TypeError(purpose)

    # SSLContext sets OP_NO_SSLv2, OP_NO_SSLv3, OP_NO_COMPRESSION,
    # OP_CIPHER_SERVER_PREFERENCE, OP_SINGLE_DH_USE and OP_SINGLE_ECDH_USE
    # by default.
    if purpose == Purpose.SERVER_AUTH:
        # verify certs and host name in client mode
        context = SSLContext(PROTOCOL_TLS_CLIENT)
        context.verify_mode = CERT_REQUIRED
        context.check_hostname = True
    elif purpose == Purpose.CLIENT_AUTH:
        context = SSLContext(PROTOCOL_TLS_SERVER)
    else:
        raise ValueError(purpose)

    # `VERIFY_X509_PARTIAL_CHAIN` makes OpenSSL's chain building behave more
    # like RFC 3280 and 5280, which specify that chain building stops with the
    # first trust anchor, even if that anchor is not self-signed.
    #
    # `VERIFY_X509_STRICT` makes OpenSSL more conservative about the
    # certificates it accepts, including "disabling workarounds for
    # some broken certificates."
    context.verify_flags |= VERIFY_X509_PARTIAL_CHAIN | VERIFY_X509_STRICT

    if cafile or capath or cadata:
        context.load_verify_locations(cafile, capath, cadata)
    elif context.verify_mode != CERT_NONE:
        # no explicit cafile, capath or cadata but the verify mode is
        # CERT_OPTIONAL or CERT_REQUIRED. Let's try to load default system
        # root CA certificates for the given purpose. This may fail silently.
        context.load_default_certs(purpose)
    # OpenSSL 1.1.1 keylog file
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
    """Create a SSLContext object for Python stdlib modules

    All Python stdlib modules shall use this function to create SSLContext
    objects in order to keep common settings in one place. The configuration
    is less restrict than create_default_context()'s to increase backward
    compatibility.
    """
    if not isinstance(purpose, _ASN1Object):
        raise TypeError(purpose)

    # SSLContext sets OP_NO_SSLv2, OP_NO_SSLv3, OP_NO_COMPRESSION,
    # OP_CIPHER_SERVER_PREFERENCE, OP_SINGLE_DH_USE and OP_SINGLE_ECDH_USE
    # by default.
    if purpose == Purpose.SERVER_AUTH:
        # verify certs and host name in client mode
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
    if check_hostname:
        context.check_hostname = True

    if keyfile and not certfile:
        raise ValueError("certfile must be specified")
    if certfile or keyfile:
        context.load_cert_chain(certfile, keyfile)

    # load CA root certs
    if cafile or capath or cadata:
        context.load_verify_locations(cafile, capath, cadata)
    elif context.verify_mode != CERT_NONE:
        # no explicit cafile, capath or cadata but the verify mode is
        # CERT_OPTIONAL or CERT_REQUIRED. Let's try to load default system
        # root CA certificates for the given purpose. This may fail silently.
        context.load_default_certs(purpose)
    # OpenSSL 1.1.1 keylog file (stub for Pyodide)
    keylogfile = os.environ.get("SSLKEYLOGFILE")
    if keylogfile and not sys.flags.ignore_environment:
        context.keylog_filename = keylogfile
    return context


# Used by http.client if no context is explicitly passed.
_create_default_https_context = create_default_context


# Backwards compatibility alias, even though it's not a public name.
_create_stdlib_context = _create_unverified_context


class SSLObject:
    """This class implements an interface on top of a low-level SSL object as
    implemented by OpenSSL. This object captures the state of an SSL connection
    but does not provide any network IO itself. IO needs to be performed
    through separate "BIO" objects which are OpenSSL's IO abstraction layer.

    This class does not have a public constructor. Instances are returned by
    ``SSLContext.wrap_bio``. This class is typically used by framework authors
    that want to implement asynchronous IO for SSL through memory buffers.

    When compared to ``SSLSocket``, this object lacks the following features:

     * Any form of network IO, including methods such as ``recv`` and ``send``.
     * The ``do_handshake_on_connect`` and ``suppress_ragged_eofs`` machinery.
    """

    def __init__(self, *args, **kwargs):
        raise TypeError(
            f"{self.__class__.__name__} does not have a public "
            f"constructor. Instances are returned by SSLContext.wrap_bio()."
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
        """Create a stub SSL object instance.

        This factory method creates a minimal SSL object that tracks state
        but does not perform actual SSL operations.
        """
        raise NotImplementedError("SSL is not supported in Pyodide")

    @property
    def context(self):
        """The SSLContext that is currently in use."""
        return self._sslobj.context

    @context.setter
    def context(self, ctx):
        self._sslobj.context = ctx

    @property
    def session(self):
        """The SSLSession for client socket."""
        return self._sslobj.session

    @session.setter
    def session(self, session):
        self._sslobj.session = session

    @property
    def session_reused(self):
        """Was the client session reused during handshake"""
        return self._sslobj.session_reused

    @property
    def server_side(self):
        """Whether this is a server-side socket."""
        return self._sslobj.server_side

    @property
    def server_hostname(self):
        """The currently set server hostname (for SNI), or ``None`` if no
        server hostname is set."""
        return self._sslobj.server_hostname

    def read(self, len=1024, buffer=None):
        """Read up to 'len' bytes from the SSL object and return them.

        If 'buffer' is provided, read into this buffer and return the number of
        bytes read.
        """
        if buffer is not None:
            v = self._sslobj.read(len, buffer)
        else:
            v = self._sslobj.read(len)
        return v

    def write(self, data):
        """Write 'data' to the SSL object and return the number of bytes
        written.

        The 'data' argument must support the buffer interface.
        """
        return self._sslobj.write(data)

    def getpeercert(self, binary_form=False):
        """Returns a formatted version of the data in the certificate provided
        by the other end of the SSL channel.

        Return None if no certificate was provided, {} if a certificate was
        provided, but not validated.
        """
        return self._sslobj.getpeercert(binary_form)

    def get_verified_chain(self):
        """Returns verified certificate chain provided by the other
        end of the SSL channel as a list of DER-encoded bytes.

        If certificate verification was disabled method acts the same as
        ``SSLSocket.get_unverified_chain``.
        """
        return []

    def get_unverified_chain(self):
        """Returns raw certificate chain provided by the other
        end of the SSL channel as a list of DER-encoded bytes.
        """
        return []

    def selected_npn_protocol(self):
        """Return the currently selected NPN protocol as a string, or ``None``
        if a next protocol was not negotiated or if NPN is not supported by one
        of the peers."""
        warnings.warn(
            "ssl NPN is deprecated, use ALPN instead", DeprecationWarning, stacklevel=2
        )
        return None

    def selected_alpn_protocol(self):
        """Return the currently selected ALPN protocol as a string, or ``None``
        if a next protocol was not negotiated or if ALPN is not supported by one
        of the peers."""
        return self._sslobj.selected_alpn_protocol()

    def cipher(self):
        """Return the currently selected cipher as a 3-tuple ``(name,
        ssl_version, secret_bits)``."""
        return self._sslobj.cipher()

    def shared_ciphers(self):
        """Return a list of ciphers shared by the client during the handshake or
        None if this is not a valid server connection.
        """
        return self._sslobj.shared_ciphers()

    def compression(self):
        """Return the current compression algorithm in use, or ``None`` if
        compression was not negotiated or not supported by one of the peers."""
        return self._sslobj.compression()

    def pending(self):
        """Return the number of bytes that can be read immediately."""
        return self._sslobj.pending()

    def do_handshake(self):
        """Start the SSL/TLS handshake."""
        self._sslobj.do_handshake()

    def unwrap(self):
        """Start the SSL shutdown handshake."""
        return self._sslobj.shutdown()

    def get_channel_binding(self, cb_type="tls-unique"):
        """Get channel binding data for current connection.  Raise ValueError
        if the requested `cb_type` is not supported.  Return bytes of the data
        or None if the data is not available (e.g. before the handshake)."""
        return self._sslobj.get_channel_binding(cb_type)

    def version(self):
        """Return a string identifying the protocol version used by the
        current SSL channel."""
        return self._sslobj.version()

    def verify_client_post_handshake(self):
        return self._sslobj.verify_client_post_handshake()


def _sslcopydoc(func):
    """Copy docstring from SSLObject to SSLSocket"""
    func.__doc__ = getattr(SSLObject, func.__name__).__doc__
    return func


class SSLSocket(socket):
    """This class implements a subtype of socket.socket that wraps
    the underlying OS socket in an SSL context when necessary, and
    provides read and write methods over that channel."""

    def __init__(self, *args, **kwargs):
        raise TypeError(
            f"{self.__class__.__name__} does not have a public "
            f"constructor. Instances are returned by "
            f"SSLContext.wrap_socket()."
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

    @property
    @_sslcopydoc
    def context(self):
        return self._context

    @context.setter
    def context(self, ctx):
        self._context = ctx
        self._sslobj.context = ctx

    @property
    @_sslcopydoc
    def session(self):
        if self._sslobj is not None:
            return self._sslobj.session

    @session.setter
    def session(self, session):
        self._session = session
        if self._sslobj is not None:
            self._sslobj.session = session

    @property
    @_sslcopydoc
    def session_reused(self):
        if self._sslobj is not None:
            return self._sslobj.session_reused

    def dup(self):
        raise NotImplementedError("Can't dup() %s instances" % self.__class__.__name__)

    def _checkClosed(self, msg=None):
        # raise an exception here if you wish to check for spurious closes
        pass

    def _check_connected(self):
        if not self._connected:
            # getpeername() will raise ENOTCONN if the socket is really
            # not connected; note that we can be connected even without
            # _connected being set, e.g. if connect() first returned
            # EAGAIN.
            self.getpeername()

    def read(self, len=1024, buffer=None):
        """Read up to LEN bytes and return them.
        Return zero-length string on EOF."""

        self._checkClosed()
        if self._sslobj is None:
            raise ValueError("Read on closed or unwrapped SSL socket.")
        try:
            if buffer is not None:
                return self._sslobj.read(len, buffer)
            else:
                return self._sslobj.read(len)
        except SSLError as x:
            if x.args[0] == SSL_ERROR_EOF and self.suppress_ragged_eofs:
                if buffer is not None:
                    return 0
                else:
                    return b""
            else:
                raise

    def write(self, data):
        """Write DATA to the underlying SSL channel.  Returns
        number of bytes of DATA actually transmitted."""

        self._checkClosed()
        if self._sslobj is None:
            raise ValueError("Write on closed or unwrapped SSL socket.")
        return self._sslobj.write(data)

    @_sslcopydoc
    def getpeercert(self, binary_form=False):
        self._checkClosed()
        self._check_connected()
        return self._sslobj.getpeercert(binary_form)

    @_sslcopydoc
    def get_verified_chain(self):
        return []

    @_sslcopydoc
    def get_unverified_chain(self):
        return []

    @_sslcopydoc
    def selected_npn_protocol(self):
        self._checkClosed()
        warnings.warn(
            "ssl NPN is deprecated, use ALPN instead", DeprecationWarning, stacklevel=2
        )

    @_sslcopydoc
    def selected_alpn_protocol(self):
        self._checkClosed()
        if self._sslobj is None or not HAS_ALPN:
            return None
        else:
            return self._sslobj.selected_alpn_protocol()

    @_sslcopydoc
    def cipher(self):
        self._checkClosed()
        if self._sslobj is None:
            return None
        else:
            return self._sslobj.cipher()

    @_sslcopydoc
    def shared_ciphers(self):
        self._checkClosed()
        if self._sslobj is None:
            return None
        else:
            return self._sslobj.shared_ciphers()

    @_sslcopydoc
    def compression(self):
        self._checkClosed()
        if self._sslobj is None:
            return None
        else:
            return self._sslobj.compression()

    def send(self, data, flags=0):
        self._checkClosed()
        if self._sslobj is not None:
            if flags != 0:
                raise ValueError(
                    "non-zero flags not allowed in calls to send() on %s"
                    % self.__class__
                )
            return self._sslobj.write(data)
        else:
            return super().send(data, flags)

    def sendto(self, data, flags_or_addr, addr=None):
        self._checkClosed()
        if self._sslobj is not None:
            raise ValueError("sendto not allowed on instances of %s" % self.__class__)
        elif addr is None:
            return super().sendto(data, flags_or_addr)
        else:
            return super().sendto(data, flags_or_addr, addr)

    def sendmsg(self, *args, **kwargs):
        # Ensure programs don't send data unencrypted if they try to
        # use this method.
        raise NotImplementedError(
            "sendmsg not allowed on instances of %s" % self.__class__
        )

    def sendall(self, data, flags=0):
        self._checkClosed()
        if self._sslobj is not None:
            if flags != 0:
                raise ValueError(
                    "non-zero flags not allowed in calls to sendall() on %s"
                    % self.__class__
                )
            count = 0
            with memoryview(data) as view, view.cast("B") as byte_view:
                amount = len(byte_view)
                while count < amount:
                    v = self.send(byte_view[count:])
                    count += v
        else:
            return super().sendall(data, flags)

    def sendfile(self, file, offset=0, count=None):
        """Send a file, possibly by using os.sendfile() if this is a
        clear-text socket.  Return the total number of bytes sent.
        """
        if self._sslobj is not None:
            return self._sendfile_use_send(file, offset, count)
        else:
            # os.sendfile() works with plain sockets only
            return super().sendfile(file, offset, count)

    def recv(self, buflen=1024, flags=0):
        self._checkClosed()
        if self._sslobj is not None:
            if flags != 0:
                raise ValueError(
                    "non-zero flags not allowed in calls to recv() on %s"
                    % self.__class__
                )
            return self.read(buflen)
        else:
            return super().recv(buflen, flags)

    def recv_into(self, buffer, nbytes=None, flags=0):
        self._checkClosed()
        if nbytes is None:
            if buffer is not None:
                with memoryview(buffer) as view:
                    nbytes = view.nbytes
                if not nbytes:
                    nbytes = 1024
            else:
                nbytes = 1024
        if self._sslobj is not None:
            if flags != 0:
                raise ValueError(
                    "non-zero flags not allowed in calls to recv_into() on %s"
                    % self.__class__
                )
            return self.read(nbytes, buffer)
        else:
            return super().recv_into(buffer, nbytes, flags)

    def recvfrom(self, buflen=1024, flags=0):
        self._checkClosed()
        if self._sslobj is not None:
            raise ValueError("recvfrom not allowed on instances of %s" % self.__class__)
        else:
            return super().recvfrom(buflen, flags)

    def recvfrom_into(self, buffer, nbytes=None, flags=0):
        self._checkClosed()
        if self._sslobj is not None:
            raise ValueError(
                "recvfrom_into not allowed on instances of %s" % self.__class__
            )
        else:
            return super().recvfrom_into(buffer, nbytes, flags)

    def recvmsg(self, *args, **kwargs):
        raise NotImplementedError(
            "recvmsg not allowed on instances of %s" % self.__class__
        )

    def recvmsg_into(self, *args, **kwargs):
        raise NotImplementedError(
            "recvmsg_into not allowed on instances of %s" % self.__class__
        )

    @_sslcopydoc
    def pending(self):
        self._checkClosed()
        if self._sslobj is not None:
            return self._sslobj.pending()
        else:
            return 0

    def shutdown(self, how):
        self._checkClosed()
        self._sslobj = None
        super().shutdown(how)

    @_sslcopydoc
    def unwrap(self):
        if self._sslobj:
            s = self._sslobj.shutdown()
            self._sslobj = None
            return s
        else:
            raise ValueError("No SSL wrapper around " + str(self))

    @_sslcopydoc
    def verify_client_post_handshake(self):
        if self._sslobj:
            return self._sslobj.verify_client_post_handshake()
        else:
            raise ValueError("No SSL wrapper around " + str(self))

    def _real_close(self):
        self._sslobj = None
        super()._real_close()

    @_sslcopydoc
    def do_handshake(self, block=False):
        self._check_connected()
        timeout = self.gettimeout()
        try:
            if timeout == 0.0 and block:
                self.settimeout(None)
            self._sslobj.do_handshake()
        finally:
            self.settimeout(timeout)

    def _real_connect(self, addr, connect_ex):
        if self.server_side:
            raise ValueError("can't connect in server-side mode")
        # Here we assume that the socket is client-side, and not
        # connected at the time of the call.  We connect it, then wrap it.
        if self._connected or self._sslobj is not None:
            raise ValueError("attempt to connect already-connected SSLSocket!")
        self._sslobj = self.context._wrap_socket(
            self, False, self.server_hostname, owner=self, session=self._session
        )
        try:
            if connect_ex:
                rc = super().connect_ex(addr)
            else:
                rc = None
                super().connect(addr)
            if not rc:
                self._connected = True
                if self.do_handshake_on_connect:
                    self.do_handshake()
            return rc
        except (OSError, ValueError):
            self._sslobj = None
            raise

    def connect(self, addr):
        """Connects to remote ADDR, and then wraps the connection in
        an SSL channel."""
        self._real_connect(addr, False)

    def connect_ex(self, addr):
        """Connects to remote ADDR, and then wraps the connection in
        an SSL channel."""
        return self._real_connect(addr, True)

    def accept(self):
        """Accepts a new connection from a remote client, and returns
        a tuple containing that new connection wrapped with a server-side
        SSL channel, and the address of the remote client."""

        newsock, addr = super().accept()
        newsock = self.context.wrap_socket(
            newsock,
            do_handshake_on_connect=self.do_handshake_on_connect,
            suppress_ragged_eofs=self.suppress_ragged_eofs,
            server_side=True,
        )
        return newsock, addr

    @_sslcopydoc
    def get_channel_binding(self, cb_type="tls-unique"):
        if self._sslobj is not None:
            return self._sslobj.get_channel_binding(cb_type)
        else:
            if cb_type not in CHANNEL_BINDING_TYPES:
                raise ValueError(f"{cb_type} channel binding type not implemented")
            return None

    @_sslcopydoc
    def version(self):
        if self._sslobj is not None:
            return self._sslobj.version()
        else:
            return None


# Python does not support forward declaration of types.
SSLContext.sslsocket_class = SSLSocket
SSLContext.sslobject_class = SSLObject


# some utility functions


def cert_time_to_seconds(cert_time):
    """Return the time in seconds since the Epoch, given the timestring
    representing the "notBefore" or "notAfter" date from a certificate
    in ``"%b %d %H:%M:%S %Y %Z"`` strptime format (C locale).

    "notBefore" or "notAfter" dates must use UTC (RFC 5280).

    Month is one of: Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec
    UTC should be specified as GMT (see ASN1_TIME_print())
    """
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
    time_format = " %d %H:%M:%S %Y GMT"  # NOTE: no month, fixed GMT
    try:
        month_number = months.index(cert_time[:3].title()) + 1
    except ValueError:
        raise ValueError(
            'time data %r does not match format "%%b%s"' % (cert_time, time_format)
        )
    else:
        # found valid month
        tt = strptime(cert_time[3:], time_format)
        # return an integer, the previous mktime()-based implementation
        # returned a float (fractional seconds are always zero here).
        return timegm((tt[0], month_number) + tt[2:6])


PEM_HEADER = "-----BEGIN CERTIFICATE-----"
PEM_FOOTER = "-----END CERTIFICATE-----"


def DER_cert_to_PEM_cert(der_cert_bytes):
    """Takes a certificate in binary DER format and returns the
    PEM version of it as a string."""

    f = str(base64.standard_b64encode(der_cert_bytes), "ASCII", "strict")
    ss = [PEM_HEADER]
    ss += [f[i : i + 64] for i in range(0, len(f), 64)]
    ss.append(PEM_FOOTER + "\n")
    return "\n".join(ss)


def PEM_cert_to_DER_cert(pem_cert_string):
    """Takes a certificate in ASCII PEM format and returns the
    DER-encoded version of it as a byte sequence"""

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
    """Retrieve the certificate from the server at the specified address,
    and return it as a PEM-encoded string.
    If 'ca_certs' is specified, validate the server cert against it.
    If 'ssl_version' is specified, use it in the connection attempt.
    If 'timeout' is specified, use it in the connection attempt.
    """

    host, port = addr
    if ca_certs is not None:
        cert_reqs = CERT_REQUIRED
    else:
        cert_reqs = CERT_NONE
    context = _create_stdlib_context(ssl_version, cert_reqs=cert_reqs, cafile=ca_certs)
    with create_connection(addr, timeout=timeout) as sock:
        with context.wrap_socket(sock, server_hostname=host) as sslsock:
            dercert = sslsock.getpeercert(True)
    return DER_cert_to_PEM_cert(dercert)


def get_protocol_name(protocol_code):
    return _PROTOCOL_NAMES.get(protocol_code, "<unknown>")
