"""The contract specification of a tradeable instrument."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from atlas.broker.models.enums import SymbolTradeMode
from atlas.broker.models.primitives import (
    BROKER_MODEL_CONFIG,
    CurrencyCode,
    Description,
    Digits,
    Points,
    Price,
    SymbolCode,
    Volume,
)

__all__ = ["Symbol"]


class Symbol(BaseModel):
    """The dealing terms of one instrument at one broker.

    Everything a caller needs in order to size an order correctly and round it
    to something the venue will accept. The same instrument at two brokers is
    two ``Symbol`` instances: the minimum volume, the contract size and the
    number of digits are properties of the venue's contract, not of the
    underlying market.
    """

    model_config = BROKER_MODEL_CONFIG

    symbol: SymbolCode = Field(description="The venue's code for the instrument.")
    description: Description = Field(default="", description="Human-readable instrument name.")
    base_currency: CurrencyCode = Field(description="Currency being bought or sold.")
    quote_currency: CurrencyCode = Field(description="Currency the price is expressed in.")
    digits: Digits = Field(description="Decimal places in a quote.")
    point: Price = Field(description="The smallest price increment: ``10 ** -digits``.")
    tick_size: Price = Field(
        description=(
            "The smallest price change the venue will quote. Usually equal to "
            "``point``, but a multiple of it on instruments quoted in steps."
        )
    )
    contract_size: Price = Field(description="Units of the base currency in one lot.")
    min_volume: Volume = Field(description="Smallest order the venue accepts, in lots.")
    max_volume: Volume = Field(description="Largest single order the venue accepts, in lots.")
    volume_step: Volume = Field(description="Granularity of order volume, in lots.")
    spread: Points = Field(
        description=(
            "The venue's currently reported spread, in points. A snapshot of a "
            "moving quantity, not a term of the contract; use a Tick for a "
            "spread that must be current."
        )
    )
    trade_mode: SymbolTradeMode = Field(description="What the venue currently permits.")

    @model_validator(mode="after")
    def _check_contract_terms_are_coherent(self) -> Symbol:
        """Reject specifications that no order could satisfy.

        Two rules, both of which catch a mis-mapped adapter field rather than a
        genuine venue configuration:

        ``point`` must equal ``10 ** -digits``
            That is the definition of a point. When it does not hold, either
            ``digits`` or ``point`` was read from the wrong place, and every
            distance converted through it will be wrong by a power of ten.

        ``max_volume`` must not be below ``min_volume``
            Otherwise no volume is orderable and every sizing calculation
            downstream clamps to an empty range.

        Returns:
            The validated instance.

        Raises:
            ValueError: If either rule is violated.
        """
        expected_point = Decimal(1).scaleb(-self.digits)
        if self.point != expected_point:
            msg = (
                f"point ({self.point}) must equal 10 ** -digits ({expected_point}) "
                f"for digits={self.digits}"
            )
            raise ValueError(msg)
        if self.max_volume < self.min_volume:
            msg = (
                f"max_volume ({self.max_volume}) must be greater than or equal to "
                f"min_volume ({self.min_volume})"
            )
            raise ValueError(msg)
        return self
