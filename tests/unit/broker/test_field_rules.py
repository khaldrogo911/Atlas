"""Unit tests for the validation rules shared by every broker model.

These rules live in ``atlas.broker.models.primitives`` and are applied by
annotation, so they are tested through the models that use them rather than by
reaching into private helpers.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from atlas.broker.models import Account, Connection, Execution, Symbol, Tick

pytestmark = pytest.mark.unit

NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
TOKYO = timezone(timedelta(hours=9))


def _tick(**overrides: object) -> Tick:
    """Build a Tick from a valid baseline with the given fields replaced."""
    payload: dict[str, object] = {
        "symbol": "EURUSD",
        "bid": Decimal("1.16240"),
        "ask": Decimal("1.16252"),
        "timestamp": NOW,
    }
    payload.update(overrides)
    return Tick.model_validate(payload)


class TestTimestamps:
    def test_a_naive_datetime_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="timezone"):
            _tick(timestamp=datetime(2026, 8, 2, 12, 0))  # noqa: DTZ001

    def test_an_offset_datetime_is_normalised_to_utc(self) -> None:
        result = _tick(timestamp=datetime(2026, 8, 2, 21, 0, tzinfo=TOKYO))

        assert result.timestamp.tzinfo is UTC
        assert result.timestamp == datetime(2026, 8, 2, 12, 0, tzinfo=UTC)

    def test_normalisation_preserves_the_instant(self) -> None:
        moment = datetime(2026, 8, 2, 21, 0, tzinfo=TOKYO)

        assert _tick(timestamp=moment).timestamp == moment

    def test_an_iso_string_with_an_offset_is_accepted(self) -> None:
        result = _tick(timestamp="2026-08-02T21:00:00+09:00")

        assert result.timestamp == datetime(2026, 8, 2, 12, 0, tzinfo=UTC)

    def test_an_iso_string_without_an_offset_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="timezone"):
            _tick(timestamp="2026-08-02T21:00:00")


class TestCodeCanonicalisation:
    @pytest.mark.parametrize("raw", ["eurusd", "EurUsd", "  EURUSD  ", "EURUSD"])
    def test_symbol_is_uppercased_and_trimmed(self, raw: str) -> None:
        assert _tick(symbol=raw).symbol == "EURUSD"

    @pytest.mark.parametrize("raw", ["usd", "Usd", " USD "])
    def test_currency_is_uppercased_and_trimmed(self, raw: str, account: Account) -> None:
        result = Account.model_validate({**account.model_dump(), "currency": raw})

        assert result.currency == "USD"

    @pytest.mark.parametrize("raw", ["", "   ", "\t\n"])
    def test_a_blank_symbol_is_rejected(self, raw: str) -> None:
        # A length constraint alone passes "   "; the trimming validator is what
        # catches it, so this fails if that validator is ever removed.
        with pytest.raises(ValidationError):
            _tick(symbol=raw)

    def test_a_blank_identifier_is_rejected(self, account: Account) -> None:
        with pytest.raises(ValidationError):
            Account.model_validate({**account.model_dump(), "account_id": "   "})

    def test_an_identifier_is_trimmed_but_not_uppercased(self, account: Account) -> None:
        # Account numbers and tickets are opaque strings; changing their case
        # could change their meaning at a venue that issues alphanumeric ones.
        result = Account.model_validate({**account.model_dump(), "account_id": "  abc-1  "})

        assert result.account_id == "abc-1"


class TestPriceRules:
    @pytest.mark.parametrize("bad", [Decimal(0), Decimal("-0.5")])
    def test_a_non_positive_price_is_rejected(self, bad: Decimal) -> None:
        with pytest.raises(ValidationError, match="greater than 0"):
            _tick(bid=bad)

    @pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
    def test_a_non_finite_price_is_rejected(self, bad: str) -> None:
        with pytest.raises(ValidationError, match="finite"):
            _tick(bid=Decimal(bad))

    @pytest.mark.parametrize("bad", ["NaN", "Infinity"])
    def test_a_non_finite_signed_amount_is_rejected(self, bad: str, execution: Execution) -> None:
        # `commission` carries no numeric bound at all, so this shows the
        # guarantee comes from the Decimal type itself, not from a constraint.
        with pytest.raises(ValidationError, match="finite"):
            Execution.model_validate({**execution.model_dump(), "commission": Decimal(bad)})


class TestVolumeRules:
    @pytest.mark.parametrize("bad", [Decimal(0), Decimal("-1")])
    def test_a_traded_volume_must_be_positive(self, bad: Decimal, execution: Execution) -> None:
        with pytest.raises(ValidationError, match="greater than 0"):
            Execution.model_validate({**execution.model_dump(), "volume": bad})

    def test_an_observed_volume_may_be_zero(self) -> None:
        # Spot FX venues routinely report zero size on a quote update; applying
        # the strictly-positive rule here would reject valid market data.
        assert _tick(volume=Decimal(0)).volume == 0

    def test_an_observed_volume_may_not_be_negative(self) -> None:
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            _tick(volume=Decimal("-1"))


class TestDecimalExactness:
    def test_a_quote_survives_a_json_round_trip_digit_for_digit(self) -> None:
        original = _tick(bid=Decimal("1.16240"))

        restored = Tick.model_validate_json(original.model_dump_json())

        assert restored.bid == Decimal("1.16240")
        assert str(restored.bid) == "1.16240"

    def test_decimals_serialise_as_json_strings(self) -> None:
        # A JSON number would hand the value to the consumer's float parser and
        # lose the exactness this layer exists to provide.
        assert '"bid":"1.16240"' in _tick(bid=Decimal("1.16240")).model_dump_json()

    def test_arithmetic_is_exact_where_float_arithmetic_is_not(self) -> None:
        result = _tick(bid=Decimal("1.10"), ask=Decimal("1.30"))

        assert result.spread == Decimal("0.20")
        # The same subtraction in binary floating point does not give 0.2.
        assert float(result.spread) != 1.30 - 1.10


class TestBoundedIntegers:
    def test_negative_digits_are_rejected(self, symbol: Symbol) -> None:
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            Symbol.model_validate({**symbol.model_dump(), "digits": -1})

    def test_a_negative_spread_is_rejected(self, symbol: Symbol) -> None:
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            Symbol.model_validate({**symbol.model_dump(), "spread": -1})

    def test_zero_digits_are_accepted(self, symbol: Symbol) -> None:
        result = Symbol.model_validate(
            {**symbol.model_dump(), "digits": 0, "point": Decimal(1), "tick_size": Decimal(1)}
        )

        assert result.digits == 0

    @pytest.mark.parametrize("bad", [0, -1])
    def test_non_positive_leverage_is_rejected(self, bad: int, account: Account) -> None:
        with pytest.raises(ValidationError, match="greater than 0"):
            Account.model_validate({**account.model_dump(), "leverage": bad})


class TestLatency:
    @pytest.mark.parametrize("bad", [float("inf"), float("nan")])
    def test_a_non_finite_latency_is_rejected(self, bad: float, connection: Connection) -> None:
        # `ge=0` alone admits positive infinity, so `allow_inf_nan=False` is
        # doing the work here and this test fails without it.
        with pytest.raises(ValidationError):
            Connection.model_validate({**connection.model_dump(), "latency_ms": bad})

    def test_an_unmeasured_latency_is_none_not_zero(self, connection: Connection) -> None:
        result = Connection.model_validate({**connection.model_dump(), "latency_ms": None})

        assert result.latency_ms is None
