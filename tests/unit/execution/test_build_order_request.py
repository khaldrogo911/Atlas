"""Tests for the translation of an approved verdict into an order request.

The contract has one branch and seven fields, and almost every way of getting it
wrong is silent: the requested volume instead of the approved one, a policy
default that quietly decides how orders reach a venue, a rejection that returns
something a caller could mistake for a trade. None of those raise. So each rule
is asserted against the value that would betray it — the reduced approval whose
two volumes differ, the rejection under every reason risk can give, the fields
that must arrive unaltered rather than merely present.

The port's own rules are exercised where this contract can reach them, and
attributed to the port rather than restated here.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

import pytest
from pydantic import ValidationError

from atlas.broker import OrderRequest
from atlas.broker.models import OrderSide, OrderType
from atlas.execution import ExecutionPolicy, build_order_request
from atlas.risk import RejectionReason, RiskVerdict, TradeIntent, VerdictStatus

pytestmark = pytest.mark.unit

REQUESTED: Final = Decimal("1.00")
REDUCED: Final = Decimal("0.25")
STOP_LOSS: Final = Decimal("1.0950")
TAKE_PROFIT: Final = Decimal("1.1150")
WORKING_PRICE: Final = Decimal("1.1000")

INTENT: Final = TradeIntent(
    symbol="EURUSD",
    side=OrderSide.BUY,
    requested_volume=REQUESTED,
    stop_loss=STOP_LOSS,
    take_profit=TAKE_PROFIT,
)

BARE_INTENT: Final = TradeIntent(
    symbol="GBPUSD",
    side=OrderSide.SELL,
    requested_volume=REQUESTED,
)

MARKET: Final = ExecutionPolicy(order_type=OrderType.MARKET)


def _approved(volume: Decimal = REQUESTED, intent: TradeIntent = INTENT) -> RiskVerdict:
    return RiskVerdict(intent=intent, status=VerdictStatus.APPROVED, approved_volume=volume)


def _rejected(reason: RejectionReason = RejectionReason.EXPOSURE_LIMIT) -> RiskVerdict:
    return RiskVerdict(intent=INTENT, status=VerdictStatus.REJECTED, reason=reason)


class TestThePolicy:
    def test_a_policy_must_say_how_the_order_is_presented(self) -> None:
        """No default: choosing MARKET here would be a trading decision."""
        assert ExecutionPolicy.model_fields["order_type"].is_required()

        with pytest.raises(ValidationError, match="order_type"):
            ExecutionPolicy.model_validate({})

    def test_a_policy_without_a_price_is_well_formed(self) -> None:
        assert ExecutionPolicy(order_type=OrderType.MARKET).price is None

    def test_a_policy_answers_two_questions_and_no_others(self) -> None:
        assert set(ExecutionPolicy.model_fields) == {"order_type", "price"}

    def test_a_policy_cannot_be_edited_after_it_is_made(self) -> None:
        policy = ExecutionPolicy(order_type=OrderType.MARKET)

        with pytest.raises(ValidationError, match="frozen"):
            policy.order_type = OrderType.LIMIT  # type: ignore[misc]

    def test_a_misspelled_answer_is_an_error_not_a_missing_value(self) -> None:
        with pytest.raises(ValidationError, match="slippage"):
            ExecutionPolicy.model_validate({"order_type": "MARKET", "slippage": 3})

    def test_a_policy_does_not_carry_a_size_or_an_instrument(self) -> None:
        """Sizing is risk's, and the instrument is the intent's."""
        fields = set(ExecutionPolicy.model_fields)

        assert fields.isdisjoint({"volume", "symbol", "side", "stop_loss", "take_profit"})


class TestAnApprovedVerdictBecomesARequest:
    def test_the_result_is_a_request_the_port_owns(self) -> None:
        request = build_order_request(_approved(), MARKET)

        assert isinstance(request, OrderRequest)

    def test_the_instrument_and_direction_come_from_the_intent(self) -> None:
        request = build_order_request(_approved(), MARKET)

        assert request is not None
        assert request.symbol == INTENT.symbol
        assert request.side is INTENT.side

    def test_the_protective_levels_come_from_the_intent(self) -> None:
        request = build_order_request(_approved(), MARKET)

        assert request is not None
        assert request.stop_loss == STOP_LOSS
        assert request.take_profit == TAKE_PROFIT

    def test_absent_protective_levels_stay_absent(self) -> None:
        """An intent that proposed no stop must not acquire one in translation."""
        request = build_order_request(_approved(intent=BARE_INTENT), MARKET)

        assert request is not None
        assert request.stop_loss is None
        assert request.take_profit is None

    def test_the_presentation_comes_from_the_policy(self) -> None:
        policy = ExecutionPolicy(order_type=OrderType.LIMIT, price=WORKING_PRICE)

        request = build_order_request(_approved(), policy)

        assert request is not None
        assert request.type is OrderType.LIMIT
        assert request.price == WORKING_PRICE

    def test_a_market_order_carries_no_working_price(self) -> None:
        request = build_order_request(_approved(), MARKET)

        assert request is not None
        assert request.price is None

    def test_the_trigger_price_is_never_supplied_here(self) -> None:
        """``stop_price`` is not one of the policy's two answers."""
        request = build_order_request(_approved(), MARKET)

        assert request is not None
        assert request.stop_price is None

    @pytest.mark.parametrize("order_type", [OrderType.MARKET, OrderType.LIMIT, OrderType.STOP])
    def test_every_reachable_presentation_produces_a_request(self, order_type: OrderType) -> None:
        price = None if order_type is OrderType.MARKET else WORKING_PRICE
        policy = ExecutionPolicy(order_type=order_type, price=price)

        request = build_order_request(_approved(), policy)

        assert request is not None
        assert request.type is order_type

    def test_nothing_is_normalised_on_the_way_through(self) -> None:
        """Values arrive as they were decided, not rounded, scaled or re-quoted."""
        verdict = _approved(volume=Decimal("0.07"))
        policy = ExecutionPolicy(order_type=OrderType.LIMIT, price=Decimal("1.10005"))

        request = build_order_request(verdict, policy)

        assert request is not None
        assert request.volume == Decimal("0.07")
        assert request.price == Decimal("1.10005")
        assert request.stop_loss == STOP_LOSS


class TestTheVolumeIsTheApprovedVolume:
    def test_a_reduced_approval_is_placed_at_the_approved_size(self) -> None:
        """The one assertion that separates a correct build from a plausible one."""
        verdict = _approved(volume=REDUCED)

        request = build_order_request(verdict, MARKET)

        assert request is not None
        assert request.volume == REDUCED
        assert request.volume != verdict.intent.requested_volume

    def test_an_unreduced_approval_is_placed_at_the_size_that_was_asked_for(self) -> None:
        verdict = _approved()

        request = build_order_request(verdict, MARKET)

        assert request is not None
        assert not verdict.is_reduced
        assert request.volume == REQUESTED

    def test_the_volume_tracks_the_verdict_and_not_the_intent(self) -> None:
        """Held across sizes, so no single figure can coincide with both.

        Every value is below the requested one, because risk "may reduce an
        intent but never enlarge one" and refuses to construct a verdict that
        does. A translation reading the wrong field therefore always overstates
        the size, never understates it.
        """
        for approved in (Decimal("0.01"), Decimal("0.33"), Decimal("0.99")):
            request = build_order_request(_approved(volume=approved), MARKET)

            assert request is not None
            assert request.volume == approved


class TestARejectedVerdictBecomesNothing:
    @pytest.mark.parametrize("reason", list(RejectionReason))
    def test_every_control_that_can_refuse_produces_nothing(self, reason: RejectionReason) -> None:
        assert build_order_request(_rejected(reason), MARKET) is None

    def test_a_rejection_is_not_an_exception(self) -> None:
        """Risk refusing a trade is risk working, not a failure to report."""
        assert build_order_request(_rejected(), MARKET) is None

    def test_a_rejection_returns_nothing_a_caller_could_mistake_for_a_trade(self) -> None:
        result = build_order_request(_rejected(), MARKET)

        assert result is None
        assert not isinstance(result, OrderRequest)

    @pytest.mark.parametrize("order_type", [OrderType.MARKET, OrderType.LIMIT, OrderType.STOP])
    def test_no_policy_can_turn_a_rejection_into_an_order(self, order_type: OrderType) -> None:
        price = None if order_type is OrderType.MARKET else WORKING_PRICE
        policy = ExecutionPolicy(order_type=order_type, price=price)

        assert build_order_request(_rejected(), policy) is None

    def test_a_request_is_produced_exactly_when_the_verdict_approves(self) -> None:
        for verdict in (_approved(), _rejected()):
            produced = build_order_request(verdict, MARKET) is not None

            assert produced is verdict.is_approved


class TestThePortsRulesAreThePortsAlone:
    """This contract adds no validation; it lets the port's fire where it applies."""

    @pytest.mark.parametrize("order_type", [OrderType.LIMIT, OrderType.STOP])
    def test_a_presentation_that_needs_a_price_and_has_none_is_refused_by_the_port(
        self, order_type: OrderType
    ) -> None:
        policy = ExecutionPolicy(order_type=order_type)

        with pytest.raises(ValidationError, match="price is required"):
            build_order_request(_approved(), policy)

    def test_the_policy_itself_does_not_second_guess_the_order_type(self) -> None:
        """Building the policy is legal; the rule fires when the request is built."""
        assert ExecutionPolicy(order_type=OrderType.LIMIT).price is None

    def test_a_market_order_with_a_price_is_the_ports_business_not_this_ones(self) -> None:
        """The port permits it, so nothing here refuses it."""
        policy = ExecutionPolicy(order_type=OrderType.MARKET, price=WORKING_PRICE)

        request = build_order_request(_approved(), policy)

        assert request is not None
        assert request.price == WORKING_PRICE

    def test_a_stop_limit_policy_cannot_be_satisfied_by_a_two_answer_policy(self) -> None:
        """Characterising a known gap, not endorsing it.

        ``STOP_LIMIT`` is the one ``OrderType`` that needs a trigger price
        *and* a working price. A policy that answers exactly two questions
        cannot supply both, so the port refuses the request by its own rule.
        Reaching STOP_LIMIT needs a third answer, and adding one is a decision
        for the task that needs it — not something to be smuggled in here.
        """
        policy = ExecutionPolicy(order_type=OrderType.STOP_LIMIT, price=WORKING_PRICE)

        with pytest.raises(ValidationError, match="stop_price is required"):
            build_order_request(_approved(), policy)


class TestNothingIsRemembered:
    def test_the_same_inputs_give_the_same_answer(self) -> None:
        verdict, policy = _approved(), MARKET

        assert build_order_request(verdict, policy) == build_order_request(verdict, policy)

    def test_a_call_does_not_change_the_verdict_it_was_given(self) -> None:
        verdict = _approved(volume=REDUCED)
        before = verdict.model_dump()

        build_order_request(verdict, MARKET)

        assert verdict.model_dump() == before

    def test_a_call_does_not_change_the_policy_it_was_given(self) -> None:
        policy = ExecutionPolicy(order_type=OrderType.LIMIT, price=WORKING_PRICE)
        before = policy.model_dump()

        build_order_request(_approved(), policy)

        assert policy.model_dump() == before

    def test_a_rejection_does_not_affect_the_next_approval(self) -> None:
        """No accumulated state, so order of calls cannot matter."""
        assert build_order_request(_rejected(), MARKET) is None

        request = build_order_request(_approved(volume=REDUCED), MARKET)

        assert request is not None
        assert request.volume == REDUCED

    def test_two_requests_from_one_verdict_are_separate_objects(self) -> None:
        verdict = _approved()

        first = build_order_request(verdict, MARKET)
        second = build_order_request(verdict, MARKET)

        assert first is not second
        assert first == second
