"""Strategy contracts and the strategy engine.

The strategy interface, its lifecycle, registration and the engine that
drives registered strategies against incoming events to produce proposed
trade intents.

Boundary:
    Emits intents, not orders. Nothing here may reach a broker directly, and
    nothing here may bypass ``atlas.risk``.

Atlas is recommendation-first, and this package is where a recommendation comes
from. A :class:`~atlas.strategy.contracts.Strategy` is shown an observation and
answers with a :class:`~atlas.risk.TradeIntent` or with ``None``. What happens
to an intent afterwards is not this package's to assume: :mod:`atlas.risk`
judges it, and only :mod:`atlas.execution` may turn an approved verdict into an
order.

:mod:`atlas.risk` is the one ``atlas`` package a module here imports, and
:mod:`atlas.broker` is deliberately not among them. An intent is *stated* in the
port's primitives, but naming them is the job of whatever constructs one, and
nothing in this package constructs one — the contract names
:class:`~atlas.risk.TradeIntent` in an annotation and stops there. No module
here can obtain a ``BrokerAdapter``, name an ``OrderRequest`` or reach a venue,
and ``tests/unit/strategy/test_strategy_boundary.py`` asserts each of those
separately by walking the AST of every module in the package.

ATLAS-TASK-0001 established this package as an empty, importable unit with a
declared responsibility. ATLAS-TASK-0012 delivered the first of it: the contract
a strategy satisfies. The lifecycle, the registry and the engine that drives
registered strategies against incoming events arrive with the tasks that
implement them.

``ConstantStrategy`` is deliberately not exported here. It is a reference
implementation rather than part of the package's surface, and a caller wanting
one imports it from :mod:`atlas.strategy.reference` — the same reason
``MockBrokerAdapter`` is absent from :mod:`atlas.broker`.
"""

from __future__ import annotations

from atlas.strategy.contracts import Strategy

__all__ = ["Strategy"]
