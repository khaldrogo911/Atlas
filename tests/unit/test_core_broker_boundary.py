"""Structural tests for the one edge ATLAS-TASK-0020 creates.

ADR-0013 puts the `BrokerAdapter` in `apps/atlas-core`, which makes
`apps/atlas-core -> atlas.broker` the first edge from an application to the
port. These tests hold that edge to the shape the decision gave it: one module
reaches the port, it reaches it for the abstraction and not for an
implementation, and holding the adapter did not turn into supervising it or
trading through it.

**This file is not an `apps/` import rule, and must not become one.** The four
package boundary tests each hold a closed `PERMITTED_ATLAS_PACKAGES` tuple — a
positive statement of everything that package may import. There is no such tuple
here, nothing is permitted by this file, and no claim is made about what an
application may import in general. That rule is undecided; ADR-0013 `:242-249`
records that it creates and implies none, and it would begin with a decision
record rather than with a test file. Every assertion below is instead a property
this task creates, each traceable to a decision already accepted: ADR-0006's
abstraction, and ADR-0013's single owner, downward-granted access and exclusion
of supervision.

What these tests deliberately do **not** claim
    That the adapter is used correctly. Nothing in the repository hands one to
    an owner, because the settings a live adapter would be built from do not
    exist and choosing an implementation without them is the decision this task
    declines to make. What is asserted here is the shape of the seam, not
    traffic across it — there is none.
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

#: The module ATLAS-TASK-0020 adds, and the sole holder of the new edge.
OWNERSHIP_MODULE: Final = CORE_SRC / "atlas" / "apps" / "core" / "broker_ownership.py"

#: The abstraction the edge exists for.
ADAPTER: Final = "BrokerAdapter"

#: Packages `apps/atlas-core` does not reach, and why each would be wrong.
#:
#: These are the pipeline: a proposal, a verdict on it, and the request built
#: from that verdict. ATLAS-TASK-0020 owns an adapter and wires nothing to it, so
#: a module here naming any of them would mean the owner had been joined to a
#: pipeline that no accepted decision has assembled.
PIPELINE_PACKAGES: Final = ("atlas.strategy", "atlas.risk", "atlas.execution")

#: Sub-packages that contain an implementation of the port rather than the port.
CONCRETE_ADAPTER_PACKAGES: Final = ("atlas.broker.mock", "atlas.broker.mt5")

#: Names that would mean an application had chosen an implementation.
#:
#: ADR-0006 shipped the mock so that a caller cannot tell which adapter it holds.
#: An application that names one has made the selection decision — and the
#: entrypoint has no configuration with which to make it. `BaseBrokerAdapter` is
#: included because inheriting from the base, or naming it, is reaching past the
#: port to the shared implementation underneath.
CONCRETE_ADAPTER_NAMES: Final = (
    "MockBrokerAdapter",
    "MT5BrokerAdapter",
    "MockVenue",
    "MT5Config",
    "BaseBrokerAdapter",
)

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
        """`if TYPE_CHECKING:` is not a hiding place, asserted against real source."""
        entrypoint = CORE_SRC / "atlas" / "apps" / "core" / "__main__.py"
        mutated = _with_line(
            _source_of(entrypoint),
            f"if TYPE_CHECKING:\n    from atlas.broker import {ADAPTER}",
        )

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


class TestExactlyOneModuleReachesThePort:
    def test_one_module_imports_the_port_and_it_is_the_ownership_module(self) -> None:
        """T-11: the edge ADR-0013 authorises exists once, where the owner lives."""
        importers = {
            _app_id(path)
            for path in CORE_SOURCES
            if any(
                _is_within(module, "atlas.broker") for module in _atlas_imports(_source_of(path))
            )
        }

        assert importers == {_app_id(OWNERSHIP_MODULE)}

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


class TestNoApplicationNamesAnImplementation:
    @pytest.mark.parametrize("path", APP_SOURCES, ids=_app_id)
    @pytest.mark.parametrize("package", CONCRETE_ADAPTER_PACKAGES)
    def test_no_app_module_imports_an_implementation_package(
        self, path: Path, package: str
    ) -> None:
        """T-13: ADR-0006's abstraction is only worth having if nothing looks past it."""
        imported = set(_atlas_imports(_source_of(path)))

        assert not any(_is_within(module, package) for module in imported), imported

    @pytest.mark.parametrize("path", APP_SOURCES, ids=_app_id)
    @pytest.mark.parametrize("name", CONCRETE_ADAPTER_NAMES)
    def test_no_app_module_names_an_implementation(self, path: Path, name: str) -> None:
        """T-13: naming one is choosing one, and nothing here has the means to choose."""
        assert name not in _referenced_names(_source_of(path))


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

    def test_this_file_states_no_positive_permission_for_an_application(self) -> None:
        """Every constant here names something excluded, or something to scan with."""
        bound = _assigned_at_module_scope(_source_of(Path(__file__).resolve()))

        assert bound == {
            "REPO_ROOT",
            "APPS_ROOT",
            "CORE_SRC",
            "APP_SOURCES",
            "CORE_SOURCES",
            "OWNERSHIP_MODULE",
            "ADAPTER",
            "PIPELINE_PACKAGES",
            "CONCRETE_ADAPTER_PACKAGES",
            "CONCRETE_ADAPTER_NAMES",
            "UNCALLED_PORT_OPERATIONS",
            "CACHING_DECORATORS",
            "WHOLE_MODULE",
            "pytestmark",
        }
