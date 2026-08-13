"""Structural tests for the risk boundary.

ATLAS-TASK-0011 introduces exactly one edge, ``atlas.risk -> atlas.broker``,
and the tests here are what stop it becoming several. They assert the shape of
the package rather than its behaviour: which packages it may import, that it
neither builds nor re-exports an order, and that an approved volume exists
nowhere except on an approved verdict.

What these tests deliberately do **not** claim
    The invariant is that execution acts only on approved risk output.
    :mod:`atlas.execution` consumes a verdict as of ATLAS-TASK-0014, but
    nothing outside the test suite produces a ``TradeIntent`` and nothing
    anywhere turns one into a ``RiskVerdict``, so there is no pipeline to
    observe and the behavioural half of that sentence is not provable today.
    What is provable now is the structural half — risk exposes no path to an
    order, and the only place an approved volume exists is on a verdict whose
    status is ``APPROVED`` — and that is all that is asserted below. The rest
    arrives with the task that drives an intent through risk.
"""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

import atlas.broker
import atlas.risk
from atlas.broker.models import OrderSide
from atlas.risk import RejectionReason, RiskVerdict, TradeIntent, VerdictStatus

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.unit

RISK_DIR: Final = Path(inspect.getfile(atlas.risk)).parent
RISK_SOURCES: Final = tuple(sorted(RISK_DIR.rglob("*.py")))

BROKER_DIR: Final = Path(inspect.getfile(atlas.broker)).parent
BROKER_SOURCES: Final = tuple(sorted(BROKER_DIR.rglob("*.py")))

#: The only ``atlas`` packages a risk module may import.
#:
#: ``atlas.risk`` is itself. ``atlas.broker`` is admitted by ATLAS-TASK-0011:
#: the contracts are stated in the port's own primitives rather than in
#: risk-local copies, which is a downward edge and the one this task creates.
#: ``atlas.common`` is admitted on the grounds ``docs/architecture/overview.md``
#: already states — dependency-free, importable anywhere, encoding no domain
#: rules — though nothing in the package needs it yet.
PERMITTED_ATLAS_PACKAGES: Final = ("atlas.risk", "atlas.broker", "atlas.common")

#: Packages risk may not import, and why each would be wrong.
#:
#: ``strategy`` and ``execution`` sit *above* risk: importing either inverts the
#: direction the boundary exists to state, and an import of ``execution`` would
#: additionally give risk a route to an order. ``config`` is not admitted
#: because contracts need no configuration, and widening the permitted set must
#: be a deliberate act in the task that needs it — the way ``atlas.common`` was
#: admitted to the port's set in ATLAS-TASK-0009. ``events`` is excluded because
#: event transport is out of this task's scope. The rest are peers or upstream
#: producers with no business inside a risk contract.
FORBIDDEN_ATLAS_PACKAGES: Final = (
    "atlas.strategy",
    "atlas.execution",
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

#: Names whose presence in risk source would mean risk had started building,
#: routing or placing an order rather than judging an intent.
ORDER_CONSTRUCTION_SYMBOLS: Final = (
    "OrderRequest",
    "OrderType",
    "OrderStatus",
    "BrokerAdapter",
    "place_order",
    "modify_order",
    "cancel_order",
    "close_position",
)


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
    """Return every ``atlas`` import in the source that risk may not make."""
    return [
        module
        for module in _atlas_imports(source)
        if not any(_is_within(module, permitted) for permitted in PERMITTED_ATLAS_PACKAGES)
    ]


def _referenced_names(source: str) -> set[str]:
    """Return every identifier the source *uses*, excluding prose.

    String constants are skipped on purpose: the modules under test discuss
    ``OrderRequest`` in their docstrings in order to say that they do not build
    one, and a scan that read prose would fail on the sentence that documents
    the rule.
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

    def test_there_is_risk_source_to_scan(self) -> None:
        assert RISK_SOURCES, "no risk sources were discovered"
        assert {path.name for path in RISK_SOURCES} >= {"__init__.py", "contracts.py"}

    def test_the_import_scanner_finds_the_edge_this_task_creates(self) -> None:
        found = {module for path in RISK_SOURCES for module in _atlas_imports(_source_of(path))}

        assert any(_is_within(module, "atlas.broker") for module in found), found

    def test_the_import_rule_can_actually_fire(self) -> None:
        assert _offending_imports("from atlas.execution import Executor") == ["atlas.execution"]

    def test_the_name_scanner_reads_real_identifiers(self) -> None:
        names = _referenced_names(_source_of(RISK_DIR / "contracts.py"))

        assert {"BaseModel", "Field", "model_validator", "Volume"} <= names

    def test_the_name_scanner_ignores_prose(self) -> None:
        assert "OrderRequest" not in _referenced_names('"""Never builds an OrderRequest."""')

    def test_the_order_symbol_rule_can_actually_fire(self) -> None:
        names = _referenced_names("from atlas.broker import OrderRequest\nx = OrderRequest")

        assert "OrderRequest" in names


class TestDependencyDirection:
    @pytest.mark.parametrize("path", RISK_SOURCES, ids=lambda path: path.name)
    def test_a_risk_module_imports_only_permitted_atlas_packages(self, path: Path) -> None:
        assert _offending_imports(_source_of(path)) == []

    @pytest.mark.parametrize("package", FORBIDDEN_ATLAS_PACKAGES)
    def test_the_rule_still_rejects_a_package_risk_may_not_reach(self, package: str) -> None:
        assert _offending_imports(f"from {package} import Thing") == [package]

    def test_risk_reaches_upward_to_nothing_at_all(self) -> None:
        imported = {module for path in RISK_SOURCES for module in _atlas_imports(_source_of(path))}
        forbidden = {
            module
            for module in imported
            for package in FORBIDDEN_ATLAS_PACKAGES
            if _is_within(module, package)
        }

        assert forbidden == set()

    def test_the_new_edge_did_not_create_a_cycle(self) -> None:
        """The port must still not see the layer above it."""
        reaching_back = {
            path.name
            for path in BROKER_SOURCES
            if any(_is_within(module, "atlas.risk") for module in _atlas_imports(_source_of(path)))
        }

        assert reaching_back == set()


class TestRiskNeverBuildsAnOrder:
    @pytest.mark.parametrize("path", RISK_SOURCES, ids=lambda path: path.name)
    @pytest.mark.parametrize("symbol", ORDER_CONSTRUCTION_SYMBOLS)
    def test_no_risk_module_names_an_order_construction_symbol(
        self, path: Path, symbol: str
    ) -> None:
        assert symbol not in _referenced_names(_source_of(path))

    @pytest.mark.parametrize("symbol", ORDER_CONSTRUCTION_SYMBOLS)
    def test_the_package_re_exports_no_order_construction_symbol(self, symbol: str) -> None:
        assert symbol not in atlas.risk.__all__
        assert not hasattr(atlas.risk, symbol)

    def test_the_package_exports_exactly_the_contracts_and_nothing_more(self) -> None:
        assert set(atlas.risk.__all__) == {
            "RISK_MODEL_CONFIG",
            "RejectionReason",
            "RiskVerdict",
            "TradeIntent",
            "VerdictStatus",
        }

    def test_no_risk_contract_carries_a_field_an_order_would_need(self) -> None:
        fields = set(TradeIntent.model_fields) | set(RiskVerdict.model_fields)

        assert fields.isdisjoint({"type", "order_type", "price", "stop_price", "order_id"})


class TestApprovedVolumeIsOnlyOnAnApprovedVerdict:
    def test_an_intent_has_no_approved_volume_to_read(self) -> None:
        assert "approved_volume" not in TradeIntent.model_fields

    def test_a_volume_is_present_exactly_when_the_verdict_approves(self) -> None:
        intent = TradeIntent(symbol="EURUSD", side=OrderSide.BUY, requested_volume=Decimal("1.00"))
        verdicts = (
            RiskVerdict(
                intent=intent, status=VerdictStatus.APPROVED, approved_volume=Decimal("1.00")
            ),
            RiskVerdict(
                intent=intent, status=VerdictStatus.APPROVED, approved_volume=Decimal("0.25")
            ),
            RiskVerdict(
                intent=intent,
                status=VerdictStatus.REJECTED,
                reason=RejectionReason.KILL_SWITCH,
            ),
        )

        for verdict in verdicts:
            assert (verdict.approved_volume is not None) is verdict.is_approved

    def test_a_consumer_that_ignores_the_status_gets_nothing_to_trade(self) -> None:
        """The bypass is not merely forbidden; there is no number to bypass with."""
        intent = TradeIntent(symbol="EURUSD", side=OrderSide.BUY, requested_volume=Decimal("1.00"))
        rejected = RiskVerdict(
            intent=intent, status=VerdictStatus.REJECTED, reason=RejectionReason.DRAWDOWN_LIMIT
        )

        assert rejected.approved_volume is None
        assert rejected.intent.requested_volume == Decimal("1.00")
