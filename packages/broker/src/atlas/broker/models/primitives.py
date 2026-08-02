"""Constrained scalar types shared by every broker domain model.

Each validation rule the broker layer guarantees is written down exactly once,
here, and applied by annotation. The alternative — repeating
``Annotated[Decimal, Field(gt=0)]`` in six model modules — guarantees that the
day one rule changes, five copies keep the old behaviour.

Two decisions are load bearing:

Decimal, never float
    Prices, volumes and money are :class:`~decimal.Decimal`. A five-digit FX
    quote is not representable in binary floating point, and an accumulated
    rounding error in a position's cost basis is a real loss, not a display
    artefact. Pydantic serialises ``Decimal`` to a JSON *string*, so the exact
    value — including its exponent — survives a round trip.

Aware timestamps, normalised to UTC
    :data:`Timestamp` rejects naive datetimes outright and converts everything
    else to UTC. Brokers report times in server-local zones that shift twice a
    year; a naive datetime crossing this boundary is a silent, seasonal bug.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, ConfigDict, Field

__all__ = [
    "BROKER_MODEL_CONFIG",
    "CurrencyCode",
    "Description",
    "Digits",
    "Identifier",
    "LatencyMilliseconds",
    "Leverage",
    "Money",
    "Name",
    "NonNegativeMoney",
    "Percentage",
    "Points",
    "Price",
    "SymbolCode",
    "Timestamp",
    "Volume",
    "VolumeOrZero",
]

#: Configuration applied to every model in this package.
#:
#: ``frozen`` makes instances hashable and safe to share between the strategy,
#: risk and execution layers without defensive copying. ``extra="forbid"``
#: turns a misspelled field in an adapter into an immediate error rather than
#: an attribute that silently reads back as missing.
BROKER_MODEL_CONFIG = ConfigDict(frozen=True, extra="forbid")


def _to_utc(value: datetime) -> datetime:
    """Convert an aware datetime to UTC.

    Args:
        value: An aware datetime. Naive values are rejected upstream by
            :class:`~pydantic.AwareDatetime` and never reach this function.

    Returns:
        The same instant expressed in UTC.
    """
    return value.astimezone(UTC)


def _required_text(value: str) -> str:
    """Trim surrounding whitespace and reject a value that is only whitespace.

    Args:
        value: The raw string.

    Returns:
        The trimmed string.

    Raises:
        ValueError: If nothing but whitespace was supplied. A length constraint
            alone cannot catch this: ``"   "`` satisfies ``min_length=1``.
    """
    trimmed = value.strip()
    if not trimmed:
        msg = "value must contain at least one non-whitespace character"
        raise ValueError(msg)
    return trimmed


def _canonical_code(value: str) -> str:
    """Trim and uppercase an instrument or currency code.

    Case is a broker-formatting detail, not information: one venue quotes
    ``eurusd``, the next ``EURUSD``. Canonicalising here is what lets the rest
    of Atlas compare codes with ``==`` and use them as dictionary keys.

    Args:
        value: The raw code.

    Returns:
        The trimmed, uppercased code.

    Raises:
        ValueError: If nothing but whitespace was supplied.
    """
    return _required_text(value).upper()


# --- Time ---------------------------------------------------------------------

#: An aware datetime, normalised to UTC. Naive values are a validation error.
Timestamp = Annotated[AwareDatetime, AfterValidator(_to_utc)]

# --- Text ---------------------------------------------------------------------

#: A broker-assigned identifier: account number, order ticket, deal ticket.
Identifier = Annotated[str, Field(min_length=1, max_length=64), AfterValidator(_required_text)]

#: A human-meaningful name, such as a broker or trade-server name.
Name = Annotated[str, Field(min_length=1, max_length=128), AfterValidator(_required_text)]

#: Free-form descriptive text. May be empty; brokers frequently omit it.
Description = Annotated[str, Field(max_length=256)]

#: An instrument code, canonicalised to upper case.
SymbolCode = Annotated[str, Field(min_length=1, max_length=32), AfterValidator(_canonical_code)]

#: A currency code, canonicalised to upper case.
#:
#: Deliberately not restricted to three characters. ISO 4217 codes are three,
#: but the same field carries venue-specific settlement currencies that are
#: not, and rejecting a real account currency is worse than accepting an
#: unusual one.
CurrencyCode = Annotated[str, Field(min_length=2, max_length=10), AfterValidator(_canonical_code)]

# --- Quantities ---------------------------------------------------------------

#: A price. Strictly positive, as required for every instrument Atlas quotes.
Price = Annotated[Decimal, Field(gt=0)]

#: A traded or requested quantity, in lots. Strictly positive.
Volume = Annotated[Decimal, Field(gt=0)]

#: A reported quantity that may legitimately be zero.
#:
#: Tick and bar volume are *observations*: a bar in which nothing traded, or a
#: quote update from a venue that reports no size, carries zero. Applying the
#: strictly-positive rule here would reject valid market data.
VolumeOrZero = Annotated[Decimal, Field(ge=0)]

#: A signed monetary amount. Profit, swap and commission are all routinely
#: negative, and equity can fall below zero on a gapped stop-out.
Money = Decimal

#: A monetary amount that cannot be negative, such as margin in use.
NonNegativeMoney = Annotated[Decimal, Field(ge=0)]

#: A non-negative ratio expressed in percent.
Percentage = Annotated[Decimal, Field(ge=0)]

#: A distance expressed in whole points. One point is ``10 ** -digits``.
Points = Annotated[int, Field(ge=0)]

#: The number of decimal places in an instrument's quotes.
Digits = Annotated[int, Field(ge=0, le=16)]

#: Account leverage expressed as the ratio's denominator: ``30`` means 1:30.
Leverage = Annotated[int, Field(gt=0)]

#: A measured round-trip latency in milliseconds.
#:
#: A float, not a Decimal: this is a measurement with no exact decimal value
#: and no accounting consequence. ``allow_inf_nan=False`` is explicit because
#: ``ge=0`` alone admits positive infinity.
LatencyMilliseconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]
