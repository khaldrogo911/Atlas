"""A venue to test the mock adapter against, and the pieces tests build on.

Every fixture here is deliberate about one thing: the venue offers two
instruments and quotes only one of them. That asymmetry is what makes the
port's "an instrument with no quote is absent from the mapping rather than
present with a null" rule testable at all, and a fixture set where everything
was quoted would pass whether or not the rule was implemented.

The clock is the venue's own, starting at
:data:`~atlas.broker.mock.venue.DEFAULT_START`. Nothing in these tests reads the
host clock, so nothing here can pass in the morning and fail at a period
boundary in the evening.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from atlas.broker.mock import DEFAULT_ACCOUNT, DEFAULT_START, MockBrokerAdapter, MockVenue
from atlas.broker.models import (
    Account,
    Candle,
    OrderSide,
    OrderType,
    Symbol,
    SymbolTradeMode,
    Tick,
    Timeframe,
)
from atlas.broker.types import OrderRequest

#: The venue clock at the start of every test.
NOW = DEFAULT_START

#: The quoted instrument. Ordinary retail terms, so that a rejection in a test
#: is caused by what the test set up rather than by the fixture.
EURUSD = Symbol(
    symbol="EURUSD",
    description="Euro vs US Dollar",
    base_currency="EUR",
    quote_currency="USD",
    digits=5,
    point=Decimal("0.00001"),
    tick_size=Decimal("0.00001"),
    contract_size=Decimal("100000"),
    min_volume=Decimal("0.01"),
    max_volume=Decimal("50"),
    volume_step=Decimal("0.01"),
    spread=12,
    trade_mode=SymbolTradeMode.FULL,
)

#: The unquoted instrument. Offered by the venue, never given a price.
GBPUSD = Symbol(
    symbol="GBPUSD",
    description="Pound Sterling vs US Dollar",
    base_currency="GBP",
    quote_currency="USD",
    digits=5,
    point=Decimal("0.00001"),
    tick_size=Decimal("0.00001"),
    contract_size=Decimal("100000"),
    min_volume=Decimal("0.01"),
    max_volume=Decimal("50"),
    volume_step=Decimal("0.01"),
    spread=18,
    trade_mode=SymbolTradeMode.FULL,
)

#: The standing quote for :data:`EURUSD`. Asymmetric about no round number, so
#: a test that confuses the two sides of the spread fails on the value.
BID = Decimal("1.10000")
ASK = Decimal("1.10012")

#: A size well inside the instrument's bounds and on its step.
VOLUME = Decimal("0.10")


def tick(
    symbol: str = "EURUSD",
    bid: Decimal = BID,
    ask: Decimal = ASK,
    *,
    at: datetime | None = None,
) -> Tick:
    """Build a quote.

    Args:
        symbol: Instrument code.
        bid: Bid price.
        ask: Ask price.
        at: Timestamp, defaulting to :data:`NOW`.

    Returns:
        The quote.
    """
    return Tick(symbol=symbol, bid=bid, ask=ask, timestamp=NOW if at is None else at)


def bar(
    minute: int,
    *,
    symbol: str = "EURUSD",
    timeframe: Timeframe = Timeframe.M1,
    is_closed: bool = True,
) -> Candle:
    """Build a bar opening a whole number of minutes after :data:`NOW`.

    Args:
        minute: How many minutes after :data:`NOW` the bar opens.
        symbol: Instrument code.
        timeframe: Bar length. The bar's own duration follows it.
        is_closed: Whether the bar has finished.

    Returns:
        The bar. Its prices carry the minute so two bars are never equal.
    """
    open_time = NOW + timedelta(minutes=minute)
    offset = Decimal(minute) / Decimal(10000)
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        open=BID + offset,
        high=BID + offset + Decimal("0.00050"),
        low=BID + offset - Decimal("0.00050"),
        close=BID + offset + Decimal("0.00010"),
        volume=Decimal(100 + minute),
        open_time=open_time,
        close_time=open_time + timeframe.duration,
        is_closed=is_closed,
    )


def market(
    side: OrderSide = OrderSide.BUY, volume: Decimal = VOLUME, symbol: str = "EURUSD"
) -> OrderRequest:
    """Build a market order request.

    Args:
        side: Direction.
        volume: Size, in lots.
        symbol: Instrument code.

    Returns:
        The request.
    """
    return OrderRequest(symbol=symbol, side=side, type=OrderType.MARKET, volume=volume)


def limit(
    price: Decimal = Decimal("1.09000"),
    side: OrderSide = OrderSide.BUY,
    volume: Decimal = VOLUME,
    symbol: str = "EURUSD",
) -> OrderRequest:
    """Build a limit order request.

    Args:
        price: Working price.
        side: Direction.
        volume: Size, in lots.
        symbol: Instrument code.

    Returns:
        The request.
    """
    return OrderRequest(symbol=symbol, side=side, type=OrderType.LIMIT, volume=volume, price=price)


def instrument(**changes: object) -> Symbol:
    """Return :data:`EURUSD` with some dealing terms changed.

    Args:
        **changes: Fields to replace.

    Returns:
        The revised instrument, revalidated. Built by dumping and validating
        rather than with ``model_copy``, for the reason the venue gives: an
        update that is applied without revalidation is stored happily and
        surfaces somewhere else entirely.
    """
    return Symbol.model_validate({**EURUSD.model_dump(), **changes})


def funds(**changes: object) -> Account:
    """Return the venue's default account with some fields changed.

    Args:
        **changes: Fields to replace.

    Returns:
        The revised account, revalidated.
    """
    return Account.model_validate({**DEFAULT_ACCOUNT.model_dump(), **changes})


@pytest.fixture
def venue() -> MockVenue:
    """A venue offering both instruments, quoting only EURUSD."""
    built = MockVenue()
    built.add_symbol(EURUSD)
    built.add_symbol(GBPUSD)
    built.publish_tick(tick())
    return built


@pytest.fixture
def offline(venue: MockVenue) -> MockBrokerAdapter:
    """An adapter bound to the venue that has not connected."""
    return MockBrokerAdapter(venue)


@pytest.fixture
def adapter(offline: MockBrokerAdapter) -> MockBrokerAdapter:
    """A connected adapter."""
    offline.connect()
    return offline
