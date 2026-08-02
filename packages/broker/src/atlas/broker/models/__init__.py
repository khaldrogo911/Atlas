"""Canonical broker domain models.

The vocabulary in which the rest of Atlas talks about accounts, instruments,
quotes, orders, positions and fills. Nothing here knows what a broker is —
these types are the contract that a ``BrokerAdapter`` translates *into*, and
everything above the adapter reads.

Import from the package, not from its modules::

    from atlas.broker.models import Order, OrderSide, OrderType

See ``README.md`` in this directory for the design rationale.
"""

from __future__ import annotations

from atlas.broker.models.account import Account
from atlas.broker.models.candle import Candle
from atlas.broker.models.connection import Connection
from atlas.broker.models.enums import (
    ConnectionState,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    SymbolTradeMode,
    Timeframe,
)
from atlas.broker.models.execution import Execution
from atlas.broker.models.order import Order
from atlas.broker.models.position import Position
from atlas.broker.models.primitives import (
    BROKER_MODEL_CONFIG,
    CurrencyCode,
    Description,
    Digits,
    Identifier,
    LatencyMilliseconds,
    Leverage,
    Money,
    Name,
    NonNegativeMoney,
    Percentage,
    Points,
    Price,
    SymbolCode,
    Timestamp,
    Volume,
    VolumeOrZero,
)
from atlas.broker.models.symbol import Symbol
from atlas.broker.models.tick import Tick

__all__ = [
    "BROKER_MODEL_CONFIG",
    "Account",
    "Candle",
    "Connection",
    "ConnectionState",
    "CurrencyCode",
    "Description",
    "Digits",
    "Execution",
    "Identifier",
    "LatencyMilliseconds",
    "Leverage",
    "Money",
    "Name",
    "NonNegativeMoney",
    "Order",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "Percentage",
    "Points",
    "Position",
    "PositionSide",
    "Price",
    "Symbol",
    "SymbolCode",
    "SymbolTradeMode",
    "Tick",
    "Timeframe",
    "Timestamp",
    "Volume",
    "VolumeOrZero",
]
