"""Tests for the decision risk returns about one intent.

Every rule below is asserted twice: once with the field that breaks it, and
once with the field that satisfies it. A rejection test alone cannot tell a
rule that fires from a model that refuses everything, and a rule nobody can
satisfy is not a boundary — it is an outage.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Final

import pytest
from pydantic import ValidationError

from atlas.broker.models import OrderSide
from atlas.risk import RejectionReason, RiskVerdict, TradeIntent, VerdictStatus

if TYPE_CHECKING:
    from enum import StrEnum

pytestmark = pytest.mark.unit

REQUESTED: Final = Decimal("1.00")

INTENT: Final = TradeIntent(
    symbol="EURUSD",
    side=OrderSide.BUY,
    requested_volume=REQUESTED,
    stop_loss=Decimal("1.0950"),
)


def _approved(**overrides: object) -> dict[str, object]:
    """Build a well-formed approval payload with the given fields replaced."""
    return {
        "intent": INTENT,
        "status": VerdictStatus.APPROVED,
        "approved_volume": REQUESTED,
    } | overrides


def _rejected(**overrides: object) -> dict[str, object]:
    """Build a well-formed rejection payload with the given fields replaced."""
    return {
        "intent": INTENT,
        "status": VerdictStatus.REJECTED,
        "reason": RejectionReason.EXPOSURE_LIMIT,
    } | overrides


class TestTheVocabulary:
    def test_a_verdict_has_exactly_two_states(self) -> None:
        assert set(VerdictStatus) == {VerdictStatus.APPROVED, VerdictStatus.REJECTED}

    def test_there_is_no_reduced_status(self) -> None:
        assert not hasattr(VerdictStatus, "REDUCED")

    def test_the_rejection_reasons_are_the_four_controls_the_package_declares(self) -> None:
        assert set(RejectionReason) == {
            RejectionReason.EXPOSURE_LIMIT,
            RejectionReason.DRAWDOWN_LIMIT,
            RejectionReason.CORRELATION_CAP,
            RejectionReason.KILL_SWITCH,
        }

    @pytest.mark.parametrize("member", [*VerdictStatus, *RejectionReason])
    def test_every_member_serialises_as_its_own_name(self, member: StrEnum) -> None:
        assert member.value == member.name


class TestApproval:
    def test_an_approval_at_the_requested_size_is_well_formed(self) -> None:
        verdict = RiskVerdict.model_validate(_approved())

        assert verdict.is_approved
        assert not verdict.is_reduced
        assert verdict.approved_volume == REQUESTED

    def test_an_approval_below_the_requested_size_is_well_formed(self) -> None:
        verdict = RiskVerdict.model_validate(_approved(approved_volume=Decimal("0.25")))

        assert verdict.is_approved
        assert verdict.is_reduced
        assert verdict.approved_volume == Decimal("0.25")

    def test_r1_an_approval_without_a_volume_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="approved_volume is required"):
            RiskVerdict.model_validate(_approved(approved_volume=None))

    def test_r1_the_same_approval_with_a_volume_is_accepted(self) -> None:
        assert RiskVerdict.model_validate(_approved()).approved_volume == REQUESTED

    def test_r2_an_approval_above_the_requested_size_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="never enlarge"):
            RiskVerdict.model_validate(_approved(approved_volume=REQUESTED + Decimal("0.01")))

    def test_r2_an_approval_exactly_at_the_requested_size_is_accepted(self) -> None:
        verdict = RiskVerdict.model_validate(_approved(approved_volume=REQUESTED))

        assert verdict.approved_volume == REQUESTED

    def test_r3_an_approval_carrying_a_rejection_reason_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="reason must be None"):
            RiskVerdict.model_validate(_approved(reason=RejectionReason.KILL_SWITCH))

    def test_r3_the_same_approval_without_a_reason_is_accepted(self) -> None:
        assert RiskVerdict.model_validate(_approved()).reason is None


class TestRejection:
    @pytest.mark.parametrize("reason", list(RejectionReason))
    def test_every_declared_reason_can_carry_a_rejection(self, reason: RejectionReason) -> None:
        verdict = RiskVerdict.model_validate(_rejected(reason=reason))

        assert not verdict.is_approved
        assert verdict.reason is reason

    def test_r4_a_rejection_carrying_a_volume_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="approved_volume must be None"):
            RiskVerdict.model_validate(_rejected(approved_volume=Decimal("0.10")))

    def test_r4_the_same_rejection_without_a_volume_is_accepted(self) -> None:
        assert RiskVerdict.model_validate(_rejected()).approved_volume is None

    def test_r5_a_rejection_without_a_reason_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="reason is required"):
            RiskVerdict.model_validate(_rejected(reason=None))

    def test_r5_the_same_rejection_with_a_reason_is_accepted(self) -> None:
        assert RiskVerdict.model_validate(_rejected()).reason is RejectionReason.EXPOSURE_LIMIT

    def test_nothing_was_approved_so_nothing_was_reduced(self) -> None:
        assert not RiskVerdict.model_validate(_rejected()).is_reduced


class TestDetail:
    def test_r6_detail_is_optional_on_an_approval(self) -> None:
        assert RiskVerdict.model_validate(_approved()).detail is None

    def test_r6_detail_is_optional_on_a_rejection(self) -> None:
        assert RiskVerdict.model_validate(_rejected()).detail is None

    def test_r6_detail_is_carried_on_an_approval_when_given(self) -> None:
        verdict = RiskVerdict.model_validate(_approved(detail="scaled to the per-instrument cap"))

        assert verdict.detail == "scaled to the per-instrument cap"

    def test_r6_detail_is_carried_on_a_rejection_when_given(self) -> None:
        verdict = RiskVerdict.model_validate(_rejected(detail="portfolio exposure at 4.2% of 4.0%"))

        assert verdict.detail == "portfolio exposure at 4.2% of 4.0%"

    def test_detail_is_not_a_substitute_for_a_reason(self) -> None:
        with pytest.raises(ValidationError, match="reason is required"):
            RiskVerdict.model_validate(_rejected(reason=None, detail="portfolio exposure exceeded"))


class TestTheIntentItJudges:
    def test_the_verdict_carries_the_whole_intent(self) -> None:
        assert RiskVerdict.model_validate(_approved()).intent == INTENT

    def test_a_verdict_without_an_intent_is_refused(self) -> None:
        payload = _approved()
        del payload["intent"]

        with pytest.raises(ValidationError):
            RiskVerdict.model_validate(payload)

    def test_reduction_is_measured_against_the_intent_the_verdict_carries(self) -> None:
        larger = TradeIntent(symbol="EURUSD", side=OrderSide.BUY, requested_volume=Decimal("2.00"))
        verdict = RiskVerdict(
            intent=larger, status=VerdictStatus.APPROVED, approved_volume=REQUESTED
        )

        assert verdict.is_reduced


class TestTheModelItself:
    def test_a_verdict_cannot_be_edited_after_the_decision_was_made(self) -> None:
        verdict = RiskVerdict.model_validate(_approved(approved_volume=Decimal("0.25")))

        with pytest.raises(ValidationError):
            verdict.approved_volume = REQUESTED

    def test_an_unknown_field_is_refused_rather_than_ignored(self) -> None:
        with pytest.raises(ValidationError):
            RiskVerdict.model_validate(_approved(approved_volumes=REQUESTED))

    def test_a_verdict_carries_exactly_the_five_specified_fields(self) -> None:
        assert set(RiskVerdict.model_fields) == {
            "intent",
            "status",
            "approved_volume",
            "reason",
            "detail",
        }
