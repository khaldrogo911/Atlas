"""MetaTrader 5 wire constants and the translation tables built from them.

Every integer here is a value the MetaTrader 5 terminal puts on the wire. They
are written as literals rather than read from the ``MetaTrader5`` package for
one reason: this module must import on a machine that has no terminal and no
wheel for its platform, because :mod:`atlas.broker.mt5` is imported by the
repository's structural tests on Linux CI.

That trade is only safe if the literals are checked against the real package
wherever it *is* installed, so ``tests/unit/broker/mt5/test_mt5_constants.py``
asserts every value below against ``MetaTrader5`` when the import succeeds, and
separately checks the ones with a documented bit encoding — the hour and day
timeframes — in a test that runs everywhere. A constant that is wrong here
returns the wrong bars, silently and forever, so it is worth two tests.

Translation tables are declared in one direction and inverted programmatically.
A hand-written reverse table is a second source of truth that drifts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from atlas.broker.models import (
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    SymbolTradeMode,
    Timeframe,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "AUTHENTICATION_ERROR_CODES",
    "CONNECTION_ERROR_CODES",
    "DOMAIN_TO_MT5_ORDER_TYPE",
    "MT5_ORDER_STATE_TO_STATUS",
    "MT5_ORDER_TYPE_TO_DOMAIN",
    "MT5_POSITION_TYPE_TO_SIDE",
    "MT5_TO_TIMEFRAME",
    "MT5_TRADE_MODE_TO_DOMAIN",
    "NOT_FOUND_ERROR_CODES",
    "ORDER_STATE_CANCELED",
    "ORDER_STATE_EXPIRED",
    "ORDER_STATE_FILLED",
    "ORDER_STATE_PARTIAL",
    "ORDER_STATE_PLACED",
    "ORDER_STATE_REJECTED",
    "ORDER_STATE_REQUEST_ADD",
    "ORDER_STATE_REQUEST_CANCEL",
    "ORDER_STATE_REQUEST_MODIFY",
    "ORDER_STATE_STARTED",
    "ORDER_TYPE_BUY",
    "ORDER_TYPE_BUY_LIMIT",
    "ORDER_TYPE_BUY_STOP",
    "ORDER_TYPE_BUY_STOP_LIMIT",
    "ORDER_TYPE_CLOSE_BY",
    "ORDER_TYPE_SELL",
    "ORDER_TYPE_SELL_LIMIT",
    "ORDER_TYPE_SELL_STOP",
    "ORDER_TYPE_SELL_STOP_LIMIT",
    "POSITION_TYPE_BUY",
    "POSITION_TYPE_SELL",
    "RES_E_AUTH_FAILED",
    "RES_E_AUTO_TRADING_DISABLED",
    "RES_E_FAIL",
    "RES_E_INTERNAL_FAIL",
    "RES_E_INTERNAL_FAIL_CONNECT",
    "RES_E_INTERNAL_FAIL_INIT",
    "RES_E_INTERNAL_FAIL_RECEIVE",
    "RES_E_INTERNAL_FAIL_SEND",
    "RES_E_INTERNAL_FAIL_TIMEOUT",
    "RES_E_INVALID_PARAMS",
    "RES_E_INVALID_VERSION",
    "RES_E_NOT_FOUND",
    "RES_E_NO_MEMORY",
    "RES_E_UNSUPPORTED",
    "RES_S_OK",
    "SYMBOL_TRADE_MODE_CLOSEONLY",
    "SYMBOL_TRADE_MODE_DISABLED",
    "SYMBOL_TRADE_MODE_FULL",
    "SYMBOL_TRADE_MODE_LONGONLY",
    "SYMBOL_TRADE_MODE_SHORTONLY",
    "TIMEFRAME_D1",
    "TIMEFRAME_H1",
    "TIMEFRAME_H4",
    "TIMEFRAME_HOUR_FLAG",
    "TIMEFRAME_M1",
    "TIMEFRAME_M5",
    "TIMEFRAME_M15",
    "TIMEFRAME_M30",
    "TIMEFRAME_TO_MT5",
    "TIMEOUT_ERROR_CODES",
]

# --- Timeframes ---------------------------------------------------------------
#
# MetaTrader 5 encodes a timeframe as its length in minutes for sub-hour bars,
# and as ``TIMEFRAME_HOUR_FLAG | hours`` from one hour upwards. A daily bar is
# encoded as 24 hours, not as a distinct unit, which is why D1 is 16408 and not
# something that looks like a day.

#: Set on every timeframe of an hour or longer.
TIMEFRAME_HOUR_FLAG: Final = 0x4000

TIMEFRAME_M1: Final = 1
TIMEFRAME_M5: Final = 5
TIMEFRAME_M15: Final = 15
TIMEFRAME_M30: Final = 30
TIMEFRAME_H1: Final = 16385
TIMEFRAME_H4: Final = 16388
TIMEFRAME_D1: Final = 16408

#: The only timeframes Atlas models. MetaTrader 5 offers twenty-one; the domain
#: deliberately offers seven, so this table is a narrowing and not a mirror.
TIMEFRAME_TO_MT5: Final[Mapping[Timeframe, int]] = {
    Timeframe.M1: TIMEFRAME_M1,
    Timeframe.M5: TIMEFRAME_M5,
    Timeframe.M15: TIMEFRAME_M15,
    Timeframe.M30: TIMEFRAME_M30,
    Timeframe.H1: TIMEFRAME_H1,
    Timeframe.H4: TIMEFRAME_H4,
    Timeframe.D1: TIMEFRAME_D1,
}

MT5_TO_TIMEFRAME: Final[Mapping[int, Timeframe]] = {
    value: key for key, value in TIMEFRAME_TO_MT5.items()
}

# --- Order types --------------------------------------------------------------
#
# One MetaTrader 5 order type carries both the direction and the presentation,
# which the domain splits into `OrderSide` and `OrderType`. The tables below are
# the whole of that translation.

ORDER_TYPE_BUY: Final = 0
ORDER_TYPE_SELL: Final = 1
ORDER_TYPE_BUY_LIMIT: Final = 2
ORDER_TYPE_SELL_LIMIT: Final = 3
ORDER_TYPE_BUY_STOP: Final = 4
ORDER_TYPE_SELL_STOP: Final = 5
ORDER_TYPE_BUY_STOP_LIMIT: Final = 6
ORDER_TYPE_SELL_STOP_LIMIT: Final = 7

#: Closes one position with another. Deliberately absent from the tables below:
#: it is a netting instruction rather than a directional order, and the domain
#: has no equivalent. Mapping one raises rather than guessing at a side.
ORDER_TYPE_CLOSE_BY: Final = 8

MT5_ORDER_TYPE_TO_DOMAIN: Final[Mapping[int, tuple[OrderSide, OrderType]]] = {
    ORDER_TYPE_BUY: (OrderSide.BUY, OrderType.MARKET),
    ORDER_TYPE_SELL: (OrderSide.SELL, OrderType.MARKET),
    ORDER_TYPE_BUY_LIMIT: (OrderSide.BUY, OrderType.LIMIT),
    ORDER_TYPE_SELL_LIMIT: (OrderSide.SELL, OrderType.LIMIT),
    ORDER_TYPE_BUY_STOP: (OrderSide.BUY, OrderType.STOP),
    ORDER_TYPE_SELL_STOP: (OrderSide.SELL, OrderType.STOP),
    ORDER_TYPE_BUY_STOP_LIMIT: (OrderSide.BUY, OrderType.STOP_LIMIT),
    ORDER_TYPE_SELL_STOP_LIMIT: (OrderSide.SELL, OrderType.STOP_LIMIT),
}

DOMAIN_TO_MT5_ORDER_TYPE: Final[Mapping[tuple[OrderSide, OrderType], int]] = {
    value: key for key, value in MT5_ORDER_TYPE_TO_DOMAIN.items()
}

# --- Order states -------------------------------------------------------------

ORDER_STATE_STARTED: Final = 0
ORDER_STATE_PLACED: Final = 1
ORDER_STATE_CANCELED: Final = 2
ORDER_STATE_PARTIAL: Final = 3
ORDER_STATE_FILLED: Final = 4
ORDER_STATE_REJECTED: Final = 5
ORDER_STATE_EXPIRED: Final = 6
ORDER_STATE_REQUEST_ADD: Final = 7
ORDER_STATE_REQUEST_MODIFY: Final = 8
ORDER_STATE_REQUEST_CANCEL: Final = 9

#: The three ``REQUEST_`` states describe an amendment the terminal is still
#: processing, not a state the order has reached. They map to ``PENDING``
#: because the order is live and unfilled throughout — which is exactly what a
#: caller needs to know — and because inventing a distinct domain status for a
#: transient terminal condition would leak MetaTrader 5's lifecycle upwards.
MT5_ORDER_STATE_TO_STATUS: Final[Mapping[int, OrderStatus]] = {
    ORDER_STATE_STARTED: OrderStatus.CREATED,
    ORDER_STATE_PLACED: OrderStatus.PENDING,
    ORDER_STATE_CANCELED: OrderStatus.CANCELLED,
    ORDER_STATE_PARTIAL: OrderStatus.PARTIALLY_FILLED,
    ORDER_STATE_FILLED: OrderStatus.FILLED,
    ORDER_STATE_REJECTED: OrderStatus.REJECTED,
    ORDER_STATE_EXPIRED: OrderStatus.EXPIRED,
    ORDER_STATE_REQUEST_ADD: OrderStatus.PENDING,
    ORDER_STATE_REQUEST_MODIFY: OrderStatus.PENDING,
    ORDER_STATE_REQUEST_CANCEL: OrderStatus.PENDING,
}

# --- Positions ----------------------------------------------------------------

POSITION_TYPE_BUY: Final = 0
POSITION_TYPE_SELL: Final = 1

MT5_POSITION_TYPE_TO_SIDE: Final[Mapping[int, PositionSide]] = {
    POSITION_TYPE_BUY: PositionSide.LONG,
    POSITION_TYPE_SELL: PositionSide.SHORT,
}

# --- Symbol trade modes -------------------------------------------------------

SYMBOL_TRADE_MODE_DISABLED: Final = 0
SYMBOL_TRADE_MODE_LONGONLY: Final = 1
SYMBOL_TRADE_MODE_SHORTONLY: Final = 2
SYMBOL_TRADE_MODE_CLOSEONLY: Final = 3
SYMBOL_TRADE_MODE_FULL: Final = 4

MT5_TRADE_MODE_TO_DOMAIN: Final[Mapping[int, SymbolTradeMode]] = {
    SYMBOL_TRADE_MODE_DISABLED: SymbolTradeMode.DISABLED,
    SYMBOL_TRADE_MODE_LONGONLY: SymbolTradeMode.LONG_ONLY,
    SYMBOL_TRADE_MODE_SHORTONLY: SymbolTradeMode.SHORT_ONLY,
    SYMBOL_TRADE_MODE_CLOSEONLY: SymbolTradeMode.CLOSE_ONLY,
    SYMBOL_TRADE_MODE_FULL: SymbolTradeMode.FULL,
}

# --- Terminal result codes ----------------------------------------------------
#
# Returned by ``MetaTrader5.last_error()`` as ``(code, description)``. These
# describe the terminal's own IPC layer, not a trade server's verdict on an
# order — that is a separate ``TRADE_RETCODE_*`` space which arrives on an
# order result and belongs with the trading methods that ATLAS-TASK-0005 will
# complete.

RES_S_OK: Final = 1
RES_E_FAIL: Final = -1
RES_E_INVALID_PARAMS: Final = -2
RES_E_NO_MEMORY: Final = -3
RES_E_NOT_FOUND: Final = -4
RES_E_INVALID_VERSION: Final = -5
RES_E_AUTH_FAILED: Final = -6
RES_E_UNSUPPORTED: Final = -7
RES_E_AUTO_TRADING_DISABLED: Final = -8
RES_E_INTERNAL_FAIL: Final = -10000
RES_E_INTERNAL_FAIL_SEND: Final = -10001
RES_E_INTERNAL_FAIL_RECEIVE: Final = -10002
RES_E_INTERNAL_FAIL_INIT: Final = -10003
RES_E_INTERNAL_FAIL_CONNECT: Final = -10004
RES_E_INTERNAL_FAIL_TIMEOUT: Final = -10005

#: Credentials or trading permission were refused. ``AUTO_TRADING_DISABLED`` is
#: grouped here rather than with connection faults because retrying cannot fix
#: it: a human has to enable algorithmic trading in the terminal.
AUTHENTICATION_ERROR_CODES: Final = frozenset(
    {RES_E_AUTH_FAILED, RES_E_AUTO_TRADING_DISABLED, RES_E_INVALID_VERSION}
)

#: The terminal could not be reached or the IPC channel failed.
CONNECTION_ERROR_CODES: Final = frozenset(
    {
        RES_E_INTERNAL_FAIL,
        RES_E_INTERNAL_FAIL_SEND,
        RES_E_INTERNAL_FAIL_RECEIVE,
        RES_E_INTERNAL_FAIL_INIT,
        RES_E_INTERNAL_FAIL_CONNECT,
    }
)

#: The terminal gave up waiting.
TIMEOUT_ERROR_CODES: Final = frozenset({RES_E_INTERNAL_FAIL_TIMEOUT})

#: The request was well formed but the terminal holds nothing matching it.
NOT_FOUND_ERROR_CODES: Final = frozenset({RES_E_NOT_FOUND})
