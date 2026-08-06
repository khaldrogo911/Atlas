"""The MetaTrader 5 implementation of :class:`~atlas.broker.adapter.BrokerAdapter`.

What this module does is narrow on purpose: it decides *which* terminal call
answers a port method, hands the result to :mod:`atlas.broker.mt5.mapper`, and
returns a domain model. It contains no translation tables and no field
arithmetic — those live in the mapper, so that the translation can be tested
against hand-built structures with no session in the picture, and so that a
reader auditing "what does Atlas do with the ``sl`` field" has one place to
look.

It also owns no connection state. That belongs to
:class:`~atlas.broker.mt5.connection.MT5Session`, which this class delegates to,
because session lifecycle and request translation fail for different reasons and
are worth being able to reason about separately.

Coverage
--------
Seven of the port's thirty-one methods raise :class:`NotImplementedError`,
each with the reason at the call site. They fall into three groups, and none of
them is a placeholder that could have been filled in with a plausible-looking
value:

Trading — ``place_order``, ``modify_order``, ``cancel_order``, ``close_position``
    Not scoped to a task yet. ATLAS-TASK-0005 removed the reason they were
    blocked — :func:`~atlas.broker.mt5.connection.error_from_retcode` now tells
    ``BrokerOrderRejectedError`` from ``BrokerInsufficientMarginError`` from
    ``BrokerTimeoutError`` — but it deliberately stopped at the translation and
    sent no orders. What remains is not translation: filling mode per
    instrument, a deviation policy, and reading deals back to report a fill at
    the price it actually happened. Returning an ``Order`` without having sent
    one would be worse than not implementing them.

Streaming — ``subscribe_ticks``, ``subscribe_candles``
    The MetaTrader 5 Python API polls. It has no callback registration and no
    push channel of any kind, so a subscription can only be built by Atlas
    running its own polling loop. That machinery is a design decision in its own
    right and is not smuggled in here. The two ``unsubscribe`` methods are
    implemented rather than raising — see their docstrings.

``server_time``
    The terminal exposes no clock endpoint. See the method.

Threading
---------
The session is synchronised by :class:`~atlas.broker.base.BaseBrokerAdapter`,
not here. ``connect``, ``disconnect`` and ``reconnect`` are that class's
methods; this one supplies :meth:`MT5BrokerAdapter._connect`,
:meth:`MT5BrokerAdapter._disconnect` and :meth:`MT5BrokerAdapter._reconnect`,
which run with the session lock already held — which is what makes it safe for
``connect`` to read the brokerage name from the terminal and cache it. No lock
is written in this module. The contract is in the base class's docstring and in
ADR-0007.

Requests are deliberately not serialised, so two threads can be inside the
terminal at once. The MetaTrader 5 Python API is a single IPC channel and
imposes its own ordering on concurrent calls; Atlas does not add a second layer
of queuing on top of it, and a request that races a ``disconnect`` fails with
:class:`~atlas.broker.exceptions.BrokerNotConnectedError` from
:meth:`~atlas.broker.mt5.connection.MT5Session.terminal`, which is already in
every one of those methods' ``Raises:`` contracts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from atlas.broker.base import BaseBrokerAdapter
from atlas.broker.exceptions import BrokerDataUnavailableError, BrokerSymbolNotFoundError
from atlas.broker.models import OrderSide, OrderType, SymbolTradeMode
from atlas.broker.mt5.connection import VENUE, MT5Session
from atlas.broker.mt5.constants import DOMAIN_TO_MT5_ORDER_TYPE, TIMEFRAME_TO_MT5
from atlas.broker.mt5.mapper import (
    to_account,
    to_broker_version,
    to_candle,
    to_decimal,
    to_order,
    to_position,
    to_symbol,
    to_tick,
)
from atlas.broker.types import UNSET

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from atlas.broker.models import (
        Account,
        Candle,
        Connection,
        ConnectionState,
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
    from atlas.broker.mt5.connection import MT5Config, Terminal
    from atlas.broker.mt5.mapper import MT5AccountInfo, MT5RateRow, MT5SymbolInfo
    from atlas.broker.types import (
        BrokerName,
        BrokerVersion,
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

__all__ = ["MT5BrokerAdapter"]

#: Reported as the broker name before a session has ever been established.
#:
#: :class:`~atlas.broker.models.Connection` requires a non-empty name, and
#: ``health()`` must answer even when disconnected. Which brokerage is at the far
#: end genuinely is not known until the terminal reports it, and naming the
#: product — "MetaTrader 5" — in a field that means the brokerage would be a
#: plausible-looking wrong answer rather than an admission of ignorance.
_UNKNOWN_BROKER: Final = "unknown"

#: ``terminal_info().ping_last`` is microseconds; the domain reports milliseconds.
_MICROSECONDS_PER_MILLISECOND: Final = 1000.0

#: Why the four trading methods raise. Written once because the reason is one
#: reason, and four paraphrases of it would drift apart.
_TRADING_DEFERRED: Final = (
    "{method} sends nothing to a venue. Translating a trade server's verdict is "
    "solved — see atlas.broker.mt5.connection.error_from_retcode — but order "
    "submission also needs a filling mode per instrument, a deviation policy, "
    "and a read of the resulting deals to report the price a fill actually got. "
    "No task has scoped those, and sending an order that cannot be reported on "
    "accurately is worse than not sending one."
)


class MT5BrokerAdapter(BaseBrokerAdapter):
    """Speaks the broker port to a MetaTrader 5 terminal.

    Constructed with an :class:`~atlas.broker.mt5.connection.MT5Config` and
    nothing else. The terminal is not touched until :meth:`connect` is called,
    so an instance can be built during composition on a machine where the
    MetaTrader5 package is not installed — the import failure surfaces on
    connect, where it is actionable, rather than at start-up.

    Only ever used against a dedicated demo account at this stage. The four
    trading methods do not send anything to a venue.

    Session bookkeeping — the cached latency and heartbeat, the
    :class:`~atlas.broker.models.Connection` snapshot built from them,
    :meth:`is_connected` and :meth:`health` — is inherited from
    :class:`~atlas.broker.base.BaseBrokerAdapter`, and so is the locking around
    the session lifecycle. What is MetaTrader 5's alone stays here: where the
    state lives (on the session), which clock stamps a heartbeat (the host's),
    and that connecting re-reads the brokerage name.
    """

    def __init__(self, config: MT5Config, *, session: MT5Session | None = None) -> None:
        """Build an adapter that is not yet connected.

        Args:
            config: Credentials and terminal location.
            session: Session to use. Defaults to one built from ``config``.
                Injected so that a test supplies a session wired to a stub
                terminal and the MetaTrader5 package is never imported.
        """
        super().__init__()
        self._session = session if session is not None else MT5Session(config)
        self._broker_name: str = _UNKNOWN_BROKER

    # --- Internals ------------------------------------------------------------

    @staticmethod
    def _now() -> datetime:
        """Return the host's current time, aware and in UTC.

        Returns:
            The observation time to stamp a snapshot with. The host's clock, not
            the venue's: it records when Atlas saw the value, which is a fact
            Atlas can actually establish.
        """
        return datetime.now(UTC)

    def _terminal(self) -> Terminal:
        """Return the live terminal handle.

        Returns:
            The connected terminal.

        Raises:
            BrokerNotConnectedError: If no session is established.
        """
        return self._session.terminal()

    def _account_info(self) -> MT5AccountInfo:
        """Return the raw terminal account structure.

        Returns:
            The structure ``account_info()`` produced.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerError: If the terminal reported no account.
        """
        raw = self._terminal().account_info()
        if raw is None:
            context = "could not read the account"
            raise self._session.error_from_terminal(context)
        return raw

    def _resolve_symbol(self, symbol: SymbolName, *, select: bool = True) -> MT5SymbolInfo:
        """Look up an instrument, tolerating a difference in case.

        Args:
            symbol: Instrument code as the caller spelled it.
            select: Whether to add the instrument to Market Watch. Required
                before the terminal will publish quotes or bars for it, so every
                market-data path leaves this on.

        Returns:
            The terminal's specification for the instrument.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the terminal does not offer it.

        Notes:
            The port promises case-insensitive matching, and the terminal does
            not provide it. The fallback is not defensive politeness: the domain
            canonicalises an instrument code to upper case on the way in, so a
            broker that appends a lower-case suffix — ``EURUSD.a`` — hands back a
            :class:`~atlas.broker.models.Symbol` whose code the terminal would
            then refuse. Without this, a value read from one port method could
            not be passed to another.

            The full scan runs only after an exact lookup has already missed.
        """
        terminal = self._terminal()
        info = terminal.symbol_info(symbol)
        if info is None:
            info = self._find_symbol_ignoring_case(symbol)
        if info is None:
            msg = f"the terminal does not offer instrument {symbol!r}"
            raise BrokerSymbolNotFoundError(msg, symbol=symbol, venue=VENUE)
        if select:
            terminal.symbol_select(info.name, True)
        return info

    def _find_symbol_ignoring_case(self, symbol: SymbolName) -> MT5SymbolInfo | None:
        """Scan the instrument list for a case-insensitive match.

        Args:
            symbol: Instrument code as the caller spelled it.

        Returns:
            The matching specification, or ``None`` if there is none.
        """
        wanted = symbol.casefold()
        for candidate in self._terminal().symbols_get() or ():
            if candidate.name.casefold() == wanted:
                return candidate
        return None

    def _rates(
        self, symbol: SymbolName, timeframe: Timeframe, start_pos: int, count: int
    ) -> tuple[Sequence[MT5RateRow], MT5SymbolInfo]:
        """Fetch bars counted back from the most recent.

        Args:
            symbol: Instrument code.
            timeframe: Bar length.
            start_pos: How many bars back to start. ``0`` is the forming bar,
                ``1`` the most recent closed one.
            count: How many bars to fetch.

        Returns:
            The rows, oldest first, and the resolved instrument.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the terminal does not offer it.
            BrokerDataUnavailableError: If the terminal holds no bars for it.
        """
        info = self._resolve_symbol(symbol)
        rows = self._terminal().copy_rates_from_pos(
            info.name, TIMEFRAME_TO_MT5[timeframe], start_pos, count
        )
        if rows is None or len(rows) == 0:
            msg = f"the terminal holds no {timeframe} bars for {info.name!r}"
            raise BrokerDataUnavailableError(msg, venue=VENUE)
        return rows, info

    @staticmethod
    def _require_aware(value: datetime, name: str) -> datetime:
        """Reject a naive datetime at the boundary.

        Args:
            value: The datetime supplied by the caller.
            name: Parameter name, for the message.

        Returns:
            The same value.

        Raises:
            ValueError: If the datetime carries no offset. The port requires
                these parameters to be aware, and the annotation cannot enforce
                it on a plain argument. A naive value would otherwise be read as
                host-local time and shift the requested period by the host's
                offset — silently, and differently on a laptop and a server.
        """
        if value.utcoffset() is None:
            msg = f"{name} must be timezone aware; got the naive value {value!r}"
            raise ValueError(msg)
        return value

    # --- What the base needs from this adapter --------------------------------

    @property
    def _session_state(self) -> ConnectionState:
        """Where this adapter keeps its lifecycle state.

        Returns:
            The session's state. The session owns it, not the adapter: the
            terminal handle and the state that says whether it is usable are the
            same fact, and splitting them across two objects is how they come to
            disagree.
        """
        return self._session.state

    @property
    def _session_broker(self) -> BrokerName:
        """Which brokerage is at the far end.

        Returns:
            The name cached at connect, or ``"unknown"`` before the terminal has
            ever reported one. See :data:`_UNKNOWN_BROKER` for why the product
            name is not used as a stand-in.
        """
        return self._broker_name

    @property
    def _session_server(self) -> ServerName:
        """Which trade server the session addresses.

        Returns:
            The configured server name. Known from construction, so
            ``health()`` names the server it failed to reach.
        """
        return self._session.config.server

    # --- Lifecycle ------------------------------------------------------------

    def _connect(self) -> Connection:
        """Establish a session with the terminal.

        Returns:
            The resulting connection state.

        Raises:
            BrokerAuthenticationError: If the terminal rejected the credentials.
            BrokerConnectionError: If the terminal could not be started, or the
                MetaTrader5 package is not installed on this host.
            BrokerTimeoutError: If the terminal did not answer in time.

        Notes:
            The brokerage's name is read here and cached, because it is the one
            identity fact the terminal reports only through the account and
            :meth:`health` must be able to answer after the session has dropped.
            The read and the cache write are both inside the session lock, so a
            second thread's ``connect`` cannot interleave between them and leave
            the name describing a different session than the state does.

            :meth:`~atlas.broker.mt5.connection.MT5Session.connect` returns
            early when the session is already usable, so the waiter behind a
            concurrent connect re-reads the name and returns rather than
            initialising the terminal twice.
        """
        self._session.connect()
        self._broker_name = self._account_info().company
        self._record_heartbeat(self._now())
        return self._connection()

    def _disconnect(self) -> None:
        """Close the session.

        Returns:
            Nothing.

        Notes:
            Never raises, as the port requires of a cleanup path.

            The latency and heartbeat readings are cleared rather than kept.
            They describe a session that no longer exists, and a stale
            measurement presented as current is the failure that makes a
            supervision dashboard actively misleading. They are cleared before
            the session goes down so that a concurrent ``health`` cannot observe
            a dead session still reporting a live latency.
        """
        self._clear_session_readings()
        self._session.disconnect()

    def _reconnect(self) -> Connection:
        """Tear down the session and establish a new one.

        Returns:
            The connection state after the attempt.

        Raises:
            BrokerAuthenticationError: If the terminal rejected the credentials.
            BrokerConnectionError: If the new session could not be established.
            BrokerTimeoutError: If the terminal did not answer in time.

        Notes:
            Exactly one attempt, with no backoff, as the port specifies. There
            are no subscriptions to invalidate because this adapter issues none.

            Composed from the public :meth:`disconnect` and :meth:`connect`,
            both of which re-enter the session lock this method already holds.
        """
        self.disconnect()
        return self.connect()

    # --- Market data ----------------------------------------------------------

    def get_symbols(self) -> Sequence[Symbol]:
        """List every instrument the terminal offers.

        Returns:
            The available instruments.

        Raises:
            BrokerNotConnectedError: If no session is established.
            ValueError: If any instrument's terms cannot be represented — an
                unmodelled trade mode, or contract terms that fail the domain
                model's coherence rules.

        Notes:
            One unmappable instrument fails the whole call, deliberately.
            Skipping it would mean Atlas reports that a venue does not offer an
            instrument it does offer, and the caller has no way to find out
            otherwise. A loud failure names the instrument and the rule it
            broke.
        """
        return [to_symbol(raw) for raw in self._terminal().symbols_get() or ()]

    def get_symbol(self, symbol: SymbolName) -> Symbol:
        """Return the contract terms of one instrument.

        Args:
            symbol: Instrument code. Matching is case-insensitive.

        Returns:
            The instrument's specification.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the terminal does not offer it.
            ValueError: If the instrument's terms cannot be represented.
        """
        return to_symbol(self._resolve_symbol(symbol, select=False))

    def get_tick(self, symbol: SymbolName) -> Tick:
        """Return the most recent quote for one instrument.

        Args:
            symbol: Instrument code.

        Returns:
            The latest quote the terminal holds.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the terminal does not offer it.
            BrokerDataUnavailableError: If the terminal has published no quote yet.

        Notes:
            No freshness check is applied. Over a weekend this returns Friday's
            close, correctly stamped with Friday's time; judging that is the
            caller's job, as the port states.
        """
        info = self._resolve_symbol(symbol)
        raw = self._terminal().symbol_info_tick(info.name)
        if raw is None:
            msg = f"the terminal has published no quote for {info.name!r}"
            raise BrokerDataUnavailableError(msg, venue=VENUE)
        return to_tick(raw, info.name, self._session.clock)

    def get_ticks(self, symbols: Sequence[SymbolName]) -> Mapping[SymbolName, Tick]:
        """Return the most recent quote for several instruments.

        Args:
            symbols: Instrument codes to quote.

        Returns:
            A mapping from the code as the caller spelled it to its latest
            quote. An instrument the terminal has not quoted is absent.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If any code is not offered.

        Notes:
            Every instrument is resolved before any is quoted, so an unknown
            code fails before a partial snapshot has been assembled.

            The terminal offers no batch quote call, so this is a loop, and the
            quotes are therefore microseconds apart rather than simultaneous.
            That is as close as MetaTrader 5 allows; the port asks for the
            closest the venue permits, not for an atomicity it cannot provide.

            Keys are the caller's spelling rather than the terminal's, so a
            result can be looked up with the value that was passed in.
        """
        resolved = {name: self._resolve_symbol(name) for name in symbols}
        terminal = self._terminal()
        clock = self._session.clock

        quotes: dict[SymbolName, Tick] = {}
        for name, info in resolved.items():
            raw = terminal.symbol_info_tick(info.name)
            if raw is not None:
                quotes[name] = to_tick(raw, info.name, clock)
        return quotes

    def get_candle(
        self, symbol: SymbolName, timeframe: Timeframe, *, include_forming: bool = False
    ) -> Candle:
        """Return the most recent bar for one instrument.

        Args:
            symbol: Instrument code.
            timeframe: Bar length.
            include_forming: If ``True``, return the bar currently being built.

        Returns:
            The requested bar.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the terminal does not offer it.
            BrokerDataUnavailableError: If the terminal holds no bars for it.

        Notes:
            The forming bar is index 0 and the most recent closed bar is index
            1, so the port's default maps onto a start position of one. The
            terminal has no flag for this; the offset *is* the distinction.
        """
        start_pos = 0 if include_forming else 1
        rows, info = self._rates(symbol, timeframe, start_pos, 1)
        return to_candle(
            rows[0], info.name, timeframe, self._session.clock, is_closed=not include_forming
        )

    def get_candles(self, symbol: SymbolName, timeframe: Timeframe, count: int) -> Sequence[Candle]:
        """Return the most recent closed bars for one instrument.

        Args:
            symbol: Instrument code.
            timeframe: Bar length.
            count: How many bars to return. Must be at least 1.

        Returns:
            Up to ``count`` closed bars, oldest first.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the terminal does not offer it.
            BrokerDataUnavailableError: If the terminal holds no bars for it.
            ValueError: If ``count`` is less than 1.
        """
        if count < 1:
            msg = f"count must be at least 1; got {count}"
            raise ValueError(msg)

        rows, info = self._rates(symbol, timeframe, 1, count)
        clock = self._session.clock
        return [to_candle(row, info.name, timeframe, clock, is_closed=True) for row in rows]

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
                to now.

        Returns:
            Closed bars whose open time falls in ``[start, end)``, oldest first.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the terminal does not offer it.
            ValueError: If either bound is naive, or ``end`` is not after
                ``start``.

        Notes:
            Two corrections are applied to what the terminal returns, and both
            matter.

            The terminal's range is inclusive at both ends while the port's is
            half-open, so a bar opening exactly at ``end`` is dropped here.
            Without that, two consecutive requests share a bar and anything
            summing over them counts it twice.

            The terminal will also return the forming bar when ``end`` reaches
            the present. It is dropped by comparing the bar's nominal close
            against the host clock, because the port promises closed bars and a
            forming one changes after it is read.

            An empty result is returned rather than raised. A period containing
            no trading — a weekend — is a true answer, and the terminal does not
            distinguish it from history that was never downloaded, so raising
            would report a fault that may not exist.
        """
        self._require_aware(start, "start")
        boundary = self._now() if end is None else self._require_aware(end, "end")
        if boundary <= start:
            msg = f"end must be after start; got start={start!r} and end={boundary!r}"
            raise ValueError(msg)

        info = self._resolve_symbol(symbol)
        clock = self._session.clock
        rows = self._terminal().copy_rates_range(
            info.name,
            TIMEFRAME_TO_MT5[timeframe],
            clock.from_utc(start),
            clock.from_utc(boundary),
        )

        now = self._now()
        candles: list[Candle] = []
        for row in rows or ():
            open_time = clock.to_utc(row["time"])
            if open_time >= boundary or open_time + timeframe.duration > now:
                continue
            candles.append(to_candle(row, info.name, timeframe, clock, is_closed=True))
        return candles

    def subscribe_ticks(
        self, symbols: Sequence[SymbolName], handler: TickHandler
    ) -> SubscriptionID:
        """Not available: the terminal cannot push quotes.

        Args:
            symbols: Instrument codes to stream.
            handler: Called once per update.

        Raises:
            NotImplementedError: Always. The MetaTrader 5 Python API is
                poll-only — it registers no callbacks and opens no push channel
                — so the terminal capability this needs does not exist. Atlas
                can synthesise it by polling ``symbol_info_tick`` on its own
                thread, but that means owning a scheduler, a change-detection
                rule and a backpressure policy, none of which should appear as a
                side effect of a mapping task.

        Notes:
            TODO(ATLAS-TASK-0004+): implement by polling once the streaming
            design is settled. If polling is rejected, the permanent answer
            becomes ``BrokerUnsupportedOperationError``, which the port already
            anticipates for a venue that cannot stream.
        """
        msg = (
            "MetaTrader 5 cannot push quotes: its Python API registers no "
            "callbacks and opens no push channel. Delivering this contract "
            "requires an Atlas-side polling loop, which is not in scope here."
        )
        raise NotImplementedError(msg)

    def unsubscribe_ticks(self, subscription_id: SubscriptionID) -> None:
        """Stop a quote subscription.

        Args:
            subscription_id: Handle returned by :meth:`subscribe_ticks`.

        Returns:
            Nothing.

        Notes:
            Does nothing, and that is the contract rather than a stub. The port
            requires this to succeed silently for a handle that is unknown or
            already cancelled; since :meth:`subscribe_ticks` issues no handles,
            every handle is unknown, and doing nothing is the specified
            behaviour. Raising here would break a cleanup path for no benefit.
        """

    def subscribe_candles(
        self, symbols: Sequence[SymbolName], timeframe: Timeframe, handler: CandleHandler
    ) -> SubscriptionID:
        """Not available: the terminal cannot push bars.

        Args:
            symbols: Instrument codes to stream.
            timeframe: Bar length.
            handler: Called once per update.

        Raises:
            NotImplementedError: Always, for the reason given on
                :meth:`subscribe_ticks`. Bars are the same problem: the terminal
                exposes ``copy_rates_from_pos`` and nothing that notifies.

        Notes:
            TODO(ATLAS-TASK-0004+): see :meth:`subscribe_ticks`.
        """
        msg = (
            "MetaTrader 5 cannot push bars: it exposes copy_rates_from_pos and "
            "nothing that notifies. See subscribe_ticks."
        )
        raise NotImplementedError(msg)

    def unsubscribe_candles(self, subscription_id: SubscriptionID) -> None:
        """Stop a bar subscription.

        Args:
            subscription_id: Handle returned by :meth:`subscribe_candles`.

        Returns:
            Nothing.

        Notes:
            A no-op, for the reason given on :meth:`unsubscribe_ticks`.
        """

    # --- Trading --------------------------------------------------------------

    def place_order(self, request: OrderRequest) -> Order:
        """Not available yet: order results cannot be reported honestly.

        Args:
            request: What to place.

        Raises:
            NotImplementedError: Always. The terminal capability exists —
                ``order_send`` — and since ATLAS-TASK-0005 so does the
                translation of its verdict:
                :func:`~atlas.broker.mt5.connection.error_from_retcode` returns
                ``BrokerOrderRejectedError``, ``BrokerInsufficientMarginError``
                or ``BrokerTimeoutError`` as the retcode requires. What is
                missing is the rest of order submission, which no task has
                scoped, and a half-specified order is not worth sending.

        Notes:
            TODO: implement over ``order_send``, translating the result with
            ``error_from_retcode``. The remaining decisions are filling-mode
            selection per instrument and a deviation policy; neither has an
            obviously right answer, which is why they are not settled here.
        """
        raise NotImplementedError(_TRADING_DEFERRED.format(method="place_order"))

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
        """Not available yet: amendment results cannot be reported honestly.

        Args:
            order_id: Ticket of the order to amend.
            price: New working price.
            stop_price: New trigger price.
            stop_loss: New protective stop.
            take_profit: New profit target.
            volume: New quantity.

        Raises:
            NotImplementedError: Always, for the reason given on
                :meth:`place_order`.

        Notes:
            TODO: implement over ``order_send`` with
            ``TRADE_ACTION_MODIFY``. Note that the terminal amends by resending
            the complete order, so this needs a read of the current order to
            fill the fields left ``UNSET`` — an amendment that omits a field
            clears it at the venue.
        """
        raise NotImplementedError(_TRADING_DEFERRED.format(method="modify_order"))

    def cancel_order(self, order_id: OrderID) -> Order:
        """Not available yet: cancellation results cannot be reported honestly.

        Args:
            order_id: Ticket of the order to cancel.

        Raises:
            NotImplementedError: Always, for the reason given on
                :meth:`place_order`. The case that matters here is an order
                that fills while the cancellation is in flight, which the port
                requires be reported as a ``FILLED`` order rather than as an
                error. That is a read of the order's resulting state, not a
                retcode distinction, so the 0005 translation does not settle it.

        Notes:
            TODO: implement over ``order_send`` with ``TRADE_ACTION_REMOVE``.
        """
        raise NotImplementedError(_TRADING_DEFERRED.format(method="cancel_order"))

    def close_position(self, position_id: PositionID, volume: Volume | None = None) -> Execution:
        """Not available yet: closing results cannot be reported honestly.

        Args:
            position_id: Ticket of the position to close.
            volume: How much to close. Defaults to the whole position.

        Raises:
            NotImplementedError: Always, for the reason given on
                :meth:`place_order`.

        Notes:
            TODO: implement by sending an opposing order with
            the ``position`` field set. The port also requires a close filled in
            several parts to be reported as one execution at the
            volume-weighted average price, which means reading the resulting
            deals back out of history rather than trusting the order result.
        """
        raise NotImplementedError(_TRADING_DEFERRED.format(method="close_position"))

    # --- Account --------------------------------------------------------------

    def get_account(self) -> Account:
        """Return the current state of the trading account.

        Returns:
            Balance, equity, margin and trading permission as the terminal
            reports them.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerError: If the terminal reported no account.
        """
        return to_account(self._account_info(), self._now())

    def get_positions(self, symbol: SymbolName | None = None) -> Sequence[Position]:
        """Return open positions, optionally for one instrument.

        Args:
            symbol: Restrict to this instrument. Defaults to all instruments.

        Returns:
            The matching open positions.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If ``symbol`` is given and not offered.
            BrokerDataUnavailableError: If the opening deal of a position cannot be
                read — see the note on commission.
            ValueError: If the terminal reports a position type Atlas does not
                model.

        Notes:
            The domain requires a position's commission and MetaTrader 5 does
            not report one: commission is charged against the *deals* that
            opened the position, not against the position itself. It is
            therefore read back per position from deal history, which costs one
            extra call each. Defaulting it to zero would be cheaper and would
            understate the cost of every position in the system.

            The terminal distinguishes "no filter" from "filter is None", so the
            unfiltered case omits the argument rather than passing ``None``.
        """
        terminal = self._terminal()
        if symbol is None:
            raw_positions = terminal.positions_get()
        else:
            raw_positions = terminal.positions_get(symbol=self._resolve_symbol(symbol).name)

        clock = self._session.clock
        return [
            to_position(raw, clock, self._position_commission(raw.ticket))
            for raw in raw_positions or ()
        ]

    def _position_commission(self, ticket: int) -> Money:
        """Sum the commission charged on the deals that make up a position.

        Args:
            ticket: The position's ticket.

        Returns:
            Total commission, signed as the venue reports it — normally
            negative, because it is a charge.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerDataUnavailableError: If the terminal returned no deals. Every
                open position has at least an opening deal, so an empty result
                means the terminal could not answer, not that the position was
                free. Reporting zero in that case would be a fabricated number
                in an accounting field.
        """
        deals = self._terminal().history_deals_get(position=ticket)
        if not deals:
            msg = (
                f"the terminal returned no deals for position {ticket}, so its "
                "commission cannot be established"
            )
            raise BrokerDataUnavailableError(msg, venue=VENUE)
        return sum((to_decimal(deal.commission) for deal in deals), start=to_decimal(0))

    def get_orders(self, symbol: SymbolName | None = None) -> Sequence[Order]:
        """Return orders still working at the terminal.

        Args:
            symbol: Restrict to this instrument. Defaults to all instruments.

        Returns:
            Orders that have not reached a terminal state.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If ``symbol`` is given and not offered.
            ValueError: If the terminal reports an order type or state Atlas
                does not model.

        Notes:
            ``orders_get`` already returns only working orders — filled and
            cancelled ones move to history. The status filter below states the
            port's contract in code rather than relying on that, so a terminal
            that ever returns a completed order does not leak one upwards.
        """
        terminal = self._terminal()
        if symbol is None:
            raw_orders = terminal.orders_get()
        else:
            raw_orders = terminal.orders_get(symbol=self._resolve_symbol(symbol).name)

        clock = self._session.clock
        orders = (to_order(raw, clock) for raw in raw_orders or ())
        return [order for order in orders if order.status.is_active]

    def get_open_positions(self) -> Sequence[Position]:
        """Return every open position.

        Returns:
            All open positions.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerDataUnavailableError: If a position's opening deal cannot be read.

        Notes:
            Delegates to :meth:`get_positions` rather than repeating it, which
            is what makes the port's consistency requirement between the two
            true by construction instead of by discipline.
        """
        return self.get_positions()

    # --- Risk -----------------------------------------------------------------

    def margin_required(
        self, symbol: SymbolName, side: OrderSide, volume: Volume, price: Price | None = None
    ) -> NonNegativeMoney:
        """Return the margin the terminal would take to open a position.

        Args:
            symbol: Instrument to be traded.
            side: Direction of the hypothetical position.
            volume: Size, in lots.
            price: Price to evaluate at. Defaults to the current market.

        Returns:
            The margin, in the account's currency.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the instrument is not offered.
            BrokerDataUnavailableError: If ``price`` was omitted and the terminal
                has published no quote to evaluate against.
            BrokerError: If the terminal declined to calculate.

        Notes:
            The terminal's own calculation, unmodified. It is evaluated as a
            market order because that is what "open a position" means here; the
            margin a venue takes does not depend on how the position was
            reached.

            Defaulting the price uses the side Atlas would actually transact at
            — ask to buy, bid to sell — rather than a mid, so the number matches
            the trade being contemplated.
        """
        info = self._resolve_symbol(symbol)
        evaluation_price = price if price is not None else self._market_price(info, side)

        margin = self._terminal().order_calc_margin(
            DOMAIN_TO_MT5_ORDER_TYPE[side, OrderType.MARKET],
            info.name,
            float(volume),
            float(evaluation_price),
        )
        if margin is None:
            context = f"could not calculate margin for {volume} lots of {info.name!r}"
            raise self._session.error_from_terminal(context)
        return to_decimal(margin)

    def _market_price(self, info: MT5SymbolInfo, side: OrderSide) -> Money:
        """Return the price the given side would transact at right now.

        Args:
            info: The resolved instrument.
            side: Direction of the hypothetical trade.

        Returns:
            The ask for a buy, the bid for a sell.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerDataUnavailableError: If the terminal has published no quote.
        """
        raw = self._terminal().symbol_info_tick(info.name)
        if raw is None:
            msg = f"the terminal has published no quote for {info.name!r}"
            raise BrokerDataUnavailableError(msg, venue=VENUE)
        tick = to_tick(raw, info.name, self._session.clock)
        return tick.ask if side is OrderSide.BUY else tick.bid

    def margin_available(self) -> Money:
        """Return the margin currently free for new positions.

        Returns:
            Free margin in the account's currency. Signed: an account past its
            maintenance requirement reports a negative value rather than zero.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerError: If the terminal reported no account.

        Notes:
            Reads through :meth:`get_account` rather than the raw structure, so
            the two can never disagree about the same number.
        """
        return self.get_account().free_margin

    def can_trade(self, symbol: SymbolName) -> bool:
        """Report whether the terminal would currently accept an order.

        Args:
            symbol: Instrument to check.

        Returns:
            ``True`` if the instrument is not disabled and the account is
            permitted to trade.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the instrument is not offered.
            BrokerError: If the terminal reported no account.
            ValueError: If the terminal reports a trade mode Atlas does not
                model.

        Notes:
            ``CLOSE_ONLY`` counts as tradeable, because the venue will accept an
            order — a closing one. The port is explicit that a caller needing
            the reason reads
            :attr:`~atlas.broker.models.Symbol.trade_mode` instead, and
            collapsing "can only close" into ``False`` would stop a risk layer
            from flattening a position it must exit.

            This does not establish that the market is open. The terminal
            reports session schedules through a symbol-info call this adapter
            does not make, so an instrument enabled outside its trading hours
            answers ``True`` here and rejects the order. That gap is recorded in
            this package's README.
        """
        symbol_info = to_symbol(self._resolve_symbol(symbol, select=False))
        return symbol_info.trade_mode is not SymbolTradeMode.DISABLED and (
            self._account_info().trade_allowed
        )

    # --- Diagnostics ----------------------------------------------------------

    def ping(self) -> bool:
        """Check whether the terminal is answering.

        Returns:
            ``True`` if the terminal responded.

        Notes:
            Never raises, as the port requires: this is the predicate a
            supervision loop uses to notice the venue is down, so it cannot
            itself fail when the venue is down. Every failure — no session, a
            dead terminal, an import that was never possible — is one ``False``.

            ``terminal_info`` is the cheapest round trip the terminal offers
            that still proves the IPC channel is alive.
        """
        try:
            answered = self._terminal().terminal_info() is not None
        except Exception:  # the port forbids this method from raising
            return False

        if answered:
            self._record_heartbeat(self._now())
        return answered

    def latency(self) -> LatencyMilliseconds:
        """Measure the round-trip time to the venue.

        Returns:
            Milliseconds for one round trip to the trade server.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerError: If the terminal did not report its status.

        Notes:
            This is the terminal's own measurement of its link to the trade
            server, refreshed by the call that reads it — not the time taken by
            the local IPC hop. The distinction is worth stating: the IPC hop is
            a fraction of a millisecond and measuring it would produce a
            reassuring number that says nothing about whether an order will
            reach the venue in time. The number a trading system needs is the
            one to the server, and the terminal is the only party positioned to
            measure it.

            The reading is cached, so :meth:`health` can report it without a
            round trip.
        """
        info = self._terminal().terminal_info()
        if info is None:
            context = "could not read the terminal status"
            raise self._session.error_from_terminal(context)

        measured = info.ping_last / _MICROSECONDS_PER_MILLISECOND
        self._record_latency(measured, at=self._now())
        return measured

    def server_time(self) -> Timestamp:
        """Not available: the terminal exposes no clock.

        Raises:
            NotImplementedError: Always. The MetaTrader 5 Python API has no
                server-time call. The nearest thing is the timestamp on the last
                quote of some instrument, which is the time of the last *trade
                server event* and not the current time — over a weekend it is
                Friday's close, and it requires naming an instrument that this
                signature has no parameter for. Returning it would look like a
                clock and behave like a stale one.

        Notes:
            TODO(ATLAS-TASK-0004+): the honest implementation needs the trade
            server's UTC offset, which is configured on
            :class:`~atlas.broker.mt5.connection.MT5Config` and cannot be
            discovered from the terminal. Once a deployment supplies a verified
            offset, this becomes the host clock corrected by it — at which point
            it is Atlas's clock, and the docstring must say so rather than
            implying the venue was asked.
        """
        msg = (
            "MetaTrader 5 exposes no server-time call. The nearest value is the "
            "timestamp of some instrument's last quote, which is the time of the "
            "last trade-server event rather than the current time."
        )
        raise NotImplementedError(msg)

    def version(self) -> BrokerVersion:
        """Return the identity and build of the terminal.

        Returns:
            Product name, version and build.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerError: If the terminal did not report its version or status.

        Notes:
            Assembled from two calls, because the terminal splits the product
            name and the build across ``terminal_info`` and ``version``. The
            release date the third element of ``version()`` carries is dropped:
            :class:`~atlas.broker.types.BrokerVersion` has nowhere to put it,
            and the build number is the value callers gate behaviour on.
        """
        terminal = self._terminal()
        reported = terminal.version()
        if reported is None:
            context = "could not read the terminal version"
            raise self._session.error_from_terminal(context)

        info = terminal.terminal_info()
        if info is None:
            context = "could not read the terminal status"
            raise self._session.error_from_terminal(context)

        terminal_version, build, _release_date = reported
        return to_broker_version(info.name, terminal_version, build)
