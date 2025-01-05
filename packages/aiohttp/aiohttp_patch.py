# mypy: ignore-errors

"""Used in test_aiohttp.py"""

from collections.abc import Iterable
from contextlib import suppress
from typing import Any

from aiohttp import ClientSession, ClientTimeout, InvalidURL, hdrs, payload
from aiohttp.client_reqrep import _merge_ssl_params
from aiohttp.helpers import TimeoutHandle, get_env_proxy_for_url, strip_auth_from_url
from multidict import CIMultiDict, istr
from yarl import URL


class Content:
    __slots__ = ("_jsresp", "_exception")

    def __init__(self, _jsresp):
        self._jsresp = _jsresp
        self._exception = None

    async def read(self):
        if self._exception:
            raise self._exception
        buf = await self._jsresp.arrayBuffer()
        self._jsresp = None
        return buf.to_bytes()

    def exception(self):
        return self._exception

    def set_exception(self, exc: BaseException) -> None:
        self._exception = exc


async def _request(
    self,
    method: str,
    str_or_url,
    *,
    params=None,
    data: Any = None,
    json: Any = None,
    cookies=None,
    headers=None,
    skip_auto_headers: Iterable[str] | None = None,
    auth=None,
    allow_redirects: bool = True,
    max_redirects: int = 10,
    compress: str | None = None,
    chunked: bool | None = None,
    expect100: bool = False,
    raise_for_status=None,
    read_until_eof: bool = True,
    proxy=None,
    proxy_auth=None,
    timeout=None,
    verify_ssl: bool | None = None,
    fingerprint: bytes | None = None,
    ssl_context=None,
    ssl=None,
    proxy_headers=None,
    trace_request_ctx=None,
    read_bufsize: int | None = None,
):
    # NOTE: timeout clamps existing connect and read timeouts.  We cannot
    # set the default to None because we need to detect if the user wants
    # to use the existing timeouts by setting timeout to None.

    if self.closed:
        raise RuntimeError("Session is closed")

    ssl = _merge_ssl_params(ssl, verify_ssl, ssl_context, fingerprint)

    if data is not None and json is not None:
        raise ValueError("data and json parameters can not be used at the same time")
    elif json is not None:
        data = payload.JsonPayload(json, dumps=self._json_serialize)

    history = []
    version = self._version
    params = params or {}

    # Merge with default headers and transform to CIMultiDict
    headers = self._prepare_headers(headers)
    proxy_headers = self._prepare_headers(proxy_headers)

    try:
        url = self._build_url(str_or_url)
    except ValueError as e:
        raise InvalidURL(str_or_url) from e

    skip_headers = set(self._skip_auto_headers)
    if skip_auto_headers is not None:
        for i in skip_auto_headers:
            skip_headers.add(istr(i))

    if proxy is not None:
        try:
            proxy = URL(proxy)
        except ValueError as e:
            raise InvalidURL(proxy) from e

    if timeout is None:
        real_timeout = self._timeout
    else:
        if not isinstance(timeout, ClientTimeout):
            real_timeout = ClientTimeout(total=timeout)  # type: ignore[arg-type]
        else:
            real_timeout = timeout
    # timeout is cumulative for all request operations
    # (request, redirects, responses, data consuming)
    tm = TimeoutHandle(self._loop, real_timeout.total)
    handle = tm.start()

    if read_bufsize is None:
        read_bufsize = self._read_bufsize

    traces = []

    timer = tm.timer()
    try:
        with timer:
            url, auth_from_url = strip_auth_from_url(url)
            if auth and auth_from_url:
                raise ValueError(
                    "Cannot combine AUTH argument with " "credentials encoded in URL"
                )

            if auth is None:
                auth = auth_from_url
            if auth is None:
                auth = self._default_auth
            # It would be confusing if we support explicit
            # Authorization header with auth argument
            if auth is not None and hdrs.AUTHORIZATION in headers:
                raise ValueError(
                    "Cannot combine AUTHORIZATION header "
                    "with AUTH argument or credentials "
                    "encoded in URL"
                )

            all_cookies = self._cookie_jar.filter_cookies(url)

            if proxy is not None:
                proxy = URL(proxy)
            elif self._trust_env:
                with suppress(LookupError):
                    proxy, proxy_auth = get_env_proxy_for_url(url)

            req = self._request_class(
                method,
                url,
                params=params,
                headers=headers,
                skip_auto_headers=skip_headers,
                data=data,
                cookies=all_cookies,
                auth=auth,
                version=version,
                compress=compress,
                chunked=chunked,
                expect100=expect100,
                loop=self._loop,
                response_class=self._response_class,
                proxy=proxy,
                proxy_auth=proxy_auth,
                timer=timer,
                session=self,
                ssl=ssl,
                proxy_headers=proxy_headers,
                traces=traces,
            )

            req.response = resp = req.response_class(
                req.method,
                req.original_url,
                writer=None,
                continue100=req._continue,
                timer=req._timer,
                request_info=req.request_info,
                traces=req._traces,
                loop=req.loop,
                session=req._session,
            )
            from js import Headers, fetch
            from pyodide.ffi import to_js

            body = None
            if req.body:
                body = to_js(req.body._value)
            jsresp = await fetch(
                str(req.url),
                method=req.method,
                headers=Headers.new(headers.items()),
                body=body,
            )
            resp.version = version
            resp.status = jsresp.status
            resp.reason = jsresp.statusText
            # This is not quite correct in handling of repeated headers
            resp._headers = CIMultiDict(jsresp.headers)
            resp._raw_headers = tuple(tuple(e) for e in jsresp.headers)
            resp.content = Content(jsresp)

        # check response status
        if raise_for_status is None:
            raise_for_status = self._raise_for_status

        if raise_for_status is None:
            pass
        elif callable(raise_for_status):
            await raise_for_status(resp)
        elif raise_for_status:
            resp.raise_for_status()

        # register connection
        if handle is not None:
            if resp.connection is not None:
                resp.connection.add_callback(handle.cancel)
            else:
                handle.cancel()

        resp._history = tuple(history)

        for trace in traces:
            await trace.send_request_end(
                method, url.update_query(params), headers, resp
            )
        return resp

    except BaseException as e:
        # cleanup timer
        tm.close()
        if handle:
            handle.cancel()
            handle = None

        for trace in traces:
            await trace.send_request_exception(
                method, url.update_query(params), headers, e
            )
        raise


ClientSession._request = _request
