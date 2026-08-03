"""The ``BrokerAdapter`` port: the sole boundary between Atlas and any venue.

Everything above this line — strategy, risk, execution, research, reporting —
depends on this abstract class and never on a concrete adapter. Nothing here
knows whether the venue behind it is MetaTrader 5, a FIX session, a REST API, a
simulator or a replay of last March.

Scope
-----
This module is a contract and nothing else. It contains no connection handling,
no retry policy, no caching, no reconnection, no networking and no trading
logic. Shared behaviour that every adapter would otherwise repeat belongs in
``BaseBrokerAdapter`` (ATLAS-TASK-0007); venue specifics belong in the concrete
adapters below it.

Synchronous by policy
---------------------
Every method blocks until it has an answer. An adapter may use threads or an
event loop internally, but the surface stays synchronous so that a strategy
run is deterministic and reproducible: the same inputs in the same order
produce the same decisions, which is not true of an interleaved async caller.

Errors
------
Implementations raise from a single planned hierarchy, delivered by a later
task. The names are referenced in the ``Raises`` section of every method below
so that the contract is written down now, before any adapter exists to shape it
around one venue's error codes::

    BrokerError
    ├── BrokerConnectionError
    │   ├── BrokerNotConnectedError      no session established
    │   └── BrokerTimeoutError           the venue did not answer in time
    ├── BrokerAuthenticationError        credentials rejected
    ├── BrokerRequestError
    │   ├── BrokerSymbolNotFoundError    unknown or unavailable instrument
    │   ├── BrokerOrderNotFoundError     unknown order ticket
    │   ├── BrokerPositionNotFoundError  unknown position ticket
    │   ├── BrokerOrderRejectedError     the venue refused the order
    │   └── BrokerInsufficientMarginError
    ├── BrokerDataUnavailableError       the venue holds no data for the request
    └── BrokerUnsupportedOperationError  the venue cannot perform this at all

An adapter never raises a venue SDK's own exception type through this surface.
Translating them is part of the adapter's job.

Credentials
-----------
No method takes credentials. An adapter receives its configuration when it is
constructed, from :mod:`atlas.config`, so a secret cannot reach a call site in
business logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from atlas.broker.types import UNSET

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
        OrderSide,
        Position,
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

__all__ = ["BrokerAdapter"]


class BrokerAdapter(ABC):
    """The contract every venue integration satisfies.

    An implementation translates between one venue and the Atlas domain
    models, in both directions, and does nothing else. Callers hold this type,
    never a concrete adapter, which is what allows a broker to be replaced
    without touching a line of business logic.

    Annotations on parameters describe intent; they do not validate. The
    enforcing boundary is the model — a price reaching an adapter as a
    parameter is checked when the adapter builds it into an
    :class:`~atlas.broker.models.Order`, not when it crosses this signature.

    Implementations must be safe to call from more than one thread. A strategy
    thread reading quotes while a risk thread queries the account is the normal
    case, not an edge case.
    """

    # --- Lifecycle ------------------------------------------------------------

    @abstractmethod
    def connect(self) -> Connection:
        """Establish a session with the venue.

        Returns:
            The resulting connection state. On success its
            :attr:`~atlas.broker.models.Connection.state` is
            ``CONNECTED`` or ``DEGRADED``.

        Raises:
            BrokerAuthenticationError: If the venue rejected the credentials.
            BrokerConnectionError: If the venue could not be reached.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            Credentials come from the adapter's own configuration, never from
            the caller. Calling this on an already-connected adapter is not an
            error and returns the current state.
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Close the session and release everything it holds.

        Returns:
            Nothing.

        Raises:
            BrokerError: Never, for the ordinary case of an already-closed or
                never-opened session. Disconnecting must be safe to call from a
                cleanup path that cannot know the current state.

        Notes:
            Active subscriptions are cancelled. Working orders and open
            positions are untouched: they live at the venue, not in the
            adapter, and disconnecting is not a flatten instruction.
        """

    @abstractmethod
    def reconnect(self) -> Connection:
        """Tear down the session and establish a new one.

        Returns:
            The connection state after the attempt.

        Raises:
            BrokerAuthenticationError: If the venue rejected the credentials.
            BrokerConnectionError: If the new session could not be established.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            Subscriptions do not survive. A caller holding a
            :data:`~atlas.broker.types.SubscriptionID` across a reconnect must
            re-subscribe; the old handle is dead. Retry and backoff policy is
            not defined here — this method makes exactly one attempt.
        """

    @abstractmethod
    def is_connected(self) -> bool:
        """Report whether the adapter currently has a usable session.

        Returns:
            ``True`` if orders and market data requests can be attempted.

        Raises:
            BrokerError: Never. This is the predicate a caller uses to decide
                whether anything else is worth trying, so it must not fail. An
                implementation that cannot determine the state reports
                ``False``.

        Notes:
            Cheap and local by contract: it must not perform a round trip. Use
            :meth:`ping` to find out whether the venue is actually answering.
            A ``DEGRADED`` session counts as connected.
        """

    @abstractmethod
    def health(self) -> Connection:
        """Return the full connectivity snapshot.

        Returns:
            The current state, including measured latency and the time of the
            last heartbeat where the adapter tracks one.

        Raises:
            BrokerError: Never. A health check that fails when things are
                unhealthy reports nothing at the moment it matters most; a
                broken session is described by a ``DISCONNECTED`` state.

        Notes:
            The richer form of :meth:`is_connected`, for logging, dashboards
            and supervision. ``latency_ms`` reports the last observed value and
            may be ``None`` before the first measurement.
        """

    # --- Market data ----------------------------------------------------------

    @abstractmethod
    def get_symbols(self) -> Sequence[Symbol]:
        """List every instrument the account may query or trade.

        Returns:
            The available instruments. Empty if the venue exposes none.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            Potentially large — thousands of instruments at some venues — and
            slow-moving. Callers that need it repeatedly should hold onto the
            result; the port does not cache.
        """

    @abstractmethod
    def get_symbol(self, symbol: SymbolName) -> Symbol:
        """Return the contract terms of one instrument.

        Args:
            symbol: Instrument code. Matching is case-insensitive.

        Returns:
            The instrument's specification.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the venue does not offer it.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            The returned :attr:`~atlas.broker.models.Symbol.spread` is a
            snapshot of a moving quantity, not a term of the contract. Size a
            trade off :meth:`get_tick` instead.
        """

    @abstractmethod
    def get_tick(self, symbol: SymbolName) -> Tick:
        """Return the most recent quote for one instrument.

        Args:
            symbol: Instrument code.

        Returns:
            The latest quote the venue has published.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the venue does not offer it.
            BrokerDataUnavailableError: If the venue has published no quote yet.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            The quote may be stale — over a weekend it will be. Its age is the
            caller's to judge from
            :attr:`~atlas.broker.models.Tick.timestamp`; the port does not
            impose a freshness policy, because what counts as stale differs
            between a scalper and a daily system.
        """

    @abstractmethod
    def get_ticks(self, symbols: Sequence[SymbolName]) -> Mapping[SymbolName, Tick]:
        """Return the most recent quote for several instruments at once.

        Args:
            symbols: Instrument codes to quote.

        Returns:
            A mapping from instrument code to its latest quote. An instrument
            for which the venue has published no quote is absent from the
            mapping rather than present with a null.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If any code is not offered by the venue.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            Exists so a multi-instrument decision rests on one snapshot. Looping
            over :meth:`get_tick` samples each instrument at a different
            instant, which silently corrupts any calculation that compares them.
            Whether the venue can honour that atomically is its own business;
            the adapter must get as close as the venue allows.
        """

    @abstractmethod
    def get_candle(
        self, symbol: SymbolName, timeframe: Timeframe, *, include_forming: bool = False
    ) -> Candle:
        """Return the most recent bar for one instrument.

        Args:
            symbol: Instrument code.
            timeframe: Bar length.
            include_forming: If ``True``, return the bar currently being built,
                whose high, low and close will still change. If ``False``, the
                default, return the most recent bar that has closed.

        Returns:
            The requested bar. Its
            :attr:`~atlas.broker.models.Candle.is_closed` flag states which
            kind it is in every case.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the venue does not offer it.
            BrokerDataUnavailableError: If the venue holds no bars for it.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            The default is the closed bar because acting on a forming one is
            the most common form of look-ahead in a live system: the bar the
            strategy decided on is not the bar that ends up in the record. The
            forming bar is reachable, but only by asking for it.
        """

    @abstractmethod
    def get_candles(self, symbol: SymbolName, timeframe: Timeframe, count: int) -> Sequence[Candle]:
        """Return the most recent closed bars for one instrument.

        Args:
            symbol: Instrument code.
            timeframe: Bar length.
            count: How many bars to return. Must be at least 1.

        Returns:
            Up to ``count`` closed bars in ascending time order, oldest first.
            Fewer are returned when the venue's history is shorter. The forming
            bar is never included.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the venue does not offer it.
            BrokerDataUnavailableError: If the venue holds no bars for it.
            BrokerTimeoutError: If the venue did not answer in time.
            ValueError: If ``count`` is less than 1.

        Notes:
            The indicator-warmup form: "the last 200 bars", without the caller
            computing a start time from a bar length and a calendar the venue
            owns. Use :meth:`get_historical_data` for an explicit period.
        """

    @abstractmethod
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
            end: Exclusive end of the period. Must be timezone aware.
                Defaults to now.

        Returns:
            Closed bars whose open time falls in ``[start, end)``, in ascending
            time order. Empty when the period contains no trading.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the venue does not offer it.
            BrokerDataUnavailableError: If the venue's history does not reach
                back to ``start``.
            BrokerTimeoutError: If the venue did not answer in time.
            ValueError: If ``end`` is not after ``start``.

        Notes:
            Half-open by design, so consecutive periods tile without
            overlapping and a bar cannot be counted twice at a boundary. The
            ranged counterpart to :meth:`get_candles`; both return the same
            model.
        """

    @abstractmethod
    def subscribe_ticks(
        self, symbols: Sequence[SymbolName], handler: TickHandler
    ) -> SubscriptionID:
        """Receive quote updates as the venue publishes them.

        Args:
            symbols: Instrument codes to stream.
            handler: Called once per update, with the quote.

        Returns:
            A handle identifying this subscription, for
            :meth:`unsubscribe_ticks`.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If any code is not offered by the venue.
            BrokerUnsupportedOperationError: If the venue cannot stream. A
                replay or snapshot-only source may legitimately refuse.

        Notes:
            The handler may be called on a thread the caller does not own, and
            must therefore be cheap and must not block: a slow handler applies
            backpressure to the feed. Do the work elsewhere and hand off. An
            exception escaping the handler must not kill the subscription.

            The port itself publishes no events. This is a delivery contract,
            not an event bus; an implementation is free to build one on top.
        """

    @abstractmethod
    def unsubscribe_ticks(self, subscription_id: SubscriptionID) -> None:
        """Stop a quote subscription.

        Args:
            subscription_id: Handle returned by :meth:`subscribe_ticks`.

        Returns:
            Nothing.

        Raises:
            BrokerError: Never for an unknown or already-cancelled handle.
                Cancelling twice is not a failure, and a cleanup path cannot
                always know what is still live.

        Notes:
            Only this subscription stops. Another component streaming the same
            instrument under its own handle is unaffected, which is why the
            handle rather than the symbol is the unit of cancellation. The
            handler may still be called once or twice while the cancellation
            reaches the feed.
        """

    @abstractmethod
    def subscribe_candles(
        self, symbols: Sequence[SymbolName], timeframe: Timeframe, handler: CandleHandler
    ) -> SubscriptionID:
        """Receive bar updates as the venue publishes them.

        Args:
            symbols: Instrument codes to stream.
            timeframe: Bar length.
            handler: Called once per update, with the bar.

        Returns:
            A handle identifying this subscription, for
            :meth:`unsubscribe_candles`.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If any code is not offered by the venue.
            BrokerUnsupportedOperationError: If the venue cannot stream bars.

        Notes:
            Both forming and closed bars are delivered;
            :attr:`~atlas.broker.models.Candle.is_closed` distinguishes them,
            and a strategy that acts only on completed bars must check it. The
            threading and backpressure rules of :meth:`subscribe_ticks` apply
            unchanged.
        """

    @abstractmethod
    def unsubscribe_candles(self, subscription_id: SubscriptionID) -> None:
        """Stop a bar subscription.

        Args:
            subscription_id: Handle returned by :meth:`subscribe_candles`.

        Returns:
            Nothing.

        Raises:
            BrokerError: Never for an unknown or already-cancelled handle.

        Notes:
            Behaves exactly as :meth:`unsubscribe_ticks`, for bars.
        """

    # --- Trading --------------------------------------------------------------

    @abstractmethod
    def place_order(self, request: OrderRequest) -> Order:
        """Submit an order to the venue.

        Args:
            request: What to place. Validated on construction, so a
                structurally impossible order cannot reach this call.

        Returns:
            The order as the venue now holds it, carrying the venue's ticket
            and status. A market order may come back already ``FILLED``; a
            pending order comes back ``PENDING``.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the instrument is not offered.
            BrokerOrderRejectedError: If the venue refused the order — market
                closed, price off, volume outside the instrument's bounds.
            BrokerInsufficientMarginError: If the account cannot support it.
            BrokerTimeoutError: If the venue did not answer in time. The order
                may still have reached the venue; a caller recovering from
                this must reconcile with :meth:`get_orders` rather than assume
                it failed.

        Notes:
            Not idempotent. The port has no client-supplied request id, so a
            blind retry can place a second order. Reconcile, do not retry.

            A pending order is understood to rest until cancelled. Time in
            force is not yet part of this contract.
        """

    @abstractmethod
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
            stop_price: New trigger price. ``None`` clears it; ``UNSET``
                leaves it.
            stop_loss: New protective stop. ``None`` removes the stop;
                ``UNSET`` leaves it.
            take_profit: New profit target. ``None`` removes the target;
                ``UNSET`` leaves it.
            volume: New quantity. ``UNSET`` leaves it. There is no ``None``:
                an order with no size is a cancellation, so use
                :meth:`cancel_order`.

        Returns:
            The order as the venue holds it after the amendment.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerOrderNotFoundError: If the ticket is unknown.
            BrokerOrderRejectedError: If the venue refused the amendment, or
                the order had already reached a terminal state.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            Three outcomes per field — leave, set, remove — need three values,
            which is why :data:`~atlas.broker.types.UNSET` exists alongside
            ``None``. Without it, removing a stop loss and declining to touch
            it would be the same call.

            Not idempotent, for the reasons given on :meth:`place_order`.
        """

    @abstractmethod
    def cancel_order(self, order_id: OrderID) -> Order:
        """Cancel a working order.

        Args:
            order_id: Ticket of the order to cancel.

        Returns:
            The order in its resulting state, normally ``CANCELLED``.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerOrderNotFoundError: If the ticket is unknown.
            BrokerOrderRejectedError: If the venue refused, which for a
                cancellation almost always means the order filled first.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            Cancels the *order*; it does not close a position the order has
            already produced. Use :meth:`close_position` for that.

            An order that filled while the cancellation was in flight comes
            back ``FILLED``. That is the honest answer, not an error, and the
            caller must read the returned status rather than assume the
            cancellation took effect.
        """

    @abstractmethod
    def close_position(self, position_id: PositionID, volume: Volume | None = None) -> Execution:
        """Close an open position, in whole or in part.

        Args:
            position_id: Ticket of the position to close.
            volume: How much to close, in lots. Defaults to the whole position.

        Returns:
            The closing execution: the price, size, commission and swap the
            venue booked.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerPositionNotFoundError: If the ticket is unknown or the
                position is already closed.
            BrokerOrderRejectedError: If the venue refused, such as a closed
                market.
            BrokerTimeoutError: If the venue did not answer in time.
            ValueError: If ``volume`` exceeds the position's open size.

        Notes:
            Returns an :class:`~atlas.broker.models.Execution` rather than a
            position, because after a full close there is no position left to
            describe, and the fill price is what the caller actually needs.
            After a partial close, query :meth:`get_open_positions` for what
            remains.

            Where a venue fills the close in several parts, the adapter reports
            one aggregate execution: ``volume`` is the total closed and
            ``price`` is the volume-weighted average.
        """

    # --- Account --------------------------------------------------------------

    @abstractmethod
    def get_account(self) -> Account:
        """Return the current state of the trading account.

        Returns:
            Balance, equity, margin and the venue's trading permission, as the
            venue reports them.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            Reported, never recomputed. Where Atlas would disagree with the
            venue's arithmetic the venue is right, because it is the one
            settling the account.
        """

    @abstractmethod
    def get_positions(self, symbol: SymbolName | None = None) -> Sequence[Position]:
        """Return open positions, optionally for one instrument.

        Args:
            symbol: Restrict to this instrument. Defaults to all instruments.

        Returns:
            The matching open positions. Empty when the account is flat.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If ``symbol`` is given and not offered.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            Open positions only. Closed-position history is a reporting concern
            and is deliberately outside this port.

            On a netting account the venue reports one position per
            instrument; on a hedging account, one per ticket. The port does not
            hide that difference, because a caller that nets two opposing
            tickets into one number has changed what the account holds.
        """

    @abstractmethod
    def get_orders(self, symbol: SymbolName | None = None) -> Sequence[Order]:
        """Return orders still working at the venue.

        Args:
            symbol: Restrict to this instrument. Defaults to all instruments.

        Returns:
            Orders that have not reached a terminal state — those for which
            :attr:`~atlas.broker.models.OrderStatus.is_active` holds.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If ``symbol`` is given and not offered.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            Working orders only. Filled and cancelled orders are history, not
            state, and are outside this port for the same reason as closed
            positions.
        """

    @abstractmethod
    def get_open_positions(self) -> Sequence[Position]:
        """Return every open position.

        Returns:
            All open positions. Empty when the account is flat.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            The unfiltered case of :meth:`get_positions`, named for what it
            answers. Implementations must keep the two consistent: this must
            return what ``get_positions()`` returns with no argument.
        """

    # --- Risk -----------------------------------------------------------------

    @abstractmethod
    def margin_required(
        self, symbol: SymbolName, side: OrderSide, volume: Volume, price: Price | None = None
    ) -> NonNegativeMoney:
        """Return the margin the venue would take to open a position.

        Args:
            symbol: Instrument to be traded.
            side: Direction of the hypothetical position.
            volume: Size, in lots.
            price: Price to evaluate at. Defaults to the current market.

        Returns:
            The margin, in the account's currency. Never negative.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the instrument is not offered.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            The venue's own calculation, not a reimplementation of it. Margin
            rules vary by instrument, account, leverage tier, session and
            regulator, and an adapter that computed this itself would be
            confidently wrong at exactly the moment the number mattered.

            ``side`` is a parameter because it is not always symmetric: a venue
            that nets exposure may charge nothing to open a position that
            offsets one already held.
        """

    @abstractmethod
    def margin_available(self) -> Money:
        """Return the margin currently free for new positions.

        Returns:
            Free margin in the account's currency. May be negative on an
            account that is past its maintenance requirement.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            The live counterpart to
            :attr:`~atlas.broker.models.Account.free_margin`. Both exist
            because an account snapshot ages: for a decision about capacity
            right now, ask now.

            Signed, deliberately. Clamping a negative to zero would hide the
            one state a risk layer most needs to see.
        """

    @abstractmethod
    def can_trade(self, symbol: SymbolName) -> bool:
        """Report whether the venue would currently accept an order.

        Args:
            symbol: Instrument to check.

        Returns:
            ``True`` if the venue is accepting orders on this instrument for
            this account right now.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerSymbolNotFoundError: If the instrument is not offered.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            Venue permission only: market open, instrument enabled, account
            allowed to trade. It does not check margin — use
            :meth:`margin_required` against :meth:`margin_available` — and it
            knows nothing about Atlas risk policy, which is the risk layer's
            decision and not a broker's.

            A bare boolean loses the reason. When one is needed, read
            :attr:`~atlas.broker.models.Symbol.trade_mode` and
            :attr:`~atlas.broker.models.Account.trade_allowed`.
        """

    # --- Diagnostics ----------------------------------------------------------

    @abstractmethod
    def ping(self) -> bool:
        """Check whether the venue is answering.

        Returns:
            ``True`` if the venue responded to a round trip.

        Raises:
            BrokerError: Never. A liveness check that raises when the venue is
                down cannot be used in the supervision loop that exists to
                notice the venue is down. Every failure is reported as
                ``False``.

        Notes:
            Performs a real round trip, unlike :meth:`is_connected`, which
            reports local state. The cheapest call the venue offers is
            sufficient; the adapter chooses it.
        """

    @abstractmethod
    def latency(self) -> LatencyMilliseconds:
        """Measure the round-trip time to the venue.

        Returns:
            Milliseconds for one round trip.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerTimeoutError: If the venue did not answer in time. A
                measurement that would be unbounded is an error, not a very
                large number.

        Notes:
            Measures now. For the last observed value without a round trip,
            read :attr:`~atlas.broker.models.Connection.latency_ms` from
            :meth:`health`.
        """

    @abstractmethod
    def server_time(self) -> Timestamp:
        """Return the venue's current time.

        Returns:
            The venue's clock, timezone aware and normalised to UTC.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            Venues run their own clocks, and sessions, rollovers and swap
            charges are defined against them, not against the host's. The
            difference from local time is a real quantity and is often not a
            whole number of hours.

            Normalised to UTC like every other timestamp in the domain, so a
            caller comparing this with a bar's open time is comparing two
            instants rather than two wall clocks.
        """

    @abstractmethod
    def version(self) -> BrokerVersion:
        """Return the identity and build of the venue interface.

        Returns:
            Product name, version, and build where the venue exposes one.

        Raises:
            BrokerNotConnectedError: If no session is established.
            BrokerTimeoutError: If the venue did not answer in time.

        Notes:
            Structured rather than a bare string so that a caller can gate a
            workaround on a build number without parsing a venue-specific
            version format in business logic.
        """
