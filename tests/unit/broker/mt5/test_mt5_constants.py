"""Unit tests for the MetaTrader 5 wire constants and translation tables.

Two kinds of check live here, and the difference matters.

The first kind derives what MetaTrader 5's encoding *should* be from its
documented rule and compares that against the table. It runs everywhere,
including on a Linux CI runner where the vendor wheel cannot be installed, and
it catches a transcription slip in a number that no other test would notice — a
wrong timeframe code does not raise, it silently requests the wrong bars.

The second kind compares the table against the installed ``MetaTrader5``
package. It is the only check that can prove Atlas and the vendor agree, and it
can run only where the wheel exists, which is Windows. It is skipped rather than
faked elsewhere: a check that cannot be performed should say so, not pass.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast

import pytest

from atlas.broker.models import OrderSide, OrderStatus, OrderType, SymbolTradeMode, Timeframe
from atlas.broker.mt5 import constants

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.unit

#: Set by MetaTrader 5 on every timeframe of an hour or longer. Written as a
#: literal rather than imported so this file derives the encoding independently
#: of the module it is checking.
HOUR_FLAG: Final = 0x4000

#: Every terminal constant Atlas declares, paired with the name it carries in
#: the vendor package. The names are identical by design — a renamed constant
#: would make this table the only place the correspondence was recorded.
DECLARED_CONSTANTS: Final[tuple[str, ...]] = (
    "TIMEFRAME_M1",
    "TIMEFRAME_M5",
    "TIMEFRAME_M15",
    "TIMEFRAME_M30",
    "TIMEFRAME_H1",
    "TIMEFRAME_H4",
    "TIMEFRAME_D1",
    "ORDER_TYPE_BUY",
    "ORDER_TYPE_SELL",
    "ORDER_TYPE_BUY_LIMIT",
    "ORDER_TYPE_SELL_LIMIT",
    "ORDER_TYPE_BUY_STOP",
    "ORDER_TYPE_SELL_STOP",
    "ORDER_TYPE_BUY_STOP_LIMIT",
    "ORDER_TYPE_SELL_STOP_LIMIT",
    "ORDER_TYPE_CLOSE_BY",
    "ORDER_STATE_STARTED",
    "ORDER_STATE_PLACED",
    "ORDER_STATE_CANCELED",
    "ORDER_STATE_PARTIAL",
    "ORDER_STATE_FILLED",
    "ORDER_STATE_REJECTED",
    "ORDER_STATE_EXPIRED",
    "ORDER_STATE_REQUEST_ADD",
    "ORDER_STATE_REQUEST_MODIFY",
    "ORDER_STATE_REQUEST_CANCEL",
    "POSITION_TYPE_BUY",
    "POSITION_TYPE_SELL",
    "SYMBOL_TRADE_MODE_DISABLED",
    "SYMBOL_TRADE_MODE_LONGONLY",
    "SYMBOL_TRADE_MODE_SHORTONLY",
    "SYMBOL_TRADE_MODE_CLOSEONLY",
    "SYMBOL_TRADE_MODE_FULL",
    "RES_S_OK",
    "RES_E_FAIL",
    "RES_E_INVALID_PARAMS",
    "RES_E_NO_MEMORY",
    "RES_E_NOT_FOUND",
    "RES_E_INVALID_VERSION",
    "RES_E_AUTH_FAILED",
    "RES_E_UNSUPPORTED",
    "RES_E_AUTO_TRADING_DISABLED",
    "RES_E_INTERNAL_FAIL",
    "RES_E_INTERNAL_FAIL_SEND",
    "RES_E_INTERNAL_FAIL_RECEIVE",
    "RES_E_INTERNAL_FAIL_INIT",
    "RES_E_INTERNAL_FAIL_CONNECT",
    "RES_E_INTERNAL_FAIL_TIMEOUT",
)

#: Every function of the vendor package the ``Terminal`` protocol declares.
DECLARED_FUNCTIONS: Final[tuple[str, ...]] = (
    "initialize",
    "shutdown",
    "last_error",
    "version",
    "terminal_info",
    "account_info",
    "symbols_get",
    "symbol_info",
    "symbol_info_tick",
    "symbol_select",
    "copy_rates_from_pos",
    "copy_rates_range",
    "positions_get",
    "orders_get",
    "history_deals_get",
    "order_calc_margin",
)


def encode_timeframe(minutes: int) -> int:
    """Encode a bar length the way MetaTrader 5 documents it.

    Args:
        minutes: The bar's length.

    Returns:
        The terminal's integer code: the length in minutes below an hour, and
        the hour flag OR'd with the number of hours at an hour and above.
    """
    hours, remainder = divmod(minutes, 60)
    if hours == 0:
        return minutes
    if remainder != 0:
        message = f"MetaTrader 5 cannot encode a {minutes}-minute bar"
        raise AssertionError(message)
    return HOUR_FLAG | hours


class TestTimeframeEncoding:
    @pytest.mark.parametrize("timeframe", list(Timeframe))
    def test_every_code_follows_the_documented_encoding(self, timeframe: Timeframe) -> None:
        # A wrong timeframe code does not raise anywhere: the terminal happily
        # returns bars of a different length, and every feature computed from
        # them is quietly wrong. Deriving the code from the rule is the only
        # check that catches a transposed digit.
        assert constants.TIMEFRAME_TO_MT5[timeframe] == encode_timeframe(timeframe.minutes)

    def test_the_daily_bar_is_encoded_as_twenty_four_hours(self) -> None:
        # The one value that looks like a mistake and is not. D1 is 16408
        # because MetaTrader 5 has no day unit; it counts 24 hours.
        assert constants.TIMEFRAME_D1 == HOUR_FLAG | 24
        assert constants.TIMEFRAME_D1 == 16408

    def test_sub_hour_timeframes_carry_no_flag(self) -> None:
        for timeframe in (Timeframe.M1, Timeframe.M5, Timeframe.M15, Timeframe.M30):
            assert constants.TIMEFRAME_TO_MT5[timeframe] & HOUR_FLAG == 0

    def test_every_modelled_timeframe_is_translatable(self) -> None:
        # The domain deliberately models fewer timeframes than the terminal
        # offers, but every one it does model must be requestable.
        assert set(constants.TIMEFRAME_TO_MT5) == set(Timeframe)

    def test_the_reverse_table_is_an_exact_inverse(self) -> None:
        inverted = {code: timeframe for timeframe, code in constants.TIMEFRAME_TO_MT5.items()}

        assert inverted == constants.MT5_TO_TIMEFRAME
        assert len(constants.MT5_TO_TIMEFRAME) == len(constants.TIMEFRAME_TO_MT5)


class TestOrderTypeTables:
    def test_every_direction_and_presentation_combination_is_covered(self) -> None:
        # MetaTrader 5 fuses side and type into one integer. If any pairing were
        # missing, orders of that shape would be unmappable in one direction and
        # unplaceable in the other.
        expected = {(side, order_type) for side in OrderSide for order_type in OrderType}

        assert set(constants.DOMAIN_TO_MT5_ORDER_TYPE) == expected

    def test_the_reverse_table_is_an_exact_inverse(self) -> None:
        inverted = {value: key for key, value in constants.MT5_ORDER_TYPE_TO_DOMAIN.items()}

        assert inverted == constants.DOMAIN_TO_MT5_ORDER_TYPE
        assert len(constants.DOMAIN_TO_MT5_ORDER_TYPE) == len(constants.MT5_ORDER_TYPE_TO_DOMAIN)

    def test_close_by_is_deliberately_unmapped(self) -> None:
        # It is a netting instruction with no direction. Mapping it would mean
        # inventing a side, which is worse than refusing the translation.
        assert constants.ORDER_TYPE_CLOSE_BY not in constants.MT5_ORDER_TYPE_TO_DOMAIN

    @pytest.mark.parametrize(
        ("code", "side"),
        [
            (constants.ORDER_TYPE_BUY, OrderSide.BUY),
            (constants.ORDER_TYPE_BUY_LIMIT, OrderSide.BUY),
            (constants.ORDER_TYPE_BUY_STOP, OrderSide.BUY),
            (constants.ORDER_TYPE_BUY_STOP_LIMIT, OrderSide.BUY),
            (constants.ORDER_TYPE_SELL, OrderSide.SELL),
            (constants.ORDER_TYPE_SELL_LIMIT, OrderSide.SELL),
            (constants.ORDER_TYPE_SELL_STOP, OrderSide.SELL),
            (constants.ORDER_TYPE_SELL_STOP_LIMIT, OrderSide.SELL),
        ],
    )
    def test_direction_survives_translation(self, code: int, side: OrderSide) -> None:
        # The failure this prevents is the worst one available here: an order
        # placed in the opposite direction to the one intended.
        assert constants.MT5_ORDER_TYPE_TO_DOMAIN[code][0] is side


class TestStateTables:
    def test_every_terminal_order_state_is_mapped(self) -> None:
        # The terminal's states are 0 through 9 with no gaps. An unmapped one
        # would raise mid-translation on a live order.
        assert set(constants.MT5_ORDER_STATE_TO_STATUS) == set(range(10))

    @pytest.mark.parametrize(
        "state",
        [
            constants.ORDER_STATE_REQUEST_ADD,
            constants.ORDER_STATE_REQUEST_MODIFY,
            constants.ORDER_STATE_REQUEST_CANCEL,
        ],
    )
    def test_an_amendment_in_flight_reads_as_pending(self, state: int) -> None:
        # These describe what the terminal is doing, not what the order has
        # reached. Throughout all three the order is live and unfilled.
        assert constants.MT5_ORDER_STATE_TO_STATUS[state] is OrderStatus.PENDING

    def test_every_position_type_is_mapped(self) -> None:
        assert set(constants.MT5_POSITION_TYPE_TO_SIDE) == {
            constants.POSITION_TYPE_BUY,
            constants.POSITION_TYPE_SELL,
        }

    def test_every_symbol_trade_mode_is_mapped(self) -> None:
        assert set(constants.MT5_TRADE_MODE_TO_DOMAIN.values()) == set(SymbolTradeMode)
        assert set(constants.MT5_TRADE_MODE_TO_DOMAIN) == set(range(5))


class TestErrorCodeGroups:
    def test_the_groups_do_not_overlap(self) -> None:
        # A code in two groups would classify differently depending on the order
        # the session happened to consult them in.
        groups = (
            constants.AUTHENTICATION_ERROR_CODES,
            constants.CONNECTION_ERROR_CODES,
            constants.TIMEOUT_ERROR_CODES,
            constants.NOT_FOUND_ERROR_CODES,
        )
        total = sum(len(group) for group in groups)

        assert len(set[int]().union(*groups)) == total

    def test_success_is_not_classified_as_a_failure(self) -> None:
        assert constants.RES_S_OK not in constants.AUTHENTICATION_ERROR_CODES
        assert constants.RES_S_OK not in constants.CONNECTION_ERROR_CODES
        assert constants.RES_S_OK not in constants.TIMEOUT_ERROR_CODES
        assert constants.RES_S_OK not in constants.NOT_FOUND_ERROR_CODES

    def test_disabled_algorithmic_trading_is_an_authentication_fault(self) -> None:
        # Grouped with credentials rather than with connection faults because
        # retrying cannot fix it — a human has to enable it in the terminal.
        assert constants.RES_E_AUTO_TRADING_DISABLED in constants.AUTHENTICATION_ERROR_CODES
        assert constants.RES_E_AUTO_TRADING_DISABLED not in constants.CONNECTION_ERROR_CODES


class TestAgainstTheInstalledPackage:
    """Checks that can only run where the vendor wheel exists.

    MetaTrader 5 publishes Windows wheels only, so these are skipped on the
    Linux CI runner. Everything above still runs there.
    """

    @staticmethod
    def _vendor() -> Mapping[str, object]:
        """Return the installed vendor module, or skip.

        Returns:
            The module's namespace.
        """
        module = pytest.importorskip(
            "MetaTrader5",
            reason="the MetaTrader5 wheel installs on Windows only",
        )
        # `vars` is typed as returning `dict[str, Any]`; the cast is what keeps
        # the Any from spreading into every comparison below.
        return cast("Mapping[str, object]", vars(module))

    @pytest.mark.parametrize("name", DECLARED_CONSTANTS)
    def test_every_declared_constant_matches_the_vendor(self, name: str) -> None:
        vendor = self._vendor()

        assert name in vendor, f"MetaTrader5 no longer defines {name}"
        assert getattr(constants, name) == vendor[name]

    @pytest.mark.parametrize("name", DECLARED_FUNCTIONS)
    def test_every_function_the_protocol_declares_exists(self, name: str) -> None:
        # The Terminal protocol is Atlas's written statement of what it uses. A
        # vendor rename must break here, not inside a market-data call.
        vendor = self._vendor()

        assert callable(vendor.get(name)), f"MetaTrader5 no longer provides {name}()"
