"""Tests for the types the port speaks that are not domain models.

Three things are under test: that the aliases really are the domain primitives
rather than lookalikes, that the ``UNSET`` sentinel survives everything a value
gets subjected to, and that ``OrderRequest`` applies the same structural rules
as the ``Order`` it will become.
"""

from __future__ import annotations

import copy
import pickle
from collections import abc
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Final, TypeAliasType, get_args, get_origin

import pytest
from pydantic import BaseModel, ValidationError

from atlas.broker import types as types_module
from atlas.broker.models import (
    BROKER_MODEL_CONFIG,
    Candle,
    Identifier,
    Name,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    SymbolCode,
    Tick,
)
from atlas.broker.types import (
    UNSET,
    BrokerName,
    BrokerVersion,
    CandleHandler,
    ExecutionID,
    OrderID,
    OrderRequest,
    PositionID,
    ServerName,
    SubscriptionID,
    SymbolName,
    TickHandler,
    Unset,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.unit

#: Each alias and the domain primitive it must resolve to. An alias that drifts
#: into its own definition creates a second rule for one concept.
ALIAS_TARGETS: Final[tuple[tuple[TypeAliasType, object, str], ...]] = (
    (BrokerName, Name, "BrokerName"),
    (ServerName, Name, "ServerName"),
    (SymbolName, SymbolCode, "SymbolName"),
    (OrderID, Identifier, "OrderID"),
    (PositionID, Identifier, "PositionID"),
    (ExecutionID, Identifier, "ExecutionID"),
    (SubscriptionID, Identifier, "SubscriptionID"),
)


#: ``(type, price, stop_price, is_valid)``. Both ``OrderRequest`` and ``Order``
#: must agree on every row.
PRICE_RULE_CASES: Final[tuple[tuple[OrderType, Decimal | None, Decimal | None, bool], ...]] = (
    (OrderType.MARKET, None, None, True),
    (OrderType.MARKET, Decimal("1.1000"), None, True),
    (OrderType.MARKET, None, Decimal("1.0990"), False),
    (OrderType.LIMIT, Decimal("1.1000"), None, True),
    (OrderType.LIMIT, None, None, False),
    (OrderType.LIMIT, Decimal("1.1000"), Decimal("1.0990"), False),
    (OrderType.STOP, Decimal("1.1000"), None, True),
    (OrderType.STOP, None, None, False),
    (OrderType.STOP, Decimal("1.1000"), Decimal("1.0990"), False),
    (OrderType.STOP_LIMIT, Decimal("1.1000"), Decimal("1.0990"), True),
    (OrderType.STOP_LIMIT, Decimal("1.1000"), None, False),
    (OrderType.STOP_LIMIT, None, Decimal("1.0990"), False),
)

_MOMENT: Final = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def _request_fields(
    order_type: OrderType, prices: Mapping[str, Decimal | None]
) -> dict[str, object]:
    """Build the payload of an OrderRequest with the given price fields."""
    return {
        "symbol": "EURUSD",
        "side": OrderSide.BUY,
        "type": order_type,
        "volume": Decimal("0.10"),
        **prices,
    }


def _order_fields(order_type: OrderType, prices: Mapping[str, Decimal | None]) -> dict[str, object]:
    """Build the payload of an Order carrying the same price fields."""
    return _request_fields(order_type, prices) | {
        "order_id": "1",
        "status": OrderStatus.PENDING,
        "created_at": _MOMENT,
        "updated_at": _MOMENT,
    }


def _accepts(model: type[BaseModel], payload: Mapping[str, object]) -> bool:
    """Report whether a model validates a payload, without asserting why."""
    try:
        model.model_validate(dict(payload))
    except ValidationError:
        return False
    return True


def _market_request(**overrides: object) -> OrderRequest:
    """Build a valid MARKET request, overriding named fields."""
    fields: dict[str, object] = {
        "symbol": "EURUSD",
        "side": OrderSide.BUY,
        "type": OrderType.MARKET,
        "volume": Decimal("0.10"),
    }
    fields.update(overrides)
    return OrderRequest.model_validate(fields)


class TestTypeAliases:
    @pytest.mark.parametrize(
        ("alias", "target"),
        [(alias, target) for alias, target, _ in ALIAS_TARGETS],
        ids=[name for _, _, name in ALIAS_TARGETS],
    )
    def test_the_alias_resolves_to_its_domain_primitive(
        self, alias: TypeAliasType, target: object
    ) -> None:
        assert alias.__value__ == target

    @pytest.mark.parametrize(
        "alias",
        [alias for alias, _, _ in ALIAS_TARGETS],
        ids=[name for _, _, name in ALIAS_TARGETS],
    )
    def test_the_alias_is_a_type_alias(self, alias: TypeAliasType) -> None:
        assert isinstance(alias, TypeAliasType)

    @pytest.mark.parametrize(
        "alias",
        [alias for alias, _, _ in ALIAS_TARGETS],
        ids=[name for _, _, name in ALIAS_TARGETS],
    )
    def test_the_alias_is_exported(self, alias: TypeAliasType) -> None:
        assert alias.__name__ in types_module.__all__

    def test_an_alias_still_validates_when_used_as_a_model_field(self) -> None:
        # The whole reason the aliases are defined in terms of the primitives:
        # an adapter can annotate a field `SymbolName` and keep the canonical
        # code rule, rather than re-declaring the constraint.
        class _Probe(BaseModel):
            model_config = BROKER_MODEL_CONFIG

            symbol: SymbolName
            order_id: OrderID

        probe = _Probe.model_validate({"symbol": "eurusd", "order_id": "123"})

        assert probe.symbol == "EURUSD"
        assert probe.order_id == "123"

    def test_an_alias_field_rejects_what_its_primitive_rejects(self) -> None:
        class _Probe(BaseModel):
            model_config = BROKER_MODEL_CONFIG

            order_id: OrderID

        with pytest.raises(ValidationError):
            _Probe.model_validate({"order_id": "   "})

    @pytest.mark.parametrize(
        ("handler", "delivered"),
        [(TickHandler, Tick), (CandleHandler, Candle)],
        ids=["TickHandler", "CandleHandler"],
    )
    def test_the_handler_receives_a_domain_model_and_returns_nothing(
        self, handler: TypeAliasType, delivered: type
    ) -> None:
        # A handler that returned a value would imply the port did something
        # with it, which would make delivery a request/response protocol.
        arguments, result = get_args(handler.__value__)

        assert get_origin(handler.__value__) is abc.Callable
        assert arguments == [delivered]
        assert result is None

    def test_the_module_exports_what_it_documents(self) -> None:
        assert types_module.__doc__
        for name in types_module.__all__:
            assert hasattr(types_module, name)


class TestUnsetSentinel:
    def test_unset_is_the_single_member(self) -> None:
        assert UNSET is Unset.SENTINEL

    def test_the_enumeration_has_exactly_one_member(self) -> None:
        # A second member would give the port two ways to mean "untouched".
        assert list(Unset) == [Unset.SENTINEL]

    def test_it_reads_as_the_exported_constant(self) -> None:
        # So a rendered signature says `= UNSET`, not `= <Unset.SENTINEL: 1>`.
        assert repr(UNSET) == "UNSET"

    def test_it_is_distinguishable_from_none(self) -> None:
        assert UNSET is not None
        assert UNSET != None  # noqa: E711 - identity and equality are both asserted

    def test_it_survives_copying(self) -> None:
        # A sentinel compared with `is` is worthless if a round trip through a
        # queue, a cache or a deep copy produces a different object.
        assert copy.copy(UNSET) is UNSET
        assert copy.deepcopy(UNSET) is UNSET
        assert pickle.loads(pickle.dumps(UNSET)) is UNSET  # noqa: S301 - our own value

    def test_it_expresses_three_outcomes(self) -> None:
        # leave / set / clear, which `None` alone cannot express.
        def resolve(value: Decimal | Unset | None) -> str:
            if value is UNSET:
                return "leave"
            if value is None:
                return "clear"
            return "set"

        assert resolve(UNSET) == "leave"
        assert resolve(None) == "clear"
        assert resolve(Decimal("1.2345")) == "set"


class TestOrderRequest:
    def test_a_market_request_needs_no_price(self) -> None:
        request = _market_request()

        assert request.type is OrderType.MARKET
        assert request.price is None

    def test_the_symbol_is_canonicalised(self) -> None:
        assert _market_request(symbol="eurusd").symbol == "EURUSD"

    @pytest.mark.parametrize("order_type", [OrderType.LIMIT, OrderType.STOP, OrderType.STOP_LIMIT])
    def test_a_priced_type_without_a_price_is_rejected(self, order_type: OrderType) -> None:
        with pytest.raises(ValidationError, match="price is required"):
            _market_request(type=order_type, stop_price=Decimal("1.1000"))

    def test_a_stop_limit_needs_both_prices(self) -> None:
        with pytest.raises(ValidationError, match="stop_price is required"):
            _market_request(type=OrderType.STOP_LIMIT, price=Decimal("1.1000"))

        request = _market_request(
            type=OrderType.STOP_LIMIT, price=Decimal("1.1000"), stop_price=Decimal("1.0990")
        )

        assert request.stop_price == Decimal("1.0990")

    @pytest.mark.parametrize("order_type", [OrderType.MARKET, OrderType.LIMIT, OrderType.STOP])
    def test_a_stop_price_on_a_type_that_has_no_trigger_is_rejected(
        self, order_type: OrderType
    ) -> None:
        with pytest.raises(ValidationError, match="stop_price must be None"):
            _market_request(type=order_type, price=Decimal("1.1000"), stop_price=Decimal("1.0990"))

    @pytest.mark.parametrize(("order_type", "price", "stop_price", "valid"), PRICE_RULE_CASES)
    def test_the_structural_rules_match_the_order_it_becomes(
        self,
        order_type: OrderType,
        price: Decimal | None,
        stop_price: Decimal | None,
        valid: bool,
    ) -> None:
        # The request and the order the venue reports back must not disagree
        # about what a well-formed order is: a request accepted here that the
        # Order model would reject could not be represented once it was filled.
        prices = {"price": price, "stop_price": stop_price}

        assert _accepts(OrderRequest, _request_fields(order_type, prices)) is valid
        assert _accepts(Order, _order_fields(order_type, prices)) is valid

    def test_the_price_rule_table_exercises_both_outcomes(self) -> None:
        outcomes = {valid for *_, valid in PRICE_RULE_CASES}

        assert outcomes == {True, False}

    def test_every_order_type_is_covered_by_the_price_rules(self) -> None:
        assert {case[0] for case in PRICE_RULE_CASES} == set(OrderType)

    def test_it_carries_no_venue_assigned_state(self) -> None:
        # A request predates the venue. Fields only the venue can fill in would
        # force the caller to invent them.
        assert not {"order_id", "status", "created_at", "updated_at", "filled_volume"} & set(
            OrderRequest.model_fields
        )

    def test_a_non_positive_volume_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _market_request(volume=Decimal("0"))

    def test_a_non_positive_price_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _market_request(type=OrderType.LIMIT, price=Decimal("0"))

    def test_it_is_frozen(self) -> None:
        with pytest.raises(ValidationError):
            _market_request().volume = Decimal("1")

    def test_an_unknown_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _market_request(magic_number=12345)

    def test_it_round_trips_through_json_without_losing_precision(self) -> None:
        request = _market_request(type=OrderType.LIMIT, price=Decimal("1.100005"))

        restored = OrderRequest.model_validate_json(request.model_dump_json())

        assert restored == request
        assert restored.price == Decimal("1.100005")

    def test_a_float_price_is_not_silently_widened(self) -> None:
        # Decimal-not-float is the whole discipline; 1.1 has no exact binary
        # representation and must not survive as one.
        request = _market_request(type=OrderType.LIMIT, price="1.1")

        assert request.price == Decimal("1.1")
        assert isinstance(request.price, Decimal)

    def test_it_is_hashable(self) -> None:
        assert {_market_request(), _market_request()} == {_market_request()}


class TestBrokerVersion:
    def test_the_minimal_form_needs_only_a_name_and_version(self) -> None:
        version = BrokerVersion(name="MetaTrader 5", version="5.0.4620")

        assert version.build is None
        assert version.api_version is None

    def test_the_full_form_carries_build_and_api_version(self) -> None:
        version = BrokerVersion(name="OANDA v20", version="3.0.25", build=4620, api_version="v20")

        assert version.build == 4620
        assert version.api_version == "v20"

    def test_a_negative_build_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BrokerVersion(name="Venue", version="1.0", build=-1)

    def test_an_empty_name_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BrokerVersion(name="  ", version="1.0")

    def test_it_is_frozen(self) -> None:
        version = BrokerVersion(name="Venue", version="1.0")

        with pytest.raises(ValidationError):
            version.version = "2.0"

    def test_an_unknown_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BrokerVersion.model_validate({"name": "Venue", "version": "1.0", "patch": 3})

    def test_it_round_trips_through_json(self) -> None:
        version = BrokerVersion(name="Venue", version="1.0", build=7, api_version="v3")

        assert BrokerVersion.model_validate_json(version.model_dump_json()) == version

    def test_builds_are_comparable(self) -> None:
        # The reason the model is structured rather than a bare string: a
        # caller gating a workaround compares numbers, not text.
        old = BrokerVersion(name="Venue", version="5.0", build=4000)
        new = BrokerVersion(name="Venue", version="5.0", build=4620)

        assert old.build is not None
        assert new.build is not None
        assert new.build > old.build
