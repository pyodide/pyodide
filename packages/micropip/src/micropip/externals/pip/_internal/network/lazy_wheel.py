"""Adapted from
https://github.com/pypa/pip/blob/main/src/pip/_internal/network/lazy_wheel.py"""

from bisect import bisect_left, bisect_right
from ..utils.wheel import pkg_resources_distribution_for_wheel
from tempfile import NamedTemporaryFile
from typing import List, Optional, Any, Iterator, Tuple
from contextlib import contextmanager
from zipfile import BadZipfile, ZipFile
from pyodide import to_js, IN_BROWSER
import asyncio

if IN_BROWSER:
    from js import fetch as jsfetch, Object

    def fetch(url, headers={}):
        return jsfetch(
            url, to_js({"headers": headers}, dict_converter=Object.fromEntries)
        )


else:
    from urllib.request import urlopen, Request

    async def fetch(url, headers={}):
        fd = urlopen(Request(url, headers=headers))
        fd.statusText = fd.reason

        async def arrayBuffer():
            class Temp:
                def to_py():
                    return fd.read()

            return Temp

        fd.arrayBuffer = arrayBuffer
        return fd


CONTENT_CHUNK_SIZE = 10 * 1024


class HTTPError(IOError):
    """An HTTP error occurred."""


async def dist_from_wheel_url(name, wheel_info):
    """Return a pkg_resources.Distribution from the given wheel URL.

    This uses HTTP range requests to only fetch the potion of the wheel
    containing metadata, just enough for the object to be constructed.
    If such requests are not supported, HTTPRangeRequestUnsupported
    is raised.
    """
    async with LazyZipOverHTTP(wheel_info["url"], wheel_info["size"]) as wheel:
        # For read-only ZIP files, ZipFile only needs methods read,
        # seek, seekable and tell, not the whole IO protocol.
        while True:
            try:
                zip_file = ZipFile(wheel)  # type: ignore
                result = pkg_resources_distribution_for_wheel(
                    zip_file, name, wheel.name
                )
                break
            except Exception:
                if wheel.coroutines:
                    # Load regions of wheel that were requested then try again.
                    await wheel.load_ranges()
                    continue
                raise

        # After context manager exit, wheel.name
        # is an invalid file by intention.
        return result


def raise_unless_request_succeeded(response):
    http_error_msg = ""

    if 400 <= response.status < 500:
        http_error_msg = "%s Client Error: %s for url: %s" % (
            response.status,
            response.statusText,
            response.url,
        )

    elif 500 <= response.status < 600:
        http_error_msg = "%s Server Error: %s for url: %s" % (
            response.status,
            response.statusText,
            response.url,
        )

    if http_error_msg:
        raise HTTPError(http_error_msg, response=response)


class LazyZipOverHTTP:
    """File-like object mapped to a ZIP file over HTTP.

    This uses HTTP range requests to lazily fetch the file's content,
    which is supposed to be fed to ZipFile.  If such requests are not
    supported by the server, raise HTTPRangeRequestUnsupported
    during initialization.
    """

    def __init__(self, url, size=None, chunk_size=CONTENT_CHUNK_SIZE):
        self._url, self._chunk_size = url, chunk_size
        self._file = NamedTemporaryFile()
        self._left = []  # type: List[int]
        self._right = []  # type: List[int]
        self._length = size
        self.coroutines = []
        self._lock = asyncio.Lock()

    @property
    def mode(self):
        # type: () -> str
        """Opening mode, which is always rb."""
        return "rb"

    @property
    def name(self):
        # type: () -> str
        """Path to the underlying file."""
        return self._file.name

    def seekable(self):
        # type: () -> bool
        """Return whether random access is supported, which is True."""
        return True

    def close(self):
        # type: () -> None
        """Close the file."""
        self._file.close()

    @property
    def closed(self):
        # type: () -> bool
        """Whether the file is closed."""
        return self._file.closed

    def read(self, size=-1):
        # type: (int) -> bytes
        """Read up to size bytes from the object and return them.

        As a convenience, if size is unspecified or -1,
        all bytes until EOF are returned.  Fewer than
        size bytes may be returned if EOF is reached.
        """
        download_size = max(size, self._chunk_size)
        start, length = self.tell(), self._length
        stop = length if size < 0 else min(start + download_size, length)
        start = max(0, stop - download_size)
        return self._file.read(size)

    def readable(self):
        # type: () -> bool
        """Return whether the file is readable, which is True."""
        return True

    def seek(self, offset, whence=0):
        # type: (int, int) -> int
        """Change stream position and return the new absolute position.

        Seek to offset relative position indicated by whence:
        * 0: Start of stream (the default).  pos should be >= 0;
        * 1: Current position - pos may be negative;
        * 2: End of stream - pos usually negative.
        """
        return self._file.seek(offset, whence)

    def tell(self):
        # type: () -> int
        """Return the current possition."""
        return self._file.tell()

    def truncate(self, size=None):
        # type: (Optional[int]) -> int
        """Resize the stream to the given size in bytes.

        If size is unspecified resize to the current position.
        The current stream position isn't changed.

        Return the new file size.
        """
        return self._file.truncate(size)

    def writable(self):
        # type: () -> bool
        """Return False."""
        return False

    async def __aenter__(self):
        # type: () -> LazyZipOverHTTP
        if self._length is None:
            self.resp = await fetch(self._url)
            self._length = int(self.resp.headers.get("content-length"))
        self.truncate(self._length)
        await self._check_zip()
        self._file.__enter__()
        return self

    async def __aexit__(self, *exc):
        # type: (*Any) -> Optional[bool]
        return self._file.__exit__(*exc)

    @contextmanager
    def _stay(self):
        # type: ()-> Iterator[None]
        """Return a context manager keeping the position.

        At the end of the block, seek back to original position.
        """
        pos = self.tell()
        try:
            yield
        finally:
            self.seek(pos)

    async def _check_zip(self):
        # type: () -> None
        """Check and download until the file is a valid ZIP."""
        end = self._length - 1
        for start in reversed(range(0, end, self._chunk_size)):
            self._download(start, end)
            await self.load_ranges()
            with self._stay():
                try:
                    # For read-only ZIP files, ZipFile only needs
                    # methods read, seek, seekable and tell.
                    ZipFile(self)  # type: ignore
                except BadZipfile:
                    pass
                else:
                    break

    async def _stream_response(self, start, end):
        """Return HTTP response to a range request from start to end."""
        headers = {}
        headers["Range"] = f"bytes={start}-{end}"
        return await fetch(self._url, headers=headers)

    def _merge(self, start, end, left, right):
        # type: (int, int, int, int) -> Iterator[Tuple[int, int]]
        """Return an iterator of intervals to be fetched.

        Args:
            start (int): Start of needed interval
            end (int): End of needed interval
            left (int): Index of first overlapping downloaded data
            right (int): Index after last overlapping downloaded data
        """
        lslice, rslice = self._left[left:right], self._right[left:right]
        i = start = min([start] + lslice[:1])
        end = max([end] + rslice[-1:])
        for j, k in zip(lslice, rslice):
            if j > i:
                yield i, j - 1
            i = k + 1
        if i <= end:
            yield i, end
        self._left[left:right], self._right[left:right] = [start], [end]

    def _download(self, start, end):
        # type: (int, int) -> None
        """Download bytes from start to end inclusively."""
        with self._stay():
            left = bisect_left(self._right, start)
            right = bisect_right(self._left, end)
            for start, end in self._merge(start, end, left, right):
                self.coroutines.append(self._load_range(start, end))

    async def _load_range(self, start, end):
        print("requesting range", start, end)
        response = await self._stream_response(start, end)
        raise_unless_request_succeeded(response)
        async with self._lock:
            self.seek(start)
            self._file.write((await response.arrayBuffer()).to_py())

    async def load_ranges(self):
        await asyncio.gather(self.coroutines)
