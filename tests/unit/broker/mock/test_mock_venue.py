"""What the in-memory venue holds, and what it refuses to invent.

Two things are being checked here, and the second matters more than the first.
The first is that the venue does what it says: a published quote is retrievable,
a filled order opens a position, a cancelled order stops working. The second is
that it does *only* that. A mock earns its place by being predictable, and every
place where this one could plausibly have guessed — revaluing a position when a
quote moves, filling a limit when a price crosses it, moving the balance when a
trade opens — has a test asserting that it does not. Those tests fail the day
somebody adds the convenience, which is the point of them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from atlas.broker.exceptions import BrokerTimeoutError
from atlas.broker.mock import DEFAULT_ACCOUNT, DEFAULT_START, SERVER, VENUE, MockVenue
from atlas.broker.models import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    Timeframe,
)
from tests.unit.broker.mock.conftest import (
    ASK,
    BID,
    EURUSD,
    GBPUSD,
    VOLUME,
    bar,
    funds,
    instrument,
    limit,
    market,
)
from tests.unit.broker.mock.conftest import tick as quote

if TYPE_CHECKING:
    from atlas.broker.models import Candle, Tick

pytestmark = pytest.mark.unit

#: A zone that is not UTC, so "normalised to UTC" has something to normalise.
GULF = timezone(timedelta(hours=4))


class TestClock:
    def test_a_new_venue_starts_at_the_documented_instant(self) -> None:
        assert MockVenue().now() == DEFAULT_START

    def test_the_clock_moves_only_when_a_test_moves_it(self, venue: MockVenue) -> None:
        first = venue.now()
        venue.publish_tick(quote())
        venue.submit(market())
        assert venue.now() == first

    def test_advancing_returns_the_new_time_and_stores_it(self, venue: MockVenue) -> None:
        moved = venue.advance(timedelta(minutes=90))

        assert moved == DEFAULT_START + timedelta(minutes=90)
        assert venue.now() == moved

    def test_setting_the_time_normalises_to_utc(self, venue: MockVenue) -> None:
        elsewhere = datetime(2021, 6, 1, 12, tzinfo=GULF)
        venue.set_time(elsewhere)

        assert venue.now() == elsewhere
        assert venue.now().tzinfo is UTC
        assert venue.now().hour == 8

    def test_a_naive_start_is_refused(self) -> None:
        with pytest.raises(ValueError, match="now must be timezone aware"):
            MockVenue(now=datetime(2020, 1, 1))  # noqa: DTZ001

    def test_a_naive_set_time_is_refused(self, venue: MockVenue) -> None:
        with pytest.raises(ValueError, match="moment must be timezone aware"):
            venue.set_time(datetime(2020, 1, 1))  # noqa: DTZ001

    def test_the_clock_will_not_run_backwards(self, venue: MockVenue) -> None:
        with pytest.raises(ValueError, match="delta must not be negative"):
            venue.advance(timedelta(seconds=-1))

    def test_a_zero_advance_is_allowed(self, venue: MockVenue) -> None:
        assert venue.advance(timedelta()) == DEFAULT_START


class TestInstruments:
    def test_an_unregistered_instrument_is_none_rather_than_an_error(self) -> None:
        assert MockVenue().symbol("EURUSD") is None

    def test_lookup_is_case_insensitive_and_ignores_surrounding_space(
        self, venue: MockVenue
    ) -> None:
        assert venue.symbol("  eurusd ") == EURUSD

    def test_registering_the_same_code_twice_replaces_rather_than_duplicates(
        self, venue: MockVenue
    ) -> None:
        revised = instrument(spread=40)
        venue.add_symbol(revised)

        assert venue.symbols() == (revised, GBPUSD)

    def test_instruments_are_listed_in_code_order(self, venue: MockVenue) -> None:
        assert [info.symbol for info in venue.symbols()] == ["EURUSD", "GBPUSD"]


class TestMarketData:
    def test_a_published_quote_is_the_one_returned(self, venue: MockVenue) -> None:
        published = quote(bid=Decimal("1.20000"), ask=Decimal("1.20015"))
        venue.publish_tick(published)

        assert venue.quote("EURUSD") == published

    def test_an_instrument_with_no_quote_reads_as_none(self, venue: MockVenue) -> None:
        assert venue.quote("GBPUSD") is None

    def test_publishing_for_an_unregistered_instrument_is_a_test_bug(
        self, venue: MockVenue
    ) -> None:
        with pytest.raises(ValueError, match="no instrument 'USDJPY' is registered"):
            venue.publish_tick(quote(symbol="USDJPY"))

    def test_bars_come_back_oldest_first_however_they_arrived(self, venue: MockVenue) -> None:
        venue.publish_candle(bar(3))
        venue.publish_candle(bar(1))
        venue.publish_candle(bar(2))

        assert [candle.open_time for candle in venue.candles("EURUSD", Timeframe.M1)] == [
            bar(1).open_time,
            bar(2).open_time,
            bar(3).open_time,
        ]

    def test_a_bar_republished_at_the_same_open_time_replaces_the_earlier_one(
        self, venue: MockVenue
    ) -> None:
        venue.publish_candle(bar(1, is_closed=False))
        venue.publish_candle(bar(1))

        held = venue.candles("EURUSD", Timeframe.M1)
        assert len(held) == 1
        assert held[0].is_closed

    def test_bars_of_different_lengths_are_held_apart(self, venue: MockVenue) -> None:
        venue.publish_candle(bar(0))
        venue.publish_candle(bar(0, timeframe=Timeframe.H1))

        assert len(venue.candles("EURUSD", Timeframe.M1)) == 1
        assert len(venue.candles("EURUSD", Timeframe.H1)) == 1

    def test_bars_for_an_unregistered_instrument_are_a_test_bug(self, venue: MockVenue) -> None:
        with pytest.raises(ValueError, match="no instrument 'USDJPY' is registered"):
            venue.publish_candle(bar(0, symbol="USDJPY"))


class TestSubscriptions:
    def test_a_subscriber_receives_a_quote_before_publish_returns(self, venue: MockVenue) -> None:
        received: list[Tick] = []
        venue.open_tick_subscription(self, ["EURUSD"], received.append)

        venue.publish_tick(quote(bid=Decimal("1.30000"), ask=Decimal("1.30020")))

        assert [tick.bid for tick in received] == [Decimal("1.30000")]

    def test_a_subscriber_hears_nothing_about_an_instrument_it_did_not_ask_for(
        self, venue: MockVenue
    ) -> None:
        received: list[Tick] = []
        venue.open_tick_subscription(self, ["GBPUSD"], received.append)

        venue.publish_tick(quote())

        assert received == []

    def test_a_bar_subscriber_hears_only_its_own_timeframe(self, venue: MockVenue) -> None:
        received: list[Candle] = []
        venue.open_candle_subscription(self, ["EURUSD"], Timeframe.H1, received.append)

        venue.publish_candle(bar(0))
        venue.publish_candle(bar(0, timeframe=Timeframe.H1))

        assert [candle.timeframe for candle in received] == [Timeframe.H1]

    def test_a_bar_subscriber_hears_forming_bars_too(self, venue: MockVenue) -> None:
        received: list[Candle] = []
        venue.open_candle_subscription(self, ["EURUSD"], Timeframe.M1, received.append)

        venue.publish_candle(bar(0, is_closed=False))

        assert [candle.is_closed for candle in received] == [False]

    def test_a_handler_that_throws_does_not_kill_its_subscription(self, venue: MockVenue) -> None:
        received: list[Tick] = []

        def explode(tick: Tick) -> None:
            received.append(tick)
            msg = "the handler is broken"
            raise RuntimeError(msg)

        venue.open_tick_subscription(self, ["EURUSD"], explode)
        venue.publish_tick(quote())
        venue.publish_tick(quote())

        assert len(received) == 2

    def test_what_a_handler_threw_is_recorded_rather_than_swallowed(self, venue: MockVenue) -> None:
        def explode(_tick: Tick) -> None:
            msg = "the handler is broken"
            raise RuntimeError(msg)

        venue.open_tick_subscription(self, ["EURUSD"], explode)
        venue.publish_tick(quote())

        assert [str(failure) for failure in venue.handler_failures] == ["the handler is broken"]

    def test_closing_a_subscription_stops_delivery(self, venue: MockVenue) -> None:
        received: list[Tick] = []
        subscription_id = venue.open_tick_subscription(self, ["EURUSD"], received.append)

        venue.close_subscription(self, subscription_id)
        venue.publish_tick(quote())

        assert received == []

    def test_one_owner_cannot_close_another_owners_subscription(self, venue: MockVenue) -> None:
        received: list[Tick] = []
        mine = venue.open_tick_subscription(self, ["EURUSD"], received.append)
        somebody_else = object()

        venue.close_subscription(somebody_else, mine)
        venue.publish_tick(quote())

        assert len(received) == 1
        assert venue.subscription_ids() == (mine,)

    def test_closing_an_unknown_handle_is_silent(self, venue: MockVenue) -> None:
        venue.close_subscription(self, "no-such-subscription")

    def test_closing_twice_is_silent(self, venue: MockVenue) -> None:
        subscription_id = venue.open_tick_subscription(self, ["EURUSD"], lambda _: None)

        venue.close_subscription(self, subscription_id)
        venue.close_subscription(self, subscription_id)

    def test_closing_by_owner_drops_both_kinds_and_leaves_other_owners_alone(
        self, venue: MockVenue
    ) -> None:
        somebody_else = object()
        theirs = venue.open_tick_subscription(somebody_else, ["EURUSD"], lambda _: None)
        venue.open_tick_subscription(self, ["EURUSD"], lambda _: None)
        venue.open_candle_subscription(self, ["EURUSD"], Timeframe.M1, lambda _: None)

        venue.close_subscriptions(self)

        assert venue.subscription_ids() == (theirs,)

    def test_handles_are_sequential_and_name_their_kind(self, venue: MockVenue) -> None:
        first = venue.open_tick_subscription(self, ["EURUSD"], lambda _: None)
        second = venue.open_tick_subscription(self, ["EURUSD"], lambda _: None)
        bars = venue.open_candle_subscription(self, ["EURUSD"], Timeframe.M1, lambda _: None)

        assert (first, second, bars) == ("tick-sub-1", "tick-sub-2", "candle-sub-1")


class TestOrdersAndFills:
    def test_a_submitted_order_rests_pending_with_a_sequential_ticket(
        self, venue: MockVenue
    ) -> None:
        order = venue.submit(limit())

        assert order.order_id == "order-1"
        assert order.status is OrderStatus.PENDING
        assert order.price == Decimal("1.09000")
        assert venue.orders() == (order,)

    def test_a_market_order_is_stamped_with_the_price_the_caller_supplied(
        self, venue: MockVenue
    ) -> None:
        order = venue.submit(market(), price=ASK)

        assert order.price == ASK

    def test_a_working_price_on_the_request_wins_for_a_non_market_order(
        self, venue: MockVenue
    ) -> None:
        order = venue.submit(limit(price=Decimal("1.05000")), price=Decimal("9.99999"))

        assert order.price == Decimal("1.05000")

    def test_filling_marks_the_order_filled_and_opens_a_position(self, venue: MockVenue) -> None:
        order = venue.submit(market(), price=ASK)

        execution = venue.fill(order.order_id, ASK)

        assert venue.require_order(order.order_id).status is OrderStatus.FILLED
        position = venue.positions()[0]
        assert position.side is PositionSide.LONG
        assert position.entry_price == ASK
        assert position.current_price == ASK
        assert execution.order_id == order.order_id
        assert execution.price == ASK

    def test_a_sell_fill_opens_a_short(self, venue: MockVenue) -> None:
        order = venue.submit(market(side=OrderSide.SELL), price=BID)

        venue.fill(order.order_id, BID)

        assert venue.positions()[0].side is PositionSide.SHORT

    def test_a_fresh_position_carries_no_profit_swap_or_commission(self, venue: MockVenue) -> None:
        order = venue.submit(market(), price=ASK)
        venue.fill(order.order_id, ASK)

        position = venue.positions()[0]
        assert (position.profit, position.swap, position.commission) == (
            Decimal(0),
            Decimal(0),
            Decimal(0),
        )

    def test_a_fill_books_an_execution_in_order(self, venue: MockVenue) -> None:
        first = venue.submit(market(), price=ASK)
        venue.fill(first.order_id, ASK)
        second = venue.submit(market(), price=ASK)
        venue.fill(second.order_id, ASK)

        assert [execution.execution_id for execution in venue.executions()] == [
            "execution-1",
            "execution-2",
        ]

    def test_a_price_that_crosses_a_resting_order_does_not_fill_it(self, venue: MockVenue) -> None:
        order = venue.submit(limit(price=Decimal("1.09000")))

        venue.publish_tick(quote(bid=Decimal("1.08000"), ask=Decimal("1.08012")))

        assert venue.require_order(order.order_id).status is OrderStatus.PENDING
        assert venue.positions() == ()

    def test_filling_an_unknown_order_is_a_test_bug(self, venue: MockVenue) -> None:
        with pytest.raises(ValueError, match="no order 'order-99' exists"):
            venue.fill("order-99", ASK)

    def test_filling_twice_is_a_test_bug(self, venue: MockVenue) -> None:
        order = venue.submit(market(), price=ASK)
        venue.fill(order.order_id, ASK)

        with pytest.raises(ValueError, match="already FILLED and cannot fill"):
            venue.fill(order.order_id, ASK)

    def test_cancelling_stops_the_order_working(self, venue: MockVenue) -> None:
        order = venue.submit(limit())

        cancelled = venue.cancel(order.order_id)

        assert cancelled.status is OrderStatus.CANCELLED
        assert venue.require_order(order.order_id).status is OrderStatus.CANCELLED

    def test_cancelling_an_unknown_order_is_a_test_bug(self, venue: MockVenue) -> None:
        with pytest.raises(ValueError, match="no order 'order-99' exists"):
            venue.cancel("order-99")

    def test_cancelling_a_filled_order_is_a_test_bug(self, venue: MockVenue) -> None:
        order = venue.submit(market(), price=ASK)
        venue.fill(order.order_id, ASK)

        with pytest.raises(ValueError, match="already FILLED and cannot be cancelled"):
            venue.cancel(order.order_id)

    def test_closing_in_full_removes_the_position_and_books_the_other_side(
        self, venue: MockVenue
    ) -> None:
        opening = venue.submit(market(), price=ASK)
        venue.fill(opening.order_id, ASK)
        position_id = venue.positions()[0].position_id

        execution = venue.close(position_id, BID)

        assert venue.position(position_id) is None
        closing = venue.require_order(execution.order_id)
        assert closing.side is OrderSide.SELL
        assert closing.type is OrderType.MARKET
        assert closing.status is OrderStatus.FILLED
        assert execution.price == BID

    def test_closing_a_short_books_a_buy(self, venue: MockVenue) -> None:
        opening = venue.submit(market(side=OrderSide.SELL), price=BID)
        venue.fill(opening.order_id, BID)
        position_id = venue.positions()[0].position_id

        execution = venue.close(position_id, ASK)

        assert venue.require_order(execution.order_id).side is OrderSide.BUY

    def test_a_partial_close_leaves_the_remainder_under_the_same_ticket(
        self, venue: MockVenue
    ) -> None:
        opening = venue.submit(market(), price=ASK)
        venue.fill(opening.order_id, ASK)
        position_id = venue.positions()[0].position_id

        venue.close(position_id, BID, Decimal("0.04"))

        remaining = venue.require_position(position_id)
        assert remaining.volume == Decimal("0.06")
        assert remaining.entry_price == ASK

    def test_closing_more_than_is_open_is_a_test_bug(self, venue: MockVenue) -> None:
        opening = venue.submit(market(), price=ASK)
        venue.fill(opening.order_id, ASK)
        position_id = venue.positions()[0].position_id

        with pytest.raises(ValueError, match="cannot close 5 of position"):
            venue.close(position_id, BID, Decimal(5))

    def test_closing_an_unknown_position_is_a_test_bug(self, venue: MockVenue) -> None:
        with pytest.raises(ValueError, match="no position 'position-99' exists"):
            venue.close("position-99", BID)

    def test_amending_restamps_from_the_venue_clock(self, venue: MockVenue) -> None:
        order = venue.submit(limit())
        venue.advance(timedelta(minutes=5))

        amended = venue.amend(order.order_id, {"price": Decimal("1.08500")})

        assert amended.price == Decimal("1.08500")
        assert amended.updated_at == DEFAULT_START + timedelta(minutes=5)
        assert amended.created_at == DEFAULT_START

    def test_an_amendment_cannot_forge_its_own_timestamp(self, venue: MockVenue) -> None:
        order = venue.submit(limit())
        venue.advance(timedelta(minutes=5))

        amended = venue.amend(order.order_id, {"updated_at": DEFAULT_START})

        assert amended.updated_at == DEFAULT_START + timedelta(minutes=5)

    def test_an_amendment_that_breaks_the_model_is_refused_by_the_model(
        self, venue: MockVenue
    ) -> None:
        order = venue.submit(limit())

        with pytest.raises(ValidationError):
            venue.amend(order.order_id, {"price": None})

    def test_a_refused_amendment_leaves_the_order_untouched(self, venue: MockVenue) -> None:
        order = venue.submit(limit())

        with pytest.raises(ValidationError):
            venue.amend(order.order_id, {"price": None})

        assert venue.require_order(order.order_id) == order

    def test_amending_an_unknown_order_is_a_test_bug(self, venue: MockVenue) -> None:
        with pytest.raises(ValueError, match="no order 'order-99' exists"):
            venue.amend("order-99", {"volume": VOLUME})

    def test_a_stored_order_replaces_the_venues_record(self, venue: MockVenue) -> None:
        order = venue.submit(limit())
        rejected = Order.model_validate({**order.model_dump(), "status": OrderStatus.REJECTED})

        venue.store_order(rejected)

        assert venue.require_order(order.order_id).status is OrderStatus.REJECTED

    def test_an_unknown_order_reads_as_none_but_requiring_it_raises(self, venue: MockVenue) -> None:
        assert venue.order("order-99") is None
        with pytest.raises(ValueError, match="no order 'order-99' exists"):
            venue.require_order("order-99")

    def test_an_unknown_position_reads_as_none_but_requiring_it_raises(
        self, venue: MockVenue
    ) -> None:
        assert venue.position("position-99") is None
        with pytest.raises(ValueError, match="no position 'position-99' exists"):
            venue.require_position("position-99")


class TestRevaluation:
    def test_a_moving_quote_does_not_revalue_a_position(self, venue: MockVenue) -> None:
        opening = venue.submit(market(), price=ASK)
        venue.fill(opening.order_id, ASK)

        venue.publish_tick(quote(bid=Decimal("1.50000"), ask=Decimal("1.50020")))

        position = venue.positions()[0]
        assert position.current_price == ASK
        assert position.profit == Decimal(0)

    def test_revaluing_changes_only_the_fields_given(self, venue: MockVenue) -> None:
        opening = venue.submit(market(), price=ASK)
        venue.fill(opening.order_id, ASK)
        position_id = venue.positions()[0].position_id

        revalued = venue.revalue(position_id, profit=Decimal("12.50"))

        assert revalued.profit == Decimal("12.50")
        assert revalued.current_price == ASK
        assert revalued.swap == Decimal(0)

    def test_revaluing_accepts_every_figure_at_once(self, venue: MockVenue) -> None:
        opening = venue.submit(market(), price=ASK)
        venue.fill(opening.order_id, ASK)
        position_id = venue.positions()[0].position_id

        revalued = venue.revalue(
            position_id,
            current_price=Decimal("1.10500"),
            profit=Decimal("48.80"),
            swap=Decimal("-1.20"),
            commission=Decimal("-0.70"),
        )

        assert (revalued.current_price, revalued.profit, revalued.swap, revalued.commission) == (
            Decimal("1.10500"),
            Decimal("48.80"),
            Decimal("-1.20"),
            Decimal("-0.70"),
        )

    def test_revaluing_an_unknown_position_is_a_test_bug(self, venue: MockVenue) -> None:
        with pytest.raises(ValueError, match="no position 'position-99' exists"):
            venue.revalue("position-99", profit=Decimal(1))


class TestAccount:
    def test_a_new_venue_holds_the_documented_account(self) -> None:
        account = MockVenue().account

        assert account == DEFAULT_ACCOUNT
        assert (account.broker, account.server) == (VENUE, SERVER)

    def test_trading_does_not_move_the_account(self, venue: MockVenue) -> None:
        before = venue.account
        opening = venue.submit(market(), price=ASK)
        venue.fill(opening.order_id, ASK)

        assert venue.account == before

    def test_the_account_is_stored_verbatim_rather_than_restamped(self, venue: MockVenue) -> None:
        venue.advance(timedelta(days=1))
        replacement = funds(balance=Decimal(250))

        venue.set_account(replacement)

        assert venue.account == replacement
        assert venue.account.timestamp == DEFAULT_START

    def test_a_venue_can_be_built_around_a_supplied_account(self) -> None:
        supplied = funds(account_id="OTHER-9")

        assert MockVenue(account=supplied).account.account_id == "OTHER-9"


class TestFaultInjection:
    def test_a_scheduled_failure_is_handed_back_once(self, venue: MockVenue) -> None:
        error = BrokerTimeoutError("too slow", venue=VENUE)
        venue.schedule_failure("get_tick", error)

        assert venue.take_failure("get_tick") is error
        assert venue.take_failure("get_tick") is None

    def test_failures_queue_and_come_back_in_order(self, venue: MockVenue) -> None:
        first = BrokerTimeoutError("first", venue=VENUE)
        second = BrokerTimeoutError("second", venue=VENUE)
        venue.schedule_failure("get_tick", first)
        venue.schedule_failure("get_tick", second)

        assert (venue.take_failure("get_tick"), venue.take_failure("get_tick")) == (first, second)

    def test_a_pending_failure_is_visible_without_consuming_it(self, venue: MockVenue) -> None:
        error = BrokerTimeoutError("too slow", venue=VENUE)
        venue.schedule_failure("get_tick", error)

        assert venue.scheduled_failures("get_tick") == (error,)
        assert venue.scheduled_failures("get_tick") == (error,)

    def test_nothing_is_scheduled_against_an_untouched_operation(self, venue: MockVenue) -> None:
        assert venue.scheduled_failures("get_tick") == ()
        assert venue.take_failure("get_tick") is None

    def test_a_misspelled_operation_fails_at_schedule_time(self, venue: MockVenue) -> None:
        with pytest.raises(ValueError, match="'get_tickk' is not a BrokerAdapter method"):
            venue.schedule_failure("get_tickk", BrokerTimeoutError("too slow", venue=VENUE))

    @pytest.mark.parametrize(
        "operation",
        ["disconnect", "health", "is_connected", "unsubscribe_candles", "unsubscribe_ticks"],
    )
    def test_an_operation_the_port_forbids_from_raising_cannot_be_failed(
        self, venue: MockVenue, operation: str
    ) -> None:
        with pytest.raises(ValueError, match="could never fire"):
            venue.schedule_failure(operation, BrokerTimeoutError("too slow", venue=VENUE))

    def test_ping_can_be_failed_because_it_reports_rather_than_raises(
        self, venue: MockVenue
    ) -> None:
        venue.schedule_failure("ping", BrokerTimeoutError("too slow", venue=VENUE))

        assert len(venue.scheduled_failures("ping")) == 1
