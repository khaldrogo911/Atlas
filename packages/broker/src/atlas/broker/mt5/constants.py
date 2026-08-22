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
    "FILLING_MODE_NAME_TO_MT5",
    "MT5_ORDER_STATE_TO_STATUS",
    "MT5_ORDER_TYPE_TO_DOMAIN",
    "MT5_POSITION_TYPE_TO_SIDE",
    "MT5_RETCODE_DESCRIPTIONS",
    "MT5_TO_TIMEFRAME",
    "MT5_TRADE_MODE_TO_DOMAIN",
    "NOT_FOUND_ERROR_CODES",
    "ORDER_FILLING_FOK",
    "ORDER_FILLING_IOC",
    "ORDER_FILLING_RETURN",
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
    "RETCODE_AUTHENTICATION_CODES",
    "RETCODE_CONNECTION_CODES",
    "RETCODE_INSUFFICIENT_MARGIN_CODES",
    "RETCODE_POSITION_NOT_FOUND_CODES",
    "RETCODE_SUCCESS_CODES",
    "RETCODE_TIMEOUT_CODES",
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
    "TRADE_ACTION_DEAL",
    "TRADE_RETCODE_CANCEL",
    "TRADE_RETCODE_CLIENT_DISABLES_AT",
    "TRADE_RETCODE_CLOSE_ONLY",
    "TRADE_RETCODE_CLOSE_ORDER_EXIST",
    "TRADE_RETCODE_CONNECTION",
    "TRADE_RETCODE_DONE",
    "TRADE_RETCODE_DONE_PARTIAL",
    "TRADE_RETCODE_ERROR",
    "TRADE_RETCODE_FIFO_CLOSE",
    "TRADE_RETCODE_FROZEN",
    "TRADE_RETCODE_INVALID",
    "TRADE_RETCODE_INVALID_CLOSE_VOLUME",
    "TRADE_RETCODE_INVALID_EXPIRATION",
    "TRADE_RETCODE_INVALID_FILL",
    "TRADE_RETCODE_INVALID_ORDER",
    "TRADE_RETCODE_INVALID_PRICE",
    "TRADE_RETCODE_INVALID_STOPS",
    "TRADE_RETCODE_INVALID_VOLUME",
    "TRADE_RETCODE_LIMIT_ORDERS",
    "TRADE_RETCODE_LIMIT_POSITIONS",
    "TRADE_RETCODE_LIMIT_VOLUME",
    "TRADE_RETCODE_LOCKED",
    "TRADE_RETCODE_LONG_ONLY",
    "TRADE_RETCODE_MARKET_CLOSED",
    "TRADE_RETCODE_NO_CHANGES",
    "TRADE_RETCODE_NO_MONEY",
    "TRADE_RETCODE_ONLY_REAL",
    "TRADE_RETCODE_ORDER_CHANGED",
    "TRADE_RETCODE_PLACED",
    "TRADE_RETCODE_POSITION_CLOSED",
    "TRADE_RETCODE_PRICE_CHANGED",
    "TRADE_RETCODE_PRICE_OFF",
    "TRADE_RETCODE_REJECT",
    "TRADE_RETCODE_REJECT_CANCEL",
    "TRADE_RETCODE_REQUOTE",
    "TRADE_RETCODE_SERVER_DISABLES_AT",
    "TRADE_RETCODE_SHORT_ONLY",
    "TRADE_RETCODE_TIMEOUT",
    "TRADE_RETCODE_TOO_MANY_REQUESTS",
    "TRADE_RETCODE_TRADE_DISABLED",
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

# --- Trade actions and filling modes -------------------------------------------
#
# `action` and `type_filling` fields of an `order_send` request. Atlas sends
# exactly one action — an immediate market deal — and configures exactly one
# filling mode per instrument rather than choosing among the three at request
# time; see ADR-0021.

#: Places an order and fills it immediately at the current market price.
TRADE_ACTION_DEAL: Final = 1

#: Fill the whole requested volume at once, at any number of prices, or fill
#: none of it.
ORDER_FILLING_FOK: Final = 0

#: Fill as much of the requested volume as is available and cancel the rest.
ORDER_FILLING_IOC: Final = 1

#: Fill as much of the requested volume as is available immediately and leave
#: the remainder working as a new order.
ORDER_FILLING_RETURN: Final = 2

#: Every filling-mode constant above, keyed by its own name.
#:
#: The bridge between two vocabularies for the same three values:
#: `BrokerSettings.filling_mode_by_instrument` (`atlas.config`) holds the
#: constant's name as a plain string, because ADR-0014 forbids that package
#: from importing this one; `MT5Config.filling_mode_by_instrument` holds the
#: int itself. `build_broker_owner` looks a configured name up here to cross
#: from one to the other.
FILLING_MODE_NAME_TO_MT5: Final[Mapping[str, int]] = {
    "ORDER_FILLING_FOK": ORDER_FILLING_FOK,
    "ORDER_FILLING_IOC": ORDER_FILLING_IOC,
    "ORDER_FILLING_RETURN": ORDER_FILLING_RETURN,
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
# order — that is the separate ``TRADE_RETCODE_*`` space further down, which
# arrives on an order result. The two spaces are disjoint in value and unrelated
# in meaning, and are never consulted by the same table.

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

# --- Trade server result codes ------------------------------------------------
#
# The ``retcode`` field of an order result. This is the trade *server's* verdict
# on an order, which is a different thing from the terminal result codes above:
# a request can reach the server perfectly and still be refused, and a request
# that never reaches the server has no retcode at all.
#
# The numbering has one gap — 10037 is not defined by the vendor — so the codes
# are written out individually rather than generated from a range.

TRADE_RETCODE_REQUOTE: Final = 10004
TRADE_RETCODE_REJECT: Final = 10006
TRADE_RETCODE_CANCEL: Final = 10007
TRADE_RETCODE_PLACED: Final = 10008
TRADE_RETCODE_DONE: Final = 10009
TRADE_RETCODE_DONE_PARTIAL: Final = 10010
TRADE_RETCODE_ERROR: Final = 10011
TRADE_RETCODE_TIMEOUT: Final = 10012
TRADE_RETCODE_INVALID: Final = 10013
TRADE_RETCODE_INVALID_VOLUME: Final = 10014
TRADE_RETCODE_INVALID_PRICE: Final = 10015
TRADE_RETCODE_INVALID_STOPS: Final = 10016
TRADE_RETCODE_TRADE_DISABLED: Final = 10017
TRADE_RETCODE_MARKET_CLOSED: Final = 10018
TRADE_RETCODE_NO_MONEY: Final = 10019
TRADE_RETCODE_PRICE_CHANGED: Final = 10020
TRADE_RETCODE_PRICE_OFF: Final = 10021
TRADE_RETCODE_INVALID_EXPIRATION: Final = 10022
TRADE_RETCODE_ORDER_CHANGED: Final = 10023
TRADE_RETCODE_TOO_MANY_REQUESTS: Final = 10024
TRADE_RETCODE_NO_CHANGES: Final = 10025
TRADE_RETCODE_SERVER_DISABLES_AT: Final = 10026
TRADE_RETCODE_CLIENT_DISABLES_AT: Final = 10027
TRADE_RETCODE_LOCKED: Final = 10028
TRADE_RETCODE_FROZEN: Final = 10029
TRADE_RETCODE_INVALID_FILL: Final = 10030
TRADE_RETCODE_CONNECTION: Final = 10031
TRADE_RETCODE_ONLY_REAL: Final = 10032
TRADE_RETCODE_LIMIT_ORDERS: Final = 10033
TRADE_RETCODE_LIMIT_VOLUME: Final = 10034
TRADE_RETCODE_INVALID_ORDER: Final = 10035
TRADE_RETCODE_POSITION_CLOSED: Final = 10036
TRADE_RETCODE_INVALID_CLOSE_VOLUME: Final = 10038
TRADE_RETCODE_CLOSE_ORDER_EXIST: Final = 10039
TRADE_RETCODE_LIMIT_POSITIONS: Final = 10040
TRADE_RETCODE_REJECT_CANCEL: Final = 10041
TRADE_RETCODE_LONG_ONLY: Final = 10042
TRADE_RETCODE_SHORT_ONLY: Final = 10043
TRADE_RETCODE_CLOSE_ONLY: Final = 10044
TRADE_RETCODE_FIFO_CLOSE: Final = 10045

#: What each retcode means, for the exception message. MetaTrader 5 returns a
#: description alongside a terminal error code but not alongside a retcode, so
#: unlike every other table here this one has no vendor source to be checked
#: against — it is transcribed from the documented meanings. Wording only: no
#: decision is taken from it.
MT5_RETCODE_DESCRIPTIONS: Final[Mapping[int, str]] = {
    TRADE_RETCODE_REQUOTE: "requote",
    TRADE_RETCODE_REJECT: "request rejected",
    TRADE_RETCODE_CANCEL: "request cancelled by the trader",
    TRADE_RETCODE_PLACED: "order placed",
    TRADE_RETCODE_DONE: "request completed",
    TRADE_RETCODE_DONE_PARTIAL: "request only partially completed",
    TRADE_RETCODE_ERROR: "request processing error",
    TRADE_RETCODE_TIMEOUT: "request cancelled by timeout",
    TRADE_RETCODE_INVALID: "invalid request",
    TRADE_RETCODE_INVALID_VOLUME: "invalid volume",
    TRADE_RETCODE_INVALID_PRICE: "invalid price",
    TRADE_RETCODE_INVALID_STOPS: "invalid stops",
    TRADE_RETCODE_TRADE_DISABLED: "trading is disabled",
    TRADE_RETCODE_MARKET_CLOSED: "market is closed",
    TRADE_RETCODE_NO_MONEY: "not enough money to complete the request",
    TRADE_RETCODE_PRICE_CHANGED: "prices changed",
    TRADE_RETCODE_PRICE_OFF: "no quotes to process the request",
    TRADE_RETCODE_INVALID_EXPIRATION: "invalid order expiration",
    TRADE_RETCODE_ORDER_CHANGED: "order state changed",
    TRADE_RETCODE_TOO_MANY_REQUESTS: "too many requests",
    TRADE_RETCODE_NO_CHANGES: "no changes in the request",
    TRADE_RETCODE_SERVER_DISABLES_AT: "algorithmic trading disabled by the server",
    TRADE_RETCODE_CLIENT_DISABLES_AT: "algorithmic trading disabled by the terminal",
    TRADE_RETCODE_LOCKED: "request locked for processing",
    TRADE_RETCODE_FROZEN: "order or position frozen",
    TRADE_RETCODE_INVALID_FILL: "invalid order filling type",
    TRADE_RETCODE_CONNECTION: "no connection with the trade server",
    TRADE_RETCODE_ONLY_REAL: "operation allowed only for live accounts",
    TRADE_RETCODE_LIMIT_ORDERS: "the pending order limit has been reached",
    TRADE_RETCODE_LIMIT_VOLUME: "the volume limit for the symbol has been reached",
    TRADE_RETCODE_INVALID_ORDER: "incorrect or prohibited order type",
    TRADE_RETCODE_POSITION_CLOSED: "the position is already closed",
    TRADE_RETCODE_INVALID_CLOSE_VOLUME: "close volume exceeds the position volume",
    TRADE_RETCODE_CLOSE_ORDER_EXIST: "a close order already exists for the position",
    TRADE_RETCODE_LIMIT_POSITIONS: "the open position limit has been reached",
    TRADE_RETCODE_REJECT_CANCEL: "pending order activation rejected, order cancelled",
    TRADE_RETCODE_LONG_ONLY: "the symbol allows long positions only",
    TRADE_RETCODE_SHORT_ONLY: "the symbol allows short positions only",
    TRADE_RETCODE_CLOSE_ONLY: "the symbol allows position closing only",
    TRADE_RETCODE_FIFO_CLOSE: "the symbol requires closing by the FIFO rule",
}

#: The server accepted the request. Not failures, and the only retcodes that are
#: not translated into an exception.
#:
#: ``DONE_PARTIAL`` is here deliberately. A partial fill is a real order with a
#: real position behind it; raising on it would discard the fill that actually
#: happened and leave the caller believing nothing was executed.
RETCODE_SUCCESS_CODES: Final = frozenset(
    {TRADE_RETCODE_PLACED, TRADE_RETCODE_DONE, TRADE_RETCODE_DONE_PARTIAL}
)

#: The server did not answer in time. The order may still have been executed.
RETCODE_TIMEOUT_CODES: Final = frozenset({TRADE_RETCODE_TIMEOUT})

#: The terminal reached no trade server at all.
RETCODE_CONNECTION_CODES: Final = frozenset({TRADE_RETCODE_CONNECTION})

#: Algorithmic trading is switched off, at the server or in the terminal. Same
#: reasoning as ``RES_E_AUTO_TRADING_DISABLED`` above: a human has to turn it
#: on, so it is a permission fault and not a transient one.
RETCODE_AUTHENTICATION_CODES: Final = frozenset(
    {TRADE_RETCODE_SERVER_DISABLES_AT, TRADE_RETCODE_CLIENT_DISABLES_AT}
)

#: The account cannot fund the order. The one refusal a sizing layer can answer.
RETCODE_INSUFFICIENT_MARGIN_CODES: Final = frozenset({TRADE_RETCODE_NO_MONEY})

#: The position named in the request no longer exists.
#:
#: There is no corresponding order group: MetaTrader 5 has no retcode meaning
#: "no such order". An adapter learns that from an empty ``orders_get`` lookup,
#: not from a rejection, so inventing a retcode for it here would be a mapping
#: the vendor does not support.
RETCODE_POSITION_NOT_FOUND_CODES: Final = frozenset({TRADE_RETCODE_POSITION_CLOSED})
