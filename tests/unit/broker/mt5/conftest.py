"""A MetaTrader 5 terminal that does not exist.

Every test in this directory runs against :class:`FakeTerminal` and the
structures below. The MetaTrader5 package is never imported, no terminal is
started, and no account is logged into — which is the point: these tests must
run on the Linux CI runner where the vendor wheel cannot be installed at all.

The structures are dataclasses rather than ``SimpleNamespace`` so that a field
Atlas reads but the fake does not define is a failure here rather than an
``AttributeError`` in the adapter. ``test_mt5_mapper.py`` additionally asserts
each one against the ``Protocol`` that declares Atlas's dependency on it, so the
fakes cannot drift away from the surface the production code expects.

Values are deliberately awkward. The account is flat, so ``margin_level``
arrives as the zero that means "undefined"; the tick carries a millisecond
timestamp that disagrees with its whole-second one; the server runs three hours
ahead of UTC. A fixture set of round, well-behaved numbers would pass whether or
not the conversions in :mod:`atlas.broker.mt5.mapper` were there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import SecretStr

from atlas.broker.mt5.connection import MT5Config, MT5Session
from atlas.broker.mt5.constants import (
    ORDER_FILLING_FOK,
    ORDER_STATE_FILLED,
    ORDER_STATE_PLACED,
    ORDER_TYPE_BUY,
    ORDER_TYPE_BUY_LIMIT,
    POSITION_TYPE_BUY,
    RES_E_AUTH_FAILED,
    SYMBOL_TRADE_MODE_FULL,
    TRADE_RETCODE_DONE,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from atlas.broker.mt5.connection import Terminal

#: A fixed instant, in UTC. Tests must never depend on the wall clock.
NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)

#: The trade server used throughout runs three hours ahead of UTC, which is the
#: single most common retail configuration and the one that makes an
#: unconverted timestamp look plausible instead of obviously wrong.
SERVER_OFFSET = timedelta(hours=3)


def server_epoch(instant: datetime) -> int:
    """Encode a UTC instant the way a MetaTrader 5 server would.

    Args:
        instant: The real instant.

    Returns:
        The epoch seconds the terminal would report: the server's wall clock,
        encoded as though it were UTC.
    """
    return int((instant + SERVER_OFFSET).timestamp())


def server_epoch_ms(instant: datetime) -> int:
    """Encode a UTC instant as the terminal's millisecond timestamp.

    Args:
        instant: The real instant.

    Returns:
        The epoch milliseconds the terminal would report.
    """
    return server_epoch(instant) * 1000


# --- Vendor structures --------------------------------------------------------


@dataclass
class FakeAccountInfo:
    """Stands in for ``MetaTrader5.account_info()``."""

    login: int = 9001234
    company: str = "Example Brokerage"
    server: str = "Example-Demo"
    currency: str = "USD"
    balance: float = 50000.0
    equity: float = 50120.5
    margin: float = 0.0
    margin_free: float = 50120.5
    margin_level: float = 0.0
    leverage: int = 30
    trade_allowed: bool = True


@dataclass
class FakeSymbolInfo:
    """Stands in for ``MetaTrader5.symbol_info()``."""

    name: str = "EURUSD"
    description: str = "Euro vs US Dollar"
    currency_base: str = "EUR"
    currency_profit: str = "USD"
    digits: int = 5
    point: float = 0.00001
    trade_tick_size: float = 0.00001
    trade_contract_size: float = 100000.0
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01
    spread: int = 12
    trade_mode: int = SYMBOL_TRADE_MODE_FULL


@dataclass
class FakeTick:
    """Stands in for ``MetaTrader5.symbol_info_tick()``."""

    time: int = field(default_factory=lambda: server_epoch(NOW))
    time_msc: int = field(default_factory=lambda: server_epoch_ms(NOW) + 250)
    bid: float = 1.1624
    ask: float = 1.16252
    last: float = 0.0
    volume: int = 0
    volume_real: float = 0.0


@dataclass
class FakePosition:
    """Stands in for one entry of ``MetaTrader5.positions_get()``."""

    ticket: int = 550001
    symbol: str = "EURUSD"
    type: int = POSITION_TYPE_BUY
    volume: float = 0.1
    price_open: float = 1.162
    price_current: float = 1.16245
    profit: float = 4.5
    swap: float = -0.32
    time_msc: int = field(default_factory=lambda: server_epoch_ms(NOW))


@dataclass
class FakeOrder:
    """Stands in for one entry of ``MetaTrader5.orders_get()``."""

    ticket: int = 660001
    symbol: str = "EURUSD"
    type: int = ORDER_TYPE_BUY_LIMIT
    state: int = ORDER_STATE_PLACED
    volume_initial: float = 0.1
    price_open: float = 1.16
    price_stoplimit: float = 0.0
    sl: float = 1.155
    tp: float = 1.17
    time_setup_msc: int = field(default_factory=lambda: server_epoch_ms(NOW))
    time_done_msc: int = 0


@dataclass
class FakeOrderResult:
    """Stands in for the result of ``MetaTrader5.order_send()``.

    Carries every field :class:`FakeOrder` does, plus the two ``order_send``
    adds on top, because :func:`~atlas.broker.mt5.mapper.to_order` is what
    translates a placed order's result — see ``MT5OrderResult``.
    """

    retcode: int = TRADE_RETCODE_DONE
    comment: str = "Request executed"
    ticket: int = 660002
    symbol: str = "EURUSD"
    type: int = ORDER_TYPE_BUY
    state: int = ORDER_STATE_FILLED
    volume_initial: float = 0.1
    price_open: float = 1.162
    price_stoplimit: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    time_setup_msc: int = field(default_factory=lambda: server_epoch_ms(NOW))
    time_done_msc: int = field(default_factory=lambda: server_epoch_ms(NOW))


@dataclass
class FakeDeal:
    """Stands in for one entry of ``MetaTrader5.history_deals_get()``."""

    ticket: int = 770001
    order: int = 660001
    symbol: str = "EURUSD"
    price: float = 1.162
    volume: float = 0.1
    commission: float = -0.7
    swap: float = 0.0
    time_msc: int = field(default_factory=lambda: server_epoch_ms(NOW))


@dataclass
class FakeTerminalInfo:
    """Stands in for ``MetaTrader5.terminal_info()``."""

    name: str = "MetaTrader 5"
    connected: bool = True
    ping_last: int = 42500


def rate_row(
    instant: datetime,
    *,
    open_: float = 1.162,
    high: float = 1.1631,
    low: float = 1.1618,
    close: float = 1.16245,
    tick_volume: float = 1834.0,
) -> dict[str, float]:
    """Build one row of a ``copy_rates_*`` array.

    Args:
        instant: The bar's real opening instant, in UTC.
        open_: Opening price.
        high: Highest price.
        low: Lowest price.
        close: Closing price.
        tick_volume: Number of price changes in the bar.

    Returns:
        A mapping with the fields the mapper reads. A plain ``dict`` is used
        rather than a NumPy record because ``MT5RateRow`` describes a subscript
        interface and nothing more, so these tests need no NumPy at all.
    """
    return {
        "time": float(server_epoch(instant)),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "tick_volume": tick_volume,
    }


# --- The terminal ------------------------------------------------------------


class FakeTerminal:
    """A scriptable stand-in for the ``MetaTrader5`` module.

    Every attribute is public and mutable so that a test states the terminal's
    condition as data — ``terminal.initialize_result = False`` — rather than by
    patching a method. Calls are recorded in :attr:`calls` for the handful of
    assertions that are about *which* terminal call was made rather than about
    what came back.
    """

    def __init__(self) -> None:
        """Build a terminal that is healthy and offers one instrument."""
        self.initialize_result = True
        self.error: tuple[int, str] = (RES_E_AUTH_FAILED, "Authorization failed")
        self.account: FakeAccountInfo | None = FakeAccountInfo()
        self.status: FakeTerminalInfo | None = FakeTerminalInfo()
        self.version_result: tuple[int, int, str] | None = (500, 4620, "20 Jun 2026")
        self.symbols: list[FakeSymbolInfo] = [FakeSymbolInfo()]
        self.ticks: dict[str, FakeTick] = {"EURUSD": FakeTick()}
        #: Newest bar first, as the terminal indexes them.
        self.rates: list[dict[str, float]] = []
        self.positions: list[FakePosition] = []
        self.orders: list[FakeOrder] = []
        self.deals: list[FakeDeal] = []
        self.margin: float | None = 38.75
        self.order_result: FakeOrderResult | None = FakeOrderResult()
        self.calls: list[str] = []
        self.selected: list[str] = []
        self.shutdown_count = 0
        #: The arguments of the most recent call of each kind, for the
        #: assertions that are about what was asked rather than what came back.
        self.initialize_args: dict[str, object] = {}
        self.rates_args: dict[str, object] = {}
        self.range_args: dict[str, object] = {}
        self.margin_args: dict[str, object] = {}
        self.order_send_args: Mapping[str, object] = {}

    # -- Lifecycle
    def initialize(
        self,
        path: str,
        *,
        login: int,
        password: str,
        server: str,
        timeout: int,
        portable: bool,
    ) -> bool:
        """Record the login attempt and report the scripted outcome."""
        self.calls.append("initialize")
        self.initialize_args = {
            "path": path,
            "login": login,
            "password": password,
            "server": server,
            "timeout": timeout,
            "portable": portable,
        }
        return self.initialize_result

    def shutdown(self) -> None:
        """Count the teardown."""
        self.calls.append("shutdown")
        self.shutdown_count += 1

    def last_error(self) -> tuple[int, str]:
        """Report the scripted error."""
        return self.error

    # -- Identity
    def version(self) -> tuple[int, int, str] | None:
        """Report the scripted version."""
        self.calls.append("version")
        return self.version_result

    def terminal_info(self) -> FakeTerminalInfo | None:
        """Report the scripted terminal status."""
        self.calls.append("terminal_info")
        return self.status

    def account_info(self) -> FakeAccountInfo | None:
        """Report the scripted account."""
        self.calls.append("account_info")
        return self.account

    # -- Instruments
    def symbols_get(self) -> Sequence[FakeSymbolInfo] | None:
        """Report every scripted instrument."""
        self.calls.append("symbols_get")
        return self.symbols

    def symbol_info(self, symbol: str) -> FakeSymbolInfo | None:
        """Look an instrument up by exact name, as the terminal does."""
        self.calls.append("symbol_info")
        return next((info for info in self.symbols if info.name == symbol), None)

    def symbol_info_tick(self, symbol: str) -> FakeTick | None:
        """Report the scripted quote, if there is one."""
        self.calls.append("symbol_info_tick")
        return self.ticks.get(symbol)

    def symbol_select(self, symbol: str, enable: bool) -> bool:
        """Record a Market Watch change."""
        self.calls.append("symbol_select")
        if enable:
            self.selected.append(symbol)
        return True

    # -- Market data
    def copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> Sequence[dict[str, float]] | None:
        """Return bars counted back from the most recent, oldest first."""
        self.calls.append("copy_rates_from_pos")
        self.rates_args = {
            "symbol": symbol,
            "timeframe": timeframe,
            "start_pos": start_pos,
            "count": count,
        }
        window = self.rates[start_pos : start_pos + count]
        return list(reversed(window))

    def copy_rates_range(
        self, symbol: str, timeframe: int, date_from: float, date_to: float
    ) -> Sequence[dict[str, float]] | None:
        """Return bars whose open time falls in an inclusive period."""
        self.calls.append("copy_rates_range")
        self.range_args = {
            "symbol": symbol,
            "timeframe": timeframe,
            "date_from": date_from,
            "date_to": date_to,
        }
        selected = [row for row in self.rates if date_from <= row["time"] <= date_to]
        return sorted(selected, key=lambda row: row["time"])

    # -- Account
    def positions_get(self, **filters: str) -> Sequence[FakePosition] | None:
        """Report open positions, honouring a ``symbol`` filter if given."""
        self.calls.append("positions_get")
        wanted = filters.get("symbol")
        if wanted is None:
            return self.positions
        return [entry for entry in self.positions if entry.symbol == wanted]

    def orders_get(self, **filters: str) -> Sequence[FakeOrder] | None:
        """Report working orders, honouring a ``symbol`` filter if given."""
        self.calls.append("orders_get")
        wanted = filters.get("symbol")
        if wanted is None:
            return self.orders
        return [entry for entry in self.orders if entry.symbol == wanted]

    def history_deals_get(self, **filters: int) -> Sequence[FakeDeal] | None:
        """Report deals matching a ``position`` filter."""
        self.calls.append("history_deals_get")
        wanted = filters.get("position")
        if wanted is None:
            return self.deals
        return [deal for deal in self.deals if wanted in (deal.order, deal.ticket)]

    def order_calc_margin(
        self, action: int, symbol: str, volume: float, price: float
    ) -> float | None:
        """Report the scripted margin."""
        self.calls.append("order_calc_margin")
        self.margin_args = {
            "action": action,
            "symbol": symbol,
            "volume": volume,
            "price": price,
        }
        return self.margin

    def order_send(self, request: Mapping[str, object]) -> FakeOrderResult | None:
        """Report the scripted result of a trade request."""
        self.calls.append("order_send")
        self.order_send_args = request
        return self.order_result


def as_terminal(terminal: FakeTerminal) -> Terminal:
    """Assert, at type-check time, that the fake satisfies the real protocol.

    Args:
        terminal: The fake.

    Returns:
        The same object, seen as a :class:`~atlas.broker.mt5.connection.Terminal`.

    Notes:
        This is the check that keeps the fake honest. MyPy rejects this return
        if :class:`FakeTerminal` drifts from the vendor surface the adapter
        declares, so a test suite cannot pass against a terminal that production
        code could not talk to. It runs under MyPy, not under pytest.
    """
    return terminal


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture
def config() -> MT5Config:
    """Return a configuration pointing at a server three hours ahead of UTC."""
    return MT5Config(
        login=9001234,
        password=SecretStr("not-a-real-password"),
        server="Example-Demo",
        terminal_path=Path("C:/Program Files/Example/terminal64.exe"),
        server_utc_offset=SERVER_OFFSET,
        deviation_points=20,
        filling_mode_by_instrument={"EURUSD": ORDER_FILLING_FOK},
    )


@pytest.fixture
def terminal() -> FakeTerminal:
    """Return a healthy terminal offering EURUSD."""
    return FakeTerminal()


@pytest.fixture
def session(config: MT5Config, terminal: FakeTerminal) -> MT5Session:
    """Return a disconnected session wired to the fake terminal."""
    return MT5Session(config, terminal_factory=lambda: terminal)
