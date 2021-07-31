import sys

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

if PY3:
    text_type = str
    binary_type = bytes
else:
    text_type = unicode
    binary_type = str


def to_bytes(s):
    if isinstance(s, binary_type):
        return s
    return text_type(s).encode("utf-8")


def to_unicode(s):
    if isinstance(s, text_type):
        return s
    return binary_type(s).decode("utf-8")
