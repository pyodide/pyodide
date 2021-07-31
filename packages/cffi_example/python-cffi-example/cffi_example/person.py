from ._person import ffi, lib
from .utils import text_type


class Person(object):
    def __init__(self, first_name, last_name, age):
        # Because person_create expects wchar_t we need to guarantee that the
        # first_name and last_name are unicode; cffi will convert
        # unicode <--> wchar_t[], but will throw an error if asked to implictly
        # convert a str/bytes --> wchar_t[].
        if not isinstance(first_name, text_type):
            raise TypeError("first_name must be unicode (got %r)" % (first_name,))
        if not isinstance(last_name, text_type):
            raise TypeError("last_name must be unicode (got %r)" % (last_name,))

        # Because ``person_create`` calls ``strdup`` on the inputs we can
        # safely pass Python byte strings directly into the constructor.  If
        # the constructor expected us to manage the lifecycle of the strings we
        # would need to allocate new char buffers for them, then make sure that
        # those character buffers are not GC'd by storing a reference to them::
        #     first_name = ffi.new("wchar_t[]", first_name)
        #     last_name = ffi.new("wchar_t[]", last_name)
        #     self._gc_keepalive = [first_name, last_name]
        p = lib.person_create(first_name, last_name, age)
        if p == ffi.NULL:
            raise MemoryError("Could not allocate person")

        # ffi.gc returns a copy of the cdata object which will have the
        # destructor (in this case ``person_destroy``) called when the Python
        # object is GC'd:
        # https://cffi.readthedocs.org/en/latest/using.html#ffi-interface
        self._p = ffi.gc(p, lib.person_destroy)

    def get_age(self):
        # Because the ``person_t`` struct is defined in the ``ffi.cdef`` call
        # we can directly access members.
        return self._p.p_age

    def get_full_name(self):
        # ffi.new() creates a managed buffer which will be automatically
        # free()'d when the Python object is GC'd:
        # https://cffi.readthedocs.org/en/latest/using.html#ffi-interface
        buf = ffi.new("wchar_t[]", 101)
        # Note: ``len(buf)`` (101, in this case) is used instead of
        # ``ffi.sizeof(buf)`` (101 * 4 = 404) because person_get_full_name
        # expects the maximum number of characters, not number of bytes.
        lib.person_get_full_name(self._p, buf, len(buf))

        # ``ffi.string`` converts a null-terminated C string to a Python byte
        # array. Note that ``buf`` will be automatically free'd when the Python
        # object is GC'd so we don't need to do anything special there.
        return ffi.string(buf)
