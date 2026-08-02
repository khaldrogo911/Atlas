"""Enumerated vocabulary of the broker domain.

Every enumeration is a :class:`~enum.StrEnum` whose value equals its member
name. Two consequences are deliberate:

* JSON encodes the member as ``"MARKET"``, not ``0``. A persisted order or a
  message on the bus stays readable, and reordering members later cannot
  silently reinterpret stored data.
* Validation is exact. ``"market"`` is rejected rather than quietly accepted,
  so an adapter that forgets to canonicalise a broker's own spelling fails at
  the boundary instead of three layers in.

The small set of properties defined here are classifications of the members
themselves — which statuses admit no further transition, how long a bar is.
They encode no policy: whether a degraded session should still be traded, or
whether a stop loss sits on the correct side of an entry, are decisions for
the risk and execution layers.
"""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum, unique
from typing import Final

__all__ = [
    "ConnectionState",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PositionSide",
    "SymbolTradeMode",
    "Timeframe",
]


@unique
class OrderSide(StrEnum):
    """The direction in which an order transacts."""

    BUY = "BUY"
    SELL = "SELL"

    @property
    def opposite(self) -> OrderSide:
        """The side that transacts in the reverse direction."""
        return OrderSide.SELL if self is OrderSide.BUY else OrderSide.BUY


@unique
class OrderType(StrEnum):
    """How an order is presented to the venue."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"

    @property
    def requires_price(self) -> bool:
        """Whether the type is undefined without an explicit price.

        A limit order without a limit, or a stop order without a trigger, is
        not an under-specified order — it is not an order at all.
        """
        return self is not OrderType.MARKET

    @property
    def requires_stop_price(self) -> bool:
        """Whether the type needs a trigger price distinct from its limit."""
        return self is OrderType.STOP_LIMIT


@unique
class OrderStatus(StrEnum):
    """The lifecycle state of an order as last reported by the venue."""

    CREATED = "CREATED"
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

    @property
    def is_terminal(self) -> bool:
        """Whether the order can never change state again."""
        return self in _TERMINAL_ORDER_STATUSES

    @property
    def is_active(self) -> bool:
        """Whether the order can still trade or be amended."""
        return self not in _TERMINAL_ORDER_STATUSES


#: Defined after the class because its members must exist first.
_TERMINAL_ORDER_STATUSES: Final = frozenset(
    {
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
    }
)


@unique
class PositionSide(StrEnum):
    """The direction of net exposure held in an instrument."""

    LONG = "LONG"
    SHORT = "SHORT"

    @property
    def opposite(self) -> PositionSide:
        """The direction of the opposing exposure."""
        return PositionSide.SHORT if self is PositionSide.LONG else PositionSide.LONG


@unique
class ConnectionState(StrEnum):
    """The lifecycle state of a session with a broker."""

    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    DEGRADED = "DEGRADED"
    DISCONNECTING = "DISCONNECTING"

    @property
    def is_usable(self) -> bool:
        """Whether a request issued in this state can reach the venue.

        ``DEGRADED`` counts as usable: the session is up, but some quality of
        service — latency, quote continuity — is not being met. Acting on that
        is a policy decision and is not made here.

        ``DISCONNECTING`` does not count. A teardown in progress may still hold
        a live socket, but nothing new should be sent through it.
        """
        return self in _USABLE_CONNECTION_STATES

    @property
    def is_transitional(self) -> bool:
        """Whether the state is expected to change without any further request."""
        return self in _TRANSITIONAL_CONNECTION_STATES


_USABLE_CONNECTION_STATES: Final = frozenset(
    {
        ConnectionState.CONNECTED,
        ConnectionState.DEGRADED,
    }
)

_TRANSITIONAL_CONNECTION_STATES: Final = frozenset(
    {
        ConnectionState.CONNECTING,
        ConnectionState.RECONNECTING,
        ConnectionState.DISCONNECTING,
    }
)


@unique
class SymbolTradeMode(StrEnum):
    """What the venue currently permits on an instrument.

    Venues restrict instruments for reasons that have nothing to do with
    Atlas — a session boundary, an expiring contract, a risk decision by the
    broker. Modelling this as an enumeration rather than a bare string means a
    close-only instrument cannot be mistaken for a tradeable one by a typo.
    """

    DISABLED = "DISABLED"
    CLOSE_ONLY = "CLOSE_ONLY"
    LONG_ONLY = "LONG_ONLY"
    SHORT_ONLY = "SHORT_ONLY"
    FULL = "FULL"


@unique
class Timeframe(StrEnum):
    """The aggregation period of a candle."""

    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"

    @property
    def minutes(self) -> int:
        """The nominal length of one bar, in whole minutes.

        Nominal, not elapsed: a daily bar spans 1440 minutes by definition,
        but a real ``D1`` bar may cover a weekend or a session that a daylight
        saving transition shortened by an hour.
        """
        return _TIMEFRAME_MINUTES[self]

    @property
    def duration(self) -> timedelta:
        """The nominal length of one bar.

        See :attr:`minutes` for what "nominal" excludes.
        """
        return timedelta(minutes=self.minutes)


_TIMEFRAME_MINUTES: Final = {
    Timeframe.M1: 1,
    Timeframe.M5: 5,
    Timeframe.M15: 15,
    Timeframe.M30: 30,
    Timeframe.H1: 60,
    Timeframe.H4: 240,
    Timeframe.D1: 1440,
}
