from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from js import AbortSignal


_abort_signal_any: Callable[[Iterable[AbortSignal]], AbortSignal] | None = None


def get_abort_signal_any() -> Callable[[Iterable[AbortSignal]], AbortSignal]:
    from js import AbortSignal

    global _abort_signal_any

    if AbortSignal.any is None:
        from ...code import run_js  # type:ignore[unreachable]

        path = Path(__file__).parent / "polyfill.js"
        source = path.read_text() + ";polyfillAbortSignal()"
        _abort_signal_any = run_js(source)
    else:
        _abort_signal_any = AbortSignal.any
    return _abort_signal_any


def abort_signal_any(signals: Iterable[AbortSignal]) -> AbortSignal:
    return (_abort_signal_any or get_abort_signal_any())(signals)


__all__ = ["abort_signal_any"]
