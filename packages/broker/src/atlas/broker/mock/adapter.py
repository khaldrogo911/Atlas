"""A complete, deterministic implementation of the broker port.

:class:`MockBrokerAdapter` implements all thirty-one methods of
:class:`~atlas.broker.adapter.BrokerAdapter` against
:class:`~atlas.broker.mock.venue.MockVenue`, an in-memory venue a test drives
directly. It exists for two reasons, and the second is the load-bearing one.

The obvious reason is that tests need something to hold. The broker README
forbids mocking the port, because a mock agrees with whatever the test asserts
— including the wrong thing — and a suite built on one passes on the day the
adapter's real behaviour changes underneath it. This class is a real
implementation bound by the same contract tests as the MetaTrader 5 adapter, so
a test that passes against it has been checked against the contract rather than
against itself.

The less obvious reason is that a port with one implementation is not a port.
Every decision in :mod:`atlas.broker.adapter` could have been an accident of
MetaTrader 5 until something else satisfied it. This does, and the places where
it satisfies the contract *better* than the terminal are where that shows:
``server_time`` returns the venue's clock, ``subscribe_ticks`` pushes, all four
trading methods trade, and ``get_historical_data`` can actually tell "the
period contains no trading" apart from "history does not reach back that far"
— four things the MT5 adapter refuses or approximates. Seven methods that
``NotImplementedError`` there work here, which is the evidence the port was
designed against a contract rather than around a vendor.

Division of labour
------------------
The venue holds state and does what a broker does. This class holds session
state — connected or not, last latency, last heartbeat — and does what an
*adapter* does: check the session, resolve an instrument code, validate an
argument, and decide which
:class:`~atlas.broker.exceptions.BrokerError` a venue condition amounts to.
Nothing here stores an order or a quote, so a test asserting through
``adapter.venue`` and a test asserting through the port's read methods are two
independent readings and can disagree.

What this adapter will not simulate
-----------------------------------
It fills a market order at the quote a test published, and nothing else happens
on its own. A resting order does not fill because a price reached it, a
position is not revalued because a quote moved, and the account does not change
when a trade opens. Each of those needs a rule — which side of the spread, what
a gap does, how profit converts into the deposit currency — that this package
would have to invent, and inventing it is how a mock quietly becomes the
authority on behaviour nobody chose. ``README.md`` in this directory records
every boundary and the reasoning behind it; ADR-0006 records the decision.

Attached stop-loss and take-profit levels are refused outright with
:class:`~atlas.broker.exceptions.BrokerUnsupportedOperationError`, because
:class:`~atlas.broker.models.Position` has nowhere to report them: accepting one
would make it invisible for exactly as long as the position is open, which is
the silent no-op the port's README forbids.

Threading
---------
The session is synchronised, by :class:`~atlas.broker.base.BaseBrokerAdapter`
and not here. ``connect``, ``disconnect`` and ``reconnect`` are that class's
methods; this one supplies :meth:`MockBrokerAdapter._connect`,
:meth:`MockBrokerAdapter._disconnect` and :meth:`MockBrokerAdapter._reconnect`,
which run with the session lock already held. No lock is written in this module,
and none should be: two adapters needing the same guarantee is the evidence it
belongs in one place. The contract is in that class's docstring and in ADR-0007.

The venue is a different matter and is *not* synchronised. It has no lock and
mints identifiers with a non-atomic read-modify-write, so one
:class:`~atlas.broker.mock.venue.MockVenue` driven from two threads — whether
through two adapters or one — is outside the guarantee above. It is a test
double for a remote server, and a remote server is not something this process
could lock either; a test that wants concurrency drives one adapter per venue.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from pydantic import ValidationError

from atlas.broker.base import BaseBrokerAdapter
from atlas.broker.exceptions import (
    BrokerDataUnavailableError,
    BrokerInsufficientMarginError,
    BrokerNotConnectedError,
    BrokerOrderNotFoundError,
    BrokerOrderRejectedError,
    BrokerPositionNotFoundError,
    BrokerSymbolNotFoundError,
    BrokerUnsupportedOperationError,
)
from atlas.broker.mock.venue import VENUE, MockVenue
from atlas.broker.models import (
    ConnectionState,
    OrderSide,
    OrderType,
    PositionSide,
    SymbolTradeMode,
)
from atlas.broker.types import UNSET, BrokerVersion

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from atlas.broker.models import (
        Account,
        Candle,
        Connection,
        Execution,
        LatencyMilliseconds,
        Money,
        NonNegativeMoney,
        Order,
        Position,
        Price,
        Symbol,
        Tick,
        Timeframe,
        Timestamp,
        Volume,
    )
    from atlas.broker.types import (
        BrokerName,
        CandleHandler,
        OrderID,
        OrderRequest,
        PositionID,
        ServerName,
        SubscriptionID,
        SymbolName,
        TickHandler,
        Unset,
    )

__all__ = ["MOCK_VERSION", "MockBrokerAdapter"]

#: The interface version this adapter reports.
#:
#: Its own, not Atlas's. It changes when the observable behaviour of this
#: adapter changes, which is what a caller gating on a version actually wants to
#: know.
MOCK_VERSION: Final = "1.0"


def _permits(mode: SymbolTradeMode, side: OrderSide) -> bool:
    """Report whether an instrument's trade mode allows opening in one direction.

    Args:
        mode: What the venue currently permits on the instrument.
        side: Direction of the order.

    Returns:
        ``True`` if an opening order in that direction would be accepted.
        ``CLOSE_ONLY`` and ``DISABLED`` both answer ``False``: neither opens
        anything, and the difference between them only matters to
        :meth:`MockBrokerAdapter.close_position`.
    """
    if mode is SymbolTradeMode.FULL:
        return True
    if mode is SymbolTradeMode.LONG_ONLY:
        return side is OrderSide.BUY
    if mode is SymbolTradeMode.SHORT_ONLY:
        return side is OrderSide.SELL
    return False


class MockBrokerAdapter(BaseBrokerAdapter):
    """The port, implemented against an in-memory venue.

    Args:
        venue: The venue to trade against. A fresh
            :class:`~atlas.broker.mock.venue.MockVenue` is created when none is
            given, which is the single-adapter case. Pass one explicitly to
            share a venue between two adapters — the arrangement that shows
            subscriptions and sessions are per-adapter while orders and
            positions are not.

    Notes:
        Starts disconnected. Every method except the five the port forbids from
        raising refuses with
        :class:`~atlas.broker.exceptions.BrokerNotConnectedError` until
        :meth:`connect` is called, because a caller that forgot to connect
        should find out here rather than against a live venue.
    """

    def __init__(self, venue: MockVenue | None = None) -> None:
        """Bind an adapter to a venue.

        Args:
            venue: The venue to trade against, or ``None`` for a fresh one.
        """
        super().__init__()
        self._venue = venue if venue is not None else MockVenue()
        self._state = ConnectionState.DISCONNECTED

    @property
    def venue(self) -> MockVenue:
        """The venue this adapter trades against.

        Exposed so a test can arrange market data and assert on the outcome
        without going through the port. Reading the result of ``place_order``
        with ``get_positions`` checks the adapter against itself; reading it
        with ``adapter.venue.positions()`` does not.
        """
        return self._venue

    # --- Session state the base assembles its snapshot from ---------------------

    @property
    def _session_state(self) -> ConnectionState:
        """The adapter's own lifecycle state.

        Returns:
            The state, which this adapter holds itself: there is no session
            object below it to ask.
        """
        return self._state

    @property
    def _session_broker(self) -> BrokerName:
        """Who the venue says is at the far end.

        Returns:
            The brokerage on the venue's account, so that renaming the venue in
            a fixture changes what ``health`` reports too.
        """
        return self._venue.account.broker

    @property
    def _session_server(self) -> ServerName:
        """Which server the venue's account belongs to.

        Returns:
            The server on the venue's account, read for the same reason as
            :attr:`_session_broker`.
        """
        return self._venue.account.server

    # --- Internals ------------------------------------------------------------

    def _require_session(self, operation: str) -> None:
        """Refuse an operation that needs a session when there is none.

        Args:
            operation: The port method being attempted, for the message.

        Raises:
            BrokerNotConnectedError: If no usable session is established.
        """
        if not self._state.is_usable:
            msg = f"{operation} needs a session; the adapter is {self._state}"
            raise BrokerNotConnectedError(msg, venue=VENUE)

    def _guard(self, operation: str) -> None:
        """Run the two checks every venue-facing method starts with.

        Args:
            operation: The port method being attempted.

        Raises:
            BrokerNotConnectedError: If no usable session is established.
            BrokerError: Whatever the venue has been told to raise here.

        Notes:
            The session check runs first, and a scheduled failure is left on the
            queue when it fires. A test that schedules a timeout and forgets to
            connect should see the missing session — the fault it actually has —
            rather than the timeout it was expecting, and should still find its
            timeout waiting once it connects.
        """
        self._require_session(operation)
        failure = self._venue.take_failure(operation)
        if failure is not None:
            raise failure

    def _establish(self, operation: str) -> Connection:
        """Bring the session up, or fail the way the venue was told to.

        Args:
            operation: Which port method is establishing it.

        Returns:
            The resulting connection state.

        Raises:
            BrokerError: Whatever the venue has been told to raise here.

        Notes:
            Shared by :meth:`_connect` and :meth:`_reconnect` so that the two
            behave identically, but keyed by ``operation`` so that each consumes
            only its own scheduled failure — a test making a connection fail
            must not accidentally make the recovery fail too.

            Reached only from the base class's lifecycle methods, so the session
            lock is held throughout and ``self._state`` needs no further
            synchronisation.
        """
        failure = self._venue.take_failure(operation)
        if failure is not None:
            self._state = ConnectionState.DISCONNECTED
            raise failure

        self._state = ConnectionState.CONNECTED
        self._record_heartbeat(self._venue.now())
        return self._connection()

    def _resolve_symbol(self, symbol: SymbolName) -> Symbol:
        """Look up an instrument, insisting the venue offers it.

        Args:
            symbol: Instrument code, in any case.

        Returns:
            The instrument's specification.

        Raises:
            BrokerSymbolNotFoundError: If the venue does not offer it.
        """
        found = self._venue.symbol(symbol)
        if found is None:
            msg = f"{VENUE} does not offer {symbol!r}"
            raise BrokerSymbolNotFoundError(msg, symbol=symbol, venue=VENUE)
        return found

    def _quote(self, info: Symbol) -> Tick:
        """Return the venue's last quote for an instrument, insisting there is one.

        Args:
            info: The instrument.

        Returns:
            The latest quote.

        Raises:
            BrokerDataUnavailableError: If no quote has been published.
        """
        tick = self._venue.quote(info.symbol)
        if tick is None:
            msg = f"{VENUE} has published no quote for {info.symbol!r}"
            raise BrokerDataUnavailableError(msg, venue=VENUE)
        return tick

    def _market_price(self, info: Symbol, side: OrderSide) -> Price:
        """Return the side of the spread an order in one direction would meet.

        Args:
            info: The instrument.
            side: Direction of the order.

        Returns:
            The ask for a buy, the bid for a sell.

        Raises:
            BrokerDataUnavailableError: If no quote has been published.
        """
        tick = self._quote(info)
        return tick.ask if side is OrderSide.BUY else tick.bid

    def _margin_for(self, info: Symbol, volume: Volume, price: Price) -> NonNegativeMoney:
        """Compute the margin a position of this size would take.

        Args:
            info: The instrument.
            volume: Size, in lots.
            price: Price to evaluate at.

        Returns:
            ``volume * contract_size * price / leverage``, which is never
            negative because none of the four can be.

        Notes:
            Expressed in the instrument's quote currency, and returned without
            conversion. This venue's instruments are assumed to be quoted in the
            account currency, and that assumption is stated here rather than
            hidden: converting would need a rate this venue has no way to know,
            and picking one would put an invented exchange rate inside a number
            a sizing layer divides by.
        """
        return volume * info.contract_size * price / self._venue.account.leverage

    def _require_tradeable(self, info: Symbol, side: OrderSide) -> None:
        """Refuse an opening order the venue would not accept.

        Args:
            info: The instrument.
            side: Direction of the order.

        Raises:
            BrokerOrderRejectedError: If the instrument's trade mode does not
                permit opening in that direction, or the account is not
                permitted to trade.
        """
        if not _permits(info.trade_mode, side):
            msg = f"{info.symbol} is {info.trade_mode} and will not accept a {side} order"
            raise BrokerOrderRejectedError(msg, reason=str(info.trade_mode), venue=VENUE)
        if not self._venue.account.trade_allowed:
            msg = f"the account {self._venue.account.account_id} is not permitted to trade"
            raise BrokerOrderRejectedError(
                msg, reason="trading is disabled on the account", venue=VENUE
            )

    def _require_valid_volume(self, info: Symbol, volume: Volume) -> None:
        """Refuse a size outside the instrument's bounds or off its step.

        Args:
            info: The instrument.
            volume: Size, in lots.

        Raises:
            BrokerOrderRejectedError: If the size is below the minimum, above
                the maximum, or not a whole multiple of the step.
        """
        if volume < info.min_volume or volume > info.max_volume:
            msg = (
                f"{volume} is outside the volume bounds for {info.symbol}: "
                f"{info.min_volume} to {info.max_volume}"
            )
            raise BrokerOrderRejectedError(msg, reason="volume out of range", venue=VENUE)
        if volume % info.volume_step != 0:
            msg = f"{volume} is not a multiple of the {info.symbol} volume step {info.volume_step}"
            raise BrokerOrderRejectedError(msg, reason="volume off step", venue=VENUE)

    @staticmethod
    def _require_no_attached_protection(
        stop_loss: Price | None, take_profit: Price | None, operation: str
    ) -> None:
        """Refuse an attached stop or target.

        Args:
            stop_loss: The requested protective stop, if any.
            take_profit: The requested profit target, if any.
            operation: The port method being attempted.

        Raises:
            BrokerUnsupportedOperationError: If either level is set.

        Notes:
            This venue does not hold protective levels, and refusing is the only
            honest answer available. :class:`~atlas.broker.models.Position` has
            no field for a stop, so an accepted one would be invisible for
            exactly as long as the position was open, and nothing here triggers
            on price, so it would never fire either. A caller would have
            protection that does not exist and no way to discover that. The port
            is explicit that a venue which cannot do something raises rather
            than silently no-ops.
        """
        attached = [
            name
            for name, value in (("stop_loss", stop_loss), ("take_profit", take_profit))
            if value is not None
        ]
        if attached:
            msg = (
                f"{VENUE} does not hold attached protective levels, so "
                f"{' and '.join(attached)} cannot be honoured; manage the exit with "
                "close_position instead"
            )
            raise BrokerUnsupportedOperationError(msg, operation=operation, venue=VENUE)

    def _working_order(self, order_id: OrderID) -> Order:
        """Look up an order that can still be acted on.

        Args:
            order_id: The ticket.

        Returns:
            The order, which is guaranteed to be in an active state.

        Raises:
            BrokerOrderNotFoundError: If the venue has never seen the ticket.
            BrokerOrderRejectedError: If the order has already reached a
                terminal state. The port is explicit that this is the answer
                for an order that finished before the request arrived.
        """
        order = self._venue.order(order_id)
        if order is None:
            msg = f"{VENUE} holds no order {order_id!r}"
            raise BrokerOrderNotFoundError(msg, order_id=order_id, venue=VENUE)
        if order.status.is_terminal:
            msg = f"order {order_id!r} is {order.status} and can no longer be changed"
            raise BrokerOrderRejectedError(msg, reason=f"order is {order.status}", venue=VENUE)
        return order

    def _positions_for(self, symbol: SymbolName | None) -> Sequence[Position]:
        """Return open positions, optionally for one instrument.

        Args:
            symbol: Restrict to this instrument, or ``None`` for all of them.

        Returns:
            The matching open positions, oldest first.

        Raises:
            BrokerSymbolNotFoundError: If ``symbol`` is given and not offered.

        Notes:
            The shared body of :meth:`get_positions` and
            :meth:`get_open_positions`, so the port's requirement that the two
            agree holds by construction rather than by two implementations
            being kept in step.
        """
        positions = self._venue.positions()
        if symbol is None:
            return list(positions)
        code = self._resolve_symbol(symbol).symbol
        return [position for position in positions if position.symbol == code]

    @staticmethod
    def _require_aware(value: datetime, name: str) -> datetime:
        """Reject a naive datetime and normalise an aware one to UTC.

        Args:
            value: The datetime supplied by the caller.
            name: Parameter name, for the message.

        Returns:
            The same instant, in UTC.

        Raises:
            ValueError: If the datetime carries no offset. A naive bound cannot
                be placed on a timeline, and guessing a zone for it would
                silently shift every result by the guess.
        """
        if value.utcoffset() is None:
            msg = f"{name} must be timezone aware; got the naive value {value!r}"
            raise ValueError(msg)
        return value.astimezone(UTC)

    # --- Lifecycle ------------------------------------------------------------

    def _connect(self) -> Connection:
        """Establish a session with the venue.

        Returns:
            The resulting connection state, ``CONNECTED`` on success.

        Raises:
            BrokerError: Whatever a test scheduled against ``connect``. Nothing
                else: there is no network here, so an unscheduled connect always
                succeeds.

        Notes:
            Calling ``connect`` while already connected returns the current
            state without touching anything, as the port requires — including
            without consuming a scheduled failure, since a call that is
            contractually not an error must not become one. That is also what
            makes the second of two concurrent connects harmless: it waits for
            the session lock, finds a session, and returns it.
        """
        if self._state.is_usable:
            return self._connection()
        return self._establish("connect")

    def _disconnect(self) -> None:
        """Close the session and release everything it holds.

        Returns:
            Nothing.

        Notes:
            Never raises, as the port requires, and is safe to call on a session
            that was never opened.

            This adapter's subscriptions are cancelled; another adapter sharing
            the same venue keeps its own. Orders and positions are untouched:
            they belong to the venue, and disconnecting is not an instruction to
            flatten.

            The latency and heartbeat readings are cleared first, because they
            described a session that no longer exists and reporting them
            afterwards would date a dead connection — and clearing them before
            the state moves means a concurrent ``health`` cannot catch the pair
            in between.

            Cancelling the subscriptions runs under the session lock, and
            :meth:`~atlas.broker.mock.venue.MockVenue.close_subscriptions`
            invokes no handler, so no user code runs while the lock is held.
        """
        self._clear_session_readings()
        self._venue.close_subscriptions(self)
        self._state = ConnectionState.DISCONNECTED

    def _reconnect(self) -> Connection:
        """Tear down the session and establish a new one.

        Returns:
            The connection state after the attempt.

        Raises:
            BrokerError: Whatever a test scheduled against ``reconnect``.

        Notes:
            Subscriptions do not survive, as the port requires, and they are
            dropped before the attempt — so a reconnect that fails leaves no
            handles behind either. Exactly one attempt is made; backoff is a
            caller's policy.

            Composed from the public :meth:`disconnect`, which re-enters the
            session lock this method already holds.
        """
        self.disconnect()
        return self._establish("reconnect")

    # --- Market data ----------------------------------------------------------

    def get_symbols(self) -> Sequence[Symbol]:
        """List every instrument the venue offers.

        Returns:
            The registered instruments, ordered by code. Empty until a test
            registers one.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerError: Whatever a test scheduled against ``get_symbols``.
        """
        self._guard("get_symbols")
        return list(self._venue.symbols())

    def get_symbol(self, symbol: SymbolName) -> Symbol:
        """Return the contract terms of one instrument.

        Args:
            symbol: Instrument code. Matching is case-insensitive.

        Returns:
            The instrument's specification.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the venue does not offer it.
            BrokerError: Whatever a test scheduled against ``get_symbol``.
        """
        self._guard("get_symbol")
        return self._resolve_symbol(symbol)

    def get_tick(self, symbol: SymbolName) -> Tick:
        """Return the most recent quote for one instrument.

        Args:
            symbol: Instrument code.

        Returns:
            The last quote published for it.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the venue does not offer it.
            BrokerDataUnavailableError: If no quote has been published.
            BrokerError: Whatever a test scheduled against ``get_tick``.

        Notes:
            The quote is exactly what was published and is as old as the venue
            clock says. Nothing here refreshes it, which makes staleness
            something a test can construct on purpose.
        """
        self._guard("get_tick")
        return self._quote(self._resolve_symbol(symbol))

    def get_ticks(self, symbols: Sequence[SymbolName]) -> Mapping[SymbolName, Tick]:
        """Return the most recent quote for several instruments at once.

        Args:
            symbols: Instrument codes to quote.

        Returns:
            A mapping from each code as the caller spelled it to its latest
            quote. An instrument with no quote is absent rather than present
            with a null.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If any code is not offered.
            BrokerError: Whatever a test scheduled against ``get_ticks``.

        Notes:
            Genuinely atomic here, which is the strongest form the port allows:
            the venue's clock cannot advance during the loop, so every quote in
            the mapping is from the same instant. Every instrument is resolved
            before any quote is read, so an unknown code fails the whole call
            rather than half of it.

            Asking for nothing returns nothing, rather than raising. Unlike a
            subscription to no instruments, a one-shot request for no quotes is
            not a mistake that hides later — it answers immediately, and the
            answer is empty.
        """
        self._guard("get_ticks")
        resolved = {code: self._resolve_symbol(code) for code in symbols}
        quotes: dict[SymbolName, Tick] = {}
        for code, info in resolved.items():
            tick = self._venue.quote(info.symbol)
            if tick is not None:
                quotes[code] = tick
        return quotes

    def get_candle(
        self, symbol: SymbolName, timeframe: Timeframe, *, include_forming: bool = False
    ) -> Candle:
        """Return the most recent bar for one instrument.

        Args:
            symbol: Instrument code.
            timeframe: Bar length.
            include_forming: If ``True``, return the newest bar of any kind. If
                ``False``, the default, return the newest closed one.

        Returns:
            The requested bar. Its ``is_closed`` flag states which kind it is,
            in both cases — asking for the forming bar when the venue holds only
            closed ones returns a closed bar that says so, rather than failing.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the venue does not offer it.
            BrokerDataUnavailableError: If the venue holds no bar of the kind
                asked for.
            BrokerError: Whatever a test scheduled against ``get_candle``.
        """
        self._guard("get_candle")
        info = self._resolve_symbol(symbol)
        series = self._venue.candles(info.symbol, timeframe)
        if include_forming and series:
            return series[-1]

        closed = [bar for bar in series if bar.is_closed]
        if not closed:
            msg = f"{VENUE} holds no closed {timeframe} bar for {info.symbol!r}"
            raise BrokerDataUnavailableError(msg, venue=VENUE)
        return closed[-1]

    def get_candles(self, symbol: SymbolName, timeframe: Timeframe, count: int) -> Sequence[Candle]:
        """Return the most recent closed bars for one instrument.

        Args:
            symbol: Instrument code.
            timeframe: Bar length.
            count: How many bars to return. Must be at least 1.

        Returns:
            Up to ``count`` closed bars, oldest first. The forming bar is never
            included.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the venue does not offer it.
            BrokerDataUnavailableError: If the venue holds no closed bars for it.
            BrokerError: Whatever a test scheduled against ``get_candles``.
            ValueError: If ``count`` is less than 1.

        Notes:
            ``count`` is checked before the session is, matching the MetaTrader
            5 adapter: an argument that could never be valid is a caller's bug
            regardless of whether a venue was reachable, and reporting the
            missing session first would hide it until the connection worked.
        """
        if count < 1:
            msg = f"count must be at least 1; got {count}"
            raise ValueError(msg)

        self._guard("get_candles")
        info = self._resolve_symbol(symbol)
        closed = [bar for bar in self._venue.candles(info.symbol, timeframe) if bar.is_closed]
        if not closed:
            msg = f"{VENUE} holds no closed {timeframe} bars for {info.symbol!r}"
            raise BrokerDataUnavailableError(msg, venue=VENUE)
        return closed[-count:]

    def get_historical_data(
        self,
        symbol: SymbolName,
        timeframe: Timeframe,
        start: Timestamp,
        end: Timestamp | None = None,
    ) -> Sequence[Candle]:
        """Return closed bars covering an explicit period.

        Args:
            symbol: Instrument code.
            timeframe: Bar length.
            start: Inclusive start of the period. Must be timezone aware.
            end: Exclusive end of the period. Must be timezone aware. Defaults
                to the venue's current time.

        Returns:
            Closed bars whose open time falls in ``[start, end)``, oldest first.
            Empty when the period contains no bars but the history covers it.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the venue does not offer it.
            BrokerDataUnavailableError: If the venue's history does not reach
                back to ``start``.
            BrokerError: Whatever a test scheduled against
                ``get_historical_data``.
            ValueError: If either bound is naive, or ``end`` is not after
                ``start``.

        Notes:
            This adapter can tell the two empty answers apart, and the
            MetaTrader 5 one cannot. A period containing no trading and a period
            before the history begins look identical to a terminal that returns
            an empty array for both, so that adapter returns empty for both and
            says so. Here the venue knows precisely which bars it holds, so
            "you asked before my history starts" is raised and "nothing traded
            then" is an empty sequence. The port distinguishes them; it took a
            second implementation to show the distinction was implementable.
        """
        lower = self._require_aware(start, "start")
        upper = self._venue.now() if end is None else self._require_aware(end, "end")
        if upper <= lower:
            msg = f"end must be after start; got start={lower!r} and end={upper!r}"
            raise ValueError(msg)

        self._guard("get_historical_data")
        info = self._resolve_symbol(symbol)
        closed = [bar for bar in self._venue.candles(info.symbol, timeframe) if bar.is_closed]
        if not closed or closed[0].open_time > lower:
            msg = (
                f"{VENUE} holds no {timeframe} history for {info.symbol!r} reaching "
                f"back to {lower.isoformat()}"
            )
            raise BrokerDataUnavailableError(msg, venue=VENUE)
        return [bar for bar in closed if lower <= bar.open_time < upper]

    def subscribe_ticks(
        self, symbols: Sequence[SymbolName], handler: TickHandler
    ) -> SubscriptionID:
        """Receive quote updates as the venue publishes them.

        Args:
            symbols: Instrument codes to stream. Must not be empty.
            handler: Called once per update, with the quote.

        Returns:
            A handle identifying this subscription.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If any code is not offered.
            BrokerError: Whatever a test scheduled against ``subscribe_ticks``.
            ValueError: If ``symbols`` is empty. A subscription that can never
                fire is indistinguishable from a market that never moves, which
                is precisely the silent failure the port forbids.

        Notes:
            Delivery is synchronous, on whichever thread calls
            :meth:`~atlas.broker.mock.venue.MockVenue.publish_tick`. The port
            permits a handler to be called on a thread the caller does not own,
            and this is the deterministic end of that licence: the handler has
            run by the time ``publish_tick`` returns, so a test needs no waiting
            and no polling.

            An exception from the handler does not kill the subscription, as the
            port requires. It is recorded on
            :attr:`~atlas.broker.mock.venue.MockVenue.handler_failures` rather
            than discarded, so a stream that is delivering into a handler that
            throws every time is still visible as such.
        """
        self._guard("subscribe_ticks")
        codes = self._resolved_codes(symbols, "subscribe_ticks")
        return self._venue.open_tick_subscription(self, codes, handler)

    def unsubscribe_ticks(self, subscription_id: SubscriptionID) -> None:
        """Stop a quote subscription.

        Args:
            subscription_id: Handle returned by :meth:`subscribe_ticks`.

        Returns:
            Nothing.

        Notes:
            Never raises, as the port requires — not for an unknown handle, not
            for one already cancelled, not for one belonging to another adapter,
            and not on a disconnected session. A cleanup path cannot always know
            what is still live.
        """
        self._venue.close_subscription(self, subscription_id)

    def subscribe_candles(
        self, symbols: Sequence[SymbolName], timeframe: Timeframe, handler: CandleHandler
    ) -> SubscriptionID:
        """Receive bar updates as the venue publishes them.

        Args:
            symbols: Instrument codes to stream. Must not be empty.
            timeframe: Bar length.
            handler: Called once per update, with the bar.

        Returns:
            A handle identifying this subscription.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If any code is not offered.
            BrokerError: Whatever a test scheduled against
                ``subscribe_candles``.
            ValueError: If ``symbols`` is empty.

        Notes:
            Forming and closed bars are both delivered, and only bars of the
            subscribed length are. The threading and failure rules of
            :meth:`subscribe_ticks` apply unchanged.
        """
        self._guard("subscribe_candles")
        codes = self._resolved_codes(symbols, "subscribe_candles")
        return self._venue.open_candle_subscription(self, codes, timeframe, handler)

    def unsubscribe_candles(self, subscription_id: SubscriptionID) -> None:
        """Stop a bar subscription.

        Args:
            subscription_id: Handle returned by :meth:`subscribe_candles`.

        Returns:
            Nothing.

        Notes:
            Behaves exactly as :meth:`unsubscribe_ticks`, for bars.
        """
        self._venue.close_subscription(self, subscription_id)

    def _resolved_codes(
        self, symbols: Sequence[SymbolName], operation: str
    ) -> tuple[SymbolName, ...]:
        """Resolve every code in a subscription request.

        Args:
            symbols: The codes the caller asked for.
            operation: The port method being attempted, for the message.

        Returns:
            The venue's canonical code for each, in the order given.

        Raises:
            BrokerSymbolNotFoundError: If any code is not offered.
            ValueError: If the sequence is empty.
        """
        if not symbols:
            msg = f"{operation} needs at least one symbol; a subscription to none can never fire"
            raise ValueError(msg)
        return tuple(self._resolve_symbol(code).symbol for code in symbols)

    # --- Trading --------------------------------------------------------------

    def place_order(self, request: OrderRequest) -> Order:
        """Submit an order to the venue.

        Args:
            request: What to place.

        Returns:
            The order as the venue now holds it. A ``MARKET`` order comes back
            ``FILLED`` with a position open against it; every other type comes
            back ``PENDING``.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the instrument is not offered.
            BrokerUnsupportedOperationError: If the request carries a
                ``stop_loss`` or a ``take_profit``. This venue holds neither.
            BrokerOrderRejectedError: If the instrument's trade mode forbids the
                direction, the account may not trade, the volume is outside the
                instrument's bounds or off its step, or a ``MARKET`` order was
                placed with no quote to fill against.
            BrokerInsufficientMarginError: If the account's free margin does not
                cover a ``MARKET`` order.
            BrokerError: Whatever a test scheduled against ``place_order``.

        Notes:
            A pending order rests until it is cancelled or a test fills it with
            :meth:`~atlas.broker.mock.venue.MockVenue.fill`. Price movement
            never triggers it, because deciding whether a limit is reached needs
            a fill policy — touch or cross, filled at the limit or at the
            market, what a gap does — that belongs to a backtest engine. The
            order stays visible in :meth:`get_orders` throughout, so this is a
            refusal to guess rather than a silent no-op.

            Only ``MARKET`` orders are margin-checked, and for the same reason:
            a resting order's fill is a test's instruction rather than a market
            event, so there is no moment at which this venue could decide the
            account had run out.
        """
        self._guard("place_order")
        info = self._resolve_symbol(request.symbol)
        self._require_no_attached_protection(request.stop_loss, request.take_profit, "place_order")
        self._require_tradeable(info, request.side)
        self._require_valid_volume(info, request.volume)

        if request.type is not OrderType.MARKET:
            return self._venue.submit(request)

        tick = self._venue.quote(info.symbol)
        if tick is None:
            msg = f"{VENUE} has published no quote for {info.symbol!r} to fill a market order at"
            raise BrokerOrderRejectedError(msg, reason="no quote", venue=VENUE)

        fill_price = tick.ask if request.side is OrderSide.BUY else tick.bid
        required = self._margin_for(info, request.volume, fill_price)
        available = self._venue.account.free_margin
        if required > available:
            msg = (
                f"{request.volume} of {info.symbol} needs {required} margin and the "
                f"account has {available} free"
            )
            raise BrokerInsufficientMarginError(
                msg, required=required, available=available, venue=VENUE
            )

        order = self._venue.submit(request, price=fill_price)
        self._venue.fill(order.order_id, fill_price)
        return self._venue.require_order(order.order_id)

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
        """Amend a working order.

        Args:
            order_id: Ticket of the order to amend.
            price: New working price. ``None`` clears it; ``UNSET`` leaves it.
            stop_price: New trigger price. ``None`` clears it; ``UNSET`` leaves
                it.
            stop_loss: Must be ``UNSET`` or ``None``. See below.
            take_profit: Must be ``UNSET`` or ``None``. See below.
            volume: New quantity. ``UNSET`` leaves it.

        Returns:
            The order as the venue holds it afterwards, restamped with the
            venue's current time.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerOrderNotFoundError: If the ticket is unknown.
            BrokerUnsupportedOperationError: If ``stop_loss`` or ``take_profit``
                is set to a price. This venue holds neither, for the reason
                given on :meth:`place_order`.
            BrokerOrderRejectedError: If the order has already reached a
                terminal state, or the amendment would produce an order the
                domain model rejects — a ``LIMIT`` with its price cleared, a
                volume of zero.
            BrokerError: Whatever a test scheduled against ``modify_order``.

        Notes:
            Setting either protective level to ``None`` is accepted and does
            nothing, which is not a special case: ``None`` means "remove", and
            there is never one of these to remove. Only setting one to a price
            is refused.
        """
        self._guard("modify_order")
        order = self._working_order(order_id)
        self._require_no_attached_protection(
            None if stop_loss is UNSET else stop_loss,
            None if take_profit is UNSET else take_profit,
            "modify_order",
        )

        updates: dict[str, object] = {}
        if price is not UNSET:
            updates["price"] = price
        if stop_price is not UNSET:
            updates["stop_price"] = stop_price
        if volume is not UNSET:
            updates["volume"] = volume

        try:
            return self._venue.amend(order.order_id, updates)
        except ValidationError as invalid:
            msg = f"the amendment to order {order_id!r} would not produce a valid order: {invalid}"
            raise BrokerOrderRejectedError(
                msg, reason="the amendment is not a well-formed order", venue=VENUE
            ) from invalid

    def cancel_order(self, order_id: OrderID) -> Order:
        """Cancel a working order.

        Args:
            order_id: Ticket of the order to cancel.

        Returns:
            The order, ``CANCELLED``.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerOrderNotFoundError: If the ticket is unknown.
            BrokerOrderRejectedError: If the order has already reached a
                terminal state — at a real venue, almost always because it
                filled first.
            BrokerError: Whatever a test scheduled against ``cancel_order``.

        Notes:
            Cancels the order and nothing else. A position the order already
            produced stays open; use :meth:`close_position` for that.
        """
        self._guard("cancel_order")
        return self._venue.cancel(self._working_order(order_id).order_id)

    def close_position(self, position_id: PositionID, volume: Volume | None = None) -> Execution:
        """Close an open position, in whole or in part.

        Args:
            position_id: Ticket of the position to close.
            volume: How much to close, in lots. Defaults to the whole position.

        Returns:
            The closing execution, at the bid for a long position and the ask
            for a short one. Commission and swap are zero, because this venue
            charges neither.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerPositionNotFoundError: If the ticket is unknown or the
                position is already closed.
            BrokerSymbolNotFoundError: If the venue no longer offers the
                instrument the position is held in.
            BrokerOrderRejectedError: If the instrument is disabled, the account
                may not trade, or there is no quote to close against.
            BrokerError: Whatever a test scheduled against ``close_position``.
            ValueError: If ``volume`` exceeds the position's open size.

        Notes:
            ``CLOSE_ONLY`` closes. That is the whole point of the mode, and
            collapsing it into a refusal would stop a risk layer from flattening
            a position it must exit.

            A partial close leaves the remainder open under the same ticket at
            the same entry price. It does not realise anything: this venue books
            no profit, so what is left is the same position in smaller size.
        """
        self._guard("close_position")
        position = self._venue.position(position_id)
        if position is None:
            msg = f"{VENUE} holds no open position {position_id!r}"
            raise BrokerPositionNotFoundError(msg, position_id=position_id, venue=VENUE)
        if volume is not None and volume > position.volume:
            msg = (
                f"cannot close {volume} of position {position_id!r}, which holds "
                f"{position.volume}"
            )
            raise ValueError(msg)

        info = self._resolve_symbol(position.symbol)
        if info.trade_mode is SymbolTradeMode.DISABLED:
            msg = f"{info.symbol} is disabled and will not accept a closing order"
            raise BrokerOrderRejectedError(msg, reason=str(info.trade_mode), venue=VENUE)
        if not self._venue.account.trade_allowed:
            msg = f"the account {self._venue.account.account_id} is not permitted to trade"
            raise BrokerOrderRejectedError(
                msg, reason="trading is disabled on the account", venue=VENUE
            )

        tick = self._venue.quote(info.symbol)
        if tick is None:
            msg = f"{VENUE} has published no quote for {info.symbol!r} to close against"
            raise BrokerOrderRejectedError(msg, reason="no quote", venue=VENUE)

        price = tick.bid if position.side is PositionSide.LONG else tick.ask
        return self._venue.close(position_id, price, volume)

    # --- Account --------------------------------------------------------------

    def get_account(self) -> Account:
        """Return the current state of the trading account.

        Returns:
            The account exactly as the venue holds it.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerError: Whatever a test scheduled against ``get_account``.

        Notes:
            Reported, never recomputed — and here that is literal. Trading
            against this venue does not move the balance, the equity or the
            margin, because deriving them needs a contract size, a conversion
            rate and a rounding rule this venue would have to invent. An account
            that must change during a test is changed with
            :meth:`~atlas.broker.mock.venue.MockVenue.set_account`.
        """
        self._guard("get_account")
        return self._venue.account

    def get_positions(self, symbol: SymbolName | None = None) -> Sequence[Position]:
        """Return open positions, optionally for one instrument.

        Args:
            symbol: Restrict to this instrument. Defaults to all instruments.

        Returns:
            The matching open positions, oldest first. Empty when flat.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If ``symbol`` is given and not offered.
            BrokerError: Whatever a test scheduled against ``get_positions``.

        Notes:
            One position per fill, never netted. Two buys of the same instrument
            are two positions, which is the hedging convention; netting them
            would change what the account holds.
        """
        self._guard("get_positions")
        return self._positions_for(symbol)

    def get_orders(self, symbol: SymbolName | None = None) -> Sequence[Order]:
        """Return orders still working at the venue.

        Args:
            symbol: Restrict to this instrument. Defaults to all instruments.

        Returns:
            Orders whose status is active, oldest first. Filled and cancelled
            orders are history and are not returned — read them from
            :meth:`~atlas.broker.mock.venue.MockVenue.orders` instead.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If ``symbol`` is given and not offered.
            BrokerError: Whatever a test scheduled against ``get_orders``.
        """
        self._guard("get_orders")
        code = None if symbol is None else self._resolve_symbol(symbol).symbol
        return [
            order
            for order in self._venue.orders()
            if order.status.is_active and (code is None or order.symbol == code)
        ]

    def get_open_positions(self) -> Sequence[Position]:
        """Return every open position.

        Returns:
            All open positions, oldest first.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerError: Whatever a test scheduled against
                ``get_open_positions``.

        Notes:
            Shares its body with :meth:`get_positions`, so the port's
            requirement that this return what ``get_positions()`` returns with
            no argument holds by construction. It keeps its own operation name
            for fault injection, so a test can fail one without failing the
            other.
        """
        self._guard("get_open_positions")
        return self._positions_for(None)

    # --- Risk -----------------------------------------------------------------

    def margin_required(
        self, symbol: SymbolName, side: OrderSide, volume: Volume, price: Price | None = None
    ) -> NonNegativeMoney:
        """Return the margin the venue would take to open a position.

        Args:
            symbol: Instrument to be traded.
            side: Direction of the hypothetical position.
            volume: Size, in lots.
            price: Price to evaluate at. Defaults to the side of the spread the
                order would meet — the ask to buy, the bid to sell.

        Returns:
            ``volume * contract_size * price / leverage``, never negative.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the instrument is not offered.
            BrokerDataUnavailableError: If ``price`` was omitted and no quote
                has been published to evaluate against. Documented here beyond
                the port's list because it is a real condition of this venue;
                the MetaTrader 5 adapter documents the same one.
            BrokerError: Whatever a test scheduled against ``margin_required``.

        Notes:
            A flat formula, and ``side`` does not enter it. That is this venue's
            rule rather than a simplification of somebody else's: netting,
            hedged-margin credits and leverage tiers are real and vary by venue,
            so this one states plainly that it applies none of them. A test that
            needs asymmetric margin is testing the venue's rules, and the venue
            to test them against is the real one.

            The result is in the instrument's quote currency and is not
            converted; see the note on the private helper for why.
        """
        self._guard("margin_required")
        info = self._resolve_symbol(symbol)
        evaluated = self._market_price(info, side) if price is None else price
        return self._margin_for(info, volume, evaluated)

    def margin_available(self) -> Money:
        """Return the margin currently free for new positions.

        Returns:
            The account's free margin, signed: an account past its maintenance
            requirement reports a negative value rather than zero.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerError: Whatever a test scheduled against ``margin_available``.

        Notes:
            Reads the same field :meth:`get_account` reports, so the two cannot
            disagree about the same number.
        """
        self._guard("margin_available")
        return self._venue.account.free_margin

    def can_trade(self, symbol: SymbolName) -> bool:
        """Report whether the venue would currently accept an order.

        Args:
            symbol: Instrument to check.

        Returns:
            ``True`` if the instrument is not disabled and the account is
            permitted to trade.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the instrument is not offered.
            BrokerError: Whatever a test scheduled against ``can_trade``.

        Notes:
            ``CLOSE_ONLY`` answers ``True``, because the venue will accept an
            order — a closing one. A caller that needs the reason reads
            ``trade_mode`` and ``trade_allowed``, as the port directs.

            Venue permission only. It does not check margin, and it says nothing
            about whether :meth:`place_order` will succeed: an instrument in
            ``LONG_ONLY`` answers ``True`` here and still refuses a sell.
        """
        self._guard("can_trade")
        info = self._resolve_symbol(symbol)
        return info.trade_mode is not SymbolTradeMode.DISABLED and (
            self._venue.account.trade_allowed
        )

    # --- Diagnostics ----------------------------------------------------------

    def ping(self) -> bool:
        """Check whether the venue is answering.

        Returns:
            ``True`` if there is a session and no failure was scheduled.

        Notes:
            Never raises, as the port requires. A failure scheduled against
            ``ping`` is consumed and reported as ``False`` rather than thrown,
            which is how a supervision loop's "the venue went away" branch gets
            exercised without a mock.

            A successful ping records a heartbeat, so :meth:`health` afterwards
            shows the venue was reached and when.
        """
        if not self._state.is_usable:
            return False
        if self._venue.take_failure("ping") is not None:
            return False
        self._record_heartbeat(self._venue.now())
        return True

    def latency(self) -> LatencyMilliseconds:
        """Measure the round-trip time to the venue.

        Returns:
            Whatever
            :attr:`~atlas.broker.mock.venue.MockVenue.latency_ms` is set to.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerError: Whatever a test scheduled against ``latency``.

        Notes:
            A dial rather than a measurement, and honestly so: there is no round
            trip here to time, and timing the function call would produce a
            reassuring sub-microsecond number that describes nothing. Set the
            venue's ``latency_ms`` to exercise a caller's threshold.

            The reading is cached, so :meth:`health` reports it without another
            call, and it records a heartbeat for the same reason :meth:`ping`
            does.
        """
        self._guard("latency")
        measured = self._venue.latency_ms
        self._record_latency(measured, at=self._venue.now())
        return measured

    def server_time(self) -> Timestamp:
        """Return the venue's current time.

        Returns:
            The venue clock, aware and in UTC.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerError: Whatever a test scheduled against ``server_time``.

        Notes:
            This venue has a real clock and it is not the host's, which is what
            makes the method meaningful here. It moves only when a test moves it
            with :meth:`~atlas.broker.mock.venue.MockVenue.advance` or
            :meth:`~atlas.broker.mock.venue.MockVenue.set_time`, so a session
            boundary or a rollover is something a test states rather than waits
            for. The MetaTrader 5 adapter cannot implement this method at all;
            that it is implementable is a property of the port, and this is the
            demonstration.
        """
        self._guard("server_time")
        return self._venue.now()

    def version(self) -> BrokerVersion:
        """Return the identity and build of the venue interface.

        Returns:
            The mock's name and interface version. ``build`` and ``api_version``
            are ``None`` because this venue has neither, and the port permits
            their absence — filling them with plausible numbers would give a
            caller something to gate on that means nothing.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerError: Whatever a test scheduled against ``version``.
        """
        self._guard("version")
        return BrokerVersion(name=VENUE, version=MOCK_VERSION, build=None, api_version=None)
