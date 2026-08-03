"""Translation from MetaTrader 5 structures into Atlas broker domain models.

This module is where MetaTrader 5 stops. Everything above it sees only
:mod:`atlas.broker.models` types, and every function here is a pure function of
its arguments: no terminal call, no clock read, no global state. That is what
makes the translation testable against hand-built structures rather than
against a running terminal, and it is why the adapter passes in the things a
mapper would otherwise have to reach for — the observation time, the closed
flag, the commission.

The MetaTrader 5 structures arrive as named tuples and NumPy records, neither
of which carries type information. Rather than accept ``Any``, each one is
described by a :class:`~typing.Protocol` below that names exactly the fields
Atlas reads. Those protocols are the real specification of Atlas's dependency
on the vendor package: anything not named there is not used, and a field the
vendor renames breaks a declared contract instead of failing at an attribute
lookup three layers away.

Three conversions are not obvious and are the ones worth knowing about:

Decimal by way of ``str``
    ``Decimal(0.1)`` is the binary expansion of a float and carries fifty
    digits of noise. ``Decimal(str(0.1))`` is ``Decimal("0.1")``. Every price
    crossing this boundary takes the second route.

Zero means absent
    MetaTrader 5 has no null. An unset stop loss, take profit or last-trade
    price is reported as ``0.0``, which the domain models would accept as a
    real price of zero. :func:`_optional_price` maps it back to ``None``.

Server time is not UTC
    A MetaTrader 5 timestamp is the *server's* wall clock encoded as a Unix
    epoch, so a terminal on a UTC+3 server reports 12:00 UTC+3 as the epoch for
    12:00 UTC. Read naively, every bar and every tick is silently wrong by the
    server's offset. :class:`ServerClock` is the one place that correction
    happens, and it is mandatory rather than defaulted at each call site.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from atlas.broker.models import (
    Account,
    Candle,
    Execution,
    Order,
    Position,
    Symbol,
    Tick,
)
from atlas.broker.mt5.constants import (
    MT5_ORDER_STATE_TO_STATUS,
    MT5_ORDER_TYPE_TO_DOMAIN,
    MT5_POSITION_TYPE_TO_SIDE,
    MT5_TRADE_MODE_TO_DOMAIN,
)
from atlas.broker.types import BrokerVersion

if TYPE_CHECKING:
    from atlas.broker.models import Money, OrderType, Timeframe

__all__ = [
    "MT5AccountInfo",
    "MT5Deal",
    "MT5Order",
    "MT5Position",
    "MT5RateRow",
    "MT5SymbolInfo",
    "MT5Tick",
    "ServerClock",
    "to_account",
    "to_broker_version",
    "to_candle",
    "to_decimal",
    "to_execution",
    "to_order",
    "to_position",
    "to_symbol",
    "to_tick",
]

#: MetaTrader 5 reports an unset price field as this value rather than as null.
_ABSENT = 0.0


# --- Time ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ServerClock:
    """Converts a MetaTrader 5 timestamp into a genuine UTC instant.

    A MetaTrader 5 timestamp is the trade server's local wall clock expressed
    as a Unix epoch. On a UTC+3 server — the default for a large share of
    retail brokers — the epoch reported for a bar that opened at 12:00 server
    time is the epoch of 12:00 UTC, three hours later than the instant that bar
    actually opened.

    Nothing in the terminal API reports the offset, so it cannot be discovered
    and must be configured. The default of zero is correct only for a server
    that publishes UTC; it is the default because a wrong non-zero guess is
    worse than an explicit "not configured", and because it makes the
    conversion the identity for anyone who has verified their server runs UTC.

    Attributes:
        offset: How far the trade server's clock runs ahead of UTC. A UTC+3
            server has an offset of three hours.
    """

    offset: timedelta = field(default=timedelta(0))

    def to_utc(self, server_epoch_seconds: float) -> datetime:
        """Convert a whole-second MetaTrader 5 timestamp to UTC.

        Args:
            server_epoch_seconds: The value of a ``time`` field.

        Returns:
            The corresponding aware UTC datetime.
        """
        return datetime.fromtimestamp(server_epoch_seconds, tz=UTC) - self.offset

    def to_utc_from_milliseconds(self, server_epoch_milliseconds: float) -> datetime:
        """Convert a millisecond MetaTrader 5 timestamp to UTC.

        Args:
            server_epoch_milliseconds: The value of a ``time_msc`` field.

        Returns:
            The corresponding aware UTC datetime, to millisecond resolution.
        """
        return self.to_utc(server_epoch_milliseconds / 1000)

    def from_utc(self, instant: datetime) -> float:
        """Convert a UTC instant into the epoch the terminal expects.

        The inverse of :meth:`to_utc`, needed because history requests are
        expressed as boundaries and the terminal reads a boundary in the same
        distorted encoding it writes bar times in. Asking a UTC+3 server for
        bars "from 12:00 UTC" without this correction quietly requests bars from
        09:00 UTC.

        Args:
            instant: An aware datetime.

        Returns:
            The epoch value to hand to a ``copy_rates_range`` boundary.
        """
        return (instant + self.offset).timestamp()


# --- The vendor surface Atlas depends on --------------------------------------


@runtime_checkable
class MT5AccountInfo(Protocol):
    """The fields Atlas reads from ``MetaTrader5.account_info()``."""

    login: int
    company: str
    server: str
    currency: str
    balance: float
    equity: float
    margin: float
    margin_free: float
    margin_level: float
    leverage: int
    trade_allowed: bool


@runtime_checkable
class MT5SymbolInfo(Protocol):
    """The fields Atlas reads from ``MetaTrader5.symbol_info()``."""

    name: str
    description: str
    currency_base: str
    currency_profit: str
    digits: int
    point: float
    trade_tick_size: float
    trade_contract_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    spread: int
    trade_mode: int


@runtime_checkable
class MT5Tick(Protocol):
    """The fields Atlas reads from ``MetaTrader5.symbol_info_tick()``."""

    time: int
    time_msc: int
    bid: float
    ask: float
    last: float
    volume: int
    volume_real: float


class MT5RateRow(Protocol):
    """One row of the array ``MetaTrader5.copy_rates_*`` returns.

    A NumPy record rather than a named tuple, so its fields are reached by
    subscript. A plain ``dict`` satisfies this protocol, which is what lets the
    candle tests run without NumPy.
    """

    def __getitem__(self, key: str, /) -> float:
        """Return the named field of the row."""
        ...


@runtime_checkable
class MT5Position(Protocol):
    """The fields Atlas reads from ``MetaTrader5.positions_get()``."""

    ticket: int
    symbol: str
    type: int
    volume: float
    price_open: float
    price_current: float
    profit: float
    swap: float
    time_msc: int


@runtime_checkable
class MT5Order(Protocol):
    """The fields Atlas reads from ``MetaTrader5.orders_get()``."""

    ticket: int
    symbol: str
    type: int
    state: int
    volume_initial: float
    price_open: float
    price_stoplimit: float
    sl: float
    tp: float
    time_setup_msc: int
    time_done_msc: int


@runtime_checkable
class MT5Deal(Protocol):
    """The fields Atlas reads from ``MetaTrader5.history_deals_get()``."""

    ticket: int
    order: int
    symbol: str
    price: float
    volume: float
    commission: float
    swap: float
    time_msc: int


# --- Scalar conversion --------------------------------------------------------


def to_decimal(value: float) -> Decimal:
    """Convert a MetaTrader 5 number to an exact decimal.

    Args:
        value: A float or int from a terminal structure.

    Returns:
        The decimal of the value's shortest round-trip representation, so that
        ``0.1`` becomes ``Decimal("0.1")`` and not its binary expansion.
    """
    return Decimal(str(value))


def _optional_price(value: float) -> Decimal | None:
    """Convert a price field that MetaTrader 5 reports as zero when unset.

    Args:
        value: A price field such as ``sl``, ``tp`` or ``last``.

    Returns:
        The decimal price, or ``None`` where the terminal reported zero.
    """
    return None if value == _ABSENT else to_decimal(value)


# --- Structures ---------------------------------------------------------------


def to_account(raw: MT5AccountInfo, observed_at: datetime) -> Account:
    """Translate terminal account information into an :class:`Account`.

    Args:
        raw: The structure returned by ``account_info()``.
        observed_at: When the snapshot was taken. Supplied by the caller
            because ``account_info()`` carries no timestamp of its own, and a
            mapper that read the clock itself would not be a pure function.

    Returns:
        The account snapshot.

    Notes:
        MetaTrader 5 reports a margin level of ``0.0`` on an account with no
        open position, where the ratio is in fact undefined. Passed through, it
        reads as the most severe margin call representable and fires every rule
        of the form ``margin_level < threshold`` on a flat account. It is
        mapped to ``None`` here, which is the case the domain model requires.
    """
    margin = to_decimal(raw.margin)
    return Account(
        account_id=str(raw.login),
        broker=raw.company,
        server=raw.server,
        currency=raw.currency,
        balance=to_decimal(raw.balance),
        equity=to_decimal(raw.equity),
        margin=margin,
        free_margin=to_decimal(raw.margin_free),
        margin_level=None if margin == 0 else to_decimal(raw.margin_level),
        leverage=raw.leverage,
        trade_allowed=raw.trade_allowed,
        timestamp=observed_at,
    )


def to_symbol(raw: MT5SymbolInfo) -> Symbol:
    """Translate a terminal symbol specification into a :class:`Symbol`.

    Args:
        raw: The structure returned by ``symbol_info()``.

    Returns:
        The instrument's dealing terms.

    Raises:
        ValueError: If the terminal reports a trade mode Atlas does not model,
            or if the contract terms fail the domain model's coherence rules —
            most often a ``point`` that does not equal ``10 ** -digits``.

    Notes:
        ``currency_profit`` is the quote currency, not ``currency_margin``:
        profit on EURUSD is denominated in USD, which is what the price is
        expressed in. ``currency_margin`` is what the venue takes collateral
        in, and on some instruments it is neither leg of the pair.
    """
    trade_mode = MT5_TRADE_MODE_TO_DOMAIN.get(raw.trade_mode)
    if trade_mode is None:
        msg = f"unknown MetaTrader 5 symbol trade mode {raw.trade_mode!r} for {raw.name!r}"
        raise ValueError(msg)

    return Symbol(
        symbol=raw.name,
        description=raw.description,
        base_currency=raw.currency_base,
        quote_currency=raw.currency_profit,
        digits=raw.digits,
        point=to_decimal(raw.point),
        tick_size=to_decimal(raw.trade_tick_size),
        contract_size=to_decimal(raw.trade_contract_size),
        min_volume=to_decimal(raw.volume_min),
        max_volume=to_decimal(raw.volume_max),
        volume_step=to_decimal(raw.volume_step),
        spread=raw.spread,
        trade_mode=trade_mode,
    )


def to_tick(raw: MT5Tick, symbol: str, clock: ServerClock) -> Tick:
    """Translate a terminal quote into a :class:`Tick`.

    Args:
        raw: The structure returned by ``symbol_info_tick()``.
        symbol: Instrument the quote belongs to. Supplied by the caller because
            the terminal's tick structure does not name its own instrument.
        clock: Converts the server's clock to UTC.

    Returns:
        The quote.

    Notes:
        ``time_msc`` is preferred over ``time``: both describe the same quote,
        but the second-resolution field cannot distinguish two updates within
        the same second, which is ordinary in liquid instruments. The
        whole-second field is used only when the terminal leaves ``time_msc``
        unset.

        ``volume_real`` is preferred over ``volume`` for the same reason — it
        is the same quantity carried at higher precision — and spot FX feeds
        routinely report zero for both, which the domain model allows.
    """
    timestamp = (
        clock.to_utc(raw.time)
        if raw.time_msc == 0
        else clock.to_utc_from_milliseconds(raw.time_msc)
    )
    volume = raw.volume_real if raw.volume_real != _ABSENT else raw.volume

    return Tick(
        symbol=symbol,
        bid=to_decimal(raw.bid),
        ask=to_decimal(raw.ask),
        last=_optional_price(raw.last),
        volume=to_decimal(volume),
        timestamp=timestamp,
    )


def to_candle(
    raw: MT5RateRow,
    symbol: str,
    timeframe: Timeframe,
    clock: ServerClock,
    *,
    is_closed: bool,
) -> Candle:
    """Translate one row of a terminal rate array into a :class:`Candle`.

    Args:
        raw: One row of the array ``copy_rates_*`` returned.
        symbol: Instrument the bar aggregates. Supplied by the caller because
            the rate array does not carry it.
        timeframe: Aggregation period. Supplied for the same reason.
        clock: Converts the server's clock to UTC.
        is_closed: Whether the period has ended. Determined by the caller, which
            is the only party that knows whether it asked for the forming bar.

    Returns:
        The bar.

    Notes:
        MetaTrader 5 reports only the opening time of a bar. The closing time
        is derived by adding the timeframe's nominal duration, which is what
        makes it nominal: a daily bar spanning a daylight-saving transition
        closes an hour away from the derived value. The alternative — leaving
        it unset — is not available, because the domain model requires it.

        ``tick_volume`` is used rather than ``real_volume``. Retail FX feeds
        report zero real volume because no exchange publishes size for a
        decentralised market, so the count of price changes is the only volume
        proxy that carries information.
    """
    open_time = clock.to_utc(raw["time"])
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        open=to_decimal(raw["open"]),
        high=to_decimal(raw["high"]),
        low=to_decimal(raw["low"]),
        close=to_decimal(raw["close"]),
        volume=to_decimal(raw["tick_volume"]),
        open_time=open_time,
        close_time=open_time + timeframe.duration,
        is_closed=is_closed,
    )


def to_position(raw: MT5Position, clock: ServerClock, commission: Money) -> Position:
    """Translate an open terminal position into a :class:`Position`.

    Args:
        raw: The structure returned by ``positions_get()``.
        clock: Converts the server's clock to UTC.
        commission: Commission charged on the position. Required rather than
            defaulted because MetaTrader 5 does not report it on a position at
            all — it is charged against the opening *deal* — so the value can
            only come from the caller, and a silent default of zero would
            understate the cost of every position in the system.

    Returns:
        The position.

    Raises:
        ValueError: If the terminal reports a position type Atlas does not
            model.

    Notes:
        The domain model has no stop-loss or take-profit field, so the
        terminal's ``sl`` and ``tp`` are dropped here. They describe pending
        instructions attached to the position rather than exposure held, and
        the layer that manages them reads them from the order.
    """
    side = MT5_POSITION_TYPE_TO_SIDE.get(raw.type)
    if side is None:
        msg = f"unknown MetaTrader 5 position type {raw.type!r} on ticket {raw.ticket!r}"
        raise ValueError(msg)

    return Position(
        position_id=str(raw.ticket),
        symbol=raw.symbol,
        side=side,
        volume=to_decimal(raw.volume),
        entry_price=to_decimal(raw.price_open),
        current_price=to_decimal(raw.price_current),
        profit=to_decimal(raw.profit),
        swap=to_decimal(raw.swap),
        commission=commission,
        opened_at=clock.to_utc_from_milliseconds(raw.time_msc),
    )


def _working_prices(raw: MT5Order, order_type: OrderType) -> tuple[Decimal | None, Decimal | None]:
    """Split a terminal order's prices into the domain's price and stop price.

    MetaTrader 5 and Atlas disagree about which field holds which price on a
    stop-limit order, and only on a stop-limit order. MetaTrader 5 puts the
    *trigger* in ``price_open`` and the *limit* in ``price_stoplimit``; Atlas
    puts the limit in ``price`` and the trigger in ``stop_price``. Getting this
    backwards produces an order that validates, transmits, and triggers at the
    wrong price.

    Args:
        raw: The terminal order.
        order_type: The already-translated domain order type.

    Returns:
        The domain ``price`` and ``stop_price``, in that order.
    """
    if order_type.requires_stop_price:
        return _optional_price(raw.price_stoplimit), _optional_price(raw.price_open)
    return _optional_price(raw.price_open), None


def to_order(raw: MT5Order, clock: ServerClock) -> Order:
    """Translate a terminal order into an :class:`Order`.

    Args:
        raw: The structure returned by ``orders_get()``.
        clock: Converts the server's clock to UTC.

    Returns:
        The order.

    Raises:
        ValueError: If the terminal reports an order type or state Atlas does
            not model. ``ORDER_TYPE_CLOSE_BY`` is the expected case: it is a
            netting instruction with no direction, and guessing a side for it
            would be worse than refusing.

    Notes:
        ``volume_initial`` is the requested quantity, which is what the domain
        model means by volume. ``volume_current`` is what remains unfilled, and
        using it would make a half-filled order look like a smaller order.

        An order that has never been touched since it was placed reports
        ``time_done_msc`` as zero, so the setup time stands in for the update
        time. Passing the zero through would date the update to 1970 and
        violate the model's requirement that it not precede creation.
    """
    directional = MT5_ORDER_TYPE_TO_DOMAIN.get(raw.type)
    if directional is None:
        msg = f"unknown MetaTrader 5 order type {raw.type!r} on ticket {raw.ticket!r}"
        raise ValueError(msg)
    side, order_type = directional

    status = MT5_ORDER_STATE_TO_STATUS.get(raw.state)
    if status is None:
        msg = f"unknown MetaTrader 5 order state {raw.state!r} on ticket {raw.ticket!r}"
        raise ValueError(msg)

    price, stop_price = _working_prices(raw, order_type)
    created_at = clock.to_utc_from_milliseconds(raw.time_setup_msc)
    updated_at = (
        created_at if raw.time_done_msc == 0 else clock.to_utc_from_milliseconds(raw.time_done_msc)
    )

    return Order(
        order_id=str(raw.ticket),
        symbol=raw.symbol,
        side=side,
        type=order_type,
        volume=to_decimal(raw.volume_initial),
        price=price,
        stop_price=stop_price,
        stop_loss=_optional_price(raw.sl),
        take_profit=_optional_price(raw.tp),
        status=status,
        created_at=created_at,
        updated_at=updated_at,
    )


def to_execution(raw: MT5Deal, clock: ServerClock) -> Execution:
    """Translate a terminal deal into an :class:`Execution`.

    Args:
        raw: The structure returned by ``history_deals_get()``.
        clock: Converts the server's clock to UTC.

    Returns:
        The fill.

    Notes:
        A MetaTrader 5 deal is the venue's record of one quantity transacting,
        which is exactly what the domain calls an execution. Balance
        operations — deposits, withdrawals, credit — also arrive as deals with
        no symbol and no volume, and are not executions; filtering them is the
        caller's job, because it needs the deal type this mapper does not read.
    """
    return Execution(
        execution_id=str(raw.ticket),
        order_id=str(raw.order),
        symbol=raw.symbol,
        price=to_decimal(raw.price),
        volume=to_decimal(raw.volume),
        commission=to_decimal(raw.commission),
        swap=to_decimal(raw.swap),
        timestamp=clock.to_utc_from_milliseconds(raw.time_msc),
    )


def to_broker_version(name: str, terminal_version: int, build: int) -> BrokerVersion:
    """Assemble the terminal's identity into a :class:`BrokerVersion`.

    Args:
        name: Product name from ``terminal_info().name``.
        terminal_version: First element of the ``version()`` tuple.
        build: Second element of the ``version()`` tuple.

    Returns:
        The version record.

    Notes:
        Takes scalars rather than a structure because the two values come from
        two different terminal calls, and there is no MetaTrader 5 object that
        carries both.
    """
    return BrokerVersion(
        name=name,
        version=str(terminal_version),
        build=build,
        api_version=None,
    )
