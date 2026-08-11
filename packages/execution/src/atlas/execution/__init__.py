"""Order lifecycle and execution management.

Translation of approved trade intents into broker orders, routing, fill
and partial-fill handling, reconciliation against broker state, and
idempotent retry of in-flight instructions.

Boundary:
    Executes only what ``atlas.risk`` has approved. Never sizes a position
    and never overrides a risk verdict.

ATLAS-TASK-0001 established this package as an empty, importable unit with a
declared responsibility. ATLAS-TASK-0014 delivered the first slice of it: the
translation, and only the translation. An approved
:class:`~atlas.risk.RiskVerdict` and an :class:`~atlas.execution.ExecutionPolicy`
become an :class:`~atlas.broker.OrderRequest`; a rejected verdict becomes
nothing.

Nothing here reaches a venue. The request this package produces is received by
no one yet — routing, fills, reconciliation and idempotent retry are the four
responsibilities above that remain untouched, and each needs state, a broker or
both. The layer that owns broker interaction arrives with the task that builds
it. See ADR-0011.
"""

from __future__ import annotations

from atlas.execution.contracts import ExecutionPolicy, build_order_request

__all__ = ["ExecutionPolicy", "build_order_request"]
