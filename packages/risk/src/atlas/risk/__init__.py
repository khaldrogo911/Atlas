"""Risk engine, exposure limits and capital allocation.

Position sizing, per-instrument and portfolio exposure limits, drawdown
controls, correlation caps and the kill switches that halt trading.

Boundary:
    Authoritative and non-bypassable: every trade intent passes through this
    package before it can become an order.

ATLAS-TASK-0001 establishes this package as an empty, importable unit with a
declared responsibility. Its implementation is delivered by a later task.
"""

from __future__ import annotations

__all__: list[str] = []
