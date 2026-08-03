"""Unit tests for the translation from MetaTrader 5 structures to domain models.

Every function under test is pure, so these tests need no session, no terminal
and no clock — which is exactly the property the adapter/mapper split was made
to buy.

Three of the conversions are here because they are the ones that fail silently
if they are wrong: the server-time correction, the zero-means-absent rule, and
the stop-limit price inversion. None of them raises when it is broken. Each one
produces a plausible number that is wrong by a fixed amount, which is the
hardest kind of defect to notice in production and the easiest kind to pin down
in a test.
"""

from __future__ import annotations

from datetime import UTC, timedelta
from decimal import Decimal

import pytest

from atlas.broker.models import (
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    SymbolTradeMode,
    Timeframe,
)
from atlas.broker.mt5.constants import (
    ORDER_STATE_FILLED,
    ORDER_TYPE_BUY_STOP_LIMIT,
    ORDER_TYPE_CLOSE_BY,
    POSITION_TYPE_SELL,
    SYMBOL_TRADE_MODE_CLOSEONLY,
)
from atlas.broker.mt5.mapper import (
    MT5AccountInfo,
    MT5Deal,
    MT5Order,
    MT5Position,
    MT5SymbolInfo,
    MT5Tick,
    ServerClock,
    to_account,
    to_broker_version,
    to_candle,
    to_decimal,
    to_execution,
    to_order,
    to_position,
    to_symbol,
    to_tick,
)
from tests.unit.broker.mt5.conftest import (
    NOW,
    SERVER_OFFSET,
    FakeAccountInfo,
    FakeDeal,
    FakeOrder,
    FakePosition,
    FakeSymbolInfo,
    FakeTick,
    rate_row,
    server_epoch,
    server_epoch_ms,
)

pytestmark = pytest.mark.unit

CLOCK = ServerClock(offset=SERVER_OFFSET)
UTC_CLOCK = ServerClock()


class TestServerClock:
    def test_a_server_timestamp_is_corrected_back_to_utc(self) -> None:
        # The whole point of the class. A UTC+3 server encodes 12:00 UTC as the
        # epoch of 15:00, so reading it as UTC dates every bar three hours late.
        assert CLOCK.to_utc(server_epoch(NOW)) == NOW

    def test_an_uncorrected_read_is_wrong_by_the_offset(self) -> None:
        # Stated explicitly so the test above cannot pass by accident: with the
        # default clock the same input lands three hours away.
        assert UTC_CLOCK.to_utc(server_epoch(NOW)) == NOW + SERVER_OFFSET

    def test_the_default_offset_is_the_identity(self) -> None:
        # Correct only for a server that publishes UTC, which is the point of
        # making it a configured value rather than a guess.
        assert UTC_CLOCK.to_utc(NOW.timestamp()) == NOW

    def test_millisecond_timestamps_keep_their_resolution(self) -> None:
        result = CLOCK.to_utc_from_milliseconds(server_epoch_ms(NOW) + 250)

        assert result == NOW + timedelta(milliseconds=250)

    def test_a_request_boundary_is_encoded_the_way_the_terminal_reads_it(self) -> None:
        # `from_utc` is the inverse, and it is not decoration: asking a UTC+3
        # server for bars "from 12:00 UTC" without it requests 09:00 UTC.
        assert CLOCK.from_utc(NOW) == server_epoch(NOW)

    def test_encoding_and_decoding_round_trip(self) -> None:
        assert CLOCK.to_utc(CLOCK.from_utc(NOW)) == NOW

    def test_every_result_is_timezone_aware(self) -> None:
        # A naive datetime escaping here would be compared against aware ones
        # elsewhere and raise far from the cause.
        assert CLOCK.to_utc(server_epoch(NOW)).tzinfo is UTC


class TestScalarConversion:
    def test_a_price_becomes_its_shortest_representation(self) -> None:
        # Decimal(0.1) is the binary expansion and carries fifty digits of
        # noise, which then propagates into every sum computed from it.
        assert to_decimal(0.1) == Decimal("0.1")
        assert str(to_decimal(0.1)) == "0.1"

    def test_an_integer_survives_intact(self) -> None:
        assert to_decimal(0) == Decimal(0)


class TestAccount:
    def test_the_fields_translate(self) -> None:
        account = to_account(FakeAccountInfo(), NOW)

        assert account.account_id == "9001234"
        assert account.broker == "Example Brokerage"
        assert account.server == "Example-Demo"
        assert account.currency == "USD"
        assert account.balance == Decimal("50000.0")
        assert account.equity == Decimal("50120.5")
        assert account.leverage == 30
        assert account.trade_allowed is True
        assert account.timestamp == NOW

    def test_an_undefined_margin_level_becomes_absent(self) -> None:
        # A flat account reports margin_level as 0.0, where the ratio is in fact
        # undefined. Passed through, it is the most severe margin call
        # representable and fires every `margin_level < threshold` rule in the
        # system on an account holding nothing.
        account = to_account(FakeAccountInfo(margin=0.0, margin_level=0.0), NOW)

        assert account.margin_level is None

    def test_a_real_margin_level_survives(self) -> None:
        raw = FakeAccountInfo(margin=1250.0, margin_level=4009.64)

        assert to_account(raw, NOW).margin_level == Decimal("4009.64")

    def test_the_observation_time_comes_from_the_caller(self) -> None:
        # account_info() carries no timestamp, and a mapper that read the clock
        # itself would not be a pure function.
        stamped = to_account(FakeAccountInfo(), NOW - timedelta(minutes=5))

        assert stamped.timestamp == NOW - timedelta(minutes=5)


class TestSymbol:
    def test_the_contract_terms_translate(self) -> None:
        symbol = to_symbol(FakeSymbolInfo())

        assert symbol.symbol == "EURUSD"
        assert symbol.base_currency == "EUR"
        assert symbol.digits == 5
        assert symbol.point == Decimal("0.00001")
        assert symbol.min_volume == Decimal("0.01")
        assert symbol.trade_mode is SymbolTradeMode.FULL

    def test_the_quote_currency_is_the_profit_currency(self) -> None:
        # Not currency_margin: profit on EURUSD is denominated in USD, which is
        # what the price is expressed in. On some instruments the margin
        # currency is neither leg of the pair.
        assert to_symbol(FakeSymbolInfo()).quote_currency == "USD"

    def test_a_restricted_instrument_keeps_its_restriction(self) -> None:
        raw = FakeSymbolInfo(trade_mode=SYMBOL_TRADE_MODE_CLOSEONLY)

        assert to_symbol(raw).trade_mode is SymbolTradeMode.CLOSE_ONLY

    def test_an_unmodelled_trade_mode_is_refused(self) -> None:
        # Guessing FULL here would let Atlas send an order the venue will reject.
        with pytest.raises(ValueError, match="unknown MetaTrader 5 symbol trade mode"):
            to_symbol(FakeSymbolInfo(trade_mode=99))


class TestTick:
    def test_the_quote_translates(self) -> None:
        tick = to_tick(FakeTick(), "EURUSD", CLOCK)

        assert tick.symbol == "EURUSD"
        assert tick.bid == Decimal("1.1624")
        assert tick.ask == Decimal("1.16252")

    def test_the_millisecond_timestamp_is_preferred(self) -> None:
        # Both fields describe the same quote, but the whole-second one cannot
        # separate two updates inside a second, which is ordinary in liquid
        # instruments.
        tick = to_tick(FakeTick(), "EURUSD", CLOCK)

        assert tick.timestamp == NOW + timedelta(milliseconds=250)

    def test_the_second_timestamp_is_used_when_the_terminal_leaves_it_unset(self) -> None:
        tick = to_tick(FakeTick(time_msc=0), "EURUSD", CLOCK)

        assert tick.timestamp == NOW

    def test_an_absent_last_price_is_not_a_price_of_zero(self) -> None:
        # MetaTrader 5 has no null. Spot FX reports no last trade at all, and
        # `Decimal("0")` in a price field is a real price to everything above.
        assert to_tick(FakeTick(last=0.0), "EURUSD", CLOCK).last is None

    def test_a_real_last_price_survives(self) -> None:
        assert to_tick(FakeTick(last=1.1625), "EURUSD", CLOCK).last == Decimal("1.1625")

    def test_the_higher_precision_volume_is_preferred(self) -> None:
        tick = to_tick(FakeTick(volume=3, volume_real=3.5), "EURUSD", CLOCK)

        assert tick.volume == Decimal("3.5")

    def test_the_integer_volume_stands_in_when_the_real_one_is_absent(self) -> None:
        tick = to_tick(FakeTick(volume=3, volume_real=0.0), "EURUSD", CLOCK)

        assert tick.volume == Decimal(3)

    def test_the_instrument_comes_from_the_caller(self) -> None:
        # The terminal's tick structure does not name its own instrument.
        assert to_tick(FakeTick(), "GBPUSD", CLOCK).symbol == "GBPUSD"


class TestCandle:
    def test_the_bar_translates(self) -> None:
        candle = to_candle(rate_row(NOW), "EURUSD", Timeframe.M15, CLOCK, is_closed=True)

        assert candle.symbol == "EURUSD"
        assert candle.timeframe is Timeframe.M15
        assert candle.open == Decimal("1.162")
        assert candle.high == Decimal("1.1631")
        assert candle.low == Decimal("1.1618")
        assert candle.close == Decimal("1.16245")
        assert candle.volume == Decimal("1834.0")

    def test_the_open_time_is_corrected_to_utc(self) -> None:
        candle = to_candle(rate_row(NOW), "EURUSD", Timeframe.H1, CLOCK, is_closed=True)

        assert candle.open_time == NOW

    def test_the_close_time_is_derived_from_the_timeframe(self) -> None:
        # MetaTrader 5 reports only the opening time. The domain model requires
        # a close, so it is nominal — see the mapper's note about daylight
        # saving.
        candle = to_candle(rate_row(NOW), "EURUSD", Timeframe.H4, CLOCK, is_closed=True)

        assert candle.close_time == NOW + timedelta(hours=4)

    def test_whether_the_bar_is_closed_comes_from_the_caller(self) -> None:
        # The row carries no such flag: only the caller knows whether it asked
        # for index 0.
        forming = to_candle(rate_row(NOW), "EURUSD", Timeframe.M5, CLOCK, is_closed=False)

        assert forming.is_closed is False


class TestPosition:
    def test_the_position_translates(self) -> None:
        position = to_position(FakePosition(), CLOCK, Decimal("-0.7"))

        assert position.position_id == "550001"
        assert position.symbol == "EURUSD"
        assert position.side is PositionSide.LONG
        assert position.volume == Decimal("0.1")
        assert position.entry_price == Decimal("1.162")
        assert position.current_price == Decimal("1.16245")
        assert position.profit == Decimal("4.5")
        assert position.swap == Decimal("-0.32")
        assert position.opened_at == NOW

    def test_a_short_position_keeps_its_direction(self) -> None:
        raw = FakePosition(type=POSITION_TYPE_SELL)

        assert to_position(raw, CLOCK, Decimal(0)).side is PositionSide.SHORT

    def test_the_commission_comes_from_the_caller(self) -> None:
        # MetaTrader 5 charges commission against the deals that opened the
        # position and reports none on the position itself, so the mapper cannot
        # obtain it and refuses to default it.
        assert to_position(FakePosition(), CLOCK, Decimal("-1.4")).commission == Decimal("-1.4")

    def test_an_unmodelled_position_type_is_refused(self) -> None:
        with pytest.raises(ValueError, match="unknown MetaTrader 5 position type"):
            to_position(FakePosition(type=42), CLOCK, Decimal(0))


class TestOrder:
    def test_the_order_translates(self) -> None:
        order = to_order(FakeOrder(), CLOCK)

        assert order.order_id == "660001"
        assert order.symbol == "EURUSD"
        assert order.side is OrderSide.BUY
        assert order.type is OrderType.LIMIT
        assert order.volume == Decimal("0.1")
        assert order.status is OrderStatus.PENDING
        assert order.created_at == NOW

    def test_a_working_order_reports_its_price_and_no_trigger(self) -> None:
        order = to_order(FakeOrder(), CLOCK)

        assert order.price == Decimal("1.16")
        assert order.stop_price is None

    def test_a_stop_limit_order_has_its_two_prices_the_right_way_round(self) -> None:
        # MetaTrader 5 puts the trigger in price_open and the limit in
        # price_stoplimit; Atlas is the other way about. Reversed, the order
        # validates, transmits and triggers at the wrong price — there is no
        # error anywhere to notice.
        raw = FakeOrder(
            type=ORDER_TYPE_BUY_STOP_LIMIT,
            price_open=1.1700,
            price_stoplimit=1.1690,
        )

        order = to_order(raw, CLOCK)

        assert order.type is OrderType.STOP_LIMIT
        assert order.stop_price == Decimal("1.17")
        assert order.price == Decimal("1.169")

    def test_attached_protection_translates(self) -> None:
        order = to_order(FakeOrder(), CLOCK)

        assert order.stop_loss == Decimal("1.155")
        assert order.take_profit == Decimal("1.17")

    def test_absent_protection_is_not_a_price_of_zero(self) -> None:
        order = to_order(FakeOrder(sl=0.0, tp=0.0), CLOCK)

        assert order.stop_loss is None
        assert order.take_profit is None

    def test_an_untouched_order_reports_its_setup_time_as_its_update_time(self) -> None:
        # time_done_msc is zero until the order changes. Passed through it would
        # date the update to 1970 and violate the model's ordering rule.
        order = to_order(FakeOrder(time_done_msc=0), CLOCK)

        assert order.updated_at == order.created_at

    def test_a_completed_order_reports_when_it_completed(self) -> None:
        done = NOW + timedelta(minutes=7)
        raw = FakeOrder(state=ORDER_STATE_FILLED, time_done_msc=server_epoch_ms(done))

        order = to_order(raw, CLOCK)

        assert order.status is OrderStatus.FILLED
        assert order.updated_at == done

    def test_the_requested_volume_is_reported_not_the_remainder(self) -> None:
        # volume_current is what is left unfilled; using it would make a
        # half-filled order look like a smaller order.
        assert to_order(FakeOrder(volume_initial=2.5), CLOCK).volume == Decimal("2.5")

    def test_a_netting_instruction_is_refused(self) -> None:
        # ORDER_TYPE_CLOSE_BY has no direction. Guessing one would be worse than
        # refusing to translate it.
        with pytest.raises(ValueError, match="unknown MetaTrader 5 order type"):
            to_order(FakeOrder(type=ORDER_TYPE_CLOSE_BY), CLOCK)

    def test_an_unmodelled_state_is_refused(self) -> None:
        with pytest.raises(ValueError, match="unknown MetaTrader 5 order state"):
            to_order(FakeOrder(state=77), CLOCK)


class TestExecution:
    def test_the_deal_translates(self) -> None:
        execution = to_execution(FakeDeal(), CLOCK)

        assert execution.execution_id == "770001"
        assert execution.order_id == "660001"
        assert execution.symbol == "EURUSD"
        assert execution.price == Decimal("1.162")
        assert execution.volume == Decimal("0.1")
        assert execution.commission == Decimal("-0.7")
        assert execution.timestamp == NOW

    def test_a_charge_keeps_its_sign(self) -> None:
        # Commission arrives negative because it is money leaving the account.
        # Taking its absolute value would turn a cost into a credit.
        assert to_execution(FakeDeal(commission=-2.5), CLOCK).commission == Decimal("-2.5")


class TestBrokerVersion:
    def test_the_two_terminal_calls_are_assembled(self) -> None:
        version = to_broker_version("MetaTrader 5", 500, 4620)

        assert version.name == "MetaTrader 5"
        assert version.version == "500"
        assert version.build == 4620
        assert version.api_version is None


class TestProtocolConformance:
    """The fakes must satisfy the protocols the production code declares.

    Without this, the suite could pass against structures the adapter could not
    actually read — the fake would have drifted from the vendor surface and
    every other test would still be green.
    """

    def test_the_account_structure_conforms(self) -> None:
        assert isinstance(FakeAccountInfo(), MT5AccountInfo)

    def test_the_symbol_structure_conforms(self) -> None:
        assert isinstance(FakeSymbolInfo(), MT5SymbolInfo)

    def test_the_tick_structure_conforms(self) -> None:
        assert isinstance(FakeTick(), MT5Tick)

    def test_the_position_structure_conforms(self) -> None:
        assert isinstance(FakePosition(), MT5Position)

    def test_the_order_structure_conforms(self) -> None:
        assert isinstance(FakeOrder(), MT5Order)

    def test_the_deal_structure_conforms(self) -> None:
        assert isinstance(FakeDeal(), MT5Deal)

    def test_a_structure_missing_a_field_does_not_conform(self) -> None:
        # Proves the checks above can fail. A quote has no ticket, no side and
        # no open price, so it must not pass for a position; a protocol
        # assertion that accepts everything tests nothing.
        assert not isinstance(FakeTick(), MT5Position)
