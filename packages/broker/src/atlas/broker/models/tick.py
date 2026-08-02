"""A single top-of-book quote update."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from atlas.broker.models.primitives import (
    BROKER_MODEL_CONFIG,
    Price,
    SymbolCode,
    Timestamp,
    VolumeOrZero,
)

__all__ = ["Tick"]


class Tick(BaseModel):
    """The best bid and offer for an instrument at an instant.

    A tick is a fact that has already happened, so the model is frozen and
    carries no notion of staleness. Deciding that a quote is too old to act on
    requires a clock and a policy, neither of which belongs in this layer.
    """

    model_config = BROKER_MODEL_CONFIG

    symbol: SymbolCode = Field(description="Instrument the quote applies to.")
    bid: Price = Field(description="Best price at which the instrument can be sold.")
    ask: Price = Field(description="Best price at which the instrument can be bought.")
    last: Price | None = Field(
        default=None,
        description=(
            "Price of the last trade. ``None`` on instruments where the venue "
            "reports no trades, which is the normal case in spot FX."
        ),
    )
    volume: VolumeOrZero = Field(
        default=Decimal(0),
        description="Size attached to the update. Zero where the venue reports none.",
    )
    timestamp: Timestamp = Field(description="When the venue published the quote.")

    @model_validator(mode="after")
    def _check_spread_is_not_negative(self) -> Tick:
        """Reject a crossed quote.

        An ask below the bid is arbitrage-free nonsense from a single venue; in
        practice it means bid and ask were mapped the wrong way round. Catching
        it here costs one comparison, and not catching it produces a strategy
        that appears to make money on every tick.

        Returns:
            The validated instance.

        Raises:
            ValueError: If the ask is below the bid.
        """
        if self.ask < self.bid:
            msg = f"ask ({self.ask}) must be greater than or equal to bid ({self.bid})"
            raise ValueError(msg)
        return self

    @property
    def spread(self) -> Decimal:
        """The bid-offer spread in price units.

        Guaranteed non-negative by validation. Divide by the instrument's
        ``point`` to express it in points.
        """
        return self.ask - self.bid

    @property
    def mid(self) -> Decimal:
        """The midpoint between bid and offer."""
        return (self.bid + self.ask) / 2
