"""Structural tests for the execution boundary.

ATLAS-TASK-0014 adds the consuming half of the boundary ATLAS-TASK-0011 defined,
and with it two edges: ``atlas.execution -> atlas.risk`` and
``atlas.execution -> atlas.broker``. The second is the one that needs guarding.
It is a type dependency — permission to *name* the port's order vocabulary — and
from the outside it is indistinguishable from permission to *call* the port. The
tests here are what make the difference real.

They assert the shape of the package rather than its behaviour: which packages an
execution module may import, that the only names it takes from the port are the
three the vocabulary consists of, that ``BrokerAdapter`` and the four trading
verbs appear nowhere, that no layer below can see execution, and that nothing was
made to pass by loosening the boundary next door.

What these tests deliberately do **not** claim
    The invariant is that only approved intents are executed. Both halves are now
    provable at this boundary — a rejected verdict yields nothing, and nothing
    here can reach a venue — but "executed" still overstates it. Nothing places
    an order, because the layer that owns broker interaction does not exist. What
    is asserted below is that the request is built correctly and that the package
    cannot acquire a route to a venue. That a running pipeline routes every
    intent through risk needs a pipeline, and there is still no engine, no
    registry and no consumer.
"""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

import atlas.broker
import atlas.execution
import atlas.risk
from atlas.broker.models import OrderSide, OrderType
from atlas.execution import ExecutionPolicy, build_order_request
from atlas.risk import RejectionReason, RiskVerdict, TradeIntent, VerdictStatus

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.unit

EXECUTION_DIR: Final = Path(inspect.getfile(atlas.execution)).parent
EXECUTION_SOURCES: Final = tuple(sorted(EXECUTION_DIR.rglob("*.py")))

RISK_DIR: Final = Path(inspect.getfile(atlas.risk)).parent
RISK_SOURCES: Final = tuple(sorted(RISK_DIR.rglob("*.py")))

BROKER_DIR: Final = Path(inspect.getfile(atlas.broker)).parent
BROKER_SOURCES: Final = tuple(sorted(BROKER_DIR.rglob("*.py")))

#: The only ``atlas`` packages an execution module may import.
#:
#: ``atlas.execution`` is itself. ``atlas.risk`` supplies the verdict this
#: package consumes. ``atlas.broker`` is the edge ADR-0011 authorises, and it is
#: authorised for its order vocabulary alone — see
#: :data:`PERMITTED_BROKER_NAMES`, which is the rule that gives the edge its
#: shape. ``atlas.common`` is **not** admitted: ATLAS-TASK-0014 does not need it,
#: and widening a permitted set must be a deliberate act in the task that needs
#: it.
PERMITTED_ATLAS_PACKAGES: Final = ("atlas.execution", "atlas.risk", "atlas.broker")

#: Packages execution may not import, and why each would be wrong.
#:
#: ``strategy`` sits beside execution across risk: importing it would let a
#: proposal reach an order builder without a verdict in between, which is the
#: bypass the whole boundary exists to prevent. ``config`` is excluded because a
#: contract needs no configuration, and because broker or venue configuration is
#: the specific thing ADR-0011 refuses execution. ``events`` is excluded because
#: nothing here is transported, ``audit`` because nothing here is recorded, and
#: ``common`` because this task does not need it. The rest are peers or upstream
#: producers with no business inside a translation.
FORBIDDEN_ATLAS_PACKAGES: Final = (
    "atlas.strategy",
    "atlas.config",
    "atlas.events",
    "atlas.common",
    "atlas.ai",
    "atlas.market",
    "atlas.features",
    "atlas.regime",
    "atlas.analytics",
    "atlas.notification",
    "atlas.learning",
    "atlas.audit",
)

#: The whole of the port's vocabulary an execution module may name.
#:
#: Three names, and they are the three an ``OrderRequest`` cannot be built
#: without: the request itself, the enumeration that says how it is presented,
#: and the type its working price is stated in. ``OrderSide``, ``SymbolName`` and
#: ``Volume`` are absent on purpose — those values are read off a verdict and
#: passed through, so nothing here has to name their types.
#:
#: This allowlist is the difference between this boundary and the one next door.
#: ``tests/unit/strategy/test_strategy_boundary.py`` permits *no* name from the
#: port; execution permits exactly these and nothing else.
PERMITTED_BROKER_NAMES: Final = ("OrderRequest", "OrderType", "Price")

#: Names whose presence in execution source would mean the type dependency had
#: become a call path.
#:
#: ``BrokerAdapter`` is the route to a venue. The four verbs are the acts
#: themselves. ``OrderStatus`` is what a venue reports back about an order that
#: exists, which nothing here has: this package builds requests and never
#: observes their fate.
VENUE_ACCESS_SYMBOLS: Final = (
    "BrokerAdapter",
    "OrderStatus",
    "place_order",
    "modify_order",
    "cancel_order",
    "close_position",
)

#: Stands in for the whole port in :func:`_broker_imports`.
#:
#: ``import atlas.broker`` binds the module rather than a name, which puts every
#: attribute on it — ``BrokerAdapter`` included — within reach. An allowlist of
#: names cannot admit it, so it is reported as its own offence.
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
    """Return every ``atlas`` import in the source that execution may not make."""
    return [
        module
        for module in _atlas_imports(source)
        if not any(_is_within(module, permitted) for permitted in PERMITTED_ATLAS_PACKAGES)
    ]


def _broker_imports(source: str) -> Iterator[str]:
    """Yield every name taken from ``atlas.broker``, however it was taken.

    A whole-module import yields :data:`WHOLE_MODULE`, because binding the module
    reaches every name in it and the point of this scan is to enumerate what an
    execution module can actually touch.
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
    """Return every name taken from the port that is not in the vocabulary.

    Unlike the strategy boundary, where every name is an offence, this rule is an
    allowlist: the edge exists so that execution can name three types, and
    anything else taken from the port is the edge being used for something it was
    not authorised for.
    """
    return [name for name in _broker_imports(source) if name not in PERMITTED_BROKER_NAMES]


def _referenced_names(source: str) -> set[str]:
    """Return every identifier the source *uses*, excluding prose.

    String constants are skipped on purpose: the modules under test discuss
    ``BrokerAdapter`` in their docstrings in order to say that they never obtain
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


def _with_line(source: str, line: str) -> str:
    """Return real source with one line spliced in, to mutate a passing file."""
    return f"{line}\n{source}"


class TestTheScannersWork:
    """A scan that inspects nothing passes everything."""

    def test_there_is_execution_source_to_scan(self) -> None:
        assert EXECUTION_SOURCES, "no execution sources were discovered"
        assert {path.name for path in EXECUTION_SOURCES} >= {"__init__.py", "contracts.py"}

    def test_there_is_risk_and_broker_source_to_scan(self) -> None:
        assert RISK_SOURCES, "no risk sources were discovered"
        assert BROKER_SOURCES, "no broker sources were discovered"

    def test_the_import_scanner_finds_both_edges_this_task_creates(self) -> None:
        found = {
            module for path in EXECUTION_SOURCES for module in _atlas_imports(_source_of(path))
        }

        assert any(_is_within(module, "atlas.risk") for module in found), found
        assert any(_is_within(module, "atlas.broker") for module in found), found

    def test_the_import_scanner_sees_through_a_type_checking_guard(self) -> None:
        """A guarded import is still an import; ``ast.walk`` descends into the block.

        ``contracts.py`` takes ``RiskVerdict`` under ``if TYPE_CHECKING:``. That
        must not be a way to acquire an edge the scanner cannot see, so the
        mechanism is asserted rather than assumed.
        """
        guarded = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from atlas.ai import X"

        assert _offending_imports(guarded) == ["atlas.ai"]

    def test_the_import_rule_can_actually_fire(self) -> None:
        assert _offending_imports("from atlas.strategy import Strategy") == ["atlas.strategy"]

    @pytest.mark.parametrize("package", FORBIDDEN_ATLAS_PACKAGES)
    def test_the_import_rule_fires_on_every_package_execution_may_not_reach(
        self, package: str
    ) -> None:
        assert _offending_imports(f"from {package} import Thing") == [package]

    @pytest.mark.parametrize("name", VENUE_ACCESS_SYMBOLS)
    def test_the_broker_allowlist_can_actually_fire(self, name: str) -> None:
        assert _offending_broker_imports(f"from atlas.broker import {name}") == [name]

    @pytest.mark.parametrize("name", PERMITTED_BROKER_NAMES)
    def test_the_broker_allowlist_admits_the_vocabulary_it_exists_for(self, name: str) -> None:
        """An allowlist that admitted nothing would pass by making the edge unusable."""
        assert _offending_broker_imports(f"from atlas.broker import {name}") == []
        assert _offending_broker_imports(f"from atlas.broker.models import {name}") == []

    def test_the_broker_allowlist_rejects_binding_the_whole_port(self) -> None:
        """A module import reaches ``BrokerAdapter``, so no allowlist can admit it."""
        assert _offending_broker_imports("import atlas.broker") == [WHOLE_MODULE]
        assert _offending_broker_imports("import atlas.broker.models") == [WHOLE_MODULE]
        assert _offending_broker_imports("import atlas.broker.adapter") == [WHOLE_MODULE]

    def test_the_name_scanner_reads_real_identifiers(self) -> None:
        names = _referenced_names(_source_of(EXECUTION_DIR / "contracts.py"))

        assert {"OrderRequest", "BaseModel", "Field", "approved_volume"} <= names

    def test_the_name_scanner_ignores_prose(self) -> None:
        assert "BrokerAdapter" not in _referenced_names('"""Never obtains a BrokerAdapter."""')

    def test_the_venue_symbol_rule_can_actually_fire(self) -> None:
        names = _referenced_names("from atlas.broker import BrokerAdapter\nx = BrokerAdapter()")

        assert "BrokerAdapter" in names


class TestTheScannersFireOnMutatedRealSource:
    """Proving the rules on snippets is not proving them on the files that ship.

    Each case takes the real, passing source of a module in this package, splices
    in one forbidden line, and asserts the scanner now reports it. A rule that
    only ever sees hand-written snippets is a rule that has never been pointed at
    the thing it protects.
    """

    @pytest.mark.parametrize("path", EXECUTION_SOURCES, ids=lambda path: path.name)
    def test_real_source_passes_before_mutation(self, path: Path) -> None:
        source = _source_of(path)

        assert _offending_imports(source) == []
        assert _offending_broker_imports(source) == []

    @pytest.mark.parametrize("path", EXECUTION_SOURCES, ids=lambda path: path.name)
    def test_an_injected_adapter_import_makes_real_source_fail(self, path: Path) -> None:
        mutated = _with_line(_source_of(path), "from atlas.broker import BrokerAdapter")

        assert _offending_broker_imports(mutated) == ["BrokerAdapter"]

    @pytest.mark.parametrize("path", EXECUTION_SOURCES, ids=lambda path: path.name)
    def test_an_injected_whole_port_import_makes_real_source_fail(self, path: Path) -> None:
        mutated = _with_line(_source_of(path), "import atlas.broker")

        assert _offending_broker_imports(mutated) == [WHOLE_MODULE]

    @pytest.mark.parametrize("path", EXECUTION_SOURCES, ids=lambda path: path.name)
    def test_an_injected_forbidden_package_makes_real_source_fail(self, path: Path) -> None:
        mutated = _with_line(_source_of(path), "from atlas.config import AtlasSettings")

        assert _offending_imports(mutated) == ["atlas.config"]

    @pytest.mark.parametrize("path", EXECUTION_SOURCES, ids=lambda path: path.name)
    def test_an_injected_place_order_call_makes_real_source_fail(self, path: Path) -> None:
        """The verb, not merely the import: a call is what the adapter is *for*."""
        mutated = _with_line(_source_of(path), "adapter.place_order(request)")

        assert "place_order" in _referenced_names(mutated)

    def test_a_guarded_adapter_import_is_caught_too(self) -> None:
        """``if TYPE_CHECKING:`` is not a hiding place, asserted against real source."""
        mutated = _with_line(
            _source_of(EXECUTION_DIR / "contracts.py"),
            "if TYPE_CHECKING:\n    from atlas.broker import BrokerAdapter",
        )

        assert _offending_broker_imports(mutated) == ["BrokerAdapter"]


class TestDependencyDirection:
    @pytest.mark.parametrize("path", EXECUTION_SOURCES, ids=lambda path: path.name)
    def test_an_execution_module_imports_only_permitted_atlas_packages(self, path: Path) -> None:
        assert _offending_imports(_source_of(path)) == []

    def test_no_execution_module_reaches_a_forbidden_package(self) -> None:
        imported = {
            module for path in EXECUTION_SOURCES for module in _atlas_imports(_source_of(path))
        }
        forbidden = {
            module
            for module in imported
            for package in FORBIDDEN_ATLAS_PACKAGES
            if _is_within(module, package)
        }

        assert forbidden == set()

    def test_the_new_edges_did_not_create_a_cycle(self) -> None:
        """Neither layer below may see the one that consumes it."""
        reaching_back = {
            path.name
            for path in (*RISK_SOURCES, *BROKER_SOURCES)
            if any(
                _is_within(module, "atlas.execution") for module in _atlas_imports(_source_of(path))
            )
        }

        assert reaching_back == set()

    def test_execution_cannot_see_the_layer_that_proposes(self) -> None:
        """A strategy must not reach an order builder without a verdict in between."""
        reaching = {
            path.name
            for path in EXECUTION_SOURCES
            if any(
                _is_within(module, "atlas.strategy") for module in _atlas_imports(_source_of(path))
            )
        }

        assert reaching == set()
        assert not hasattr(atlas.execution, "strategy")


class TestExecutionNamesTheVocabularyAndNothingElse:
    @pytest.mark.parametrize("path", EXECUTION_SOURCES, ids=lambda path: path.name)
    def test_an_execution_module_takes_no_name_from_the_port_outside_the_vocabulary(
        self, path: Path
    ) -> None:
        assert _offending_broker_imports(_source_of(path)) == []

    @pytest.mark.parametrize("path", EXECUTION_SOURCES, ids=lambda path: path.name)
    @pytest.mark.parametrize("symbol", VENUE_ACCESS_SYMBOLS)
    def test_no_execution_module_names_a_venue_access_symbol(self, path: Path, symbol: str) -> None:
        assert symbol not in _referenced_names(_source_of(path))

    @pytest.mark.parametrize("symbol", VENUE_ACCESS_SYMBOLS)
    def test_the_package_re_exports_no_venue_access_symbol(self, symbol: str) -> None:
        assert symbol not in atlas.execution.__all__
        assert not hasattr(atlas.execution, symbol)

    def test_the_package_exports_exactly_the_contract_and_nothing_more(self) -> None:
        assert set(atlas.execution.__all__) == {"ExecutionPolicy", "build_order_request"}

    def test_the_package_re_exports_none_of_the_port_it_names(self) -> None:
        """Naming ``OrderRequest`` is permitted; becoming a second door to it is not."""
        for name in PERMITTED_BROKER_NAMES:
            assert name not in atlas.execution.__all__

    def test_nothing_here_holds_state_between_calls(self) -> None:
        """The contract is a function and a frozen value, not a service."""
        assert ExecutionPolicy.model_config["frozen"] is True
        assert not hasattr(build_order_request, "__self__")


class TestTheBoundariesNextDoorWereNotWidened:
    """The cheap way to pass the tests above is to move the problem next door."""

    def test_risk_still_exports_exactly_what_it_exported(self) -> None:
        assert set(atlas.risk.__all__) == {
            "RISK_MODEL_CONFIG",
            "RejectionReason",
            "RiskVerdict",
            "TradeIntent",
            "VerdictStatus",
            "evaluate_exposure",
        }

    @pytest.mark.parametrize("name", ["OrderRequest", "OrderType", "Price", "BrokerAdapter"])
    def test_risk_did_not_start_re_exporting_the_port(self, name: str) -> None:
        """The vocabulary must come from the port, not through a shorter door."""
        assert name not in atlas.risk.__all__
        assert not hasattr(atlas.risk, name)

    def test_the_port_still_owns_the_request(self) -> None:
        """The vocabulary is imported from the port, not restated beside it.

        Asserted on the source rather than on the imported object, because
        ``no_implicit_reexport`` means an execution module is not a legitimate
        route to a broker name — which is itself the rule being protected. That
        the thing built is the port's class is asserted where it is built, in
        ``test_build_order_request.py``.
        """
        assert "OrderRequest" in atlas.broker.__all__

        taken = {name for path in EXECUTION_SOURCES for name in _broker_imports(_source_of(path))}

        assert "OrderRequest" in taken

    def test_no_risk_contract_acquired_a_field_an_order_would_need(self) -> None:
        """Execution must not have been made easier by moving presentation into risk."""
        fields = set(TradeIntent.model_fields) | set(RiskVerdict.model_fields)

        assert fields.isdisjoint({"type", "order_type", "price", "stop_price", "order_id"})


class TestTheContractIsSatisfiable:
    """An abstraction no one has exercised is an abstraction no one has tried."""

    @staticmethod
    def _intent(*, stop_loss: Decimal | None = None) -> TradeIntent:
        return TradeIntent(
            symbol="EURUSD",
            side=OrderSide.BUY,
            requested_volume=Decimal("1.00"),
            stop_loss=stop_loss,
        )

    def test_an_approved_verdict_becomes_a_request(self) -> None:
        verdict = RiskVerdict(
            intent=self._intent(),
            status=VerdictStatus.APPROVED,
            approved_volume=Decimal("1.00"),
        )

        request = build_order_request(verdict, ExecutionPolicy(order_type=OrderType.MARKET))

        assert request is not None
        assert request.symbol == "EURUSD"
        assert request.side is OrderSide.BUY
        assert request.type is OrderType.MARKET
        assert request.volume == Decimal("1.00")

    def test_a_rejected_verdict_becomes_nothing(self) -> None:
        verdict = RiskVerdict(
            intent=self._intent(),
            status=VerdictStatus.REJECTED,
            reason=RejectionReason.KILL_SWITCH,
        )

        assert build_order_request(verdict, ExecutionPolicy(order_type=OrderType.MARKET)) is None

    def test_a_reduced_approval_carries_the_approved_volume(self) -> None:
        """The accident a third ``REDUCED`` status was rejected to prevent."""
        verdict = RiskVerdict(
            intent=self._intent(),
            status=VerdictStatus.APPROVED,
            approved_volume=Decimal("0.25"),
        )

        request = build_order_request(verdict, ExecutionPolicy(order_type=OrderType.MARKET))

        assert request is not None
        assert request.volume == Decimal("0.25")
        assert request.volume != verdict.intent.requested_volume
