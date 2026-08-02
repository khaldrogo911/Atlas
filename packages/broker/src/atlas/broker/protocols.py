"""Capability protocols: the parts of the port a caller can depend on alone.

:class:`~atlas.broker.adapter.BrokerAdapter` is what an *implementer*
satisfies. These protocols are what a *consumer* asks for. A component that
only reads bars should say so::

    def warm_up(feed: SupportsMarketData, symbol: SymbolName) -> Sequence[Candle]:
        return feed.get_candles(symbol, Timeframe.H1, 200)

That signature cannot place an order, and no test of it needs a venue — a stub
with seven methods satisfies it. Structural typing means nothing has to
inherit from these; :class:`~atlas.broker.adapter.BrokerAdapter` satisfies all
of them by having the methods, and so does anything else that does.

Each method's contract — parameters, exceptions, threading, notes — is written
once, on :class:`~atlas.broker.adapter.BrokerAdapter`. The one-line summaries
here identify a method; they deliberately do not restate its contract, because
two copies of a twenty-line contract diverge. A test asserts that every
signature here is identical to the one on the port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from atlas.broker.types import UNSET

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from atlas.broker.models import (
        Candle,
        Connection,
        Execution,
        LatencyMilliseconds,
        Order,
        Price,
        Symbol,
        Tick,
        Timeframe,
        Timestamp,
        Volume,
    )
    from atlas.broker.types import (
        BrokerVersion,
        CandleHandler,
        OrderID,
        OrderRequest,
        PositionID,
        SubscriptionID,
        SymbolName,
        TickHandler,
        Unset,
    )

__all__ = [
    "SupportsConnection",
    "SupportsDiagnostics",
    "SupportsMarketData",
    "SupportsStreaming",
    "SupportsTrading",
]


@runtime_checkable
class SupportsConnection(Protocol):
    """Establishing, ending and reporting on a venue session."""

    def connect(self) -> Connection:
        """Establish a session with the venue."""

    def disconnect(self) -> None:
        """Close the session and release everything it holds."""

    def reconnect(self) -> Connection:
        """Tear down the session and establish a new one."""

    def is_connected(self) -> bool:
        """Report whether the adapter currently has a usable session."""

    def health(self) -> Connection:
        """Return the full connectivity snapshot."""


@runtime_checkable
class SupportsMarketData(Protocol):
    """Pull access to instruments, quotes and bars.

    Deliberately excludes subscriptions. A replay engine or a REST-only venue
    can serve every method here and stream nothing, and folding streaming in
    would make this protocol unsatisfiable for exactly the sources most worth
    testing against. Streaming is :class:`SupportsStreaming`.
    """

    def get_symbols(self) -> Sequence[Symbol]:
        """List every instrument the account may query or trade."""

    def get_symbol(self, symbol: SymbolName) -> Symbol:
        """Return the contract terms of one instrument."""

    def get_tick(self, symbol: SymbolName) -> Tick:
        """Return the most recent quote for one instrument."""

    def get_ticks(self, symbols: Sequence[SymbolName]) -> Mapping[SymbolName, Tick]:
        """Return the most recent quote for several instruments at once."""

    def get_candle(
        self, symbol: SymbolName, timeframe: Timeframe, *, include_forming: bool = False
    ) -> Candle:
        """Return the most recent bar for one instrument."""

    def get_candles(self, symbol: SymbolName, timeframe: Timeframe, count: int) -> Sequence[Candle]:
        """Return the most recent closed bars for one instrument."""

    def get_historical_data(
        self,
        symbol: SymbolName,
        timeframe: Timeframe,
        start: Timestamp,
        end: Timestamp | None = None,
    ) -> Sequence[Candle]:
        """Return closed bars covering an explicit period."""


@runtime_checkable
class SupportsStreaming(Protocol):
    """Push delivery of quotes and bars."""

    def subscribe_ticks(
        self, symbols: Sequence[SymbolName], handler: TickHandler
    ) -> SubscriptionID:
        """Receive quote updates as the venue publishes them."""

    def unsubscribe_ticks(self, subscription_id: SubscriptionID) -> None:
        """Stop a quote subscription."""

    def subscribe_candles(
        self, symbols: Sequence[SymbolName], timeframe: Timeframe, handler: CandleHandler
    ) -> SubscriptionID:
        """Receive bar updates as the venue publishes them."""

    def unsubscribe_candles(self, subscription_id: SubscriptionID) -> None:
        """Stop a bar subscription."""


@runtime_checkable
class SupportsTrading(Protocol):
    """Placing, amending and unwinding risk at the venue."""

    def place_order(self, request: OrderRequest) -> Order:
        """Submit an order to the venue."""

    def modify_order(
        self,
        order_id: OrderID,
        *,
        price: Price | Unset | None = UNSET,
        stop_price: Price | Unset | None = UNSET,
        stop_loss: Price | Unset | None = UNSET,
        take_profit: Price | Unset | None = UNSET,
        volume: Volume | Unset = UNSET,
    ) -> Order:
        """Amend a working order."""

    def cancel_order(self, order_id: OrderID) -> Order:
        """Cancel a working order."""

    def close_position(self, position_id: PositionID, volume: Volume | None = None) -> Execution:
        """Close an open position, in whole or in part."""


@runtime_checkable
class SupportsDiagnostics(Protocol):
    """Liveness, timing and identity of the venue interface."""

    def ping(self) -> bool:
        """Check whether the venue is answering."""

    def latency(self) -> LatencyMilliseconds:
        """Measure the round-trip time to the venue."""

    def server_time(self) -> Timestamp:
        """Return the venue's current time."""

    def version(self) -> BrokerVersion:
        """Return the identity and build of the venue interface."""
