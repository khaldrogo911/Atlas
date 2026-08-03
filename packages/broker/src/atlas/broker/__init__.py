"""Vendor-neutral broker abstraction.

The :class:`~atlas.broker.adapter.BrokerAdapter` port and the types it speaks.
Concrete venue integrations are adapters behind this port, and nothing above it
knows which one is loaded::

    from atlas.broker import BrokerAdapter, OrderRequest

Boundary:
    Defines the port and its data contracts only. Order sizing, routing and
    risk decisions belong to ``atlas.execution`` and ``atlas.risk``.

The domain vocabulary — ``Order``, ``Position``, ``Tick`` and the rest — lives
in :mod:`atlas.broker.models` and is imported from there. This package exports
the port, its capability protocols, the request types that only the port uses,
and the exception hierarchy every adapter raises, so that the two import paths
say which layer a name belongs to.

See ``README.md`` in this directory for the design rationale.
"""

from __future__ import annotations

from atlas.broker.adapter import BrokerAdapter
from atlas.broker.exceptions import (
    BrokerAuthenticationError,
    BrokerConnectionError,
    BrokerDataUnavailableError,
    BrokerError,
    BrokerInsufficientMarginError,
    BrokerNotConnectedError,
    BrokerOrderNotFoundError,
    BrokerOrderRejectedError,
    BrokerPositionNotFoundError,
    BrokerRequestError,
    BrokerSymbolNotFoundError,
    BrokerTimeoutError,
    BrokerUnsupportedOperationError,
)
from atlas.broker.protocols import (
    SupportsConnection,
    SupportsDiagnostics,
    SupportsMarketData,
    SupportsStreaming,
    SupportsTrading,
)
from atlas.broker.types import (
    UNSET,
    BrokerName,
    BrokerVersion,
    CandleHandler,
    ExecutionID,
    OrderID,
    OrderRequest,
    PositionID,
    ServerName,
    SubscriptionID,
    SymbolName,
    TickHandler,
    Unset,
)

__all__ = [
    "UNSET",
    "BrokerAdapter",
    "BrokerAuthenticationError",
    "BrokerConnectionError",
    "BrokerDataUnavailableError",
    "BrokerError",
    "BrokerInsufficientMarginError",
    "BrokerName",
    "BrokerNotConnectedError",
    "BrokerOrderNotFoundError",
    "BrokerOrderRejectedError",
    "BrokerPositionNotFoundError",
    "BrokerRequestError",
    "BrokerSymbolNotFoundError",
    "BrokerTimeoutError",
    "BrokerUnsupportedOperationError",
    "BrokerVersion",
    "CandleHandler",
    "ExecutionID",
    "OrderID",
    "OrderRequest",
    "PositionID",
    "ServerName",
    "SubscriptionID",
    "SupportsConnection",
    "SupportsDiagnostics",
    "SupportsMarketData",
    "SupportsStreaming",
    "SupportsTrading",
    "SymbolName",
    "TickHandler",
    "Unset",
]
