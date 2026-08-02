"""Unit tests for the Account model."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from atlas.broker.models import Account

pytestmark = pytest.mark.unit


def _account(account: Account, **overrides: object) -> Account:
    """Revalidate a valid account with the given fields replaced."""
    return Account.model_validate({**account.model_dump(), **overrides})


class TestMarginLevel:
    def test_a_margin_level_reported_against_zero_margin_is_rejected(
        self, account: Account
    ) -> None:
        # Venues send 0 here on a flat account. Carried through, it reads as the
        # most severe margin call possible and fires any `< threshold` rule.
        with pytest.raises(ValidationError, match="undefined, not zero"):
            _account(account, margin=Decimal(0), margin_level=Decimal(0))

    def test_a_flat_account_carries_no_margin_level(self, account: Account) -> None:
        result = _account(account, margin=Decimal(0), margin_level=None)

        assert result.margin_level is None

    def test_a_margin_level_is_optional_when_margin_is_pledged(self, account: Account) -> None:
        # Not every venue reports it; absence is not an error.
        result = _account(account, margin=Decimal("1200.00"), margin_level=None)

        assert result.margin_level is None

    def test_a_negative_margin_level_is_rejected(self, account: Account) -> None:
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            _account(account, margin_level=Decimal("-1"))


class TestSignedAmounts:
    def test_equity_may_be_negative(self, account: Account) -> None:
        # A gapped stop-out can leave the account owing money.
        assert _account(account, equity=Decimal("-250.00")).equity == Decimal("-250.00")

    def test_balance_may_be_negative(self, account: Account) -> None:
        assert _account(account, balance=Decimal("-10.00")).balance == Decimal("-10.00")

    def test_free_margin_may_be_negative(self, account: Account) -> None:
        # Free margin below zero is precisely the margin-call condition.
        result = _account(account, free_margin=Decimal("-500.00"))

        assert result.free_margin == Decimal("-500.00")

    def test_margin_may_not_be_negative(self, account: Account) -> None:
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            _account(account, margin=Decimal("-1"))


class TestReportedValues:
    def test_equity_is_not_recomputed_from_balance(self, account: Account) -> None:
        # The broker is the authority on its own arithmetic. Atlas records what
        # it was told; disagreeing silently would be worse than disagreeing
        # loudly, and this layer has no basis on which to disagree at all.
        result = _account(account, balance=Decimal("100.00"), equity=Decimal("999.00"))

        assert result.balance == Decimal("100.00")
        assert result.equity == Decimal("999.00")

    def test_trading_can_be_disallowed(self, account: Account) -> None:
        assert _account(account, trade_allowed=False).trade_allowed is False
