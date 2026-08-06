"""The in-memory venue that :class:`~atlas.broker.mock.adapter.MockBrokerAdapter` speaks to.

A :class:`MockVenue` holds everything a broker holds — instruments, quotes,
bars, an account, orders, positions, fills, a clock — and nothing else. It knows
no port method names except as fault-injection keys, performs no validation that
belongs to the port, and raises no :class:`~atlas.broker.exceptions.BrokerError`
of its own. Deciding what a caller of the port sees is the adapter's job; this
module is the state that decision is made against.

Why the state is a separate object
----------------------------------
A test asserting that ``place_order`` opened a position must be able to look at
the position *without* going through ``get_positions``. Using the adapter to
check the adapter is exactly the failure that mocking causes: both sides agree
because they are the same wrong belief. ``adapter.venue.positions()`` reads the
venue directly, so the two readings are independent and can disagree.

What this venue will not do
---------------------------
It invents no price. Every fill happens at a price the caller supplied — the
quote a test published, or the explicit argument to :meth:`fill`. Price
movement triggers nothing: a resting order does not fill because a quote
crossed it, because deciding *whether* it fills needs a policy (touch or cross,
fill at the limit or at the market, what a gap does, whether size is available)
that belongs to a backtest engine. A venue that picked one silently would make
every caller's tests agree with a rule nobody chose.

It books no accounting. Positions carry the profit, swap and commission they
were opened with — zero, zero and zero — until :meth:`revalue` says otherwise,
and the account changes only when :meth:`set_account` changes it. Deriving
profit needs the contract size, the rate from the quote currency to the deposit
currency, and the venue's rounding; a mock that guessed at those would produce
a strategy that appears to make money.

Both refusals are the same rule: this venue reports what it was told, and
declines to be the authority on anything it would have to invent.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from atlas.broker.adapter import BrokerAdapter
from atlas.broker.models import (
    Account,
    Execution,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSide,
)
from atlas.common.clock import ManualClock

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import timedelta

    from atlas.broker.exceptions import BrokerError
    from atlas.broker.models import (
        Candle,
        Money,
        Price,
        Symbol,
        Tick,
        Timeframe,
        Volume,
    )
    from atlas.broker.types import (
        CandleHandler,
        OrderID,
        OrderRequest,
        PositionID,
        SubscriptionID,
        SymbolName,
        TickHandler,
    )

__all__ = ["DEFAULT_ACCOUNT", "DEFAULT_START", "SERVER", "VENUE", "MockVenue"]

#: The brokerage name this venue reports.
VENUE: Final = "Mock Broker"

#: The trade server this venue reports.
SERVER: Final = "mock-server"

#: Where the venue clock starts.
#:
#: An arbitrary instant, chosen only because it is round and unambiguous. What
#: matters is that it does not move unless a test moves it: nothing in this
#: package reads the host clock, so a run at midnight on a leap day produces the
#: same timestamps as a run at noon.
DEFAULT_START: Final = datetime(2020, 1, 1, tzinfo=UTC)

#: A funded, unencumbered account, so a test needing one need not build twelve
#: fields to get there.
#:
#: Supplied because the alternative is worse. A test that only wants "an account
#: exists" will reach for :mod:`unittest.mock` rather than fill in a leverage
#: tier it does not care about, and that is the habit this package exists to
#: remove. Anything a test *does* care about it sets with
#: :meth:`MockVenue.set_account`.
DEFAULT_ACCOUNT: Final = Account(
    account_id="MOCK-1",
    broker=VENUE,
    server=SERVER,
    currency="USD",
    balance=Decimal(100_000),
    equity=Decimal(100_000),
    margin=Decimal(0),
    free_margin=Decimal(100_000),
    leverage=100,
    trade_allowed=True,
    timestamp=DEFAULT_START,
)

#: The round-trip time this venue reports until a test changes it.
DEFAULT_LATENCY_MS: Final = 1.0

#: Every port method, read off the port itself so the two cannot drift.
_PORT_OPERATIONS: Final = frozenset(BrokerAdapter.__abstractmethods__)

#: Port methods the contract forbids from raising.
#:
#: Scheduling a failure against one of these would queue an error that can never
#: be delivered, which is a silent test bug of exactly the kind this package
#: exists to prevent. ``ping`` is absent deliberately: it may not raise either,
#: but it *can* report the failure, as ``False``.
_UNFAILABLE_OPERATIONS: Final = frozenset(
    {"disconnect", "health", "is_connected", "unsubscribe_candles", "unsubscribe_ticks"}
)


@dataclass(frozen=True, slots=True)
class _TickSubscription:
    """A live quote subscription and who owns it."""

    subscription_id: str
    owner: object
    symbols: frozenset[str]
    handler: TickHandler


@dataclass(frozen=True, slots=True)
class _CandleSubscription:
    """A live bar subscription and who owns it."""

    subscription_id: str
    owner: object
    symbols: frozenset[str]
    timeframe: Timeframe
    handler: CandleHandler


def _canonical(code: str) -> str:
    """Normalise an instrument code the way the domain models do.

    Args:
        code: The code as a caller spelled it.

    Returns:
        The trimmed, upper-cased code, so that a lookup here agrees with the
        :data:`~atlas.broker.models.SymbolCode` stored on a model.
    """
    return code.strip().upper()


def _revised(order: Order, updates: Mapping[str, object]) -> Order:
    """Rebuild an order with some fields changed, revalidating the result.

    Args:
        order: The order as the venue currently holds it.
        updates: Fields to replace.

    Returns:
        The amended order.

    Raises:
        ValidationError: If the amendment produces an order the domain model
            rejects — a limit with no limit price, a volume of zero, timestamps
            that run backwards.

    Notes:
        ``model_copy`` is deliberately not used, here or anywhere in this
        package. It applies the update without revalidating, so an amendment
        that breaks the model's own coherence rules would be stored and would
        surface somewhere else entirely.
    """
    data = order.model_dump()
    data.update(updates)
    return Order.model_validate(data)


def _restated(position: Position, updates: Mapping[str, object]) -> Position:
    """Rebuild a position with some fields changed, revalidating the result.

    Args:
        position: The position as the venue currently holds it.
        updates: Fields to replace.

    Returns:
        The amended position.

    Raises:
        ValidationError: If the amendment produces a position the domain model
            rejects — a volume reduced to zero, a negative price.
    """
    data = position.model_dump()
    data.update(updates)
    return Position.model_validate(data)


class MockVenue:
    """A broker's worth of state, held in memory and driven by a test.

    Every mutating method is something a real venue does — publish a quote,
    accept an order, book a fill, close a position — and every one of them is
    driven explicitly rather than by the passage of time or the movement of a
    price. See the module docstring for why.

    Attributes:
        latency_ms: What :meth:`~atlas.broker.adapter.BrokerAdapter.latency`
            reports. A plain attribute because it is a dial, not state: set it
            to exercise a caller's latency threshold.
    """

    def __init__(
        self, *, account: Account = DEFAULT_ACCOUNT, now: datetime = DEFAULT_START
    ) -> None:
        """Build an empty venue.

        Args:
            account: The account this venue holds. Defaults to
                :data:`DEFAULT_ACCOUNT`.
            now: Where the venue clock starts. Must be timezone aware.

        Raises:
            ValueError: If ``now`` is naive. A naive start would make every
                timestamp this venue stamps depend on the host's zone.
        """
        self.latency_ms: float = DEFAULT_LATENCY_MS
        self._account = account
        self._clock = ManualClock(self._require_aware(now, "now"))
        self._symbols: dict[str, Symbol] = {}
        self._quotes: dict[str, Tick] = {}
        self._bars: dict[tuple[str, Timeframe], list[Candle]] = {}
        self._orders: dict[str, Order] = {}
        self._positions: dict[str, Position] = {}
        self._executions: list[Execution] = []
        self._tick_subscriptions: dict[str, _TickSubscription] = {}
        self._candle_subscriptions: dict[str, _CandleSubscription] = {}
        self._failures: dict[str, deque[BrokerError]] = {}
        self._handler_failures: list[BaseException] = []
        self._counters: dict[str, int] = {}

    # --- Internals ------------------------------------------------------------

    @staticmethod
    def _require_aware(value: datetime, name: str) -> datetime:
        """Reject a naive datetime and normalise an aware one to UTC.

        Args:
            value: The datetime supplied by the caller.
            name: Parameter name, for the message.

        Returns:
            The same instant, expressed in UTC.

        Raises:
            ValueError: If the datetime carries no offset.
        """
        if value.utcoffset() is None:
            msg = f"{name} must be timezone aware; got the naive value {value!r}"
            raise ValueError(msg)
        return value.astimezone(UTC)

    def _next_id(self, prefix: str) -> str:
        """Mint the next identifier in a series.

        Args:
            prefix: The series, which becomes the identifier's prefix.

        Returns:
            ``"<prefix>-<n>"``, counting from one. Sequential rather than random
            so that a failing test names the same ticket on every run.
        """
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        return f"{prefix}-{self._counters[prefix]}"

    def _require_symbol(self, code: str) -> str:
        """Assert that an instrument is registered, and canonicalise its code.

        Args:
            code: The instrument code.

        Returns:
            The canonical code.

        Raises:
            ValueError: If no such instrument has been added. Publishing market
                data for an instrument the venue does not offer is a fault in
                the test, not a condition the port describes, so it is a
                ``ValueError`` rather than a broker error.
        """
        canonical = _canonical(code)
        if canonical not in self._symbols:
            msg = f"no instrument {canonical!r} is registered; call add_symbol first"
            raise ValueError(msg)
        return canonical

    def _deliver_tick(self, subscription: _TickSubscription, tick: Tick) -> None:
        """Hand a quote to one subscriber, absorbing anything it throws.

        Args:
            subscription: The subscription being served.
            tick: The quote to deliver.

        Notes:
            The port requires that an exception escaping a handler must not kill
            the subscription. Absorbing it silently would be the other half of
            that trade, so the exception is recorded on
            :attr:`handler_failures` and a test can assert on it.
        """
        try:
            subscription.handler(tick)
        except Exception as failure:  # the port forbids this from killing the subscription
            self._handler_failures.append(failure)

    def _deliver_candle(self, subscription: _CandleSubscription, candle: Candle) -> None:
        """Hand a bar to one subscriber, absorbing anything it throws.

        Args:
            subscription: The subscription being served.
            candle: The bar to deliver.
        """
        try:
            subscription.handler(candle)
        except Exception as failure:  # the port forbids this from killing the subscription
            self._handler_failures.append(failure)

    # --- Clock ----------------------------------------------------------------

    @property
    def clock(self) -> ManualClock:
        """The venue's clock, which its adapter also runs on.

        A :class:`~atlas.common.clock.ManualClock`, so it moves only when this
        venue's :meth:`advance` or :meth:`set_time` moves it. Exposed because
        :class:`~atlas.broker.mock.adapter.MockBrokerAdapter` hands it to
        :class:`~atlas.broker.base.BaseBrokerAdapter` as *its* clock: one notion
        of now for the venue and the adapter in front of it, rather than two
        that can disagree about how long ago a heartbeat was.
        """
        return self._clock

    def now(self) -> datetime:
        """Return the venue's current time.

        Returns:
            The venue clock, aware and in UTC. Nothing in this package reads the
            host clock, so this is the only notion of "now" the mock has.
        """
        return self._clock.now()

    def set_time(self, moment: datetime) -> None:
        """Move the venue clock to an instant.

        Args:
            moment: Where to set it. Must be timezone aware.

        Raises:
            ValueError: If ``moment`` is naive.

        Notes:
            A jump rather than time passing, which is the distinction
            :class:`~atlas.common.clock.ManualClock` draws: this moves what the
            venue calls "now" and credits no elapsed time, so a heartbeat's age
            is unaffected. Use :meth:`advance` to make time pass.
        """
        self._clock.set_time(self._require_aware(moment, "moment"))

    def advance(self, delta: timedelta) -> datetime:
        """Move the venue clock forwards.

        Args:
            delta: How far forwards. Must not be negative.

        Returns:
            The new venue time.

        Raises:
            ValueError: If ``delta`` is negative. A clock that runs backwards
                produces orders that were updated before they were created, and
                the domain model rejects those several steps later.

        Notes:
            Time passing, so a heartbeat recorded before this call is exactly
            ``delta`` older after it. That is what makes a test for a timeout
            measured in hours run instantly and assert an exact number.
        """
        if delta.total_seconds() < 0:
            msg = f"delta must not be negative; got {delta!r}"
            raise ValueError(msg)
        return self._clock.advance(delta)

    # --- Account --------------------------------------------------------------

    @property
    def account(self) -> Account:
        """The account this venue holds."""
        return self._account

    def set_account(self, account: Account) -> None:
        """Replace the account.

        Args:
            account: The new state. Its ``timestamp`` is kept as given rather
                than restamped: it says when the state was established, and this
                venue does not change it behind a test's back.
        """
        self._account = account

    # --- Instruments ----------------------------------------------------------

    def add_symbol(self, symbol: Symbol) -> None:
        """Register an instrument, replacing any registration under the same code.

        Args:
            symbol: The instrument's dealing terms.
        """
        self._symbols[symbol.symbol] = symbol

    def symbol(self, code: SymbolName) -> Symbol | None:
        """Look up one instrument.

        Args:
            code: The instrument code. Matching is case-insensitive.

        Returns:
            The instrument, or ``None`` if it is not registered.
        """
        return self._symbols.get(_canonical(code))

    def symbols(self) -> tuple[Symbol, ...]:
        """List every registered instrument.

        Returns:
            The instruments, ordered by code so that two runs agree.
        """
        return tuple(self._symbols[code] for code in sorted(self._symbols))

    # --- Market data ----------------------------------------------------------

    def publish_tick(self, tick: Tick) -> None:
        """Publish a quote and deliver it to every subscriber watching it.

        Args:
            tick: The quote.

        Raises:
            ValueError: If the instrument is not registered.

        Notes:
            Delivery is synchronous, on the calling thread. The port permits it
            — a handler "may be called on a thread the caller does not own" — and
            a test that must reason about ordering gets a deterministic one.
        """
        code = self._require_symbol(tick.symbol)
        self._quotes[code] = tick
        for subscription in tuple(self._tick_subscriptions.values()):
            if code in subscription.symbols:
                self._deliver_tick(subscription, tick)

    def quote(self, code: SymbolName) -> Tick | None:
        """Return the last quote published for an instrument.

        Args:
            code: The instrument code.

        Returns:
            The quote, or ``None`` if none has been published.
        """
        return self._quotes.get(_canonical(code))

    def publish_candle(self, candle: Candle) -> None:
        """Publish a bar and deliver it to every subscriber watching it.

        Args:
            candle: The bar. A bar whose open time matches one already held
                replaces it, which is how a forming bar is updated.

        Raises:
            ValueError: If the instrument is not registered.
        """
        code = self._require_symbol(candle.symbol)
        key = (code, candle.timeframe)
        series = [bar for bar in self._bars.get(key, ()) if bar.open_time != candle.open_time]
        series.append(candle)
        series.sort(key=lambda bar: bar.open_time)
        self._bars[key] = series
        for subscription in tuple(self._candle_subscriptions.values()):
            if code in subscription.symbols and subscription.timeframe is candle.timeframe:
                self._deliver_candle(subscription, candle)

    def candles(self, code: SymbolName, timeframe: Timeframe) -> tuple[Candle, ...]:
        """Return every bar held for one instrument and timeframe.

        Args:
            code: The instrument code.
            timeframe: The bar length.

        Returns:
            The bars, oldest first, forming and closed alike.
        """
        return tuple(self._bars.get((_canonical(code), timeframe), ()))

    # --- Subscriptions --------------------------------------------------------

    def open_tick_subscription(
        self, owner: object, symbols: Sequence[SymbolName], handler: TickHandler
    ) -> SubscriptionID:
        """Register a quote subscription.

        Args:
            owner: Whoever the subscription belongs to, so that one adapter's
                disconnect cannot cancel another's stream.
            symbols: Instrument codes to watch.
            handler: Called once per matching quote.

        Returns:
            The subscription handle.
        """
        subscription_id = self._next_id("tick-sub")
        self._tick_subscriptions[subscription_id] = _TickSubscription(
            subscription_id=subscription_id,
            owner=owner,
            symbols=frozenset(_canonical(code) for code in symbols),
            handler=handler,
        )
        return subscription_id

    def open_candle_subscription(
        self,
        owner: object,
        symbols: Sequence[SymbolName],
        timeframe: Timeframe,
        handler: CandleHandler,
    ) -> SubscriptionID:
        """Register a bar subscription.

        Args:
            owner: Whoever the subscription belongs to.
            symbols: Instrument codes to watch.
            timeframe: The bar length to watch.
            handler: Called once per matching bar.

        Returns:
            The subscription handle.
        """
        subscription_id = self._next_id("candle-sub")
        self._candle_subscriptions[subscription_id] = _CandleSubscription(
            subscription_id=subscription_id,
            owner=owner,
            symbols=frozenset(_canonical(code) for code in symbols),
            timeframe=timeframe,
            handler=handler,
        )
        return subscription_id

    def close_subscription(self, owner: object, subscription_id: SubscriptionID) -> None:
        """Cancel one subscription, if it exists and belongs to this owner.

        Args:
            owner: Whoever is cancelling.
            subscription_id: The handle to cancel.

        Notes:
            Silent for an unknown handle, one already cancelled, and one
            belonging to somebody else. The port requires the unsubscribe
            methods never to raise, and a cleanup path cannot always know what
            is still live.
        """
        tick = self._tick_subscriptions.get(subscription_id)
        if tick is not None and tick.owner is owner:
            del self._tick_subscriptions[subscription_id]
        candle = self._candle_subscriptions.get(subscription_id)
        if candle is not None and candle.owner is owner:
            del self._candle_subscriptions[subscription_id]

    def close_subscriptions(self, owner: object) -> None:
        """Cancel every subscription belonging to one owner.

        Args:
            owner: Whose subscriptions to drop.
        """
        for tick_id, tick in tuple(self._tick_subscriptions.items()):
            if tick.owner is owner:
                del self._tick_subscriptions[tick_id]
        for candle_id, candle in tuple(self._candle_subscriptions.items()):
            if candle.owner is owner:
                del self._candle_subscriptions[candle_id]

    def subscription_ids(self) -> tuple[SubscriptionID, ...]:
        """List every live subscription handle.

        Returns:
            The handles, quote subscriptions first, each group in the order it
            was opened.
        """
        return (*self._tick_subscriptions, *self._candle_subscriptions)

    @property
    def handler_failures(self) -> tuple[BaseException, ...]:
        """Everything a subscription handler has thrown, in the order it threw.

        Recorded rather than swallowed. The port requires a handler's exception
        not to kill its subscription; it does not require the exception to
        disappear, and a stream that silently drops every update because the
        handler throws on each one is a bug a test should be able to see.
        """
        return tuple(self._handler_failures)

    # --- Orders, positions and fills ------------------------------------------

    def submit(self, request: OrderRequest, *, price: Price | None = None) -> Order:
        """Record a new working order.

        Args:
            request: What was asked for.
            price: The indicative price to stamp on a MARKET order, which has no
                working price of its own. Ignored on every other type, whose
                price comes from the request.

        Returns:
            The order as the venue now holds it, ``PENDING`` and unfilled.
        """
        working_price = request.price if request.type is not OrderType.MARKET else price
        order = Order(
            order_id=self._next_id("order"),
            symbol=request.symbol,
            side=request.side,
            type=request.type,
            volume=request.volume,
            price=working_price,
            stop_price=request.stop_price,
            status=OrderStatus.PENDING,
            created_at=self.now(),
            updated_at=self.now(),
        )
        self._orders[order.order_id] = order
        return order

    def fill(self, order_id: OrderID, price: Price) -> Execution:
        """Fill a working order in full, at a price the caller names.

        Args:
            order_id: The order to fill.
            price: The price it fills at. Nothing here derives one: a limit
                order does not fill because a quote reached it, so the only
                honest source of a fill price is the caller.

        Returns:
            The resulting fill.

        Raises:
            ValueError: If the order is unknown or has already reached a
                terminal state. Both are faults in the test rather than
                conditions the port describes.

        Notes:
            Partial fills are not modelled.
            :class:`~atlas.broker.models.Order` carries no filled quantity, so a
            ``PARTIALLY_FILLED`` order would tell a caller that some unknowable
            amount had traded. Fill twice against two orders instead.
        """
        order = self._orders.get(order_id)
        if order is None:
            msg = f"no order {order_id!r} exists"
            raise ValueError(msg)
        if order.status.is_terminal:
            msg = f"order {order_id!r} is already {order.status} and cannot fill"
            raise ValueError(msg)

        self._orders[order_id] = _revised(
            order, {"status": OrderStatus.FILLED, "updated_at": self.now()}
        )
        position = Position(
            position_id=self._next_id("position"),
            symbol=order.symbol,
            side=PositionSide.LONG if order.side is OrderSide.BUY else PositionSide.SHORT,
            volume=order.volume,
            entry_price=price,
            current_price=price,
            profit=Decimal(0),
            swap=Decimal(0),
            commission=Decimal(0),
            opened_at=self.now(),
        )
        self._positions[position.position_id] = position
        return self._book(order_id, order.symbol, price, order.volume)

    def close(
        self, position_id: PositionID, price: Price, volume: Volume | None = None
    ) -> Execution:
        """Close a position, in whole or in part, at a price the caller names.

        Args:
            position_id: The position to close.
            price: The price it closes at.
            volume: How much to close. Defaults to the whole position.

        Returns:
            The closing fill.

        Raises:
            ValueError: If the position is unknown, or ``volume`` exceeds what
                is open.

        Notes:
            A closing order is recorded alongside the fill, on the opposite
            side and already ``FILLED``, because that is what the venue actually
            did and it keeps :meth:`orders` a complete history.
        """
        position = self._positions.get(position_id)
        if position is None:
            msg = f"no position {position_id!r} exists"
            raise ValueError(msg)
        closing = position.volume if volume is None else volume
        if closing > position.volume:
            msg = (
                f"cannot close {closing} of position {position_id!r}, "
                f"which holds {position.volume}"
            )
            raise ValueError(msg)

        order = Order(
            order_id=self._next_id("order"),
            symbol=position.symbol,
            side=OrderSide.SELL if position.side is PositionSide.LONG else OrderSide.BUY,
            type=OrderType.MARKET,
            volume=closing,
            price=price,
            status=OrderStatus.FILLED,
            created_at=self.now(),
            updated_at=self.now(),
        )
        self._orders[order.order_id] = order

        if closing == position.volume:
            del self._positions[position_id]
        else:
            self._positions[position_id] = _restated(
                position, {"volume": position.volume - closing}
            )
        return self._book(order.order_id, position.symbol, price, closing)

    def _book(self, order_id: str, symbol: str, price: Price, volume: Volume) -> Execution:
        """Record one fill.

        Args:
            order_id: The order that transacted.
            symbol: The instrument.
            price: The price it transacted at.
            volume: The quantity.

        Returns:
            The execution, which is also appended to :meth:`executions`.

        Notes:
            Commission and swap are zero because this venue charges neither.
            That is a property of the venue, stated once here, and not a
            placeholder: a test that needs a costed fill sets the numbers it
            wants on the position with :meth:`revalue`.
        """
        execution = Execution(
            execution_id=self._next_id("execution"),
            order_id=order_id,
            symbol=symbol,
            price=price,
            volume=volume,
            commission=Decimal(0),
            swap=Decimal(0),
            timestamp=self.now(),
        )
        self._executions.append(execution)
        return execution

    def cancel(self, order_id: OrderID) -> Order:
        """Cancel a working order.

        Args:
            order_id: The order to cancel.

        Returns:
            The order, now ``CANCELLED``.

        Raises:
            ValueError: If the order is unknown or already terminal.
        """
        order = self._orders.get(order_id)
        if order is None:
            msg = f"no order {order_id!r} exists"
            raise ValueError(msg)
        if order.status.is_terminal:
            msg = f"order {order_id!r} is already {order.status} and cannot be cancelled"
            raise ValueError(msg)
        cancelled = _revised(order, {"status": OrderStatus.CANCELLED, "updated_at": self.now()})
        self._orders[order_id] = cancelled
        return cancelled

    def store_order(self, order: Order) -> None:
        """Replace the venue's record of one order.

        Args:
            order: The order as it now stands.
        """
        self._orders[order.order_id] = order

    def amend(self, order_id: OrderID, updates: Mapping[str, object]) -> Order:
        """Change some fields of a working order.

        Args:
            order_id: The order to amend.
            updates: Fields to replace. ``updated_at`` is set from the venue
                clock and cannot be supplied here, because the venue is the only
                party that knows when it accepted the change.

        Returns:
            The order as it now stands.

        Raises:
            ValueError: If the order is unknown.
            ValidationError: If the amendment produces an order the domain model
                rejects. Left to escape rather than translated: what a *venue*
                makes of a bad amendment is the adapter's judgement, not this
                object's.
        """
        order = self.require_order(order_id)
        revised = _revised(order, {**updates, "updated_at": self.now()})
        self._orders[order_id] = revised
        return revised

    def revalue(
        self,
        position_id: PositionID,
        *,
        current_price: Price | None = None,
        profit: Money | None = None,
        swap: Money | None = None,
        commission: Money | None = None,
    ) -> Position:
        """Restate a position's mark-to-market figures.

        Args:
            position_id: The position to restate.
            current_price: The price it is now valued at.
            profit: Unrealised profit in the deposit currency.
            swap: Financing accrued so far.
            commission: Commission charged on the position.

        Returns:
            The position as it now stands.

        Raises:
            ValueError: If the position is unknown.

        Notes:
            This is the only way a position's valuation changes. The venue does
            not revalue on a published quote, because profit in the deposit
            currency needs the contract size, a conversion rate and the venue's
            rounding, and inventing those would make the mock the one thing it
            exists to replace: a thing that agrees with whatever is asserted.
        """
        position = self._positions.get(position_id)
        if position is None:
            msg = f"no position {position_id!r} exists"
            raise ValueError(msg)
        updates = {
            name: value
            for name, value in (
                ("current_price", current_price),
                ("profit", profit),
                ("swap", swap),
                ("commission", commission),
            )
            if value is not None
        }
        revalued = _restated(position, updates)
        self._positions[position_id] = revalued
        return revalued

    def order(self, order_id: OrderID) -> Order | None:
        """Look up one order, whatever state it is in.

        Args:
            order_id: The ticket.

        Returns:
            The order, or ``None`` if the venue has never seen it.
        """
        return self._orders.get(order_id)

    def require_order(self, order_id: OrderID) -> Order:
        """Look up one order, insisting it exists.

        Args:
            order_id: The ticket.

        Returns:
            The order.

        Raises:
            ValueError: If the venue has never seen it.
        """
        order = self._orders.get(order_id)
        if order is None:
            msg = f"no order {order_id!r} exists"
            raise ValueError(msg)
        return order

    def orders(self) -> tuple[Order, ...]:
        """List every order the venue has seen, working and finished alike.

        Returns:
            The orders, in the sequence they were created.
        """
        return tuple(self._orders.values())

    def position(self, position_id: PositionID) -> Position | None:
        """Look up one open position.

        Args:
            position_id: The ticket.

        Returns:
            The position, or ``None`` if it is unknown or already closed.
        """
        return self._positions.get(position_id)

    def require_position(self, position_id: PositionID) -> Position:
        """Look up one open position, insisting it exists.

        Args:
            position_id: The ticket.

        Returns:
            The position.

        Raises:
            ValueError: If it is unknown or already closed.
        """
        position = self._positions.get(position_id)
        if position is None:
            msg = f"no position {position_id!r} exists"
            raise ValueError(msg)
        return position

    def positions(self) -> tuple[Position, ...]:
        """List every open position.

        Returns:
            The positions, in the sequence they were opened.
        """
        return tuple(self._positions.values())

    def executions(self) -> tuple[Execution, ...]:
        """List every fill the venue has booked.

        Returns:
            The fills, oldest first. Append-only, as the model requires.
        """
        return tuple(self._executions)

    # --- Fault injection ------------------------------------------------------

    def schedule_failure(self, operation: str, error: BrokerError) -> None:
        """Arrange for the next call to one port method to fail.

        Args:
            operation: The port method, by name.
            error: What it should raise.

        Raises:
            ValueError: If ``operation`` is not a port method, or is one the
                port forbids from raising.

        Notes:
            This exists so that a caller's ``except BrokerTimeoutError`` branch
            can be tested without :mod:`unittest.mock`, which would otherwise be
            the only way to reach it and would take the adapter's real behaviour
            with it.

            Failures queue. Scheduling three makes the next three calls fail, in
            order, after which the method behaves normally again. The name is
            checked against the port's own method inventory because a typo would
            otherwise queue an error that never fires, and a test asserting on a
            failure that cannot happen passes for the wrong reason.
        """
        if operation not in _PORT_OPERATIONS:
            msg = f"{operation!r} is not a BrokerAdapter method"
            raise ValueError(msg)
        if operation in _UNFAILABLE_OPERATIONS:
            msg = (
                f"the port forbids {operation} from raising, so a failure "
                "scheduled against it could never fire"
            )
            raise ValueError(msg)
        self._failures.setdefault(operation, deque()).append(error)

    def take_failure(self, operation: str) -> BrokerError | None:
        """Take the next scheduled failure for one port method, if any.

        Args:
            operation: The port method, by name.

        Returns:
            The error to raise, removed from the queue, or ``None`` when nothing
            is scheduled.
        """
        queued = self._failures.get(operation)
        if not queued:
            return None
        return queued.popleft()

    def scheduled_failures(self, operation: str) -> tuple[BrokerError, ...]:
        """List the failures still queued against one port method.

        Args:
            operation: The port method, by name.

        Returns:
            The queued errors, next one first.
        """
        return tuple(self._failures.get(operation, ()))
