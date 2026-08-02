"""An aggregated OHLCV bar."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from atlas.broker.models.enums import Timeframe
from atlas.broker.models.primitives import (
    BROKER_MODEL_CONFIG,
    Price,
    SymbolCode,
    Timestamp,
    VolumeOrZero,
)

__all__ = ["Candle"]


class Candle(BaseModel):
    """One bar of aggregated price action.

    :attr:`is_closed` is the field that matters. A bar that is still forming
    will change, and a feature computed from a forming bar and then compared
    against history computed from closed bars is the most common way a
    backtest and a live system silently disagree. The flag is required, with
    no default, so that an adapter has to state which kind of bar it produced.
    """

    model_config = BROKER_MODEL_CONFIG

    symbol: SymbolCode = Field(description="Instrument the bar aggregates.")
    timeframe: Timeframe = Field(description="Aggregation period of the bar.")
    open: Price = Field(description="First traded or quoted price of the period.")
    high: Price = Field(description="Highest price of the period.")
    low: Price = Field(description="Lowest price of the period.")
    close: Price = Field(description="Last price of the period so far.")
    volume: VolumeOrZero = Field(
        default=Decimal(0),
        description="Volume traded in the period. Zero in a period with no trades.",
    )
    open_time: Timestamp = Field(description="Start of the aggregation period.")
    close_time: Timestamp = Field(description="End of the aggregation period.")
    is_closed: bool = Field(
        description="Whether the period has ended and the bar can no longer change."
    )

    @model_validator(mode="after")
    def _check_bar_is_coherent(self) -> Candle:
        """Reject a bar whose extremes or times contradict each other.

        The high must be the highest of the four prices and the low the lowest.
        A bar that violates this is not merely odd — indicator maths built on
        it produces negative ranges and silently wrong volatility.

        The period must also move forwards. Equal open and close times would
        make a bar of zero duration, which no timeframe describes.

        Returns:
            The validated instance.

        Raises:
            ValueError: If the OHLC ordering or the period bounds are invalid.
        """
        if self.high < max(self.open, self.close, self.low):
            msg = (
                f"high ({self.high}) must be the greatest of open ({self.open}), "
                f"low ({self.low}) and close ({self.close})"
            )
            raise ValueError(msg)
        if self.low > min(self.open, self.close, self.high):
            msg = (
                f"low ({self.low}) must be the least of open ({self.open}), "
                f"high ({self.high}) and close ({self.close})"
            )
            raise ValueError(msg)
        if self.close_time <= self.open_time:
            msg = (
                f"close_time ({self.close_time.isoformat()}) must be after "
                f"open_time ({self.open_time.isoformat()})"
            )
            raise ValueError(msg)
        return self

    @property
    def price_range(self) -> Decimal:
        """The high-to-low range of the bar, in price units."""
        return self.high - self.low
