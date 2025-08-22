"""
Internal utilities for HTTP module.
"""

from typing import Any
from ..ffi import JsException


def _construct_abort_reason(reason: Any) -> JsException | None:
    """Construct an abort reason from a given value."""
    if reason is None:
        return None
    return JsException("AbortError", reason)