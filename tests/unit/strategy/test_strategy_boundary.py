"""Structural tests for the strategy boundary.

ATLAS-TASK-0012 adds the producing half of the boundary ATLAS-TASK-0011 defined,
and with it exactly one edge: ``atlas.strategy -> atlas.risk``. The tests here
are what stop a second one appearing — in particular ``atlas.strategy ->
atlas.broker``, which a strategy that constructed its own intent would need and
which no module in this package is permitted to take.

They assert the shape of the package rather than its behaviour: which packages a
strategy module may import, that it takes *no* name from the port, that the
eight order-construction symbols appear nowhere, that no module here can reach
execution, and that nothing was made to pass by loosening the boundary next
door.

What these tests deliberately do **not** claim
    The invariant is that a strategy proposes and cannot bypass risk. Half of
    that is provable today — nothing here can obtain an adapter, name an order or
    reach :mod:`atlas.execution`. The other half, that a real pipeline routes
    every intent through risk before an order exists, needs a pipeline. There is
    no engine, no registry and nothing that turns an intent into a verdict, so
    what is asserted below is the structural half and nothing more.
"""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

import atlas.risk
import atlas.strategy
from atlas.broker.models import OrderSide
from atlas.risk import TradeIntent
from atlas.strategy import Strategy
from atlas.strategy.reference import ConstantStrategy

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.unit

STRATEGY_DIR: Final = Path(inspect.getfile(atlas.strategy)).parent
STRATEGY_SOURCES: Final = tuple(sorted(STRATEGY_DIR.rglob("*.py")))

RISK_DIR: Final = Path(inspect.getfile(atlas.risk)).parent
RISK_SOURCES: Final = tuple(sorted(RISK_DIR.rglob("*.py")))

#: The only ``atlas`` packages a strategy module may import.
#:
#: ``atlas.strategy`` is itself. ``atlas.risk`` is the edge this task exists to
#: create: a strategy produces a ``TradeIntent``, which risk owns.
#: ``atlas.common`` is admitted on the grounds ``docs/architecture/overview.md``
#: already states — dependency-free, importable anywhere, encoding no domain
#: rules — though nothing here needs it yet.
#:
#: ``atlas.broker`` is **not** on this list, which is the decision that shapes
#: the package. See :data:`INTENT_PRIMITIVES`.
PERMITTED_ATLAS_PACKAGES: Final = (
    "atlas.strategy",
    "atlas.risk",
    "atlas.common",
)

#: Packages a strategy may not import, and why each would be wrong.
#:
#: ``execution`` is the one that matters: an import of it is a route around the
#: verdict, which is the single thing this boundary exists to prevent.
#: ``broker`` is next: a strategy that can name the port is a strategy that has
#: started describing *how* to reach a venue rather than *what* it would like.
#: ``market``, ``features`` and ``regime`` are excluded because ATLAS-TASK-0012
#: defines no market-data contract — a strategy's input is a type parameter, and
#: naming one of those packages here would fix its shape before it exists.
#: ``events`` is excluded because event transport is out of this task's scope,
#: and ``config`` because a contract needs no configuration. The rest are peers
#: with no business inside a proposal.
FORBIDDEN_ATLAS_PACKAGES: Final = (
    "atlas.execution",
    "atlas.broker",
    "atlas.config",
    "atlas.events",
    "atlas.ai",
    "atlas.market",
    "atlas.features",
    "atlas.regime",
    "atlas.analytics",
    "atlas.notification",
    "atlas.learning",
    "atlas.audit",
)

#: The four names a ``TradeIntent`` is stated in — and which a strategy module
#: may nonetheless not import.
#:
#: Whatever *constructs* an intent must name these four: under ``mypy --strict``
#: with ``init_typed = True``, ``TradeIntent(side="BUY")`` is a type error even
#: though the string works at runtime. That is precisely why no module in this
#: package constructs one. A caller with a concrete intent to hand over builds
#: it, and the type it hands over is the only contract a strategy names.
#:
#: They are listed here for two assertions: that none of them is imported by
#: strategy source, and that ``atlas.risk`` did not start re-exporting them to
#: make such an import look shorter.
INTENT_PRIMITIVES: Final = ("OrderSide", "Price", "SymbolName", "Volume")

#: Names whose presence in strategy source would mean a strategy had started
#: deciding how to reach a venue rather than proposing what it would like.
#:
#: ``BrokerAdapter`` is a route to a venue. ``OrderRequest``, ``OrderType`` and
#: ``OrderStatus`` are execution's vocabulary. The four verbs are the acts
#: themselves.
ORDER_CONSTRUCTION_SYMBOLS: Final = (
    "BrokerAdapter",
    "OrderRequest",
    "OrderType",
    "OrderStatus",
    "place_order",
    "modify_order",
    "cancel_order",
    "close_position",
)

#: Stands in for the whole port in :func:`_broker_imports`.
#:
#: ``import atlas.broker`` binds the module rather than a name, which puts every
#: attribute on it within reach. It is never a permitted name, so a module that
#: does this fails the same rule that catches ``BrokerAdapter`` by name.
WHOLE_MODULE: Final = "<module>"


def _atlas_imports(source: str) -> Iterator[str]:
    """Yield the full module name of every ``atlas`` import in a source string."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("atlas"):
                    yield alias.name
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.startswith("atlas")
        ):
            yield node.module


def _is_within(module: str, package: str) -> bool:
    """Whether ``module`` is ``package`` or something inside it."""
    return module == package or module.startswith(f"{package}.")


def _offending_imports(source: str) -> list[str]:
    """Return every ``atlas`` import in the source that a strategy may not make."""
    return [
        module
        for module in _atlas_imports(source)
        if not any(_is_within(module, permitted) for permitted in PERMITTED_ATLAS_PACKAGES)
    ]


def _broker_imports(source: str) -> Iterator[str]:
    """Yield every name taken from ``atlas.broker``, however it was taken.

    A whole-module import yields :data:`WHOLE_MODULE`, because binding the module
    reaches every name in it and the point of this scan is to enumerate what a
    strategy can actually touch.
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_within(alias.name, "atlas.broker"):
                    yield WHOLE_MODULE
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and _is_within(node.module, "atlas.broker")
        ):
            for alias in node.names:
                yield alias.name


def _offending_broker_imports(source: str) -> list[str]:
    """Return every name taken from the port, all of which are offending.

    There is no permitted subset, so this is every name the scan finds. The
    function is kept distinct from :func:`_broker_imports` so that the rule
    being enforced — *nothing* — is named at the call sites that enforce it.
    """
    return list(_broker_imports(source))


def _referenced_names(source: str) -> set[str]:
    """Return every identifier the source *uses*, excluding prose.

    String constants are skipped on purpose: the modules under test discuss
    ``BrokerAdapter`` in their docstrings in order to say that they cannot obtain
    one, and a scan that read prose would fail on the sentence that documents the
    rule.
    """
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.name.rsplit(".", 1)[-1])
            if node.asname is not None:
                names.add(node.asname)
    return names


def _source_of(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestTheScannersWork:
    """A scan that inspects nothing passes everything."""

    def test_there_is_strategy_source_to_scan(self) -> None:
        assert STRATEGY_SOURCES, "no strategy sources were discovered"
        assert {path.name for path in STRATEGY_SOURCES} >= {
            "__init__.py",
            "contracts.py",
            "reference.py",
        }

    def test_there_is_risk_source_to_scan(self) -> None:
        assert RISK_SOURCES, "no risk sources were discovered"

    def test_the_import_scanner_finds_the_edge_this_task_creates(self) -> None:
        found = {module for path in STRATEGY_SOURCES for module in _atlas_imports(_source_of(path))}

        assert any(_is_within(module, "atlas.risk") for module in found), found

    def test_the_import_rule_can_actually_fire(self) -> None:
        assert _offending_imports("from atlas.execution import Executor") == ["atlas.execution"]

    @pytest.mark.parametrize("name", ORDER_CONSTRUCTION_SYMBOLS)
    def test_the_broker_name_rule_can_actually_fire(self, name: str) -> None:
        assert _offending_broker_imports(f"from atlas.broker import {name}") == [name]

    @pytest.mark.parametrize("name", INTENT_PRIMITIVES)
    def test_the_broker_name_rule_admits_none_of_the_four_either(self, name: str) -> None:
        """The primitives an intent is stated in are refused like everything else."""
        assert _offending_broker_imports(f"from atlas.broker.models import {name}") == [name]

    def test_the_broker_name_rule_rejects_binding_the_whole_port(self) -> None:
        """A module import reaches every name in the module, so it is refused as one."""
        assert _offending_broker_imports("import atlas.broker") == [WHOLE_MODULE]
        assert _offending_broker_imports("import atlas.broker.models") == [WHOLE_MODULE]

    def test_the_name_scanner_reads_real_identifiers(self) -> None:
        names = _referenced_names(_source_of(STRATEGY_DIR / "reference.py"))

        assert "TradeIntent" in names

    def test_the_name_scanner_ignores_prose(self) -> None:
        assert "BrokerAdapter" not in _referenced_names('"""Cannot obtain a BrokerAdapter."""')

    def test_the_order_symbol_rule_can_actually_fire(self) -> None:
        names = _referenced_names("from atlas.broker import BrokerAdapter\nx = BrokerAdapter")

        assert "BrokerAdapter" in names


class TestDependencyDirection:
    @pytest.mark.parametrize("path", STRATEGY_SOURCES, ids=lambda path: path.name)
    def test_a_strategy_module_imports_only_permitted_atlas_packages(self, path: Path) -> None:
        assert _offending_imports(_source_of(path)) == []

    @pytest.mark.parametrize("package", FORBIDDEN_ATLAS_PACKAGES)
    def test_the_rule_still_rejects_a_package_a_strategy_may_not_reach(self, package: str) -> None:
        assert _offending_imports(f"from {package} import Thing") == [package]

    def test_no_strategy_module_reaches_a_forbidden_package(self) -> None:
        imported = {
            module for path in STRATEGY_SOURCES for module in _atlas_imports(_source_of(path))
        }
        forbidden = {
            module
            for module in imported
            for package in FORBIDDEN_ATLAS_PACKAGES
            if _is_within(module, package)
        }

        assert forbidden == set()

    def test_nothing_here_can_reach_execution(self) -> None:
        """The bypass this boundary exists to prevent, named on its own."""
        reaching = {
            path.name
            for path in STRATEGY_SOURCES
            if any(
                _is_within(module, "atlas.execution") for module in _atlas_imports(_source_of(path))
            )
        }

        assert reaching == set()
        assert not hasattr(atlas.strategy, "execution")

    def test_the_new_edge_did_not_create_a_cycle(self) -> None:
        """Risk must still not see the layer above it."""
        reaching_back = {
            path.name
            for path in RISK_SOURCES
            if any(
                _is_within(module, "atlas.strategy") for module in _atlas_imports(_source_of(path))
            )
        }

        assert reaching_back == set()


class TestStrategyNeverReachesTheVenue:
    @pytest.mark.parametrize("path", STRATEGY_SOURCES, ids=lambda path: path.name)
    def test_a_strategy_module_takes_no_name_from_the_port(self, path: Path) -> None:
        assert _offending_broker_imports(_source_of(path)) == []

    def test_the_reference_implementation_introduces_no_dependency_on_the_port(self) -> None:
        """The rule that shaped ``ConstantStrategy``, asserted against it by name.

        A reference implementation that built its own intent would have to name
        ``SymbolName``, ``OrderSide``, ``Price`` and ``Volume``, and the whole
        package would carry an edge to :mod:`atlas.broker` to serve a fixture.
        It is handed a finished intent instead, and whatever needs one builds it
        in test code.
        """
        source = _source_of(STRATEGY_DIR / "reference.py")

        assert _offending_broker_imports(source) == []
        assert _offending_imports(source) == []

    @pytest.mark.parametrize("name", INTENT_PRIMITIVES)
    def test_no_strategy_module_names_a_primitive_an_intent_is_stated_in(self, name: str) -> None:
        offending = {
            path.name for path in STRATEGY_SOURCES if name in _referenced_names(_source_of(path))
        }

        assert offending == set()

    @pytest.mark.parametrize("path", STRATEGY_SOURCES, ids=lambda path: path.name)
    @pytest.mark.parametrize("symbol", ORDER_CONSTRUCTION_SYMBOLS)
    def test_no_strategy_module_names_an_order_construction_symbol(
        self, path: Path, symbol: str
    ) -> None:
        assert symbol not in _referenced_names(_source_of(path))

    @pytest.mark.parametrize("symbol", ORDER_CONSTRUCTION_SYMBOLS)
    def test_the_package_re_exports_no_order_construction_symbol(self, symbol: str) -> None:
        assert symbol not in atlas.strategy.__all__
        assert not hasattr(atlas.strategy, symbol)

    def test_the_package_exports_exactly_the_contract_and_nothing_more(self) -> None:
        assert set(atlas.strategy.__all__) == {"Strategy"}


class TestTheRiskBoundaryWasNotWidened:
    """The cheap way to pass the tests above is to move the problem next door."""

    def test_risk_still_exports_exactly_what_it_exported(self) -> None:
        assert set(atlas.risk.__all__) == {
            "RISK_MODEL_CONFIG",
            "RejectionReason",
            "RiskVerdict",
            "TradeIntent",
            "VerdictStatus",
        }

    @pytest.mark.parametrize("name", INTENT_PRIMITIVES)
    def test_risk_does_not_re_export_a_broker_primitive_to_shorten_the_import(
        self, name: str
    ) -> None:
        """The forbidden import must not become a permitted one by going next door."""
        assert name not in atlas.risk.__all__
        assert not hasattr(atlas.risk, name)

    @pytest.mark.parametrize("path", RISK_SOURCES, ids=lambda path: path.name)
    def test_no_risk_module_imports_the_layer_above_it(self, path: Path) -> None:
        offending = [
            module
            for module in _atlas_imports(_source_of(path))
            if _is_within(module, "atlas.strategy")
        ]

        assert offending == []


class TestTheContractIsSatisfiable:
    """An abstraction no one has implemented is an abstraction no one has tried.

    The intents below are built *here*, in test code, which is the whole reason
    :mod:`atlas.strategy.reference` imports nothing from the port. Naming
    ``OrderSide`` is what constructing an intent costs, and a test is where that
    cost belongs.
    """

    def test_the_reference_implementation_satisfies_the_protocol(self) -> None:
        strategy: Strategy[object] = ConstantStrategy()

        assert isinstance(strategy, Strategy)

    def test_a_strategy_may_produce_a_valid_trade_intent(self) -> None:
        strategy = ConstantStrategy(
            TradeIntent(
                symbol="EURUSD",
                side=OrderSide.BUY,
                requested_volume=Decimal("0.10"),
                stop_loss=Decimal("1.0950"),
            )
        )

        intent = strategy.propose(object())

        assert isinstance(intent, TradeIntent)
        assert intent.symbol == "EURUSD"
        assert intent.side is OrderSide.BUY
        assert intent.requested_volume == Decimal("0.10")
        assert intent.stop_loss == Decimal("1.0950")
        assert intent.take_profit is None

    def test_a_strategy_may_have_no_opinion(self) -> None:
        """``None`` is an ordinary answer, and there is no sentinel to mistake for one."""
        assert ConstantStrategy().propose(object()) is None

    def test_what_a_strategy_produces_is_a_recommendation_and_not_an_order(self) -> None:
        intent = ConstantStrategy(
            TradeIntent(symbol="EURUSD", side=OrderSide.SELL, requested_volume=Decimal("1.00"))
        ).propose(object())

        assert intent is not None
        assert set(type(intent).model_fields).isdisjoint(
            {"type", "order_type", "price", "stop_price", "order_id", "approved_volume"}
        )
