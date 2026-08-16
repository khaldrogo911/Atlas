"""Structural tests for the three edges `apps/atlas-core` has to the broker.

ADR-0013 puts the `BrokerAdapter` in `apps/atlas-core`, which made
`apps/atlas-core -> atlas.broker` the first edge from an application to the
port. ADR-0015 added the second: `composition.py` reaches past the port to the
implementation it selected, in order to translate settings into it and build
one. ADR-0017 added the third: start-up opens a session and reports whether it
opened, so `__main__.py` names the one error it has to handle. These tests hold
all three edges to the shape their decisions gave them: the port is imported by
the module that owns an adapter and by the one that reports a failure to reach
a venue, the implementation is named by the module that constructs one, and
holding an adapter still did not turn into supervising it or trading through it.

**This file is not an `apps/` import rule, and must not become one.** The four
package boundary tests each hold a closed `PERMITTED_ATLAS_PACKAGES` tuple — a
positive statement of everything that package may import. There is no such tuple
here. Exactly two permissions are stated below, both named and both traceable:
ADR-0015 selected `MT5BrokerAdapter`, and one module may name that
implementation and its configuration type for the one purpose the record gave
it; ADR-0017 decided that start-up reports a session it could not open, and one
module may name `BrokerError` for that. Each extends to no other module, to no
other name, and to no claim about what an application may import in general.
That general rule is still undecided — ADR-0013 `:242-249` records that it
creates and implies none, and ADR-0015 leaves it exactly there. It would begin
with a decision record rather than with a test file, which is precisely how both
permissions here began.

Every other assertion is a property some accepted decision creates: ADR-0006's
abstraction, ADR-0013's single owner, downward-granted access and exclusion of
supervision, ADR-0015's bounded selection, and ADR-0017's bounded error handling.

What these tests deliberately do **not** claim
    That the adapter is used correctly. ATLAS-TASK-0023 builds one and hands it
    to an owner, and ADR-0017 has start-up open a session and close it again;
    nothing supervises that session, and nothing consumes what the owner holds.
    What is asserted here is the shape of the seam, not traffic across it —
    there is still none beyond connecting and disconnecting.
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

#: Packages `apps/atlas-core` does not reach, and why each would be wrong.
#:
#: These are the pipeline: a proposal, a verdict on it, and the request built
#: from that verdict. ATLAS-TASK-0020 owns an adapter and wires nothing to it, so
#: a module here naming any of them would mean the owner had been joined to a
#: pipeline that no accepted decision has assembled.
PIPELINE_PACKAGES: Final = ("atlas.strategy", "atlas.risk", "atlas.execution")

#: Sub-packages that contain an implementation of the port rather than the port.
CONCRETE_ADAPTER_PACKAGES: Final = ("atlas.broker.mock", "atlas.broker.mt5")

#: The implementation ADR-0015 selected, and the configuration type it is built
#: from. Nameable in :data:`COMPOSITION_MODULE`, for translation and
#: construction, and nowhere else under `apps/`.
SELECTED_IMPLEMENTATION_NAMES: Final = ("MT5BrokerAdapter", "MT5Config")

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

#: Port methods an owner does not call, and each one's reason.
#:
#: `reconnect` and `health` are the supervision surface: deciding when to
#: re-establish a session, and on what evidence, is the duty ADR-0013 `:84-86`
#: assigns to the owner and this task defers. `ping`, `latency` and
#: `is_connected` are the polling that a supervision loop would do. The rest are
#: trading and account state, which belong to a consumer that does not exist.
UNCALLED_PORT_OPERATIONS: Final = (
    "reconnect",
    "health",
    "ping",
    "latency",
    "is_connected",
    "place_order",
    "modify_order",
    "cancel_order",
    "close_position",
    "get_account",
    "get_positions",
    "margin_required",
    "margin_available",
    "can_trade",
)

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

    @pytest.mark.parametrize("operation", UNCALLED_PORT_OPERATIONS)
    def test_the_port_operation_rule_can_actually_fire(self, operation: str) -> None:
        assert operation in _referenced_names(f"adapter.{operation}()")

    @pytest.mark.parametrize("package", PIPELINE_PACKAGES)
    def test_the_pipeline_rule_can_actually_fire(self, package: str) -> None:
        assert list(_atlas_imports(f"from {package} import Thing")) == [package]

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


class TestTheOwnerIsNotWiredToAPipeline:
    @pytest.mark.parametrize("path", CORE_SOURCES, ids=_app_id)
    @pytest.mark.parametrize("package", PIPELINE_PACKAGES)
    def test_no_atlas_core_module_imports_a_pipeline_package(
        self, path: Path, package: str
    ) -> None:
        """T-10: owning an adapter is not joining the flow that would use one."""
        imported = set(_atlas_imports(_source_of(path)))

        assert not any(_is_within(module, package) for module in imported), imported


class TestThePortIsImportedOnlyWhereAuthorised:
    def test_two_modules_import_the_port_and_both_are_named(self) -> None:
        """T-11: the port itself is imported to own an adapter and to report on one.

        The port is `atlas.broker` itself. ADR-0015 added a module that reaches
        *into* that package, for `atlas.broker.mt5` and for nothing that the
        port declares, so this assertion is written against the exact module
        rather than against everything beneath it. What reaches beneath it is
        asserted separately, by name, and is three.

        ADR-0013's edge is still the only one that exists in order to *hold* an
        adapter. ADR-0017 added the second importer of the port for a different
        reason: start-up opens a session and reports whether it opened, which
        means naming the error it reports. That is the whole of the grant, and
        the assertion below pins it to one name.
        """
        importers = {
            _app_id(path)
            for path in CORE_SOURCES
            if "atlas.broker" in set(_atlas_imports(_source_of(path)))
        }

        assert importers == {_app_id(OWNERSHIP_MODULE), _app_id(ENTRYPOINT_MODULE)}

    def test_one_module_names_the_abstraction_and_it_is_the_same_one(self) -> None:
        """T-12: across every application, not merely across the one that owns it."""
        namers = {
            _app_id(path) for path in APP_SOURCES if ADAPTER in _referenced_names(_source_of(path))
        }

        assert namers == {_app_id(OWNERSHIP_MODULE)}

    def test_the_ownership_module_takes_two_names_from_the_port_and_no_others(self) -> None:
        """The edge is used for the abstraction and the refusal, and nothing else."""
        taken = set(_broker_names(_source_of(OWNERSHIP_MODULE)))

        assert taken == {ADAPTER, "BrokerNotConnectedError"}

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

    def test_three_modules_reach_the_broker_package_and_all_are_named(self) -> None:
        """Owning the port, constructing an implementation, reporting a failure.

        Those are the three reasons any accepted record gives, each granted to
        one named module. A fourth reacher is a decision nobody has recorded.
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


class TestNoApplicationSupervisesOrTrades:
    @pytest.mark.parametrize("path", APP_SOURCES, ids=_app_id)
    @pytest.mark.parametrize("operation", UNCALLED_PORT_OPERATIONS)
    def test_no_app_module_names_an_operation_the_owner_does_not_call(
        self, path: Path, operation: str
    ) -> None:
        """T-14: the owner connects and disconnects; everything else is someone else's."""
        assert operation not in _referenced_names(_source_of(path))

    def test_the_ownership_module_calls_only_the_two_lifecycle_methods(self) -> None:
        """The positive half: those two are present, so the rule above is not vacuous."""
        names = _referenced_names(_source_of(OWNERSHIP_MODULE))

        assert {"connect", "disconnect"} <= names


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


class TestThisFileIsNotAnApplicationImportRule:
    """§14.2, and stop condition 4: the undecided rule does not begin in a test file."""

    def test_this_file_declares_no_allowlist(self) -> None:
        bound = _assigned_at_module_scope(_source_of(Path(__file__).resolve()))

        assert not [name for name in bound if name.startswith("PERMITTED")], bound

    def test_this_file_states_two_bounded_permissions_and_nothing_wider(self) -> None:
        """Every constant here is an exclusion, a scanning aid, or one of two grants.

        The first grant is :data:`SELECTED_IMPLEMENTATION_NAMES`, bounded by
        :data:`COMPOSITION_MODULE`: one implementation, one module, one record.
        The second is :data:`HANDLED_PORT_ERROR`, bounded by
        :data:`ENTRYPOINT_MODULE`: one name, one module, one record. Pinning the
        whole set is what makes a wider grant impossible to add quietly — a new
        constant fails here before it can permit anything.
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
            "ADAPTER",
            "HANDLED_PORT_ERROR",
            "PIPELINE_PACKAGES",
            "CONCRETE_ADAPTER_PACKAGES",
            "SELECTED_IMPLEMENTATION_NAMES",
            "UNSELECTED_IMPLEMENTATION_NAMES",
            "CONCRETE_ADAPTER_NAMES",
            "UNCALLED_PORT_OPERATIONS",
            "CACHING_DECORATORS",
            "WHOLE_MODULE",
            "pytestmark",
        }
