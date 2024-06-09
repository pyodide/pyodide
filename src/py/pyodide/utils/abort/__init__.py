from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from js import AbortSignal

from ...code import run_js

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


_abort_signal_any: Callable[[Iterable[AbortSignal]], AbortSignal] | None = (
    AbortSignal.any
)


def get_abort_signal_any() -> Callable[[Iterable[AbortSignal]], AbortSignal]:
    global _abort_signal_any
    path = Path(__file__).parent / "polyfill.js"
    source = path.read_text() + ";polyfillAbortSignal()"
    _abort_signal_any = run_js(source)
    return _abort_signal_any  # type:ignore[return-value]


def abort_signal_any(signals: Iterable[AbortSignal]) -> AbortSignal:
    return (_abort_signal_any or get_abort_signal_any())(signals)


__all__ = ["abort_signal_any"]
