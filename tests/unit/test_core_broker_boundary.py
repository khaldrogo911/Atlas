"""Structural tests for the four edges `apps/atlas-core` has to the broker.

ADR-0013 puts the `BrokerAdapter` in `apps/atlas-core`, which made
`apps/atlas-core -> atlas.broker` the first edge from an application to the
port. ADR-0015 added the second: `composition.py` reaches past the port to the
implementation it selected, in order to translate settings into it and build
one. ADR-0017 added the third: start-up opens a session and reports whether it
opened, so `__main__.py` names the one error it has to handle. ADR-0019 added
the fourth: a runtime entrypoint holds one session open for the life of a
process and drives the pipeline over it, so `runtime.py` supervises, recovers
and submits. These tests hold all four edges to the shape their decisions gave
them, and — now that traffic exists — hold the traffic to its granted list.

**This file is not an `apps/` import rule, and must not become one.** The four
package boundary tests each hold a closed `PERMITTED_ATLAS_PACKAGES` tuple — a
positive statement of everything that package may import. There is no such tuple
here. Exactly five permissions are stated below, each named and each traceable:
ADR-0015 selected `MT5BrokerAdapter`, and one module may name that
implementation and its configuration type for the one purpose the record gave
it; ADR-0017 decided that start-up reports a session it could not open, and one
module may name `BrokerError` for that; ADR-0019 gave the runtime the pipeline,
and one module may take six named symbols from the three pipeline packages;
ADR-0019 gave the runtime supervision and submission, and one module may name
six port operations. ADR-0020 gave the runtime a poll instead of a stream, and
the ownership module may name one port operation for the read it performs.
Each extends to no other module, to no other name, and to
no claim about what an application may import in general. That general rule is
still undecided — ADR-0013 `:242-249` records that it creates and implies none,
and neither ADR-0015 nor ADR-0019 moves it. It would begin with a decision
record rather than with a test file, which is precisely how all five
permissions here began.

Every other assertion is a property some accepted decision creates: ADR-0006's
abstraction, ADR-0013's single owner and downward-granted access, ADR-0015's
bounded selection, ADR-0017's bounded error handling, and ADR-0019's bounded
grant of supervision and trading to one named module, and ADR-0020's bounded
grant of a market-data read to the ownership module.

What these tests deliberately do **not** claim
    That the adapter is used *well*. ADR-0019 decided which operations the
    runtime may reach for and in what order the pipeline runs; it decided no
    polling interval, no retry policy, no health threshold, no instrument and
    no strategy. What is asserted here is the shape of the seam and the size of
    the traffic list, never that the traffic is a good idea.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.unit

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
APPS_ROOT: Final = REPO_ROOT / "apps"
CORE_SRC: Final = APPS_ROOT / "atlas-core" / "src"

#: Every application module in the repository, and every module in the one app
#: this task touches. The first set is what the "nowhere else" assertions scan;
#: the second is what the "exactly one" assertions scan.
APP_SOURCES: Final = tuple(sorted(APPS_ROOT.rglob("*.py")))
CORE_SOURCES: Final = tuple(sorted(CORE_SRC.rglob("*.py")))

#: The module ATLAS-TASK-0020 adds, and the sole importer of the port itself.
OWNERSHIP_MODULE: Final = CORE_SRC / "atlas" / "apps" / "core" / "broker_ownership.py"

#: The module ATLAS-TASK-0023 adds, and the sole holder of ADR-0015's permission.
COMPOSITION_MODULE: Final = CORE_SRC / "atlas" / "apps" / "core" / "composition.py"

#: The process entrypoint, and the sole holder of ADR-0017's permission.
ENTRYPOINT_MODULE: Final = CORE_SRC / "atlas" / "apps" / "core" / "__main__.py"

#: The module ATLAS-TASK-0029 adds, and the sole holder of ADR-0019's permissions.
#:
#: ADR-0019 requires its grants to be bounded by a named module rather than by a
#: directory, a prefix or a package, so the runtime is a single path here and the
#: two grants below are checked against it and against nothing else. A second
#: runtime module is a decision nobody has recorded, and fails the censuses.
RUNTIME_MODULE: Final = CORE_SRC / "atlas" / "apps" / "core" / "runtime.py"

#: The abstraction the edge exists for.
ADAPTER: Final = "BrokerAdapter"

#: The one name ADR-0017 permits :data:`ENTRYPOINT_MODULE` to take from the port.
#:
#: Start-up opens a session, reports whether it opened and exits, so the
#: entrypoint has to name the failure it reports. It is the port's root error and
#: nothing else — not the abstraction, not the refusal, and not an
#: implementation. A wider grant would be the entrypoint acquiring an adapter
#: rather than reporting on one, which is the property T-12 exists to hold.
HANDLED_PORT_ERROR: Final = "BrokerError"

#: The pipeline: a proposal, a verdict on it, and the request built from that
#: verdict.
#:
#: Until ADR-0019 no application module reached any of them, because the owner
#: had been joined to no pipeline. ADR-0019 assembled one and gave it to
#: :data:`RUNTIME_MODULE` alone, so these packages are now reachable from
#: exactly one module and unreachable from every other — including the other
#: three modules of the same application, and both other applications.
PIPELINE_PACKAGES: Final = ("atlas.strategy", "atlas.risk", "atlas.execution")

#: The six pipeline symbols ADR-0019 permits :data:`RUNTIME_MODULE` to take.
#:
#: Written per package, because the grant is per package: the runtime may see a
#: strategy's contract, the risk boundary's two values and its exposure check,
#: and execution's policy and builder. It may not see a concrete strategy, a
#: risk internal, or anything else those packages export. Reaching for a
#: seventh name is how the pipeline stops being the one ADR-0019 assembled, so
#: the grant is a closed list rather than a package-wide exemption.
PIPELINE_NAME_GRANT: Final = {
    "atlas.strategy": ("Strategy",),
    "atlas.risk": ("TradeIntent", "RiskVerdict", "evaluate_exposure"),
    "atlas.execution": ("ExecutionPolicy", "build_order_request"),
}

#: Sub-packages that contain an implementation of the port rather than the port.
CONCRETE_ADAPTER_PACKAGES: Final = ("atlas.broker.mock", "atlas.broker.mt5")

#: The implementation ADR-0015 selected, and the configuration type it is built
#: from. Nameable in :data:`COMPOSITION_MODULE`, for translation and
#: construction, and nowhere else under `apps/`.
SELECTED_IMPLEMENTATION_NAMES: Final = ("MT5BrokerAdapter", "MT5Config", "FILLING_MODE_NAME_TO_MT5")

#: Implementations ADR-0015 did not select. Nameable nowhere under `apps/`.
#:
#: ADR-0006 shipped the mock so that a caller cannot tell which adapter it holds,
#: and ADR-0015 states plainly that it is not a fallback: a module permitted to
#: name the selected implementation is still not permitted to name the one it was
#: selected over, because branching between the two is the decision no record
#: makes. `BaseBrokerAdapter` is included because inheriting from the base, or
#: naming it, is reaching past the port to the shared implementation underneath.
UNSELECTED_IMPLEMENTATION_NAMES: Final = (
    "MockBrokerAdapter",
    "MockVenue",
    "BaseBrokerAdapter",
)

#: Every name that would mean an application had chosen an implementation.
#:
#: Retained as the union so that the "can actually fire" case still proves the
#: scanner sees all five, whichever side of the selection each one falls on.
CONCRETE_ADAPTER_NAMES: Final = SELECTED_IMPLEMENTATION_NAMES + UNSELECTED_IMPLEMENTATION_NAMES

#: Port methods no application module calls, and each one's reason.
#:
#: `latency` is a measurement nothing acts on: ADR-0019 routes liveness through
#: `ping`, and a number with no threshold attached to it is the health policy
#: that record declines to write. The four order verbs beyond submission are
#: order lifecycle, which ADR-0019 `:21` defers entire — amending, cancelling
#: and closing are the decisions a position manager makes, and there is none.
#: `get_positions` is the state that manager would read. The three risk
#: helpers are the venue's own margin arithmetic, which ADR-0012 put on the
#: other side of the boundary: risk is handed its state and reads its own
#: limits, so an application that asked the broker whether it could trade would
#: be running a second risk model next to the one that already decided.
#:
#: This tuple was fourteen names until ADR-0019, and is eight because that
#: record moved exactly six of them into :data:`RUNTIME_PORT_OPERATIONS`. The
#: six did not become unguarded: they became guarded by module instead of
#: forbidden outright.
UNCALLED_PORT_OPERATIONS: Final = (
    "latency",
    "modify_order",
    "cancel_order",
    "close_position",
    "get_positions",
    "margin_required",
    "margin_available",
    "can_trade",
)

#: The six port operations ADR-0019 permits :data:`RUNTIME_MODULE` to name.
#:
#: `is_connected`, `health` and `ping` are the evidence a supervision loop
#: reads; `reconnect` is the one action it may take on that evidence.
#: `get_account` is the state ADR-0012 requires risk to be *handed*, which
#: makes fetching it the caller's job. `place_order` is submission, and
#: submission only — ADR-0019 stops there deliberately, which is why the four
#: verbs that would follow it stay in :data:`UNCALLED_PORT_OPERATIONS`.
#:
#: The grant is the pair, not the tuple: these names are permitted *in one
#: module*. Anywhere else under `apps/` they are exactly as forbidden as they
#: were before ADR-0019, which is what :func:`_authorised_callers_of` asserts.
RUNTIME_PORT_OPERATIONS: Final = (
    "is_connected",
    "health",
    "ping",
    "reconnect",
    "get_account",
    "place_order",
)

#: The one port operation ADR-0020 permits :data:`OWNERSHIP_MODULE` to name.
#:
#: `get_tick` is the read
#: :func:`~atlas.apps.core.broker_ownership.build_polling_observer` wraps.
#: Granted to the module that already owns the adapter, rather than to a new
#: one, because ADR-0020 built the read on the seam ADR-0013 already opened
#: instead of opening another.
MARKET_DATA_PORT_OPERATIONS: Final = ("get_tick",)

#: Decorators that would move the adapter out of an instance and into the module.
#:
#: `atlas.config` caches `get_settings` this way, and §12.1 of the task declines
#: to follow it: a cached module-level accessor is importable from anywhere,
#: which is acquisition-upward wearing the owner's clothes.
CACHING_DECORATORS: Final = ("lru_cache", "cache")

#: Stands in for the whole port when it is bound as a module rather than by name.
WHOLE_MODULE: Final = "<module>"


def _app_id(path: Path) -> str:
    """Identify a scanned module by its path below `apps/`."""
    return path.relative_to(APPS_ROOT).as_posix()


def _source_of(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _with_line(source: str, line: str) -> str:
    """Return real source with one line spliced in, to mutate a passing file."""
    return f"{line}\n{source}"


def _is_within(module: str, package: str) -> bool:
    """Whether ``module`` is ``package`` or something inside it."""
    return module == package or module.startswith(f"{package}.")


def _authorised_importers_of(package: str) -> set[str]:
    """The app modules ADR-0015 permits to import ``package``, by app id.

    One cell of the `APP_SOURCES` x `CONCRETE_ADAPTER_PACKAGES` cross product is
    filled and the rest are empty: the composition module may reach the package
    holding the implementation the record selected. The mock's package is not
    that one, in the composition module or anywhere else.
    """
    if _is_within(package, "atlas.broker.mt5"):
        return {_app_id(COMPOSITION_MODULE)}
    return set()


def _authorised_namers_of(name: str) -> set[str]:
    """The app modules ADR-0015 permits to name ``name``, by app id."""
    if name in SELECTED_IMPLEMENTATION_NAMES:
        return {_app_id(COMPOSITION_MODULE)}
    return set()


def _authorised_callers_of(operation: str) -> set[str]:
    """The app modules ADR-0019 permits to name ``operation``, by app id.

    The runtime is granted six operations; every other module is granted none,
    including the three that share its application. An operation outside the
    six is authorised to nobody, which is what keeps
    :data:`UNCALLED_PORT_OPERATIONS` a prohibition rather than a preference.
    """
    if operation in RUNTIME_PORT_OPERATIONS:
        return {_app_id(RUNTIME_MODULE)}
    return set()


def _authorised_callers_of_market_data(operation: str) -> set[str]:
    """The app modules ADR-0020 permits to name ``operation``, by app id.

    Mirrors :func:`_authorised_callers_of`: the ownership module is granted one
    operation; every other module, including the other three in its own
    application, is granted none.
    """
    if operation in MARKET_DATA_PORT_OPERATIONS:
        return {_app_id(OWNERSHIP_MODULE)}
    return set()


def _authorised_importers_of_pipeline(package: str) -> set[str]:
    """The app modules ADR-0019 permits to import ``package``, by app id."""
    if any(_is_within(package, granted) for granted in PIPELINE_NAME_GRANT):
        return {_app_id(RUNTIME_MODULE)}
    return set()


def _pipeline_names(source: str, package: str) -> set[str]:
    """Return every name taken from ``package``, or a whole-module import of it.

    Mirrors :func:`_broker_names` for the pipeline side of the boundary, so a
    module cannot widen its grant from six names to everything the package
    exports by binding the module instead of the names.
    """
    taken: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            taken |= {WHOLE_MODULE for alias in node.names if _is_within(alias.name, package)}
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and _is_within(node.module, package)
        ):
            taken |= {alias.name for alias in node.names}
    return taken


def _atlas_imports(source: str) -> Iterator[str]:
    """Yield the full module name of every ``atlas`` import in a source string.

    ``ast.walk`` descends into an ``if TYPE_CHECKING:`` block, so an import
    written for the type checker is reported like any other. That matters here:
    the ownership module takes :data:`ADAPTER` under exactly such a guard, and a
    scan that could not see it would be measuring the wrong file.
    """
    for node in ast.walk(ast.parse(source)):
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


def _broker_names(source: str) -> Iterator[str]:
    """Yield every name taken from ``atlas.broker``, however it was taken.

    A whole-module import yields :data:`WHOLE_MODULE`: binding the module reaches
    every name on it, so what was imported cannot be described by a list of
    names.
    """
    for node in ast.walk(ast.parse(source)):
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


def _names_in(node: ast.AST) -> set[str]:
    """Return every identifier a subtree *uses*, excluding prose.

    String constants are skipped deliberately. The modules under test discuss the
    port in their docstrings in order to say what they do not do with it, and a
    scan that read prose would fail on the sentence documenting the rule.
    """
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
        elif isinstance(child, ast.alias):
            names.add(child.name.rsplit(".", 1)[-1])
            if child.asname is not None:
                names.add(child.asname)
    return names


def _referenced_names(source: str) -> set[str]:
    """Return every identifier the source uses, excluding prose."""
    return _names_in(ast.parse(source))


def _module_level_assignments(source: str) -> Iterator[ast.Assign | ast.AnnAssign]:
    """Yield every assignment written at module scope, ignoring nested ones."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign | ast.AnnAssign):
            yield node


def _module_level_bindings_naming(source: str, name: str) -> list[str]:
    """Return the module-scope assignments whose target or value names ``name``."""
    return [
        ast.unparse(node) for node in _module_level_assignments(source) if name in _names_in(node)
    ]


def _assigned_at_module_scope(source: str) -> set[str]:
    """Return every name bound by an assignment at module scope."""
    bound: set[str] = set()
    for node in _module_level_assignments(source):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                bound.add(target.id)
    return bound


def _decorator_names(source: str) -> set[str]:
    """Return every identifier appearing in a decorator anywhere in the source."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            for decorator in node.decorator_list:
                names |= _names_in(decorator)
    return names


class TestTheScannersWork:
    """A scan that inspects nothing passes everything."""

    def test_there_is_application_source_to_scan(self) -> None:
        assert APP_SOURCES, "no application sources were discovered"
        assert CORE_SOURCES, "no atlas-core sources were discovered"
        assert {path.name for path in CORE_SOURCES} >= {
            "__init__.py",
            "__main__.py",
            OWNERSHIP_MODULE.name,
            RUNTIME_MODULE.name,
        }

    def test_every_application_on_disk_is_scanned(self) -> None:
        """An app added later must not escape these rules by being invisible to them."""
        on_disk = {path.name for path in APPS_ROOT.iterdir() if path.is_dir()}
        scanned = {path.relative_to(APPS_ROOT).parts[0] for path in APP_SOURCES}

        assert scanned == on_disk

    def test_the_ownership_module_is_among_the_scanned_files(self) -> None:
        assert OWNERSHIP_MODULE.is_file()
        assert OWNERSHIP_MODULE in CORE_SOURCES
        assert OWNERSHIP_MODULE in APP_SOURCES

    def test_the_entrypoint_module_is_among_the_scanned_files(self) -> None:
        assert ENTRYPOINT_MODULE.is_file()
        assert ENTRYPOINT_MODULE in CORE_SOURCES
        assert ENTRYPOINT_MODULE in APP_SOURCES

    def test_the_runtime_module_is_among_the_scanned_files(self) -> None:
        """ADR-0019's grants are worth nothing if the module holding them is unscanned."""
        assert RUNTIME_MODULE.is_file()
        assert RUNTIME_MODULE in CORE_SOURCES
        assert RUNTIME_MODULE in APP_SOURCES

    def test_the_import_scanner_finds_the_edge_this_task_creates(self) -> None:
        found = set(_atlas_imports(_source_of(OWNERSHIP_MODULE)))

        assert any(_is_within(module, "atlas.broker") for module in found), found

    def test_the_import_scanner_sees_through_a_type_checking_guard(self) -> None:
        """The ownership module takes the abstraction under such a guard."""
        guarded = (
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from atlas.risk import X"
        )

        assert list(_atlas_imports(guarded)) == ["atlas.risk"]

    def test_the_name_scanner_reads_real_identifiers(self) -> None:
        names = _referenced_names(_source_of(OWNERSHIP_MODULE))

        assert {ADAPTER, "BrokerNotConnectedError", "connect", "disconnect"} <= names

    def test_the_name_scanner_ignores_prose(self) -> None:
        assert ADAPTER not in _referenced_names(f'"""Never obtains a {ADAPTER}."""')
        assert "place_order" not in _referenced_names('"""Never calls place_order."""')

    @pytest.mark.parametrize("name", CONCRETE_ADAPTER_NAMES)
    def test_the_implementation_rule_can_actually_fire(self, name: str) -> None:
        assert name in _referenced_names(f"from atlas.broker.mock import {name}")

    @pytest.mark.parametrize("operation", UNCALLED_PORT_OPERATIONS + RUNTIME_PORT_OPERATIONS)
    def test_the_port_operation_rule_can_actually_fire(self, operation: str) -> None:
        """Both halves: a forbidden operation and a granted one are equally visible.

        A grant is only bounded if the scanner can see the granted name too. If
        it could not, the six in :data:`RUNTIME_PORT_OPERATIONS` would appear
        confined to one module by accident rather than by assertion.
        """
        assert operation in _referenced_names(f"adapter.{operation}()")

    @pytest.mark.parametrize("package", PIPELINE_PACKAGES)
    def test_the_pipeline_rule_can_actually_fire(self, package: str) -> None:
        assert list(_atlas_imports(f"from {package} import Thing")) == [package]

    @pytest.mark.parametrize("package", PIPELINE_PACKAGES)
    def test_the_pipeline_name_scanner_reports_names_and_whole_modules(self, package: str) -> None:
        assert _pipeline_names(f"from {package} import Thing", package) == {"Thing"}
        assert _pipeline_names(f"import {package}", package) == {WHOLE_MODULE}
        assert _pipeline_names("from atlas.common import Clock", package) == set()

    def test_the_module_level_binding_rule_can_actually_fire(self) -> None:
        source = f"from atlas.broker import {ADAPTER}\nADAPTER: {ADAPTER} = build()"

        assert _module_level_bindings_naming(source, ADAPTER) == [f"ADAPTER: {ADAPTER} = build()"]

    def test_the_module_level_binding_rule_ignores_a_binding_inside_a_function(self) -> None:
        source = f"def f() -> None:\n    x: {ADAPTER} = build()"

        assert _module_level_bindings_naming(source, ADAPTER) == []

    @pytest.mark.parametrize("decorator", CACHING_DECORATORS)
    def test_the_decorator_rule_can_actually_fire(self, decorator: str) -> None:
        source = f"import functools\n\n\n@functools.{decorator}\ndef f() -> None:\n    return None"

        assert decorator in _decorator_names(source)

    def test_the_broker_name_scanner_reports_a_whole_module_import(self) -> None:
        assert list(_broker_names("import atlas.broker")) == [WHOLE_MODULE]
        assert list(_broker_names(f"from atlas.broker import {ADAPTER}")) == [ADAPTER]


class TestTheScannersFireOnMutatedRealSource:
    """Proving a rule on a snippet is not proving it on the file that ships.

    Each case takes the real, passing source of an application module, splices in
    one forbidden line, and asserts the scanner now reports it.
    """

    @pytest.mark.parametrize("path", APP_SOURCES, ids=_app_id)
    def test_an_injected_pipeline_import_makes_real_source_fail(self, path: Path) -> None:
        mutated = _with_line(_source_of(path), "from atlas.risk import TradeIntent")

        assert "atlas.risk" in set(_atlas_imports(mutated))

    @pytest.mark.parametrize("path", APP_SOURCES, ids=_app_id)
    def test_an_injected_implementation_import_makes_real_source_fail(self, path: Path) -> None:
        mutated = _with_line(_source_of(path), "from atlas.broker.mock import MockBrokerAdapter")

        assert "MockBrokerAdapter" in _referenced_names(mutated)
        assert "atlas.broker.mock" in set(_atlas_imports(mutated))

    @pytest.mark.parametrize("path", APP_SOURCES, ids=_app_id)
    def test_an_injected_trading_call_makes_real_source_fail(self, path: Path) -> None:
        mutated = _with_line(_source_of(path), "adapter.place_order(request)")

        assert "place_order" in _referenced_names(mutated)

    @pytest.mark.parametrize("path", APP_SOURCES, ids=_app_id)
    def test_an_injected_module_level_adapter_makes_real_source_fail(self, path: Path) -> None:
        mutated = _with_line(_source_of(path), f"ADAPTER: {ADAPTER} = build()")

        assert _module_level_bindings_naming(mutated, ADAPTER) != []

    def test_a_guarded_port_import_is_caught_in_a_module_that_has_none(self) -> None:
        """`if TYPE_CHECKING:` is not a hiding place, asserted against real source.

        Written against the package's own `__init__.py`, which imports nothing.
        The entrypoint used to serve here and no longer can: ADR-0017 gave it a
        port import of its own, which would leave the second assertion true
        before the mutation as well as after it. The precondition is asserted
        rather than assumed, so a control that has stopped controlling anything
        fails here instead of passing quietly.
        """
        importless = CORE_SRC / "atlas" / "apps" / "core" / "__init__.py"
        source = _source_of(importless)
        assert "atlas.broker" not in set(_atlas_imports(source))

        mutated = _with_line(source, f"if TYPE_CHECKING:\n    from atlas.broker import {ADAPTER}")

        assert ADAPTER in _referenced_names(mutated)
        assert "atlas.broker" in set(_atlas_imports(mutated))


class TestOnlyTheRuntimeIsWiredToThePipeline:
    """T-10, as ADR-0019 left it.

    Owning an adapter is still not joining the flow that would use one — the
    ownership module, the composition module and the entrypoint reach no
    pipeline package, and neither does any module of any other application.
    What changed is that one module was given the flow entire, by name, and may
    take six symbols across it.
    """

    @pytest.mark.parametrize("path", APP_SOURCES, ids=_app_id)
    @pytest.mark.parametrize("package", PIPELINE_PACKAGES)
    def test_no_app_module_imports_a_pipeline_package_it_was_not_granted(
        self, path: Path, package: str
    ) -> None:
        """Widened from `atlas-core` to every application, since the grant is by module.

        Scanning only `atlas-core` would have let a second application assemble
        a pipeline of its own without failing anything here.
        """
        imported = set(_atlas_imports(_source_of(path)))
        reaches = any(_is_within(module, package) for module in imported)

        assert not reaches or _app_id(path) in _authorised_importers_of_pipeline(package), imported

    @pytest.mark.parametrize("package", PIPELINE_PACKAGES)
    def test_the_runtime_reaches_every_pipeline_package(self, package: str) -> None:
        """The positive half: the grant is used, so the rule above is not vacuous."""
        imported = set(_atlas_imports(_source_of(RUNTIME_MODULE)))

        assert any(_is_within(module, package) for module in imported), imported

    @pytest.mark.parametrize("package", PIPELINE_PACKAGES)
    def test_the_runtime_takes_only_the_granted_pipeline_names(self, package: str) -> None:
        """Six symbols, bounded per package. A seventh fails here.

        Subset rather than equality: ADR-0019 states what the runtime *may*
        take, and an implementation that needs fewer names than it was granted
        is narrower than the record, not wider than it.
        """
        taken = _pipeline_names(_source_of(RUNTIME_MODULE), package)

        assert taken <= set(PIPELINE_NAME_GRANT[package]), taken

    def test_the_pipeline_grant_is_bounded_to_one_module(self) -> None:
        granted = {
            module
            for package in PIPELINE_PACKAGES
            for module in _authorised_importers_of_pipeline(package)
        }

        assert granted == {_app_id(RUNTIME_MODULE)}

    def test_the_pipeline_grant_rule_can_actually_fire(self) -> None:
        """A seventh name in the granted module is caught, asserted on real source."""
        mutated = _with_line(_source_of(RUNTIME_MODULE), "from atlas.risk import RiskError")

        assert not _pipeline_names(mutated, "atlas.risk") <= set(PIPELINE_NAME_GRANT["atlas.risk"])


class TestThePortIsImportedOnlyWhereAuthorised:
    def test_three_modules_import_the_port_and_all_are_named(self) -> None:
        """T-11: the port itself is imported to own an adapter and to report on one.

        The port is `atlas.broker` itself. ADR-0015 added a module that reaches
        *into* that package, for `atlas.broker.mt5` and for nothing that the
        port declares, so this assertion is written against the exact module
        rather than against everything beneath it. What reaches beneath it is
        asserted separately, by name, and is four.

        ADR-0013's edge is still the only one that exists in order to *hold* an
        adapter. ADR-0017 added the second importer of the port for a different
        reason: start-up opens a session and reports whether it opened, which
        means naming the error it reports. ADR-0019 added the third for a third
        reason: a loop that absorbs a failed cycle and supervises the session
        on the next one has to name the failure it absorbs. Each grant is
        pinned to its names below, and no two of them are the same grant.
        """
        importers = {
            _app_id(path)
            for path in CORE_SOURCES
            if "atlas.broker" in set(_atlas_imports(_source_of(path)))
        }

        assert importers == {
            _app_id(OWNERSHIP_MODULE),
            _app_id(ENTRYPOINT_MODULE),
            _app_id(RUNTIME_MODULE),
        }

    def test_one_module_names_the_abstraction_and_it_is_the_same_one(self) -> None:
        """T-12: across every application, not merely across the one that owns it."""
        namers = {
            _app_id(path) for path in APP_SOURCES if ADAPTER in _referenced_names(_source_of(path))
        }

        assert namers == {_app_id(OWNERSHIP_MODULE)}

    def test_the_ownership_module_takes_three_names_from_the_port_and_no_others(self) -> None:
        """The edge is used for the abstraction, the refusal and the read, and nothing else."""
        taken = set(_broker_names(_source_of(OWNERSHIP_MODULE)))

        assert taken == {ADAPTER, "BrokerNotConnectedError", "Tick"}

    def test_the_entrypoint_takes_one_name_from_the_port_and_it_is_the_error(self) -> None:
        """ADR-0017's grant, bounded to the failure it exists to report.

        The entrypoint handles a session that would not open. It does not hold
        an adapter, refuse access to one, or name an implementation, so one name
        is all its edge is for. This is what fails if the entrypoint's import is
        ever widened to carry the abstraction across as well.
        """
        taken = set(_broker_names(_source_of(ENTRYPOINT_MODULE)))

        assert taken == {HANDLED_PORT_ERROR}

    def test_the_entrypoint_grant_does_not_extend_to_the_owners_names(self) -> None:
        """Two modules import the port; they are not interchangeable.

        Stated positively so that the boundary cannot be satisfied by a module
        that imports the port for one reason and then uses it for the other.
        """
        taken = set(_broker_names(_source_of(ENTRYPOINT_MODULE)))

        assert ADAPTER not in taken
        assert "BrokerNotConnectedError" not in taken
        assert HANDLED_PORT_ERROR not in set(_broker_names(_source_of(OWNERSHIP_MODULE)))

    def test_the_entrypoint_grant_rule_can_actually_fire(self) -> None:
        """A widened entrypoint import is caught, asserted on real source."""
        mutated = _with_line(_source_of(ENTRYPOINT_MODULE), f"from atlas.broker import {ADAPTER}")

        assert set(_broker_names(mutated)) == {HANDLED_PORT_ERROR, ADAPTER}

    def test_the_runtime_takes_one_name_from_the_port_and_it_is_the_error(self) -> None:
        """ADR-0019's port grant, bounded to the failure a cycle absorbs.

        The runtime supervises a session and submits through it, but it reaches
        the adapter through the owner rather than by typing one. So its import
        of the port is for the same single reason the entrypoint's is — naming
        the error it handles — and widening it to carry the abstraction across
        is what fails here, and in T-12.
        """
        taken = set(_broker_names(_source_of(RUNTIME_MODULE)))

        assert taken == {HANDLED_PORT_ERROR}

    def test_the_runtime_does_not_name_the_abstraction(self) -> None:
        """ADR-0019 withheld :data:`ADAPTER` deliberately, so T-12 stays at one.

        Stated here as well as in T-12 because this is the module where the
        temptation is real: a runtime that typed the adapter it supervises
        would read naturally and would move the port into a second application
        module, which is the one thing the grant does not permit.
        """
        assert ADAPTER not in _referenced_names(_source_of(RUNTIME_MODULE))


class TestTheCompositionModuleIsTheAuthorisedEdge:
    """The positive half of ADR-0015's permission: it exists, and it is one.

    The assertions in :class:`TestAnImplementationIsReachedOnlyWhereAuthorised`
    would all pass if the composition module were deleted. These are what fail
    in that case, and what fails if a second module acquires the same reach.
    """

    def test_the_composition_module_is_among_the_scanned_files(self) -> None:
        assert COMPOSITION_MODULE.is_file()
        assert COMPOSITION_MODULE in CORE_SOURCES
        assert COMPOSITION_MODULE in APP_SOURCES

    def test_four_modules_reach_the_broker_package_and_all_are_named(self) -> None:
        """Owning the port, constructing one, reporting a failure, absorbing one.

        Those are the four reasons the accepted records give, each granted to
        one named module. A fifth reacher is a decision nobody has recorded.
        """
        reachers = {
            _app_id(path)
            for path in APP_SOURCES
            if any(
                _is_within(module, "atlas.broker") for module in _atlas_imports(_source_of(path))
            )
        }

        assert reachers == {
            _app_id(OWNERSHIP_MODULE),
            _app_id(COMPOSITION_MODULE),
            _app_id(ENTRYPOINT_MODULE),
            _app_id(RUNTIME_MODULE),
        }

    def test_the_composition_module_takes_only_the_selected_implementation(self) -> None:
        """The edge is used for translation and construction, and nothing else."""
        taken = set(_broker_names(_source_of(COMPOSITION_MODULE)))

        assert taken == set(SELECTED_IMPLEMENTATION_NAMES)

    @pytest.mark.parametrize("name", SELECTED_IMPLEMENTATION_NAMES)
    def test_exactly_one_app_module_names_the_selected_implementation(self, name: str) -> None:
        namers = {
            _app_id(path) for path in APP_SOURCES if name in _referenced_names(_source_of(path))
        }

        assert namers == {_app_id(COMPOSITION_MODULE)}

    def test_the_composition_module_does_not_name_the_abstraction(self) -> None:
        """It constructs an implementation and hands it over; it never types one.

        Naming :data:`ADAPTER` here would put the port in two application
        modules, which is the property T-12 exists to hold.
        """
        assert ADAPTER not in _referenced_names(_source_of(COMPOSITION_MODULE))

    def test_the_composition_module_binds_nothing_at_module_scope_but_its_exports(self) -> None:
        assert _assigned_at_module_scope(_source_of(COMPOSITION_MODULE)) == {"__all__"}

    @pytest.mark.parametrize("decorator", CACHING_DECORATORS)
    def test_the_composition_module_caches_nothing(self, decorator: str) -> None:
        """A cached builder is importable from anywhere, which is a locator."""
        assert decorator not in _decorator_names(_source_of(COMPOSITION_MODULE))

    def test_the_authorisation_is_bounded_to_one_module(self) -> None:
        """The helpers grant the composition module and no other, for either check."""
        granted = _authorised_importers_of("atlas.broker.mt5") | _authorised_namers_of("MT5Config")

        assert granted == {_app_id(COMPOSITION_MODULE)}

    @pytest.mark.parametrize("name", UNSELECTED_IMPLEMENTATION_NAMES)
    def test_the_authorisation_does_not_extend_to_an_unselected_implementation(
        self, name: str
    ) -> None:
        """`MockBrokerAdapter` is not a fallback, in the one permitted module either."""
        assert _authorised_namers_of(name) == set()
        assert name not in _referenced_names(_source_of(COMPOSITION_MODULE))

    def test_the_authorisation_does_not_extend_to_the_mock_package(self) -> None:
        assert _authorised_importers_of("atlas.broker.mock") == set()

    def test_the_composition_edge_rule_can_actually_fire(self) -> None:
        """A second module taking the same reach is caught, asserted on real source."""
        mutated = _with_line(
            _source_of(ENTRYPOINT_MODULE),
            "from atlas.broker.mt5 import MT5BrokerAdapter",
        )

        assert "atlas.broker.mt5" in set(_atlas_imports(mutated))
        assert "MT5BrokerAdapter" in _referenced_names(mutated)


class TestAnImplementationIsReachedOnlyWhereAuthorised:
    """T-13, as ADR-0015 left it.

    ADR-0006's abstraction is still only worth having if nothing looks past it
    without authority. What changed is that one module now has that authority,
    for one implementation, granted by name in a decision record. These two
    assertions are the negative half — nothing reaches an implementation it was
    not granted. The positive half, that the grant is used and used exactly
    once, is asserted in :class:`TestTheCompositionModuleIsTheAuthorisedEdge`.
    """

    @pytest.mark.parametrize("path", APP_SOURCES, ids=_app_id)
    @pytest.mark.parametrize("package", CONCRETE_ADAPTER_PACKAGES)
    def test_no_app_module_imports_an_implementation_package_it_was_not_granted(
        self, path: Path, package: str
    ) -> None:
        imported = set(_atlas_imports(_source_of(path)))
        reaches = any(_is_within(module, package) for module in imported)

        assert not reaches or _app_id(path) in _authorised_importers_of(package), imported

    @pytest.mark.parametrize("path", APP_SOURCES, ids=_app_id)
    @pytest.mark.parametrize("name", CONCRETE_ADAPTER_NAMES)
    def test_no_app_module_names_an_implementation_it_was_not_granted(
        self, path: Path, name: str
    ) -> None:
        """Naming one is choosing one, and only one module was given the choice."""
        names_it = name in _referenced_names(_source_of(path))

        assert not names_it or _app_id(path) in _authorised_namers_of(name)


class TestOnlyTheRuntimeSupervisesOrTrades:
    """T-14, as ADR-0019 left it.

    Eight operations are named by no application module at all, and six more
    are named by exactly one. The second half is the part that would rot: a
    grant checked only by removing names from a prohibition list is a grant to
    every application at once, which is not what ADR-0019 wrote.
    """

    @pytest.mark.parametrize("path", APP_SOURCES, ids=_app_id)
    @pytest.mark.parametrize("operation", UNCALLED_PORT_OPERATIONS)
    def test_no_app_module_names_an_operation_no_record_authorises(
        self, path: Path, operation: str
    ) -> None:
        """Order lifecycle, venue-side risk and an unread measurement, still nowhere."""
        assert operation not in _referenced_names(_source_of(path))

    @pytest.mark.parametrize("path", APP_SOURCES, ids=_app_id)
    @pytest.mark.parametrize("operation", RUNTIME_PORT_OPERATIONS)
    def test_no_app_module_but_the_runtime_names_a_granted_operation(
        self, path: Path, operation: str
    ) -> None:
        """The six are permitted in one module and forbidden in every other one."""
        names_it = operation in _referenced_names(_source_of(path))

        assert not names_it or _app_id(path) in _authorised_callers_of(operation)

    def test_the_operation_grant_is_bounded_to_one_module(self) -> None:
        granted = {
            module
            for operation in RUNTIME_PORT_OPERATIONS
            for module in _authorised_callers_of(operation)
        }

        assert granted == {_app_id(RUNTIME_MODULE)}

    @pytest.mark.parametrize("operation", UNCALLED_PORT_OPERATIONS)
    def test_the_operation_grant_does_not_extend_to_a_withheld_operation(
        self, operation: str
    ) -> None:
        """Narrowing the prohibition list did not quietly authorise what stayed on it."""
        assert _authorised_callers_of(operation) == set()

    def test_the_operation_grant_rule_can_actually_fire(self) -> None:
        """A granted operation in an ungranted module is caught, on real source."""
        mutated = _with_line(_source_of(ENTRYPOINT_MODULE), "adapter.reconnect()")

        assert "reconnect" in _referenced_names(mutated)
        assert _app_id(ENTRYPOINT_MODULE) not in _authorised_callers_of("reconnect")

    def test_the_ownership_module_calls_only_the_two_lifecycle_methods(self) -> None:
        """The positive half: those two are present, so the rule above is not vacuous."""
        names = _referenced_names(_source_of(OWNERSHIP_MODULE))

        assert {"connect", "disconnect"} <= names

    def test_the_runtime_supervises_and_submits_through_the_owner(self) -> None:
        """The positive half of ADR-0019's grant: five of the six are exercised.

        The floor is asserted by name so that the module-bounded rule above
        cannot be satisfied by a runtime that supervises nothing and submits
        nothing. `health` is the sixth, and is absent — see the test below.
        """
        names = _referenced_names(_source_of(RUNTIME_MODULE))
        used = {operation for operation in RUNTIME_PORT_OPERATIONS if operation in names}

        assert used >= {"is_connected", "ping", "reconnect", "get_account", "place_order"}
        assert used <= set(RUNTIME_PORT_OPERATIONS)

    def test_the_granted_health_call_is_not_yet_exercised(self) -> None:
        """A granted permission the implementation does not need, recorded as such.

        ADR-0019 grants `health`, and the runtime calls `is_connected` and
        `ping` instead. `health` returns a richer snapshot, and acting on
        anything in it beyond what `is_connected` already reports means
        choosing a staleness threshold or a degraded-state rule — the health
        policy ADR-0019 explicitly does not define. So the grant is real and
        unexercised, which is a narrower state than the record permits rather
        than a wider one. This test exists so that condition is visible in the
        suite rather than only in a task report; a later record that defines
        the policy deletes it.
        """
        assert "health" not in _referenced_names(_source_of(RUNTIME_MODULE))


class TestOnlyTheOwnershipModuleReadsMarketData:
    """The fifth grant: ADR-0020 lets :data:`OWNERSHIP_MODULE` call ``get_tick``.

    A narrower mirror of :class:`TestOnlyTheRuntimeSupervisesOrTrades` — one
    operation and one module rather than six operations and the runtime — for
    the same reason that class exists: a grant checked only by removing a name
    from a prohibition list is a grant to every application at once.
    """

    def test_the_market_data_grant_rule_can_actually_fire(self) -> None:
        """A granted operation in an ungranted module is caught, on real source."""
        mutated = _with_line(_source_of(ENTRYPOINT_MODULE), "adapter.get_tick(symbol)")

        assert "get_tick" in _referenced_names(mutated)
        assert _app_id(ENTRYPOINT_MODULE) not in _authorised_callers_of_market_data("get_tick")


class TestTheAdapterIsHeldOnAnInstance:
    @pytest.mark.parametrize("path", APP_SOURCES, ids=_app_id)
    def test_no_module_level_assignment_binds_an_adapter(self, path: Path) -> None:
        """T-15: a process-global is importable from anywhere, which is a locator."""
        assert _module_level_bindings_naming(_source_of(path), ADAPTER) == []

    def test_the_ownership_module_binds_nothing_at_module_scope_but_its_exports(self) -> None:
        """H-2: no module-level state of any kind, cached or otherwise."""
        assert _assigned_at_module_scope(_source_of(OWNERSHIP_MODULE)) == {"__all__"}

    @pytest.mark.parametrize("decorator", CACHING_DECORATORS)
    def test_the_ownership_module_caches_nothing(self, decorator: str) -> None:
        """H-2: the `get_settings` precedent is deliberately not followed."""
        assert decorator not in _decorator_names(_source_of(OWNERSHIP_MODULE))

    def test_the_runtime_binds_nothing_at_module_scope_but_its_exports(self) -> None:
        """The module that holds a session for a process lifetime holds none of it.

        A runtime keeps the longest-lived state in the application, which makes
        it the likeliest place for that state to escape into a module global
        where anything could import it.
        """
        assert _assigned_at_module_scope(_source_of(RUNTIME_MODULE)) == {"__all__"}

    @pytest.mark.parametrize("decorator", CACHING_DECORATORS)
    def test_the_runtime_caches_nothing(self, decorator: str) -> None:
        """A cached runtime factory is a process-wide singleton by another name."""
        assert decorator not in _decorator_names(_source_of(RUNTIME_MODULE))


class TestThisFileIsNotAnApplicationImportRule:
    """§14.2, and stop condition 4: the undecided rule does not begin in a test file."""

    def test_this_file_declares_no_allowlist(self) -> None:
        bound = _assigned_at_module_scope(_source_of(Path(__file__).resolve()))

        assert not [name for name in bound if name.startswith("PERMITTED")], bound

    def test_this_file_states_five_bounded_permissions_and_nothing_wider(self) -> None:
        """Every constant here is an exclusion, a scanning aid, or one of five grants.

        The first grant is :data:`SELECTED_IMPLEMENTATION_NAMES`, bounded by
        :data:`COMPOSITION_MODULE`: one implementation, one module, one record.
        The second is :data:`HANDLED_PORT_ERROR`, bounded by
        :data:`ENTRYPOINT_MODULE`: one name, one module, one record. ADR-0019
        added the third and fourth, both bounded by :data:`RUNTIME_MODULE`:
        :data:`PIPELINE_NAME_GRANT`, six symbols across three packages, and
        :data:`RUNTIME_PORT_OPERATIONS`, six operations on the port. ADR-0020
        added the fifth, bounded by :data:`OWNERSHIP_MODULE`:
        :data:`MARKET_DATA_PORT_OPERATIONS`, one operation on the port.

        Pinning the whole set is what makes a wider grant impossible to add
        quietly — a new constant fails here before it can permit anything, and
        that is exactly what happened to the two ADR-0019 needed. A grant
        written inside a helper function instead would have slipped past this
        test, which is the reason both are stated at module scope where a
        reviewer reads them next to the records that authorise them.
        """
        bound = _assigned_at_module_scope(_source_of(Path(__file__).resolve()))

        assert bound == {
            "REPO_ROOT",
            "APPS_ROOT",
            "CORE_SRC",
            "APP_SOURCES",
            "CORE_SOURCES",
            "OWNERSHIP_MODULE",
            "COMPOSITION_MODULE",
            "ENTRYPOINT_MODULE",
            "RUNTIME_MODULE",
            "ADAPTER",
            "HANDLED_PORT_ERROR",
            "MARKET_DATA_PORT_OPERATIONS",
            "PIPELINE_PACKAGES",
            "PIPELINE_NAME_GRANT",
            "CONCRETE_ADAPTER_PACKAGES",
            "SELECTED_IMPLEMENTATION_NAMES",
            "UNSELECTED_IMPLEMENTATION_NAMES",
            "CONCRETE_ADAPTER_NAMES",
            "UNCALLED_PORT_OPERATIONS",
            "RUNTIME_PORT_OPERATIONS",
            "CACHING_DECORATORS",
            "WHOLE_MODULE",
            "pytestmark",
        }
