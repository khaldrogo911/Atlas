"""What the mock adapter promises the port, and where it refuses.

Structured around one device. :data:`GUARDED_CALLS` maps every port method that
needs a session to a thunk that invokes it, and a test asserts that its key set
is exactly the port's own method inventory minus the methods the contract
exempts. Three tests then drive the whole table: each guarded method refuses
without a session, each raises the failure scheduled against its own name, and
each leaves that failure queued when the session check fires first. Between them
they prove the guard is wired into every method that needs it and spelled
correctly in each, and a thirty-second port method added later fails the key-set
assertion rather than slipping through untested.

The rest is the behaviour a caller can rely on, and — in ``TestBoundaries`` —
the behaviour a caller must not: the places where this adapter could have
guessed and does not.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Final

import pytest
from pydantic import ValidationError

from atlas.broker import (
    SupportsConnection,
    SupportsDiagnostics,
    SupportsMarketData,
    SupportsStreaming,
    SupportsTrading,
)
from atlas.broker.adapter import BrokerAdapter
from atlas.broker.exceptions import (
    BrokerDataUnavailableError,
    BrokerInsufficientMarginError,
    BrokerNotConnectedError,
    BrokerOrderNotFoundError,
    BrokerOrderRejectedError,
    BrokerPositionNotFoundError,
    BrokerSymbolNotFoundError,
    BrokerTimeoutError,
    BrokerUnsupportedOperationError,
)
from atlas.broker.mock import DEFAULT_ACCOUNT, SERVER, VENUE, MockBrokerAdapter, MockVenue
from atlas.broker.mock.adapter import MOCK_VERSION
from atlas.broker.models import (
    ConnectionState,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    SymbolTradeMode,
    Timeframe,
)
from atlas.broker.types import OrderRequest
from tests.unit.broker.mock.conftest import (
    ASK,
    BID,
    NOW,
    VOLUME,
    bar,
    funds,
    instrument,
    limit,
    market,
)
from tests.unit.broker.mock.conftest import tick as quote

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from atlas.broker.models import Candle, Order, Position, Tick

pytestmark = pytest.mark.unit

#: Port methods the contract forbids from raising at all.
NEVER_RAISES: Final = frozenset(
    {"disconnect", "health", "is_connected", "unsubscribe_candles", "unsubscribe_ticks"}
)

#: Port methods that are meaningful without a session.
#:
#: The two that establish one, and the one whose job is to report that there
#: is none.
SESSION_FREE: Final = frozenset({"connect", "reconnect", "ping"})

#: A price for a protective level, which this venue refuses to hold.
PROTECTIVE_LEVEL: Final = Decimal("1.05000")

#: A zone that is not UTC, so "normalised to UTC" has something to normalise.
GULF: Final = timezone(timedelta(hours=4))

#: Every port method that needs a session, and one valid way to call it.
#:
#: Arguments are chosen to survive whatever validation happens *before* the
#: guard — ``get_candles`` checks its count first, ``get_historical_data``
#: checks its bounds — so that every thunk reaches the guard and no further.
GUARDED_CALLS: Final[Mapping[str, Callable[[MockBrokerAdapter], object]]] = {
    "get_symbols": lambda adapter: adapter.get_symbols(),
    "get_symbol": lambda adapter: adapter.get_symbol("EURUSD"),
    "get_tick": lambda adapter: adapter.get_tick("EURUSD"),
    "get_ticks": lambda adapter: adapter.get_ticks(["EURUSD"]),
    "get_candle": lambda adapter: adapter.get_candle("EURUSD", Timeframe.M1),
    "get_candles": lambda adapter: adapter.get_candles("EURUSD", Timeframe.M1, 1),
    "get_historical_data": lambda adapter: adapter.get_historical_data(
        "EURUSD", Timeframe.M1, NOW - timedelta(days=1), NOW
    ),
    "subscribe_ticks": lambda adapter: adapter.subscribe_ticks(["EURUSD"], lambda _: None),
    "subscribe_candles": lambda adapter: adapter.subscribe_candles(
        ["EURUSD"], Timeframe.M1, lambda _: None
    ),
    "place_order": lambda adapter: adapter.place_order(market()),
    "modify_order": lambda adapter: adapter.modify_order("order-1", volume=VOLUME),
    "cancel_order": lambda adapter: adapter.cancel_order("order-1"),
    "close_position": lambda adapter: adapter.close_position("position-1"),
    "get_account": lambda adapter: adapter.get_account(),
    "get_positions": lambda adapter: adapter.get_positions(),
    "get_orders": lambda adapter: adapter.get_orders(),
    "get_open_positions": lambda adapter: adapter.get_open_positions(),
    "margin_required": lambda adapter: adapter.margin_required("EURUSD", OrderSide.BUY, VOLUME),
    "margin_available": lambda adapter: adapter.margin_available(),
    "can_trade": lambda adapter: adapter.can_trade("EURUSD"),
    "latency": lambda adapter: adapter.latency(),
    "server_time": lambda adapter: adapter.server_time(),
    "version": lambda adapter: adapter.version(),
}

#: Market buys carrying a level this venue cannot hold, one per field.
PROTECTED_REQUESTS: Final[Mapping[str, OrderRequest]] = {
    "stop_loss": OrderRequest(
        symbol="EURUSD",
        side=OrderSide.BUY,
        type=OrderType.MARKET,
        volume=VOLUME,
        stop_loss=PROTECTIVE_LEVEL,
    ),
    "take_profit": OrderRequest(
        symbol="EURUSD",
        side=OrderSide.BUY,
        type=OrderType.MARKET,
        volume=VOLUME,
        take_profit=PROTECTIVE_LEVEL,
    ),
}

#: Amendments that try to attach a level this venue cannot hold.
ATTACH_PROTECTION: Final[Mapping[str, Callable[[MockBrokerAdapter, str], Order]]] = {
    "stop_loss": lambda adapter, order_id: adapter.modify_order(
        order_id, stop_loss=PROTECTIVE_LEVEL
    ),
    "take_profit": lambda adapter, order_id: adapter.modify_order(
        order_id, take_profit=PROTECTIVE_LEVEL
    ),
}

#: Amendments that remove a level, which there is never one of to remove.
CLEAR_PROTECTION: Final[Mapping[str, Callable[[MockBrokerAdapter, str], Order]]] = {
    "stop_loss": lambda adapter, order_id: adapter.modify_order(order_id, stop_loss=None),
    "take_profit": lambda adapter, order_id: adapter.modify_order(order_id, take_profit=None),
}


def open_long(adapter: MockBrokerAdapter, symbol: str = "EURUSD") -> Position:
    """Open a long position through the port and return it.

    Args:
        adapter: A connected adapter.
        symbol: Instrument to buy.

    Returns:
        The resulting position, read from the venue rather than from the port,
        so that a test asserting on it is not using the adapter to check itself.
    """
    adapter.place_order(market(symbol=symbol))
    return adapter.venue.positions()[-1]


class TestPortConformance:
    def test_the_adapter_is_concrete(self, venue: MockVenue) -> None:
        assert isinstance(MockBrokerAdapter(venue), BrokerAdapter)

    def test_it_satisfies_every_capability_protocol(self, adapter: MockBrokerAdapter) -> None:
        assert isinstance(adapter, SupportsConnection)
        assert isinstance(adapter, SupportsMarketData)
        assert isinstance(adapter, SupportsStreaming)
        assert isinstance(adapter, SupportsTrading)
        assert isinstance(adapter, SupportsDiagnostics)

    def test_no_port_method_is_left_inherited_from_the_abstract_base(
        self, adapter: MockBrokerAdapter
    ) -> None:
        inherited = [
            name
            for name in sorted(BrokerAdapter.__abstractmethods__)
            if getattr(type(adapter), name) is getattr(BrokerAdapter, name)
        ]

        assert inherited == []

    def test_the_guarded_table_covers_exactly_the_methods_that_need_a_session(self) -> None:
        expected = set(BrokerAdapter.__abstractmethods__) - NEVER_RAISES - SESSION_FREE

        assert set(GUARDED_CALLS) == expected

    def test_an_adapter_builds_its_own_venue_when_none_is_given(self) -> None:
        assert isinstance(MockBrokerAdapter().venue, MockVenue)

    def test_the_venue_is_the_one_it_was_given(self, venue: MockVenue) -> None:
        assert MockBrokerAdapter(venue).venue is venue


class TestSessionGuard:
    @pytest.mark.parametrize("operation", sorted(GUARDED_CALLS))
    def test_every_guarded_method_refuses_without_a_session(
        self, offline: MockBrokerAdapter, operation: str
    ) -> None:
        with pytest.raises(BrokerNotConnectedError, match=f"{operation} needs a session"):
            GUARDED_CALLS[operation](offline)

    @pytest.mark.parametrize("operation", sorted(GUARDED_CALLS))
    def test_every_guarded_method_raises_the_failure_scheduled_against_its_own_name(
        self, adapter: MockBrokerAdapter, operation: str
    ) -> None:
        scheduled = BrokerTimeoutError("the venue went quiet", operation=operation, venue=VENUE)
        adapter.venue.schedule_failure(operation, scheduled)

        with pytest.raises(BrokerTimeoutError) as raised:
            GUARDED_CALLS[operation](adapter)

        assert raised.value is scheduled

    @pytest.mark.parametrize("operation", sorted(GUARDED_CALLS))
    def test_a_scheduled_failure_survives_a_call_that_had_no_session(
        self, offline: MockBrokerAdapter, operation: str
    ) -> None:
        scheduled = BrokerTimeoutError("the venue went quiet", operation=operation, venue=VENUE)
        offline.venue.schedule_failure(operation, scheduled)

        with pytest.raises(BrokerNotConnectedError):
            GUARDED_CALLS[operation](offline)

        assert offline.venue.scheduled_failures(operation) == (scheduled,)

    @pytest.mark.parametrize("operation", sorted(NEVER_RAISES))
    def test_the_methods_the_port_exempts_work_on_a_dead_session(
        self, offline: MockBrokerAdapter, operation: str
    ) -> None:
        exempt: Mapping[str, Callable[[], object]] = {
            "disconnect": offline.disconnect,
            "health": offline.health,
            "is_connected": offline.is_connected,
            "unsubscribe_ticks": lambda: offline.unsubscribe_ticks("tick-sub-1"),
            "unsubscribe_candles": lambda: offline.unsubscribe_candles("candle-sub-1"),
        }

        exempt[operation]()

        assert offline.is_connected() is False

    def test_a_failure_is_consumed_once_and_the_next_call_succeeds(
        self, adapter: MockBrokerAdapter
    ) -> None:
        adapter.venue.schedule_failure("get_tick", BrokerTimeoutError("slow", venue=VENUE))

        with pytest.raises(BrokerTimeoutError):
            adapter.get_tick("EURUSD")

        assert adapter.get_tick("EURUSD").bid == BID


class TestLifecycle:
    def test_an_adapter_starts_disconnected(self, offline: MockBrokerAdapter) -> None:
        assert offline.is_connected() is False
        assert offline.health().state is ConnectionState.DISCONNECTED

    def test_connecting_reports_the_venue_and_server(self, offline: MockBrokerAdapter) -> None:
        connection = offline.connect()

        assert connection.state is ConnectionState.CONNECTED
        assert connection.connected is True
        assert (connection.broker, connection.server) == (VENUE, SERVER)

    def test_connecting_records_a_heartbeat_from_the_venue_clock(
        self, offline: MockBrokerAdapter
    ) -> None:
        offline.venue.advance(timedelta(hours=3))

        assert offline.connect().last_heartbeat == NOW + timedelta(hours=3)

    def test_no_latency_is_reported_before_it_is_measured(self, adapter: MockBrokerAdapter) -> None:
        assert adapter.health().latency_ms is None

    def test_connecting_twice_is_idempotent(self, adapter: MockBrokerAdapter) -> None:
        assert adapter.connect().state is ConnectionState.CONNECTED
        assert adapter.is_connected() is True

    def test_a_redundant_connect_does_not_consume_a_scheduled_failure(
        self, adapter: MockBrokerAdapter
    ) -> None:
        scheduled = BrokerTimeoutError("slow", venue=VENUE)
        adapter.venue.schedule_failure("connect", scheduled)

        adapter.connect()

        assert adapter.venue.scheduled_failures("connect") == (scheduled,)

    def test_a_failed_connect_leaves_the_adapter_disconnected(
        self, offline: MockBrokerAdapter
    ) -> None:
        offline.venue.schedule_failure("connect", BrokerTimeoutError("slow", venue=VENUE))

        with pytest.raises(BrokerTimeoutError):
            offline.connect()

        assert offline.is_connected() is False

    def test_disconnecting_clears_the_readings_that_described_the_session(
        self, adapter: MockBrokerAdapter
    ) -> None:
        adapter.latency()
        adapter.disconnect()

        health = adapter.health()
        assert health.latency_ms is None
        assert health.last_heartbeat is None
        assert health.connected is False

    def test_disconnecting_an_adapter_that_never_connected_is_safe(
        self, offline: MockBrokerAdapter
    ) -> None:
        offline.disconnect()

        assert offline.is_connected() is False

    def test_disconnecting_drops_this_adapters_subscriptions(
        self, adapter: MockBrokerAdapter
    ) -> None:
        adapter.subscribe_ticks(["EURUSD"], lambda _: None)

        adapter.disconnect()

        assert adapter.venue.subscription_ids() == ()

    def test_disconnecting_leaves_another_adapters_subscriptions_alone(
        self, venue: MockVenue
    ) -> None:
        mine = MockBrokerAdapter(venue)
        theirs = MockBrokerAdapter(venue)
        mine.connect()
        theirs.connect()
        mine.subscribe_ticks(["EURUSD"], lambda _: None)
        their_handle = theirs.subscribe_ticks(["EURUSD"], lambda _: None)

        mine.disconnect()

        assert venue.subscription_ids() == (their_handle,)

    def test_disconnecting_does_not_flatten_positions(self, adapter: MockBrokerAdapter) -> None:
        open_long(adapter)

        adapter.disconnect()

        assert len(adapter.venue.positions()) == 1

    def test_reconnecting_establishes_a_new_session(self, adapter: MockBrokerAdapter) -> None:
        assert adapter.reconnect().state is ConnectionState.CONNECTED
        assert adapter.is_connected() is True

    def test_reconnecting_drops_subscriptions(self, adapter: MockBrokerAdapter) -> None:
        adapter.subscribe_ticks(["EURUSD"], lambda _: None)

        adapter.reconnect()

        assert adapter.venue.subscription_ids() == ()

    def test_a_failed_reconnect_leaves_no_subscriptions_behind(
        self, adapter: MockBrokerAdapter
    ) -> None:
        adapter.subscribe_ticks(["EURUSD"], lambda _: None)
        adapter.venue.schedule_failure("reconnect", BrokerTimeoutError("slow", venue=VENUE))

        with pytest.raises(BrokerTimeoutError):
            adapter.reconnect()

        assert adapter.venue.subscription_ids() == ()
        assert adapter.is_connected() is False

    def test_a_failure_scheduled_against_connect_does_not_fail_the_recovery(
        self, offline: MockBrokerAdapter
    ) -> None:
        offline.venue.schedule_failure("connect", BrokerTimeoutError("slow", venue=VENUE))

        with pytest.raises(BrokerTimeoutError):
            offline.connect()

        assert offline.reconnect().state is ConnectionState.CONNECTED


class TestSymbols:
    def test_a_venue_offering_nothing_lists_nothing(self) -> None:
        bare = MockBrokerAdapter()
        bare.connect()

        assert list(bare.get_symbols()) == []

    def test_instruments_come_back_in_code_order(self, adapter: MockBrokerAdapter) -> None:
        assert [info.symbol for info in adapter.get_symbols()] == ["EURUSD", "GBPUSD"]

    def test_one_instrument_is_returned_whole(self, adapter: MockBrokerAdapter) -> None:
        info = adapter.get_symbol("EURUSD")

        assert info.contract_size == Decimal("100000")
        assert info.trade_mode is SymbolTradeMode.FULL

    def test_lookup_is_case_insensitive(self, adapter: MockBrokerAdapter) -> None:
        assert adapter.get_symbol("eurusd").symbol == "EURUSD"

    def test_an_instrument_the_venue_does_not_offer_names_itself_in_the_error(
        self, adapter: MockBrokerAdapter
    ) -> None:
        with pytest.raises(BrokerSymbolNotFoundError) as raised:
            adapter.get_symbol("USDJPY")

        assert raised.value.symbol == "USDJPY"
        assert raised.value.venue == VENUE


class TestTicks:
    def test_the_last_published_quote_is_returned(self, adapter: MockBrokerAdapter) -> None:
        assert adapter.get_tick("EURUSD") == quote()

    def test_a_quote_does_not_go_stale_on_its_own(self, adapter: MockBrokerAdapter) -> None:
        adapter.venue.advance(timedelta(days=7))

        assert adapter.get_tick("EURUSD").timestamp == NOW

    def test_an_instrument_with_no_quote_is_a_data_problem_not_a_symbol_problem(
        self, adapter: MockBrokerAdapter
    ) -> None:
        with pytest.raises(BrokerDataUnavailableError, match="no quote for 'GBPUSD'"):
            adapter.get_tick("GBPUSD")

    def test_several_quotes_are_keyed_by_the_spelling_the_caller_used(
        self, adapter: MockBrokerAdapter
    ) -> None:
        quotes = adapter.get_ticks(["eurusd"])

        assert list(quotes) == ["eurusd"]

    def test_an_instrument_with_no_quote_is_absent_rather_than_null(
        self, adapter: MockBrokerAdapter
    ) -> None:
        quotes = adapter.get_ticks(["EURUSD", "GBPUSD"])

        assert set(quotes) == {"EURUSD"}

    def test_one_unknown_code_fails_the_whole_request(self, adapter: MockBrokerAdapter) -> None:
        with pytest.raises(BrokerSymbolNotFoundError):
            adapter.get_ticks(["EURUSD", "USDJPY"])

    def test_asking_for_no_quotes_answers_with_none(self, adapter: MockBrokerAdapter) -> None:
        assert adapter.get_ticks([]) == {}


class TestCandles:
    def test_the_newest_closed_bar_is_returned(self, adapter: MockBrokerAdapter) -> None:
        for minute in (0, 1, 2):
            adapter.venue.publish_candle(bar(minute))

        assert adapter.get_candle("EURUSD", Timeframe.M1).open_time == bar(2).open_time

    def test_the_forming_bar_is_excluded_unless_it_is_asked_for(
        self, adapter: MockBrokerAdapter
    ) -> None:
        adapter.venue.publish_candle(bar(0))
        adapter.venue.publish_candle(bar(1, is_closed=False))

        assert adapter.get_candle("EURUSD", Timeframe.M1).is_closed is True
        assert adapter.get_candle("EURUSD", Timeframe.M1, include_forming=True).is_closed is False

    def test_asking_for_the_forming_bar_when_there_is_none_returns_a_closed_one(
        self, adapter: MockBrokerAdapter
    ) -> None:
        adapter.venue.publish_candle(bar(0))

        assert adapter.get_candle("EURUSD", Timeframe.M1, include_forming=True).is_closed is True

    def test_a_venue_holding_only_a_forming_bar_has_no_closed_bar_to_give(
        self, adapter: MockBrokerAdapter
    ) -> None:
        adapter.venue.publish_candle(bar(0, is_closed=False))

        with pytest.raises(BrokerDataUnavailableError, match="no closed M1 bar"):
            adapter.get_candle("EURUSD", Timeframe.M1)

    def test_the_requested_number_of_bars_comes_back_oldest_first(
        self, adapter: MockBrokerAdapter
    ) -> None:
        for minute in range(5):
            adapter.venue.publish_candle(bar(minute))

        series = adapter.get_candles("EURUSD", Timeframe.M1, 2)

        assert [candle.open_time for candle in series] == [bar(3).open_time, bar(4).open_time]

    def test_asking_for_more_bars_than_exist_returns_what_there_is(
        self, adapter: MockBrokerAdapter
    ) -> None:
        adapter.venue.publish_candle(bar(0))

        assert len(adapter.get_candles("EURUSD", Timeframe.M1, 500)) == 1

    def test_the_forming_bar_is_never_in_a_series(self, adapter: MockBrokerAdapter) -> None:
        adapter.venue.publish_candle(bar(0))
        adapter.venue.publish_candle(bar(1, is_closed=False))

        series = adapter.get_candles("EURUSD", Timeframe.M1, 10)

        assert [candle.is_closed for candle in series] == [True]

    def test_a_venue_with_no_closed_bars_says_so(self, adapter: MockBrokerAdapter) -> None:
        with pytest.raises(BrokerDataUnavailableError, match="no closed M1 bars"):
            adapter.get_candles("EURUSD", Timeframe.M1, 1)

    @pytest.mark.parametrize("count", [0, -1])
    def test_an_impossible_count_is_refused_before_the_session_is_checked(
        self, offline: MockBrokerAdapter, count: int
    ) -> None:
        with pytest.raises(ValueError, match="count must be at least 1"):
            offline.get_candles("EURUSD", Timeframe.M1, count)


class TestHistoricalData:
    @staticmethod
    def _stock(adapter: MockBrokerAdapter, minutes: tuple[int, ...]) -> None:
        """Publish one closed M1 bar per minute offset."""
        for minute in minutes:
            adapter.venue.publish_candle(bar(minute))

    def test_the_period_is_half_open(self, adapter: MockBrokerAdapter) -> None:
        self._stock(adapter, (0, 1, 2, 3))

        series = adapter.get_historical_data(
            "EURUSD", Timeframe.M1, NOW + timedelta(minutes=1), NOW + timedelta(minutes=3)
        )

        assert [candle.open_time for candle in series] == [bar(1).open_time, bar(2).open_time]

    def test_omitting_the_end_runs_to_the_venue_clock(self, adapter: MockBrokerAdapter) -> None:
        self._stock(adapter, (0, 1, 2))
        adapter.venue.advance(timedelta(minutes=2))

        series = adapter.get_historical_data("EURUSD", Timeframe.M1, NOW)

        assert [candle.open_time for candle in series] == [bar(0).open_time, bar(1).open_time]

    def test_a_quiet_period_inside_the_history_is_empty_rather_than_an_error(
        self, adapter: MockBrokerAdapter
    ) -> None:
        self._stock(adapter, (0, 1, 10, 11))

        series = adapter.get_historical_data(
            "EURUSD", Timeframe.M1, NOW + timedelta(minutes=4), NOW + timedelta(minutes=6)
        )

        assert list(series) == []

    def test_a_period_before_the_history_begins_is_an_error(
        self, adapter: MockBrokerAdapter
    ) -> None:
        self._stock(adapter, (0, 1))

        with pytest.raises(BrokerDataUnavailableError, match="reaching back to"):
            adapter.get_historical_data(
                "EURUSD", Timeframe.M1, NOW - timedelta(days=1), NOW + timedelta(minutes=1)
            )

    def test_a_venue_with_no_history_at_all_is_an_error(self, adapter: MockBrokerAdapter) -> None:
        with pytest.raises(BrokerDataUnavailableError):
            adapter.get_historical_data("EURUSD", Timeframe.M1, NOW, NOW + timedelta(minutes=1))

    def test_the_forming_bar_is_excluded(self, adapter: MockBrokerAdapter) -> None:
        self._stock(adapter, (0,))
        adapter.venue.publish_candle(bar(1, is_closed=False))

        series = adapter.get_historical_data(
            "EURUSD", Timeframe.M1, NOW, NOW + timedelta(minutes=5)
        )

        assert [candle.is_closed for candle in series] == [True]

    def test_a_naive_start_is_refused_before_the_session_is_checked(
        self, offline: MockBrokerAdapter
    ) -> None:
        with pytest.raises(ValueError, match="start must be timezone aware"):
            offline.get_historical_data(
                "EURUSD",
                Timeframe.M1,
                datetime(2020, 1, 1),  # noqa: DTZ001
                NOW,
            )

    def test_a_naive_end_is_refused(self, offline: MockBrokerAdapter) -> None:
        with pytest.raises(ValueError, match="end must be timezone aware"):
            offline.get_historical_data(
                "EURUSD",
                Timeframe.M1,
                NOW,
                datetime(2021, 1, 1),  # noqa: DTZ001
            )

    def test_a_period_that_does_not_run_forwards_is_refused(
        self, offline: MockBrokerAdapter
    ) -> None:
        with pytest.raises(ValueError, match="end must be after start"):
            offline.get_historical_data("EURUSD", Timeframe.M1, NOW, NOW)

    def test_a_bound_in_another_zone_names_the_same_instant(
        self, adapter: MockBrokerAdapter
    ) -> None:
        self._stock(adapter, (0, 1, 2))

        series = adapter.get_historical_data(
            "EURUSD",
            Timeframe.M1,
            NOW.astimezone(GULF),
            (NOW + timedelta(minutes=2)).astimezone(GULF),
        )

        assert [candle.open_time for candle in series] == [bar(0).open_time, bar(1).open_time]


class TestStreaming:
    def test_a_subscriber_receives_published_quotes(self, adapter: MockBrokerAdapter) -> None:
        received: list[Tick] = []
        adapter.subscribe_ticks(["EURUSD"], received.append)

        adapter.venue.publish_tick(quote(bid=Decimal("1.20000"), ask=Decimal("1.20010")))

        assert [tick.ask for tick in received] == [Decimal("1.20010")]

    def test_a_subscription_takes_the_venues_spelling_of_the_code(
        self, adapter: MockBrokerAdapter
    ) -> None:
        received: list[Tick] = []
        adapter.subscribe_ticks(["eurusd"], received.append)

        adapter.venue.publish_tick(quote())

        assert len(received) == 1

    def test_unsubscribing_stops_delivery(self, adapter: MockBrokerAdapter) -> None:
        received: list[Tick] = []
        handle = adapter.subscribe_ticks(["EURUSD"], received.append)

        adapter.unsubscribe_ticks(handle)
        adapter.venue.publish_tick(quote())

        assert received == []

    def test_a_bar_subscriber_receives_published_bars_of_its_own_length(
        self, adapter: MockBrokerAdapter
    ) -> None:
        received: list[Candle] = []
        adapter.subscribe_candles(["EURUSD"], Timeframe.M1, received.append)

        adapter.venue.publish_candle(bar(0))
        adapter.venue.publish_candle(bar(0, timeframe=Timeframe.H1))

        assert [candle.timeframe for candle in received] == [Timeframe.M1]

    def test_unsubscribing_bars_stops_delivery(self, adapter: MockBrokerAdapter) -> None:
        received: list[Candle] = []
        handle = adapter.subscribe_candles(["EURUSD"], Timeframe.M1, received.append)

        adapter.unsubscribe_candles(handle)
        adapter.venue.publish_candle(bar(0))

        assert received == []

    @pytest.mark.parametrize("subscribe", ["subscribe_ticks", "subscribe_candles"])
    def test_a_subscription_to_nothing_is_refused(
        self, adapter: MockBrokerAdapter, subscribe: str
    ) -> None:
        calls: Mapping[str, Callable[[], object]] = {
            "subscribe_ticks": lambda: adapter.subscribe_ticks([], lambda _: None),
            "subscribe_candles": lambda: adapter.subscribe_candles(
                [], Timeframe.M1, lambda _: None
            ),
        }

        with pytest.raises(ValueError, match="needs at least one symbol"):
            calls[subscribe]()

    def test_an_unknown_code_in_a_subscription_is_refused(self, adapter: MockBrokerAdapter) -> None:
        with pytest.raises(BrokerSymbolNotFoundError):
            adapter.subscribe_ticks(["EURUSD", "USDJPY"], lambda _: None)

    def test_a_refused_subscription_leaves_no_handle_behind(
        self, adapter: MockBrokerAdapter
    ) -> None:
        with pytest.raises(BrokerSymbolNotFoundError):
            adapter.subscribe_ticks(["USDJPY"], lambda _: None)

        assert adapter.venue.subscription_ids() == ()

    def test_a_throwing_handler_does_not_stop_the_stream(self, adapter: MockBrokerAdapter) -> None:
        seen: list[Tick] = []

        def explode(tick: Tick) -> None:
            seen.append(tick)
            msg = "the caller's handler is broken"
            raise RuntimeError(msg)

        adapter.subscribe_ticks(["EURUSD"], explode)
        adapter.venue.publish_tick(quote())
        adapter.venue.publish_tick(quote())

        assert len(seen) == 2
        assert len(adapter.venue.handler_failures) == 2

    def test_unsubscribing_an_unknown_handle_is_silent(self, adapter: MockBrokerAdapter) -> None:
        adapter.unsubscribe_ticks("tick-sub-404")
        adapter.unsubscribe_candles("candle-sub-404")

        assert adapter.is_connected() is True

    def test_one_adapter_cannot_unsubscribe_another(self, venue: MockVenue) -> None:
        mine = MockBrokerAdapter(venue)
        theirs = MockBrokerAdapter(venue)
        mine.connect()
        theirs.connect()
        received: list[Tick] = []
        their_handle = theirs.subscribe_ticks(["EURUSD"], received.append)

        mine.unsubscribe_ticks(their_handle)
        venue.publish_tick(quote())

        assert len(received) == 1


class TestPlaceOrder:
    def test_a_market_buy_fills_at_the_ask(self, adapter: MockBrokerAdapter) -> None:
        order = adapter.place_order(market())

        assert order.status is OrderStatus.FILLED
        assert order.price == ASK

    def test_a_market_sell_fills_at_the_bid(self, adapter: MockBrokerAdapter) -> None:
        order = adapter.place_order(market(side=OrderSide.SELL))

        assert order.price == BID

    def test_a_filled_market_order_opens_a_position(self, adapter: MockBrokerAdapter) -> None:
        adapter.place_order(market())

        position = adapter.venue.positions()[0]
        assert position.side is PositionSide.LONG
        assert position.volume == VOLUME
        assert position.entry_price == ASK

    def test_a_filled_market_order_is_no_longer_working(self, adapter: MockBrokerAdapter) -> None:
        adapter.place_order(market())

        assert list(adapter.get_orders()) == []

    def test_a_limit_order_rests_pending(self, adapter: MockBrokerAdapter) -> None:
        order = adapter.place_order(limit())

        assert order.status is OrderStatus.PENDING
        assert [working.order_id for working in adapter.get_orders()] == [order.order_id]
        assert adapter.venue.positions() == ()

    def test_a_limit_order_does_not_fill_when_the_price_reaches_it(
        self, adapter: MockBrokerAdapter
    ) -> None:
        order = adapter.place_order(limit(price=Decimal("1.09000")))

        adapter.venue.publish_tick(quote(bid=Decimal("1.08000"), ask=Decimal("1.08012")))

        assert adapter.venue.require_order(order.order_id).status is OrderStatus.PENDING

    def test_an_unknown_instrument_is_refused(self, adapter: MockBrokerAdapter) -> None:
        with pytest.raises(BrokerSymbolNotFoundError):
            adapter.place_order(market(symbol="USDJPY"))

    @pytest.mark.parametrize("field", sorted(PROTECTED_REQUESTS))
    def test_an_attached_protective_level_is_refused_rather_than_ignored(
        self, adapter: MockBrokerAdapter, field: str
    ) -> None:
        with pytest.raises(BrokerUnsupportedOperationError) as raised:
            adapter.place_order(PROTECTED_REQUESTS[field])

        assert raised.value.operation == "place_order"
        assert field in str(raised.value)

    def test_a_refused_protective_level_places_nothing(self, adapter: MockBrokerAdapter) -> None:
        with pytest.raises(BrokerUnsupportedOperationError):
            adapter.place_order(PROTECTED_REQUESTS["stop_loss"])

        assert adapter.venue.orders() == ()

    @pytest.mark.parametrize(
        ("mode", "side"),
        [
            (SymbolTradeMode.LONG_ONLY, OrderSide.SELL),
            (SymbolTradeMode.SHORT_ONLY, OrderSide.BUY),
            (SymbolTradeMode.CLOSE_ONLY, OrderSide.BUY),
            (SymbolTradeMode.DISABLED, OrderSide.BUY),
        ],
    )
    def test_a_trade_mode_that_forbids_the_direction_rejects_the_order(
        self, adapter: MockBrokerAdapter, mode: SymbolTradeMode, side: OrderSide
    ) -> None:
        adapter.venue.add_symbol(instrument(trade_mode=mode))

        with pytest.raises(BrokerOrderRejectedError) as raised:
            adapter.place_order(market(side=side))

        assert raised.value.reason == str(mode)

    @pytest.mark.parametrize(
        ("mode", "side"),
        [
            (SymbolTradeMode.LONG_ONLY, OrderSide.BUY),
            (SymbolTradeMode.SHORT_ONLY, OrderSide.SELL),
        ],
    )
    def test_a_trade_mode_that_permits_the_direction_accepts_the_order(
        self, adapter: MockBrokerAdapter, mode: SymbolTradeMode, side: OrderSide
    ) -> None:
        adapter.venue.add_symbol(instrument(trade_mode=mode))

        assert adapter.place_order(market(side=side)).status is OrderStatus.FILLED

    def test_an_account_barred_from_trading_rejects_the_order(
        self, adapter: MockBrokerAdapter
    ) -> None:
        adapter.venue.set_account(funds(trade_allowed=False))

        with pytest.raises(BrokerOrderRejectedError) as raised:
            adapter.place_order(market())

        assert raised.value.reason == "trading is disabled on the account"

    @pytest.mark.parametrize("volume", [Decimal("0.001"), Decimal(500)])
    def test_a_size_outside_the_instruments_bounds_is_rejected(
        self, adapter: MockBrokerAdapter, volume: Decimal
    ) -> None:
        with pytest.raises(BrokerOrderRejectedError) as raised:
            adapter.place_order(market(volume=volume))

        assert raised.value.reason == "volume out of range"

    def test_a_size_off_the_instruments_step_is_rejected(self, adapter: MockBrokerAdapter) -> None:
        with pytest.raises(BrokerOrderRejectedError) as raised:
            adapter.place_order(market(volume=Decimal("0.015")))

        assert raised.value.reason == "volume off step"

    def test_a_market_order_with_no_quote_to_fill_against_is_rejected(
        self, adapter: MockBrokerAdapter
    ) -> None:
        with pytest.raises(BrokerOrderRejectedError) as raised:
            adapter.place_order(market(symbol="GBPUSD"))

        assert raised.value.reason == "no quote"

    def test_a_market_order_beyond_the_free_margin_is_refused_with_both_numbers(
        self, adapter: MockBrokerAdapter
    ) -> None:
        adapter.venue.set_account(funds(free_margin=Decimal(50)))

        with pytest.raises(BrokerInsufficientMarginError) as raised:
            adapter.place_order(market())

        assert raised.value.required == VOLUME * Decimal("100000") * ASK / 100
        assert raised.value.available == Decimal(50)

    def test_a_resting_order_is_not_margin_checked(self, adapter: MockBrokerAdapter) -> None:
        adapter.venue.set_account(funds(free_margin=Decimal(0)))

        assert adapter.place_order(limit()).status is OrderStatus.PENDING

    def test_two_buys_are_two_positions_rather_than_one_netted_position(
        self, adapter: MockBrokerAdapter
    ) -> None:
        adapter.place_order(market())
        adapter.place_order(market())

        assert len(adapter.get_positions()) == 2


class TestModifyOrder:
    def test_a_working_price_can_be_moved(self, adapter: MockBrokerAdapter) -> None:
        order = adapter.place_order(limit())

        amended = adapter.modify_order(order.order_id, price=Decimal("1.08500"))

        assert amended.price == Decimal("1.08500")

    def test_a_size_can_be_changed(self, adapter: MockBrokerAdapter) -> None:
        order = adapter.place_order(limit())

        amended = adapter.modify_order(order.order_id, volume=Decimal("0.20"))

        assert amended.volume == Decimal("0.20")

    def test_an_amendment_is_restamped_from_the_venue_clock(
        self, adapter: MockBrokerAdapter
    ) -> None:
        order = adapter.place_order(limit())
        adapter.venue.advance(timedelta(minutes=7))

        amended = adapter.modify_order(order.order_id, volume=Decimal("0.20"))

        assert amended.updated_at == NOW + timedelta(minutes=7)

    def test_fields_left_unset_are_left_alone(self, adapter: MockBrokerAdapter) -> None:
        order = adapter.place_order(limit(price=Decimal("1.09000")))

        amended = adapter.modify_order(order.order_id, volume=Decimal("0.20"))

        assert amended.price == Decimal("1.09000")

    def test_an_unknown_ticket_names_itself_in_the_error(self, adapter: MockBrokerAdapter) -> None:
        with pytest.raises(BrokerOrderNotFoundError) as raised:
            adapter.modify_order("order-404", volume=VOLUME)

        assert raised.value.order_id == "order-404"

    def test_an_order_that_already_finished_is_rejected_rather_than_missing(
        self, adapter: MockBrokerAdapter
    ) -> None:
        order = adapter.place_order(market())

        with pytest.raises(BrokerOrderRejectedError) as raised:
            adapter.modify_order(order.order_id, volume=Decimal("0.20"))

        assert raised.value.reason == "order is FILLED"

    @pytest.mark.parametrize("field", sorted(ATTACH_PROTECTION))
    def test_attaching_a_protective_level_is_refused(
        self, adapter: MockBrokerAdapter, field: str
    ) -> None:
        order = adapter.place_order(limit())

        with pytest.raises(BrokerUnsupportedOperationError) as raised:
            ATTACH_PROTECTION[field](adapter, order.order_id)

        assert raised.value.operation == "modify_order"

    @pytest.mark.parametrize("field", sorted(CLEAR_PROTECTION))
    def test_removing_a_protective_level_that_was_never_there_is_accepted(
        self, adapter: MockBrokerAdapter, field: str
    ) -> None:
        order = adapter.place_order(limit())

        amended = CLEAR_PROTECTION[field](adapter, order.order_id)

        assert amended.order_id == order.order_id

    def test_an_amendment_the_domain_model_rejects_becomes_a_rejection(
        self, adapter: MockBrokerAdapter
    ) -> None:
        order = adapter.place_order(limit())

        with pytest.raises(BrokerOrderRejectedError) as raised:
            adapter.modify_order(order.order_id, price=None)

        assert raised.value.reason == "the amendment is not a well-formed order"
        assert isinstance(raised.value.__cause__, ValidationError)

    def test_a_rejected_amendment_leaves_the_order_as_it_was(
        self, adapter: MockBrokerAdapter
    ) -> None:
        order = adapter.place_order(limit())

        with pytest.raises(BrokerOrderRejectedError):
            adapter.modify_order(order.order_id, price=None)

        assert adapter.venue.require_order(order.order_id) == order


class TestCancelOrder:
    def test_cancelling_stops_the_order_working(self, adapter: MockBrokerAdapter) -> None:
        order = adapter.place_order(limit())

        cancelled = adapter.cancel_order(order.order_id)

        assert cancelled.status is OrderStatus.CANCELLED
        assert list(adapter.get_orders()) == []

    def test_an_unknown_ticket_names_itself_in_the_error(self, adapter: MockBrokerAdapter) -> None:
        with pytest.raises(BrokerOrderNotFoundError) as raised:
            adapter.cancel_order("order-404")

        assert raised.value.order_id == "order-404"

    def test_an_order_that_already_filled_is_rejected(self, adapter: MockBrokerAdapter) -> None:
        order = adapter.place_order(market())

        with pytest.raises(BrokerOrderRejectedError, match="FILLED"):
            adapter.cancel_order(order.order_id)

    def test_cancelling_twice_is_rejected(self, adapter: MockBrokerAdapter) -> None:
        order = adapter.place_order(limit())
        adapter.cancel_order(order.order_id)

        with pytest.raises(BrokerOrderRejectedError, match="CANCELLED"):
            adapter.cancel_order(order.order_id)

    def test_cancelling_an_order_does_not_touch_the_position_it_made(
        self, adapter: MockBrokerAdapter
    ) -> None:
        order = adapter.place_order(market())

        with pytest.raises(BrokerOrderRejectedError):
            adapter.cancel_order(order.order_id)

        assert len(adapter.get_positions()) == 1


class TestClosePosition:
    def test_a_long_closes_at_the_bid(self, adapter: MockBrokerAdapter) -> None:
        position = open_long(adapter)

        execution = adapter.close_position(position.position_id)

        assert execution.price == BID
        assert list(adapter.get_positions()) == []

    def test_a_short_closes_at_the_ask(self, adapter: MockBrokerAdapter) -> None:
        adapter.place_order(market(side=OrderSide.SELL))
        position = adapter.venue.positions()[0]

        assert adapter.close_position(position.position_id).price == ASK

    def test_a_close_charges_nothing(self, adapter: MockBrokerAdapter) -> None:
        position = open_long(adapter)

        execution = adapter.close_position(position.position_id)

        assert (execution.commission, execution.swap) == (Decimal(0), Decimal(0))

    def test_a_partial_close_leaves_the_rest_open_at_the_same_entry(
        self, adapter: MockBrokerAdapter
    ) -> None:
        position = open_long(adapter)

        adapter.close_position(position.position_id, Decimal("0.04"))

        remaining = adapter.get_positions()[0]
        assert remaining.position_id == position.position_id
        assert remaining.volume == Decimal("0.06")
        assert remaining.entry_price == ASK

    def test_an_unknown_ticket_names_itself_in_the_error(self, adapter: MockBrokerAdapter) -> None:
        with pytest.raises(BrokerPositionNotFoundError) as raised:
            adapter.close_position("position-404")

        assert raised.value.position_id == "position-404"

    def test_a_position_already_closed_is_not_found(self, adapter: MockBrokerAdapter) -> None:
        position = open_long(adapter)
        adapter.close_position(position.position_id)

        with pytest.raises(BrokerPositionNotFoundError):
            adapter.close_position(position.position_id)

    def test_closing_more_than_is_open_is_a_caller_error(self, adapter: MockBrokerAdapter) -> None:
        position = open_long(adapter)

        with pytest.raises(ValueError, match="cannot close 5 of position"):
            adapter.close_position(position.position_id, Decimal(5))

    def test_a_close_only_instrument_still_closes(self, adapter: MockBrokerAdapter) -> None:
        position = open_long(adapter)
        adapter.venue.add_symbol(instrument(trade_mode=SymbolTradeMode.CLOSE_ONLY))

        assert adapter.close_position(position.position_id).price == BID

    def test_a_disabled_instrument_will_not_close(self, adapter: MockBrokerAdapter) -> None:
        position = open_long(adapter)
        adapter.venue.add_symbol(instrument(trade_mode=SymbolTradeMode.DISABLED))

        with pytest.raises(BrokerOrderRejectedError) as raised:
            adapter.close_position(position.position_id)

        assert raised.value.reason == str(SymbolTradeMode.DISABLED)

    def test_an_account_barred_from_trading_will_not_close(
        self, adapter: MockBrokerAdapter
    ) -> None:
        position = open_long(adapter)
        adapter.venue.set_account(funds(trade_allowed=False))

        with pytest.raises(BrokerOrderRejectedError) as raised:
            adapter.close_position(position.position_id)

        assert raised.value.reason == "trading is disabled on the account"

    def test_a_position_with_no_quote_cannot_be_closed(self, adapter: MockBrokerAdapter) -> None:
        opening = adapter.venue.submit(market(symbol="GBPUSD"), price=Decimal("1.30000"))
        adapter.venue.fill(opening.order_id, Decimal("1.30000"))
        position = adapter.venue.positions()[0]

        with pytest.raises(BrokerOrderRejectedError) as raised:
            adapter.close_position(position.position_id)

        assert raised.value.reason == "no quote"


class TestAccountReads:
    def test_the_account_is_the_one_the_venue_holds(self, adapter: MockBrokerAdapter) -> None:
        assert adapter.get_account() == DEFAULT_ACCOUNT

    def test_positions_come_back_oldest_first(self, adapter: MockBrokerAdapter) -> None:
        first = open_long(adapter)
        second = open_long(adapter)

        assert [position.position_id for position in adapter.get_positions()] == [
            first.position_id,
            second.position_id,
        ]

    def test_positions_can_be_filtered_by_instrument(self, adapter: MockBrokerAdapter) -> None:
        open_long(adapter)
        adapter.venue.publish_tick(
            quote(symbol="GBPUSD", bid=Decimal("1.30000"), ask=Decimal("1.30018"))
        )
        open_long(adapter, symbol="GBPUSD")

        assert [position.symbol for position in adapter.get_positions("GBPUSD")] == ["GBPUSD"]

    def test_filtering_by_an_unknown_instrument_is_refused(
        self, adapter: MockBrokerAdapter
    ) -> None:
        with pytest.raises(BrokerSymbolNotFoundError):
            adapter.get_positions("USDJPY")

    def test_open_positions_agrees_with_unfiltered_positions(
        self, adapter: MockBrokerAdapter
    ) -> None:
        open_long(adapter)

        assert list(adapter.get_open_positions()) == list(adapter.get_positions())

    def test_only_working_orders_are_returned(self, adapter: MockBrokerAdapter) -> None:
        resting = adapter.place_order(limit())
        adapter.place_order(market())
        cancelled = adapter.place_order(limit(price=Decimal("1.08000")))
        adapter.cancel_order(cancelled.order_id)

        assert [order.order_id for order in adapter.get_orders()] == [resting.order_id]

    def test_orders_can_be_filtered_by_instrument(self, adapter: MockBrokerAdapter) -> None:
        adapter.place_order(limit())
        adapter.place_order(limit(price=Decimal("1.20000"), symbol="GBPUSD"))

        assert [order.symbol for order in adapter.get_orders("GBPUSD")] == ["GBPUSD"]

    def test_filtering_orders_by_an_unknown_instrument_is_refused(
        self, adapter: MockBrokerAdapter
    ) -> None:
        with pytest.raises(BrokerSymbolNotFoundError):
            adapter.get_orders("USDJPY")


class TestRisk:
    def test_margin_follows_the_stated_formula(self, adapter: MockBrokerAdapter) -> None:
        required = adapter.margin_required(
            "EURUSD", OrderSide.BUY, Decimal("1.00"), Decimal("1.20000")
        )

        assert required == Decimal("1200.00")

    def test_a_buy_is_evaluated_at_the_ask_and_a_sell_at_the_bid(
        self, adapter: MockBrokerAdapter
    ) -> None:
        buy = adapter.margin_required("EURUSD", OrderSide.BUY, VOLUME)
        sell = adapter.margin_required("EURUSD", OrderSide.SELL, VOLUME)

        assert buy == VOLUME * Decimal("100000") * ASK / 100
        assert sell == VOLUME * Decimal("100000") * BID / 100

    def test_an_explicit_price_overrides_the_quote(self, adapter: MockBrokerAdapter) -> None:
        required = adapter.margin_required("EURUSD", OrderSide.BUY, VOLUME, Decimal("2.00000"))

        assert required == VOLUME * Decimal("100000") * Decimal("2.00000") / 100

    def test_margin_needs_a_quote_when_no_price_is_given(self, adapter: MockBrokerAdapter) -> None:
        with pytest.raises(BrokerDataUnavailableError):
            adapter.margin_required("GBPUSD", OrderSide.BUY, VOLUME)

    def test_margin_for_an_unknown_instrument_is_refused(self, adapter: MockBrokerAdapter) -> None:
        with pytest.raises(BrokerSymbolNotFoundError):
            adapter.margin_required("USDJPY", OrderSide.BUY, VOLUME)

    def test_available_margin_is_the_account_field(self, adapter: MockBrokerAdapter) -> None:
        assert adapter.margin_available() == DEFAULT_ACCOUNT.free_margin
        assert adapter.margin_available() == adapter.get_account().free_margin

    def test_available_margin_can_be_negative(self, adapter: MockBrokerAdapter) -> None:
        adapter.venue.set_account(funds(free_margin=Decimal(-250)))

        assert adapter.margin_available() == Decimal(-250)

    @pytest.mark.parametrize(
        ("mode", "expected"),
        [
            (SymbolTradeMode.FULL, True),
            (SymbolTradeMode.LONG_ONLY, True),
            (SymbolTradeMode.SHORT_ONLY, True),
            (SymbolTradeMode.CLOSE_ONLY, True),
            (SymbolTradeMode.DISABLED, False),
        ],
    )
    def test_can_trade_reports_venue_permission_only(
        self, adapter: MockBrokerAdapter, mode: SymbolTradeMode, expected: bool
    ) -> None:
        adapter.venue.add_symbol(instrument(trade_mode=mode))

        assert adapter.can_trade("EURUSD") is expected

    def test_can_trade_is_false_when_the_account_may_not_trade(
        self, adapter: MockBrokerAdapter
    ) -> None:
        adapter.venue.set_account(funds(trade_allowed=False))

        assert adapter.can_trade("EURUSD") is False

    def test_can_trade_says_nothing_about_whether_an_order_will_be_accepted(
        self, adapter: MockBrokerAdapter
    ) -> None:
        adapter.venue.add_symbol(instrument(trade_mode=SymbolTradeMode.LONG_ONLY))

        assert adapter.can_trade("EURUSD") is True
        with pytest.raises(BrokerOrderRejectedError):
            adapter.place_order(market(side=OrderSide.SELL))

    def test_can_trade_for_an_unknown_instrument_is_refused(
        self, adapter: MockBrokerAdapter
    ) -> None:
        with pytest.raises(BrokerSymbolNotFoundError):
            adapter.can_trade("USDJPY")


class TestDiagnostics:
    def test_a_disconnected_adapter_does_not_answer_a_ping(
        self, offline: MockBrokerAdapter
    ) -> None:
        assert offline.ping() is False

    def test_a_connected_adapter_answers_a_ping(self, adapter: MockBrokerAdapter) -> None:
        assert adapter.ping() is True

    def test_a_scheduled_failure_makes_a_ping_report_rather_than_raise(
        self, adapter: MockBrokerAdapter
    ) -> None:
        adapter.venue.schedule_failure("ping", BrokerTimeoutError("slow", venue=VENUE))

        assert adapter.ping() is False
        assert adapter.ping() is True

    def test_a_failed_ping_records_no_heartbeat(self, adapter: MockBrokerAdapter) -> None:
        adapter.venue.advance(timedelta(minutes=5))
        adapter.venue.schedule_failure("ping", BrokerTimeoutError("slow", venue=VENUE))

        adapter.ping()

        assert adapter.health().last_heartbeat == NOW

    def test_a_successful_ping_records_a_heartbeat(self, adapter: MockBrokerAdapter) -> None:
        adapter.venue.advance(timedelta(minutes=5))

        adapter.ping()

        assert adapter.health().last_heartbeat == NOW + timedelta(minutes=5)

    def test_a_disconnected_ping_is_not_answered_by_the_venue_at_all(
        self, offline: MockBrokerAdapter
    ) -> None:
        scheduled = BrokerTimeoutError("slow", venue=VENUE)
        offline.venue.schedule_failure("ping", scheduled)

        assert offline.ping() is False
        assert offline.venue.scheduled_failures("ping") == (scheduled,)

    def test_latency_reports_the_venues_dial(self, adapter: MockBrokerAdapter) -> None:
        adapter.venue.latency_ms = 42.5

        assert adapter.latency() == 42.5

    def test_a_measured_latency_is_cached_for_health(self, adapter: MockBrokerAdapter) -> None:
        adapter.venue.latency_ms = 42.5
        adapter.latency()

        assert adapter.health().latency_ms == 42.5

    def test_server_time_is_the_venue_clock(self, adapter: MockBrokerAdapter) -> None:
        assert adapter.server_time() == NOW

        adapter.venue.advance(timedelta(days=3))

        assert adapter.server_time() == NOW + timedelta(days=3)

    def test_the_version_names_the_venue_and_admits_what_it_has_not_got(
        self, adapter: MockBrokerAdapter
    ) -> None:
        version = adapter.version()

        assert version.name == VENUE
        assert version.version == MOCK_VERSION
        assert version.build is None
        assert version.api_version is None


class TestBoundaries:
    """The places where this adapter could plausibly guess, and does not.

    Each of these fails the day somebody adds the convenience, which is the
    reason to write them down rather than the reason not to.
    """

    def test_trading_does_not_move_the_account(self, adapter: MockBrokerAdapter) -> None:
        before = adapter.get_account()

        position = open_long(adapter)
        adapter.close_position(position.position_id)

        assert adapter.get_account() == before

    def test_a_moving_quote_does_not_revalue_an_open_position(
        self, adapter: MockBrokerAdapter
    ) -> None:
        open_long(adapter)

        adapter.venue.publish_tick(quote(bid=Decimal("1.50000"), ask=Decimal("1.50020")))

        position = adapter.get_positions()[0]
        assert position.current_price == ASK
        assert position.profit == Decimal(0)

    def test_a_partial_close_realises_nothing(self, adapter: MockBrokerAdapter) -> None:
        position = open_long(adapter)

        adapter.close_position(position.position_id, Decimal("0.04"))

        assert adapter.get_positions()[0].profit == Decimal(0)

    def test_a_resting_order_is_still_visible_after_the_price_passes_it(
        self, adapter: MockBrokerAdapter
    ) -> None:
        order = adapter.place_order(limit(price=Decimal("1.09000")))

        adapter.venue.publish_tick(quote(bid=Decimal("1.05000"), ask=Decimal("1.05012")))

        assert [working.order_id for working in adapter.get_orders()] == [order.order_id]

    def test_the_clock_does_not_move_on_its_own(self, adapter: MockBrokerAdapter) -> None:
        first = adapter.server_time()

        adapter.place_order(market())
        adapter.get_symbols()

        assert adapter.server_time() == first

    def test_two_adapters_share_the_venues_positions(self, venue: MockVenue) -> None:
        mine = MockBrokerAdapter(venue)
        theirs = MockBrokerAdapter(venue)
        mine.connect()
        theirs.connect()

        mine.place_order(market())

        assert len(theirs.get_positions()) == 1

    def test_two_adapters_do_not_share_a_session(self, venue: MockVenue) -> None:
        mine = MockBrokerAdapter(venue)
        theirs = MockBrokerAdapter(venue)

        mine.connect()

        assert theirs.is_connected() is False

    def test_identifiers_are_the_same_on_every_run(self, venue: MockVenue) -> None:
        adapter = MockBrokerAdapter(venue)
        adapter.connect()

        first = adapter.place_order(limit())
        second = adapter.place_order(limit())

        assert (first.order_id, second.order_id) == ("order-1", "order-2")
