"""Unit tests for the MetaTrader 5 implementation of the broker port.

The adapter decides *which* terminal call answers a port method and hands the
result to the mapper. These tests are therefore about two things the mapper
tests cannot see: which call was made, and with what arguments. A conversion
that is merely wrong is caught next door; what is caught here is asking for the
forming bar when a closed one was wanted, sending a UTC boundary to a server
that reads it as local time, or filtering positions by the caller's spelling of
an instrument rather than the terminal's.

Nothing here starts a terminal or logs into an account. The adapter takes its
session by injection, the session takes its terminal from a factory, and the
factory returns :class:`~tests.unit.broker.mt5.conftest.FakeTerminal` — so the
MetaTrader5 package is never imported and these tests run on a Linux runner
where the wheel cannot be installed at all.

The host clock is frozen at :data:`~tests.unit.broker.mt5.conftest.NOW` by the
``adapter`` fixture. Two behaviours — dropping the forming bar, and stamping a
heartbeat — are defined against "now", and a test that reads the real clock
would assert either nothing or something that fails at a period boundary.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Final

import pytest

from atlas.broker.adapter import BrokerAdapter
from atlas.broker.models import (
    ConnectionState,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    SymbolTradeMode,
    Timeframe,
)
from atlas.broker.mt5.adapter import MT5BrokerAdapter
from atlas.broker.mt5.connection import (
    MT5DataUnavailableError,
    MT5Error,
    MT5NotConnectedError,
    MT5SymbolNotFoundError,
    MT5TimeoutError,
)
from atlas.broker.mt5.constants import (
    ORDER_STATE_FILLED,
    ORDER_TYPE_BUY,
    ORDER_TYPE_SELL,
    RES_E_FAIL,
    RES_E_INTERNAL_FAIL_TIMEOUT,
    SYMBOL_TRADE_MODE_CLOSEONLY,
    SYMBOL_TRADE_MODE_DISABLED,
    TIMEFRAME_H4,
    TIMEFRAME_M15,
)
from atlas.broker.types import OrderRequest
from tests.unit.broker.mt5.conftest import (
    NOW,
    FakeAccountInfo,
    FakeDeal,
    FakeOrder,
    FakePosition,
    FakeSymbolInfo,
    FakeTick,
    rate_row,
    server_epoch,
)

if TYPE_CHECKING:
    from atlas.broker.models import Candle, Tick
    from atlas.broker.mt5.connection import MT5Config, MT5Session
    from tests.unit.broker.mt5.conftest import FakeTerminal

pytestmark = pytest.mark.unit

#: How many methods :class:`~atlas.broker.adapter.BrokerAdapter` declares.
#:
#: Quoted in ``atlas.broker.mt5.adapter``'s module docstring and in this
#: package's README, both of which state how much of the port this adapter
#: covers. A method added to the port without those being revisited leaves the
#: documented coverage silently wrong, so the number is asserted rather than
#: only written down.
PORT_METHOD_COUNT: Final = 31

#: The bar length used wherever the timeframe itself is not what is being tested.
QUARTER_HOUR: Final = timedelta(minutes=15)

#: The position ticket used throughout, so that a position and the deals that
#: opened it can be matched without repeating a magic number.
POSITION_TICKET: Final = 550001


def ignore_tick(_tick: Tick) -> None:
    """Discard a quote.

    Args:
        _tick: The quote. Never delivered: the method that takes this handler
            raises before any subscription exists.
    """


def ignore_candle(_candle: Candle) -> None:
    """Discard a bar.

    Args:
        _candle: The bar. Never delivered, for the reason given on
            :func:`ignore_tick`.
    """


@pytest.fixture
def offline(config: MT5Config, session: MT5Session) -> MT5BrokerAdapter:
    """Return an adapter that has never connected.

    Args:
        config: Credentials and terminal location.
        session: A session wired to the fake terminal.

    Returns:
        The adapter, with its real clock and an untouched terminal.
    """
    return MT5BrokerAdapter(config, session=session)


@pytest.fixture
def adapter(
    config: MT5Config,
    session: MT5Session,
    terminal: FakeTerminal,
    monkeypatch: pytest.MonkeyPatch,
) -> MT5BrokerAdapter:
    """Return a connected adapter whose host clock is frozen at ``NOW``.

    Args:
        config: Credentials and terminal location.
        session: A session wired to the fake terminal.
        terminal: The terminal that session will connect to.
        monkeypatch: Used to freeze the clock.

    Returns:
        A connected adapter.

    Notes:
        The terminal's call log is cleared after connecting, so a test asserting
        on which calls a method made does not have to skip past the two that
        establishing the session always makes. The lifecycle tests build their
        own adapter from the ``offline`` fixture for exactly that reason.
    """
    monkeypatch.setattr(MT5BrokerAdapter, "_now", staticmethod(lambda: NOW))
    built = MT5BrokerAdapter(config, session=session)
    built.connect()
    terminal.calls.clear()
    return built


class TestPortConformance:
    def test_the_adapter_is_a_broker_adapter(self, offline: MT5BrokerAdapter) -> None:
        assert isinstance(offline, BrokerAdapter)

    def test_no_port_method_is_left_abstract(self) -> None:
        # Instantiating the adapter above already proves this, but it proves it
        # as a TypeError naming the class. Stated here, a method added to the
        # port and forgotten here fails with the method's own name.
        assert MT5BrokerAdapter.__abstractmethods__ == frozenset()

    def test_the_port_is_the_size_this_package_documents(self) -> None:
        assert len(BrokerAdapter.__abstractmethods__) == PORT_METHOD_COUNT

    def test_construction_touches_no_terminal(
        self, offline: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # The adapter is built during composition, which may happen on a host
        # with no terminal installed. A failure there is not actionable; the
        # same failure on connect() is.
        assert offline.is_connected() is False
        assert terminal.calls == []

    def test_a_request_without_a_session_is_refused(self, offline: MT5BrokerAdapter) -> None:
        with pytest.raises(MT5NotConnectedError):
            offline.get_account()


class TestLifecycle:
    def test_connecting_reports_a_usable_session(self, offline: MT5BrokerAdapter) -> None:
        result = offline.connect()

        assert result.state is ConnectionState.CONNECTED
        assert result.connected is True
        assert result.server == "Example-Demo"

    def test_connecting_caches_the_brokerage_name(self, offline: MT5BrokerAdapter) -> None:
        # The account is the only place the terminal reports which brokerage is
        # at the far end, so the name is read once and kept.
        assert offline.connect().broker == "Example Brokerage"

    def test_the_brokerage_is_unknown_before_a_session(self, offline: MT5BrokerAdapter) -> None:
        result = offline.health()

        assert result.broker == "unknown"
        assert result.state is ConnectionState.DISCONNECTED
        assert result.connected is False

    def test_health_makes_no_round_trip(
        self, offline: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # Health is read precisely when the venue is unreachable, so it answers
        # from local state or it is useless.
        offline.health()

        assert terminal.calls == []

    def test_the_brokerage_name_survives_a_disconnect(self, offline: MT5BrokerAdapter) -> None:
        offline.connect()
        offline.disconnect()

        assert offline.health().broker == "Example Brokerage"

    def test_a_disconnect_clears_a_stale_latency_reading(self, adapter: MT5BrokerAdapter) -> None:
        # A measurement from a session that no longer exists, presented as
        # current, is what makes a supervision dashboard actively misleading.
        adapter.latency()
        adapter.disconnect()
        result = adapter.health()

        assert result.latency_ms is None
        assert result.last_heartbeat is None
        assert result.connected is False

    def test_reconnecting_tears_the_old_session_down_first(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        result = adapter.reconnect()

        assert terminal.calls[:2] == ["shutdown", "initialize"]
        assert terminal.shutdown_count == 1
        assert result.connected is True

    def test_is_connected_tracks_the_session(self, offline: MT5BrokerAdapter) -> None:
        assert offline.is_connected() is False
        offline.connect()
        assert offline.is_connected() is True
        offline.disconnect()
        assert offline.is_connected() is False

    def test_connecting_stamps_a_heartbeat(self, adapter: MT5BrokerAdapter) -> None:
        assert adapter.health().last_heartbeat == NOW


class TestSymbols:
    def test_every_offered_instrument_is_listed(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        terminal.symbols = [FakeSymbolInfo(), FakeSymbolInfo(name="GBPUSD", currency_base="GBP")]

        assert [symbol.symbol for symbol in adapter.get_symbols()] == ["EURUSD", "GBPUSD"]

    def test_an_instrument_is_found_despite_a_difference_in_case(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # The domain uppercases an instrument code on the way into a model, so a
        # broker whose suffix is lower case hands back a Symbol whose code the
        # terminal itself would then refuse. Without the fallback scan, a value
        # read from one port method could not be passed to another.
        terminal.symbols = [FakeSymbolInfo(name="EURUSD.a")]

        assert adapter.get_symbol("EURUSD.A").symbol == "EURUSD.A"

    def test_an_exact_match_does_not_scan_the_instrument_list(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        adapter.get_symbol("EURUSD")

        assert "symbols_get" not in terminal.calls

    def test_reading_a_specification_does_not_add_it_to_market_watch(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # Asking what an instrument's terms are is not a statement of intent to
        # quote it, and Market Watch is terminal-wide shared state.
        adapter.get_symbol("EURUSD")

        assert terminal.selected == []

    def test_an_unknown_instrument_is_refused(self, adapter: MT5BrokerAdapter) -> None:
        with pytest.raises(MT5SymbolNotFoundError):
            adapter.get_symbol("NOPE")

    def test_the_terminals_trade_mode_reaches_the_model(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        terminal.symbols = [FakeSymbolInfo(trade_mode=SYMBOL_TRADE_MODE_CLOSEONLY)]

        assert adapter.get_symbol("EURUSD").trade_mode is SymbolTradeMode.CLOSE_ONLY


class TestTicks:
    def test_a_quote_is_returned_in_utc(self, adapter: MT5BrokerAdapter) -> None:
        # The fake's tick carries a server timestamp 250 ms past NOW on a server
        # running three hours ahead. Read without the correction it would land
        # three hours late, which is plausible enough to survive review.
        result = adapter.get_tick("EURUSD")

        assert result.timestamp == NOW + timedelta(milliseconds=250)
        assert result.bid == Decimal("1.1624")
        assert result.ask == Decimal("1.16252")

    def test_quoting_adds_the_instrument_to_market_watch(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # The terminal publishes neither quotes nor bars for an instrument that
        # is not selected, so every market-data path has to select first.
        adapter.get_tick("EURUSD")

        assert terminal.selected == ["EURUSD"]

    def test_an_unquoted_instrument_is_reported_as_unavailable(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        terminal.ticks = {}

        with pytest.raises(MT5DataUnavailableError):
            adapter.get_tick("EURUSD")

    def test_a_batch_is_keyed_by_the_callers_spelling(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # Keyed by the terminal's spelling instead, a caller could not look up
        # the result with the value it passed in.
        terminal.symbols = [FakeSymbolInfo(name="EURUSD.a")]
        terminal.ticks = {"EURUSD.a": FakeTick()}

        assert list(adapter.get_ticks(["EURUSD.A"])) == ["EURUSD.A"]

    def test_an_unquoted_instrument_is_omitted_from_a_batch(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        terminal.symbols = [FakeSymbolInfo(), FakeSymbolInfo(name="GBPUSD", currency_base="GBP")]

        assert list(adapter.get_ticks(["EURUSD", "GBPUSD"])) == ["EURUSD"]

    def test_a_batch_resolves_every_instrument_before_quoting_any(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # An unknown code fails before a partial snapshot has been assembled,
        # rather than after some of it has been read.
        with pytest.raises(MT5SymbolNotFoundError):
            adapter.get_ticks(["EURUSD", "NOPE"])

        assert "symbol_info_tick" not in terminal.calls


class TestCandles:
    def test_the_default_bar_is_the_last_closed_one(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # Position 0 is the forming bar and position 1 the most recent closed
        # one. The terminal has no flag for this: the offset *is* the
        # distinction, so the offset is what the test asserts.
        terminal.rates = [rate_row(NOW), rate_row(NOW - QUARTER_HOUR)]

        result = adapter.get_candle("EURUSD", Timeframe.M15)

        assert terminal.rates_args == {
            "symbol": "EURUSD",
            "timeframe": TIMEFRAME_M15,
            "start_pos": 1,
            "count": 1,
        }
        assert result.open_time == NOW - QUARTER_HOUR
        assert result.is_closed is True

    def test_the_forming_bar_is_asked_for_by_position(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        terminal.rates = [rate_row(NOW), rate_row(NOW - QUARTER_HOUR)]

        result = adapter.get_candle("EURUSD", Timeframe.M15, include_forming=True)

        assert terminal.rates_args["start_pos"] == 0
        assert result.open_time == NOW
        assert result.is_closed is False

    def test_the_timeframe_is_sent_in_the_terminals_encoding(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # H4 is 0x4000 | 4, not 240. A timeframe encoded wrongly returns the
        # wrong bars silently and forever.
        terminal.rates = [rate_row(NOW), rate_row(NOW - timedelta(hours=4))]

        adapter.get_candle("EURUSD", Timeframe.H4)

        assert terminal.rates_args["timeframe"] == TIMEFRAME_H4

    def test_an_instrument_with_no_bars_is_reported_as_unavailable(
        self, adapter: MT5BrokerAdapter
    ) -> None:
        with pytest.raises(MT5DataUnavailableError):
            adapter.get_candle("EURUSD", Timeframe.M15)

    def test_bars_are_returned_oldest_first(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # The terminal indexes bars newest first. Anything computing a moving
        # average over the result reads a reversed series otherwise, which
        # produces a number rather than an error.
        terminal.rates = [rate_row(NOW - QUARTER_HOUR * index) for index in range(4)]

        result = adapter.get_candles("EURUSD", Timeframe.M15, 3)

        assert [candle.open_time for candle in result] == [
            NOW - QUARTER_HOUR * 3,
            NOW - QUARTER_HOUR * 2,
            NOW - QUARTER_HOUR,
        ]

    def test_a_series_excludes_the_forming_bar(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        terminal.rates = [rate_row(NOW - QUARTER_HOUR * index) for index in range(4)]

        result = adapter.get_candles("EURUSD", Timeframe.M15, 3)

        assert all(candle.is_closed for candle in result)
        assert NOW not in [candle.open_time for candle in result]

    def test_a_count_below_one_is_refused(self, adapter: MT5BrokerAdapter) -> None:
        with pytest.raises(ValueError, match="count must be at least 1"):
            adapter.get_candles("EURUSD", Timeframe.M15, 0)


class TestHistoricalData:
    def test_a_naive_start_is_refused(self, adapter: MT5BrokerAdapter) -> None:
        # A naive bound would be read as host-local time, shifting the requested
        # period by the host's offset — silently, and differently on a laptop
        # and a server.
        with pytest.raises(ValueError, match="start must be timezone aware"):
            adapter.get_historical_data("EURUSD", Timeframe.M15, NOW.replace(tzinfo=None))

    def test_a_naive_end_is_refused(self, adapter: MT5BrokerAdapter) -> None:
        with pytest.raises(ValueError, match="end must be timezone aware"):
            adapter.get_historical_data(
                "EURUSD", Timeframe.M15, NOW - timedelta(hours=1), NOW.replace(tzinfo=None)
            )

    def test_an_end_before_the_start_is_refused(self, adapter: MT5BrokerAdapter) -> None:
        with pytest.raises(ValueError, match="end must be after start"):
            adapter.get_historical_data("EURUSD", Timeframe.M15, NOW, NOW)

    def test_the_boundaries_are_sent_in_the_servers_encoding(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # Asking a UTC+3 server for bars "from 12:00 UTC" without the correction
        # quietly requests bars from 09:00 UTC.
        start = NOW - timedelta(hours=1)

        adapter.get_historical_data("EURUSD", Timeframe.M15, start, NOW)

        assert terminal.range_args["date_from"] == server_epoch(start)
        assert terminal.range_args["date_to"] == server_epoch(NOW)

    def test_a_bar_opening_exactly_at_the_end_is_dropped(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # The terminal's range is inclusive at both ends and the port's is
        # half-open. Without the correction two consecutive requests share a
        # bar, and anything summing over them counts it twice.
        terminal.rates = [rate_row(NOW - QUARTER_HOUR * index) for index in range(1, 4)]

        result = adapter.get_historical_data(
            "EURUSD", Timeframe.M15, NOW - timedelta(hours=1), NOW - QUARTER_HOUR
        )

        assert [candle.open_time for candle in result] == [
            NOW - QUARTER_HOUR * 3,
            NOW - QUARTER_HOUR * 2,
        ]

    def test_the_forming_bar_is_dropped(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # An end in the future is what makes this the only rule in play: the bar
        # opening at NOW is inside the requested period and is dropped because
        # it has not closed. The bar before it closes exactly at NOW and stays.
        terminal.rates = [rate_row(NOW - QUARTER_HOUR * index) for index in range(3)]

        result = adapter.get_historical_data(
            "EURUSD", Timeframe.M15, NOW - timedelta(hours=1), NOW + timedelta(hours=1)
        )

        assert [candle.open_time for candle in result] == [
            NOW - QUARTER_HOUR * 2,
            NOW - QUARTER_HOUR,
        ]

    def test_a_period_with_no_trading_is_empty_rather_than_an_error(
        self, adapter: MT5BrokerAdapter
    ) -> None:
        # A weekend is a true answer, and the terminal does not distinguish it
        # from history that was never downloaded — so raising would report a
        # fault that may not exist.
        result = adapter.get_historical_data(
            "EURUSD", Timeframe.M15, NOW - timedelta(days=2), NOW - timedelta(days=1)
        )

        assert result == []

    def test_the_end_defaults_to_now(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        adapter.get_historical_data("EURUSD", Timeframe.M15, NOW - timedelta(hours=1))

        assert terminal.range_args["date_to"] == server_epoch(NOW)


class TestAccount:
    def test_the_account_is_reported_as_the_terminal_has_it(
        self, adapter: MT5BrokerAdapter
    ) -> None:
        result = adapter.get_account()

        assert result.account_id == "9001234"
        assert result.balance == Decimal("50000")
        assert result.equity == Decimal("50120.5")
        assert result.timestamp == NOW

    def test_a_flat_accounts_margin_level_is_undefined_rather_than_zero(
        self, adapter: MT5BrokerAdapter
    ) -> None:
        # Passed through, the terminal's 0.0 reads as the most severe margin
        # call representable and fires every `margin_level < threshold` rule on
        # an account holding nothing.
        assert adapter.get_account().margin_level is None

    def test_an_unreadable_account_is_an_error(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        terminal.account = None
        terminal.error = (RES_E_FAIL, "Generic failure")

        with pytest.raises(MT5Error, match="could not read the account"):
            adapter.get_account()

    def test_available_margin_is_the_accounts_free_margin(self, adapter: MT5BrokerAdapter) -> None:
        # Read through get_account rather than the raw structure, so the two can
        # never disagree about the same number.
        assert adapter.margin_available() == adapter.get_account().free_margin


class TestPositions:
    def test_an_open_position_is_reported_with_its_commission(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # MetaTrader 5 charges commission against the deals that opened a
        # position, never against the position, so it costs one extra call per
        # position to report it at all.
        terminal.positions = [FakePosition(ticket=POSITION_TICKET)]
        terminal.deals = [FakeDeal(order=POSITION_TICKET)]

        result = adapter.get_positions()

        assert [position.position_id for position in result] == [str(POSITION_TICKET)]
        assert result[0].side is PositionSide.LONG
        assert result[0].commission == Decimal("-0.7")

    def test_commission_is_summed_over_the_opening_deals(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        terminal.positions = [FakePosition(ticket=POSITION_TICKET)]
        terminal.deals = [
            FakeDeal(order=POSITION_TICKET, commission=-0.7),
            FakeDeal(order=POSITION_TICKET, ticket=770002, commission=-0.35),
        ]

        assert adapter.get_positions()[0].commission == Decimal("-1.05")

    def test_a_position_whose_deals_cannot_be_read_is_an_error(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # Every open position has at least an opening deal, so an empty result
        # means the terminal could not answer — not that the position was free.
        # Reporting zero would be a fabricated number in an accounting field.
        terminal.positions = [FakePosition(ticket=POSITION_TICKET)]

        with pytest.raises(MT5DataUnavailableError, match="commission cannot be established"):
            adapter.get_positions()

    def test_the_filter_uses_the_terminals_spelling_of_the_instrument(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # Passing the caller's spelling straight through would return nothing
        # for a broker whose codes carry a lower-case suffix.
        terminal.symbols = [FakeSymbolInfo(name="EURUSD.a")]
        terminal.positions = [FakePosition(ticket=POSITION_TICKET, symbol="EURUSD.a")]
        terminal.deals = [FakeDeal(order=POSITION_TICKET)]

        assert len(adapter.get_positions("EURUSD.A")) == 1

    def test_open_positions_delegates_to_the_filtered_read(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # The port requires the two to agree; delegation makes that true by
        # construction rather than by discipline.
        terminal.positions = [FakePosition(ticket=POSITION_TICKET)]
        terminal.deals = [FakeDeal(order=POSITION_TICKET)]

        assert adapter.get_open_positions() == adapter.get_positions()


class TestOrders:
    def test_a_working_order_is_reported(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        terminal.orders = [FakeOrder()]

        result = adapter.get_orders()

        assert [order.order_id for order in result] == ["660001"]
        assert result[0].status is OrderStatus.PENDING
        assert result[0].side is OrderSide.BUY
        assert result[0].type is OrderType.LIMIT

    def test_a_completed_order_is_not_reported(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # `orders_get` already returns working orders only. The filter states
        # the port's contract in code, so a terminal that ever returns a
        # completed order does not leak one upwards.
        terminal.orders = [FakeOrder(state=ORDER_STATE_FILLED)]

        assert adapter.get_orders() == []

    def test_orders_can_be_filtered_by_instrument(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        terminal.symbols = [FakeSymbolInfo(), FakeSymbolInfo(name="GBPUSD", currency_base="GBP")]
        terminal.orders = [FakeOrder(), FakeOrder(ticket=660002, symbol="GBPUSD")]

        assert [order.symbol for order in adapter.get_orders("GBPUSD")] == ["GBPUSD"]


class TestRisk:
    def test_margin_is_the_terminals_own_calculation(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        result = adapter.margin_required("EURUSD", OrderSide.BUY, Decimal("0.1"), Decimal("1.16"))

        assert result == Decimal("38.75")
        assert terminal.margin_args == {
            "action": ORDER_TYPE_BUY,
            "symbol": "EURUSD",
            "volume": 0.1,
            "price": 1.16,
        }

    def test_a_buy_is_evaluated_at_the_ask(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # The side Atlas would actually transact at, rather than a mid, so the
        # number matches the trade being contemplated.
        adapter.margin_required("EURUSD", OrderSide.BUY, Decimal("0.1"))

        assert terminal.margin_args["price"] == 1.16252

    def test_a_sell_is_evaluated_at_the_bid(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        adapter.margin_required("EURUSD", OrderSide.SELL, Decimal("0.1"))

        assert terminal.margin_args["price"] == 1.1624
        assert terminal.margin_args["action"] == ORDER_TYPE_SELL

    def test_margin_cannot_be_calculated_without_a_quote(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        terminal.ticks = {}

        with pytest.raises(MT5DataUnavailableError):
            adapter.margin_required("EURUSD", OrderSide.BUY, Decimal("0.1"))

    def test_a_refused_calculation_is_an_error(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        terminal.margin = None
        terminal.error = (RES_E_FAIL, "Generic failure")

        with pytest.raises(MT5Error, match="could not calculate margin"):
            adapter.margin_required("EURUSD", OrderSide.BUY, Decimal("0.1"))

    def test_a_permitted_instrument_can_be_traded(self, adapter: MT5BrokerAdapter) -> None:
        assert adapter.can_trade("EURUSD") is True

    def test_a_disabled_instrument_cannot_be_traded(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        terminal.symbols = [FakeSymbolInfo(trade_mode=SYMBOL_TRADE_MODE_DISABLED)]

        assert adapter.can_trade("EURUSD") is False

    def test_a_close_only_instrument_can_still_be_traded(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # The venue will accept an order — a closing one. Collapsing this into
        # False would stop a risk layer flattening a position it must exit.
        terminal.symbols = [FakeSymbolInfo(trade_mode=SYMBOL_TRADE_MODE_CLOSEONLY)]

        assert adapter.can_trade("EURUSD") is True

    def test_an_account_without_permission_cannot_trade(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        terminal.account = FakeAccountInfo(trade_allowed=False)

        assert adapter.can_trade("EURUSD") is False


class TestDiagnostics:
    def test_a_ping_confirms_a_live_terminal(self, adapter: MT5BrokerAdapter) -> None:
        assert adapter.ping() is True

    def test_a_successful_ping_refreshes_the_heartbeat(
        self, adapter: MT5BrokerAdapter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        later = NOW + timedelta(minutes=5)
        monkeypatch.setattr(MT5BrokerAdapter, "_now", staticmethod(lambda: later))

        adapter.ping()

        assert adapter.health().last_heartbeat == later

    def test_a_ping_without_a_session_is_false_rather_than_an_error(
        self, offline: MT5BrokerAdapter
    ) -> None:
        # This is the predicate a supervision loop uses to notice the venue is
        # down, so it cannot itself fail when the venue is down.
        assert offline.ping() is False

    def test_a_ping_is_false_when_the_terminal_does_not_answer(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        terminal.status = None

        assert adapter.ping() is False

    def test_latency_is_reported_in_milliseconds(self, adapter: MT5BrokerAdapter) -> None:
        # The terminal reports its link to the trade server in microseconds.
        assert adapter.latency() == 42.5

    def test_the_latency_reading_is_cached_for_health(self, adapter: MT5BrokerAdapter) -> None:
        adapter.latency()

        assert adapter.health().latency_ms == 42.5

    def test_a_terminal_that_cannot_report_status_raises_its_own_error(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # Classified from the terminal's last error rather than raised flat, so
        # a caller can tell a timeout from a refusal.
        terminal.status = None
        terminal.error = (RES_E_INTERNAL_FAIL_TIMEOUT, "Timeout")

        with pytest.raises(MT5TimeoutError, match="could not read the terminal status"):
            adapter.latency()

    def test_the_version_is_assembled_from_two_calls(self, adapter: MT5BrokerAdapter) -> None:
        # The terminal splits the product name and the build across
        # `terminal_info` and `version`; no single structure carries both.
        result = adapter.version()

        assert result.name == "MetaTrader 5"
        assert result.version == "500"
        assert result.build == 4620

    def test_an_unreadable_version_is_an_error(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        terminal.version_result = None
        terminal.error = (RES_E_FAIL, "Generic failure")

        with pytest.raises(MT5Error, match="could not read the terminal version"):
            adapter.version()


class TestUnavailable:
    """The seven methods that refuse, and the two that deliberately do not.

    Each refusal names what is missing. That is the whole point of the group:
    a ``NotImplementedError`` with no reason is indistinguishable from an
    unfinished method, and the four trading ones in particular must not be
    mistaken for "not written yet" — they are "cannot be reported on honestly
    until the exception hierarchy exists".
    """

    def test_placing_an_order_is_deferred(self, adapter: MT5BrokerAdapter) -> None:
        request = OrderRequest(
            symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=Decimal("0.1")
        )

        with pytest.raises(NotImplementedError, match="ATLAS-TASK-0005"):
            adapter.place_order(request)

    def test_modifying_an_order_is_deferred(self, adapter: MT5BrokerAdapter) -> None:
        with pytest.raises(NotImplementedError, match="ATLAS-TASK-0005"):
            adapter.modify_order("660001", price=Decimal("1.16"))

    def test_cancelling_an_order_is_deferred(self, adapter: MT5BrokerAdapter) -> None:
        with pytest.raises(NotImplementedError, match="ATLAS-TASK-0005"):
            adapter.cancel_order("660001")

    def test_closing_a_position_is_deferred(self, adapter: MT5BrokerAdapter) -> None:
        with pytest.raises(NotImplementedError, match="ATLAS-TASK-0005"):
            adapter.close_position(str(POSITION_TICKET))

    def test_no_order_reaches_the_terminal(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # The refusal is only worth anything if nothing was sent first. This
        # adapter is pointed at a demo account today and will not always be.
        request = OrderRequest(
            symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=Decimal("0.1")
        )

        with pytest.raises(NotImplementedError):
            adapter.place_order(request)

        assert terminal.calls == []

    def test_streaming_quotes_is_not_available(self, adapter: MT5BrokerAdapter) -> None:
        # The vendor API polls: it registers no callbacks and opens no push
        # channel, so this is a missing terminal capability rather than an
        # unwritten method.
        with pytest.raises(NotImplementedError, match="cannot push quotes"):
            adapter.subscribe_ticks(["EURUSD"], ignore_tick)

    def test_streaming_bars_is_not_available(self, adapter: MT5BrokerAdapter) -> None:
        with pytest.raises(NotImplementedError, match="cannot push bars"):
            adapter.subscribe_candles(["EURUSD"], Timeframe.M15, ignore_candle)

    def test_the_server_clock_is_not_available(self, adapter: MT5BrokerAdapter) -> None:
        # The nearest value is some instrument's last quote time, which over a
        # weekend is Friday's close. It would look like a clock and behave like
        # a stale one.
        with pytest.raises(NotImplementedError, match="no server-time call"):
            adapter.server_time()

    def test_cancelling_an_unknown_quote_subscription_is_silent(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # The port requires an unknown or already-cancelled handle to succeed
        # silently. Since no handle is ever issued, every handle is unknown, and
        # doing nothing is the specified behaviour rather than a stub.
        adapter.unsubscribe_ticks("no-such-subscription")

        assert terminal.calls == []

    def test_cancelling_an_unknown_bar_subscription_is_silent(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        adapter.unsubscribe_candles("no-such-subscription")

        assert terminal.calls == []


class TestNoVendorObjectEscapes:
    def test_every_read_returns_a_domain_type(
        self, adapter: MT5BrokerAdapter, terminal: FakeTerminal
    ) -> None:
        # The constraint this package exists to satisfy: no MetaTrader 5
        # structure, and no dictionary standing in for one, crosses the port. A
        # fake leaking through would be caught here by its module.
        terminal.rates = [rate_row(NOW), rate_row(NOW - QUARTER_HOUR)]
        terminal.positions = [FakePosition(ticket=POSITION_TICKET)]
        terminal.deals = [FakeDeal(order=POSITION_TICKET)]
        terminal.orders = [FakeOrder()]

        returned: list[object] = [
            adapter.health(),
            adapter.version(),
            adapter.get_account(),
            adapter.get_symbol("EURUSD"),
            adapter.get_tick("EURUSD"),
            adapter.get_candle("EURUSD", Timeframe.M15),
            *adapter.get_symbols(),
            *adapter.get_candles("EURUSD", Timeframe.M15, 1),
            *adapter.get_ticks(["EURUSD"]).values(),
            *adapter.get_positions(),
            *adapter.get_orders(),
        ]

        modules = {type(value).__module__ for value in returned}
        foreign = sorted(name for name in modules if not name.startswith("atlas.broker."))
        assert foreign == []
