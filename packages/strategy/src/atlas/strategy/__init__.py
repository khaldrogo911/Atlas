"""Strategy contracts and the strategy engine.

The strategy interface, its lifecycle, registration and the engine that
drives registered strategies against incoming events to produce proposed
trade intents.

Boundary:
    Emits intents, not orders. Nothing here may place, route or price an order,
    and nothing here may bypass ``atlas.risk``.

Atlas is recommendation-first, and this package is where a recommendation comes
from. A :class:`~atlas.strategy.contracts.Strategy` is shown an observation and
answers with a :class:`~atlas.risk.TradeIntent` or with ``None``. What happens
to an intent afterwards is not this package's to assume: :mod:`atlas.risk`
judges it, and only :mod:`atlas.execution` may turn an approved verdict into an
order.

The four names a strategy may take from :mod:`atlas.broker` — ``SymbolName``,
``OrderSide``, ``Price`` and ``Volume`` — are the vocabulary a
:class:`~atlas.risk.TradeIntent` is stated in, and taking them is how a strategy
avoids inventing a second definition of a price. That is a type dependency and
not a call path: no module here can obtain a ``BrokerAdapter``, name an
``OrderRequest`` or reach a venue, and
``tests/unit/strategy/test_strategy_boundary.py`` asserts each of those
separately.

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
