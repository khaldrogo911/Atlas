"""Structural tests for the risk boundary.

ATLAS-TASK-0011 introduces the edge ``atlas.risk -> atlas.broker`` and
ATLAS-TASK-0017 adds ``atlas.risk -> atlas.config``, which carries the single
name ``get_settings``. Two edges, both downward, and the tests here are what
stop them becoming more. They assert the shape of the package rather than its
behaviour: which packages it may import and which names it may take from the one
it reads its own limit from, that it reaches no credential-bearing configuration
even though the import allowlist cannot see that far, that it neither builds nor
re-exports an order, and that an approved volume exists nowhere except on an
approved verdict.

What these tests deliberately do **not** claim
    The invariant is that execution acts only on approved risk output.
    :mod:`atlas.execution` consumes a verdict as of ATLAS-TASK-0014 and
    :func:`~atlas.risk.evaluate_exposure` produces one as of ATLAS-TASK-0017,
    but nothing outside the test suite produces a ``TradeIntent`` and nothing
    outside it hands one to the control, so there is still no pipeline to
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
import atlas.config
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
#: risk-local copies, which is a downward edge and the one that task creates.
#: ``atlas.config`` is admitted by ATLAS-TASK-0017 under ADR-0012 — a control
#: that is handed its state must still read its own limit, and a limit that
#: arrived as an argument would be a limit the caller chose. It is the only
#: entry here that additionally carries a *name* allowlist; see
#: :data:`PERMITTED_CONFIG_NAMES`. ``atlas.common`` is admitted on the grounds
#: ``docs/architecture/overview.md`` already states — dependency-free,
#: importable anywhere, encoding no domain rules — though nothing in the package
#: needs it yet.
PERMITTED_ATLAS_PACKAGES: Final = ("atlas.risk", "atlas.broker", "atlas.config", "atlas.common")

#: Packages risk may not import, and why each would be wrong.
#:
#: ``strategy`` and ``execution`` sit *above* risk: importing either inverts the
#: direction the boundary exists to state, and an import of ``execution`` would
#: additionally give risk a route to an order. ``config`` sat here until
#: ATLAS-TASK-0017, on the grounds that contracts need no configuration and that
#: widening the permitted set must be a deliberate act in the task that needs it
#: — the way ``atlas.common`` was admitted to the port's set in
#: ATLAS-TASK-0009. That task is the deliberate act, and the edge it takes is
#: bounded by a name allowlist the other permitted packages do not have.
#: ``events`` is excluded because event transport is out of scope. The rest are
#: peers or upstream producers with no business inside a risk contract.
FORBIDDEN_ATLAS_PACKAGES: Final = (
    "atlas.strategy",
    "atlas.execution",
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

#: Port operations ADR-0012 forbids risk to call.
#:
#: Risk is handed the state it judges; it does not go and fetch it.
#: ``margin_required`` is the one that bites hardest, because a control that
#: could ask what an intent would cost would be a different control from the one
#: this package has — and its absence is why the verdict cannot depend on the
#: size of the intent.
PORT_OPERATION_SYMBOLS: Final = (
    "get_account",
    "get_positions",
    "margin_required",
    "margin_available",
    "can_trade",
)

#: The only names a risk module may take from :mod:`atlas.config`.
#:
#: The edge exists so that risk can read its own limit, and for nothing else.
#: ``get_settings`` is cached and carries a return annotation, so the attribute
#: chain below it type-checks with no further import. ``load_settings`` is one
#: character away in the same ``__all__`` and would let risk rebuild settings
#: behind the cache's back; ``AtlasSettings`` would bring the whole tree in as a
#: type; ``RiskSettings`` is exported by convention and still not admitted.
#:
#: The allowlist applies to the package. Taking even the permitted name out of
#: ``atlas.config.settings`` reaches around the package's ``__all__``, which is
#: what ``no_implicit_reexport`` exists to prevent, and is an offence on the
#: module rather than on the name.
PERMITTED_CONFIG_NAMES: Final = ("get_settings",)

#: Stands in for the whole package in :func:`_config_imports`.
#:
#: ``import atlas.config`` binds the module rather than a name, which puts every
#: attribute on it within reach. A name allowlist cannot admit that, so it is
#: reported as its own offence. The mechanic is ported from
#: ``tests/unit/execution/test_execution_boundary.py``, where the same problem
#: already has the same answer.
WHOLE_MODULE: Final = "<module>"

#: Configuration names whose presence in risk source would mean risk had reached
#: a credential.
#:
#: The import allowlist cannot see any of these, because reaching them takes no
#: import at all: ``get_settings()`` returns the whole settings tree, so
#: ``get_settings().postgres.password.get_secret_value()`` resolves — and
#: type-checks — with ``get_settings`` as the only imported name. The escape
#: path is attribute access, so this scan is attribute-level, and the set is
#: derived from what actually leaks: two of the three sections that lead
#: anywhere credential-bearing, the field itself, its unwrap, its type, and
#: the two composites that embed the secret in a plain connection string
#: without the word "password" appearing anywhere. ``safe_dsn`` and
#: ``safe_url`` are deliberately absent — they mask by construction, and
#: their existence is precisely the evidence that ``dsn`` and ``url`` do not.
#:
#: The three sections are ``postgres``, ``redis`` and ``broker``, and the
#: third is deliberately absent from the tuple. ``_referenced_names``
#: registers the last segment of an ``ast.alias``, so the entry would fire on
#: ``import atlas.broker`` — a form ``atlas.risk`` is expressly permitted to
#: use, and one that reaches no credential. No risk module writes it today,
#: which is the point: the entry would be a false positive waiting for the
#: first one that did. Nothing escapes by leaving it out, because reaching
#: the broker credential still requires ``password``, ``get_secret_value`` or
#: ``SecretStr``, each of which is named below.
CREDENTIAL_SYMBOLS: Final = (
    "postgres",
    "redis",
    "password",
    "get_secret_value",
    "SecretStr",
    "dsn",
    "url",
)

#: The configuration access risk is *required* to keep.
#:
#: A guard hardened into a general ban on configuration would satisfy the scan
#: above and destroy the edge ADR-0012 admitted. This is what stops that.
PERMITTED_CONFIG_ACCESS: Final = "get_settings().risk.max_margin_utilisation"


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


def _config_imports(source: str) -> Iterator[tuple[str, str]]:
    """Yield ``(module, name)`` for every import that reaches ``atlas.config``.

    A whole-module import yields :data:`WHOLE_MODULE` as the name, because
    binding the module reaches every attribute on it and the point of this scan
    is to enumerate what a risk module can actually touch. The module is yielded
    alongside the name because *where* a name was taken from decides whether it
    was taken legitimately: the package's ``__all__`` is the surface ADR-0012
    admitted, and reaching around it into a submodule is its own offence however
    innocent the name looks.
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_within(alias.name, "atlas.config"):
                    yield alias.name, WHOLE_MODULE
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and _is_within(node.module, "atlas.config")
        ):
            for alias in node.names:
                yield node.module, alias.name


def _offending_config_imports(source: str) -> list[str]:
    """Return every name taken from configuration that is not in the vocabulary.

    The package allowlist above admits ``atlas.config`` wholesale; this is the
    rule that keeps the edge to the one name ADR-0012 needs. Everything else
    reachable through that package — the uncached loader, the settings tree, the
    section class — is the edge being used for something it was not authorised
    for. An offence taken from a submodule is reported by its full path, because
    ``from atlas.config.settings import get_settings`` and
    ``from atlas.config import get_settings`` are not the same act even though
    they bind the same object.
    """
    return [
        name if module == "atlas.config" else f"{module}.{name}"
        for module, name in _config_imports(source)
        if module != "atlas.config" or name not in PERMITTED_CONFIG_NAMES
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


def _credential_references(source: str) -> set[str]:
    """Return every credential-bearing configuration name the source reaches.

    Attribute-level, because the import allowlist cannot reach this far: one
    permitted import of ``get_settings`` is enough to resolve the entire settings
    tree, and every name in :data:`CREDENTIAL_SYMBOLS` is an attribute hop away
    from it.
    """
    return _referenced_names(source) & set(CREDENTIAL_SYMBOLS)


def _with_line(source: str, line: str) -> str:
    """Return real source with one line spliced in front of it.

    Used to mutate a file that currently passes and watch the scan fail on it,
    which is the difference between a scanner that works on a string and a
    scanner that is wired to the module it protects.
    """
    return f"{line}\n{source}"


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


class TestTheConfigurationEdgeCarriesOneName:
    """ADR-0012 gave risk one reason to read configuration: its own limit."""

    def test_the_edge_this_task_creates_is_actually_present(self) -> None:
        """An allowlist over an absent edge would be vacuously satisfied."""
        taken = {pair for path in RISK_SOURCES for pair in _config_imports(_source_of(path))}

        assert ("atlas.config", "get_settings") in taken, taken

    @pytest.mark.parametrize("path", RISK_SOURCES, ids=lambda path: path.name)
    def test_a_risk_module_takes_only_the_permitted_name(self, path: Path) -> None:
        assert _offending_config_imports(_source_of(path)) == []

    def test_the_permitted_name_is_not_reported(self) -> None:
        """The rule that rejects everything also rejects the edge itself."""
        assert _offending_config_imports("from atlas.config import get_settings") == []

    @pytest.mark.parametrize(
        ("statement", "offence"),
        [
            ("from atlas.config import load_settings", "load_settings"),
            ("from atlas.config import AtlasSettings", "AtlasSettings"),
            ("from atlas.config import RiskSettings", "RiskSettings"),
            (
                "from atlas.config.settings import get_settings",
                "atlas.config.settings.get_settings",
            ),
            ("import atlas.config", WHOLE_MODULE),
        ],
        ids=[
            "uncached-loader",
            "whole-settings-tree",
            "section-class",
            "around-the-packages-all",
            "whole-module",
        ],
    )
    def test_the_name_rule_rejects_what_the_edge_does_not_carry(
        self, statement: str, offence: str
    ) -> None:
        assert _offending_config_imports(statement) == [offence]

    @pytest.mark.parametrize(
        "name", ["get_settings", "load_settings", "AtlasSettings", "RiskSettings"]
    )
    def test_every_counter_example_names_something_that_really_exists(self, name: str) -> None:
        """A rule shown to reject only unimportable names has been shown nothing."""
        assert name in atlas.config.__all__
        assert hasattr(atlas.config, name)


class TestRiskIsHandedItsStateAndNeverFetchesIt:
    """ADR-0012's other half: the edge is to configuration, not to the venue."""

    @pytest.mark.parametrize("path", RISK_SOURCES, ids=lambda path: path.name)
    @pytest.mark.parametrize("symbol", PORT_OPERATION_SYMBOLS)
    def test_no_risk_module_names_a_port_operation(self, path: Path, symbol: str) -> None:
        assert symbol not in _referenced_names(_source_of(path))

    def test_the_port_operation_rule_can_actually_fire(self) -> None:
        names = _referenced_names("cost = adapter.margin_required(symbol, volume)")

        assert "margin_required" in names


class TestRiskReachesNoCredential:
    """The guard the import allowlist cannot provide.

    One permitted import is enough to resolve the entire settings tree, so the
    property that matters here is not what a risk module imports but what it
    reaches. Every test below is attribute-level for that reason.
    """

    @pytest.mark.parametrize("path", RISK_SOURCES, ids=lambda path: path.name)
    def test_no_risk_module_reaches_a_credential_bearing_name(self, path: Path) -> None:
        assert _credential_references(_source_of(path)) == set()

    def test_the_access_the_edge_exists_for_scans_clean(self) -> None:
        """The guard must not be 'hardened' into a ban on reading the limit."""
        names = _referenced_names(f"limit = {PERMITTED_CONFIG_ACCESS}")

        assert {"get_settings", "risk", "max_margin_utilisation"} <= names
        assert _credential_references(f"limit = {PERMITTED_CONFIG_ACCESS}") == set()

    @pytest.mark.parametrize(
        ("statement", "reached"),
        [
            (
                "get_settings().postgres.password.get_secret_value()",
                {"postgres", "password", "get_secret_value"},
            ),
            ("get_settings().redis.url", {"redis", "url"}),
            ("get_settings().postgres.dsn", {"postgres", "dsn"}),
            ("from pydantic import SecretStr", {"SecretStr"}),
        ],
        ids=["unwrapped-password", "redis-url", "postgres-dsn", "the-secret-type"],
    )
    def test_the_scan_reports_a_real_violating_line(
        self, statement: str, reached: set[str]
    ) -> None:
        assert _credential_references(statement) == reached

    def test_the_scan_is_wired_to_the_module_it_protects(self) -> None:
        """Injected into the real file, not scanned as a standalone string.

        A scanner demonstrated only on constructed strings has been shown to
        work; it has not been shown to be pointed at anything.
        """
        source = _source_of(RISK_DIR / "exposure.py")

        assert _credential_references(source) == set()
        assert _credential_references(
            _with_line(source, "_ = get_settings().postgres.password.get_secret_value()")
        ) == {"postgres", "password", "get_secret_value"}

    def test_prose_describing_the_rule_does_not_trip_the_scanner(self) -> None:
        assert _credential_references('"""Never reads the database password."""') == set()

    def test_the_module_documents_the_rule_and_still_scans_clean(self) -> None:
        """Prose immunity, asserted on the module that actually carries prose."""
        source = _source_of(RISK_DIR / "exposure.py")

        assert "password" in source
        assert _credential_references(source) == set()


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
            "evaluate_exposure",
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
