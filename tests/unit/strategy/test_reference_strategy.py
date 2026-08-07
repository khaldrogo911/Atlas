"""Tests for the reference implementation, most of which assert what it cannot do.

:class:`~atlas.strategy.reference.ConstantStrategy` exists to prove the contract
can be implemented. Its value depends entirely on it staying inert, so the tests
below spend more effort on the absence of behaviour than on the presence of it:
no observation is read, no clock is held, no randomness is drawn, no I/O is
performed, and the class is kept off the package's public surface so nothing
reaches for it by accident.

A reference implementation that could see a price is one edit away from being a
trading strategy, and the edit is the kind nobody reviews closely because the
file already existed. These tests are what make that edit visible.

It is *handed* the intent it returns rather than building one, which is what
keeps :mod:`atlas.broker` out of the strategy package entirely: constructing a
:class:`~atlas.risk.TradeIntent` means naming the four primitives it is stated
in, so the construction happens here, in test code, where that dependency is
allowed. ``tests/unit/strategy/test_strategy_boundary.py`` asserts the
production side of the same rule.
"""

from __future__ import annotations

import ast
import inspect
import sys
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest
from pydantic import ValidationError

import atlas.strategy
from atlas.broker.models import OrderSide
from atlas.risk import TradeIntent
from atlas.strategy.reference import ConstantStrategy

if TYPE_CHECKING:
    from atlas.strategy import Strategy

pytestmark = pytest.mark.unit

REFERENCE_MODULE: Final = sys.modules[ConstantStrategy.__module__]
REFERENCE_SOURCE: Final = Path(inspect.getfile(ConstantStrategy)).read_text(encoding="utf-8")

#: Modules whose presence would mean the reference implementation had acquired a
#: way to observe something. Each maps to one of the properties the task
#: required: no market data, no I/O, no clock, no randomness.
FORBIDDEN_MODULES: Final = (
    "random",
    "secrets",
    "time",
    "datetime",
    "os",
    "sys",
    "pathlib",
    "socket",
    "subprocess",
    "sqlite3",
    "json",
    "csv",
    "urllib",
    "http",
    "asyncio",
    "threading",
)

#: Builtins that would mean the same thing, reached without an import.
FORBIDDEN_BUILTINS: Final = ("open", "input", "print", "eval", "exec", "__import__")


def _imported_modules(source: str) -> set[str]:
    """Return the top-level name of every module the source imports."""
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module.split(".", 1)[0])
    return modules


def _called_names(source: str) -> set[str]:
    """Return the name of every function called by name in the source."""
    tree = ast.parse(source)
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def _an_intent() -> TradeIntent:
    return TradeIntent(symbol="EURUSD", side=OrderSide.BUY, requested_volume=Decimal("0.50"))


class TestTheScannersWork:
    """A scan that inspects nothing passes everything."""

    def test_there_is_source_to_scan(self) -> None:
        assert "class ConstantStrategy" in REFERENCE_SOURCE

    def test_the_module_scanner_finds_what_the_file_does_import(self) -> None:
        assert {"atlas", "typing", "__future__"} <= _imported_modules(REFERENCE_SOURCE)

    @pytest.mark.parametrize("module", FORBIDDEN_MODULES)
    def test_the_module_rule_can_actually_fire(self, module: str) -> None:
        assert module in _imported_modules(f"import {module}")
        assert module in _imported_modules(f"from {module} import thing")

    def test_the_call_scanner_finds_a_real_call(self) -> None:
        assert _called_names("x = int('1')") == {"int"}

    @pytest.mark.parametrize("builtin", FORBIDDEN_BUILTINS)
    def test_the_call_rule_can_actually_fire(self, builtin: str) -> None:
        assert builtin in _called_names(f"{builtin}('x')")


class TestItObservesNothing:
    @pytest.mark.parametrize("module", FORBIDDEN_MODULES)
    def test_it_imports_nothing_that_could_observe_anything(self, module: str) -> None:
        assert module not in _imported_modules(REFERENCE_SOURCE)

    @pytest.mark.parametrize("builtin", FORBIDDEN_BUILTINS)
    def test_it_calls_no_builtin_that_could_observe_anything(self, builtin: str) -> None:
        assert builtin not in _called_names(REFERENCE_SOURCE)

    def test_it_discards_the_observation_it_is_given(self) -> None:
        intent = _an_intent()
        strategy = ConstantStrategy(intent)

        assert strategy.propose(object()) is intent
        assert strategy.propose("a string") is intent
        assert strategy.propose(None) is intent
        assert strategy.propose(Decimal("1.2345")) is intent

    def test_its_answer_depends_only_on_how_it_was_built(self) -> None:
        """Asked a hundred times, it says the same thing a hundred times."""
        strategy = ConstantStrategy(_an_intent())

        answers = {strategy.propose(index) for index in range(100)}

        assert len(answers) == 1

    def test_being_asked_repeatedly_does_not_change_it(self) -> None:
        abstaining = ConstantStrategy()

        assert [abstaining.propose(index) for index in range(5)] == [None] * 5


class TestBothAnswersAreFirstClass:
    def test_the_default_is_to_abstain(self) -> None:
        assert ConstantStrategy().propose(object()) is None

    def test_an_explicit_none_abstains_too(self) -> None:
        assert ConstantStrategy(None).propose(object()) is None

    def test_it_returns_the_intent_it_was_handed(self) -> None:
        intent = _an_intent()

        assert ConstantStrategy(intent).propose(object()) is intent

    def test_it_returns_a_fully_specified_intent_unchanged(self) -> None:
        intent = TradeIntent(
            symbol="XAUUSD",
            side=OrderSide.SELL,
            requested_volume=Decimal("0.02"),
            stop_loss=Decimal("2410.00"),
            take_profit=Decimal("2380.00"),
        )

        assert ConstantStrategy(intent).propose(object()) == intent

    def test_the_levels_are_optional_because_the_contract_says_so(self) -> None:
        intent = ConstantStrategy(_an_intent()).propose(object())

        assert intent is not None
        assert intent.stop_loss is None
        assert intent.take_profit is None


class TestValidationBelongsToTheContract:
    """A second copy of a validation rule is a second rule, and it diverges.

    Every rejection below comes from :class:`~atlas.risk.TradeIntent`, and the
    reference implementation is not in the path — it cannot be, because it never
    constructs an intent. That is the same decision that keeps
    :mod:`atlas.broker` out of this package: whatever builds an intent names the
    port's primitives and enforces the port's rules, and neither job is a
    strategy's.
    """

    @pytest.mark.parametrize("volume", [Decimal("0"), Decimal("-1")])
    def test_the_contract_refuses_a_volume_before_a_strategy_ever_sees_it(
        self, volume: Decimal
    ) -> None:
        with pytest.raises(ValidationError):
            TradeIntent(symbol="EURUSD", side=OrderSide.BUY, requested_volume=volume)

    def test_the_contract_refuses_a_negative_price_before_a_strategy_ever_sees_it(self) -> None:
        with pytest.raises(ValidationError):
            TradeIntent(
                symbol="EURUSD",
                side=OrderSide.BUY,
                requested_volume=Decimal("0.10"),
                stop_loss=Decimal("-1"),
            )

    def test_the_reference_implementation_rejects_nothing_of_its_own(self) -> None:
        """No ``raise`` anywhere in it, so it can add no rule of its own to diverge."""
        raises = [
            node for node in ast.walk(ast.parse(REFERENCE_SOURCE)) if isinstance(node, ast.Raise)
        ]

        assert raises == []

    def test_an_intent_that_exists_is_accepted_without_re_checking(self) -> None:
        intent = _an_intent()

        assert ConstantStrategy(intent).propose(object()) is intent


class TestItIsNotPartOfThePublicSurface:
    def test_it_is_absent_from_the_package_exports(self) -> None:
        assert "ConstantStrategy" not in atlas.strategy.__all__

    def test_importing_the_package_does_not_bring_it_along(self) -> None:
        """The same reason ``MockBrokerAdapter`` is absent from :mod:`atlas.broker`."""
        assert not hasattr(atlas.strategy, "ConstantStrategy")

    def test_its_own_module_declares_it(self) -> None:
        assert REFERENCE_MODULE.__all__ == ["ConstantStrategy"]

    def test_it_is_reachable_only_by_naming_the_module(self) -> None:
        strategy: Strategy[object] = ConstantStrategy()

        assert type(strategy).__module__ == "atlas.strategy.reference"

    def test_it_claims_nothing_about_profitability(self) -> None:
        """The docstring is where a future reader is told not to trade this."""
        assert "Not a trading strategy:" in (REFERENCE_MODULE.__doc__ or "")
