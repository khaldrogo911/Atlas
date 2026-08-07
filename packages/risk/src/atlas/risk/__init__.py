"""Risk engine, exposure limits and capital allocation.

Position sizing, per-instrument and portfolio exposure limits, drawdown
controls, correlation caps and the kill switches that halt trading.

Boundary:
    Authoritative and non-bypassable: every trade intent passes through this
    package before it can become an order.

Atlas is recommendation-first, and this package is where that is enforced.
:mod:`atlas.strategy` produces a :class:`~atlas.risk.contracts.TradeIntent` — a
recommendation, not an instruction. Risk evaluates it against the authoritative
account, position and risk state and produces a
:class:`~atlas.risk.contracts.RiskVerdict`. Only an approved intent may
proceed, and :mod:`atlas.execution` is what turns it into an
``OrderRequest``. Risk decides; it does not place.

ATLAS-TASK-0001 established this package as an empty, importable unit with a
declared responsibility. ATLAS-TASK-0011 delivered the first of it: the two
contracts the boundary is stated in. The controls that reach a verdict —
sizing, the exposure and drawdown limits, the correlation cap, the kill
switches — arrive with the tasks that implement them, and each names its own
:class:`~atlas.risk.contracts.RejectionReason`.
"""

from __future__ import annotations

from atlas.risk.contracts import (
    RISK_MODEL_CONFIG,
    RejectionReason,
    RiskVerdict,
    TradeIntent,
    VerdictStatus,
)

__all__ = [
    "RISK_MODEL_CONFIG",
    "RejectionReason",
    "RiskVerdict",
    "TradeIntent",
    "VerdictStatus",
]
