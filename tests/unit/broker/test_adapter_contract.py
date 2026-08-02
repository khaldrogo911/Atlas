"""Contract tests for the BrokerAdapter port.

The port has no behaviour to test — that is the point of it. What can be
tested, and what matters, is that it stays a contract: abstract, complete,
documented, free of implementation, and unaware of any particular venue.

The method inventory below is a direct transcription of the architect's
specification, so the test is the spec rather than a restatement of whatever
the source happens to contain.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

from atlas.broker import BrokerAdapter
from atlas.broker import adapter as adapter_module

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.unit

ADAPTER_PATH = Path(inspect.getfile(adapter_module))
PACKAGE_DIR = ADAPTER_PATH.parent
PORT_SOURCES = (
    PACKAGE_DIR / "adapter.py",
    PACKAGE_DIR / "protocols.py",
    PACKAGE_DIR / "types.py",
)

MANDATED_METHODS: Final[dict[str, tuple[str, ...]]] = {
    "lifecycle": ("connect", "disconnect", "reconnect", "is_connected", "health"),
    "market_data": (
        "get_symbols",
        "get_symbol",
        "get_tick",
        "get_ticks",
        "get_candle",
        "get_candles",
        "get_historical_data",
        "subscribe_ticks",
        "unsubscribe_ticks",
        "subscribe_candles",
        "unsubscribe_candles",
    ),
    "trading": ("place_order", "modify_order", "cancel_order", "close_position"),
    "account": ("get_account", "get_positions", "get_orders", "get_open_positions"),
    "risk": ("margin_required", "margin_available", "can_trade"),
    "diagnostics": ("ping", "latency", "server_time", "version"),
}

ALL_MANDATED: Final = tuple(name for group in MANDATED_METHODS.values() for name in group)

# Captured from the source, then frozen. Changing any of these is a breaking
# change to every adapter and every caller, so it must be a deliberate edit to
# this table rather than a side effect of editing the port.
PINNED_SIGNATURES: Final[dict[str, str]] = {
    "can_trade": "(self, symbol: 'SymbolName') -> 'bool'",
    "cancel_order": "(self, order_id: 'OrderID') -> 'Order'",
    "close_position": (
        "(self, position_id: 'PositionID', volume: 'Volume | None' = None) -> 'Execution'"
    ),
    "connect": "(self) -> 'Connection'",
    "disconnect": "(self) -> 'None'",
    "get_account": "(self) -> 'Account'",
    "get_candle": (
        "(self, symbol: 'SymbolName', timeframe: 'Timeframe', *, "
        "include_forming: 'bool' = False) -> 'Candle'"
    ),
    "get_candles": (
        "(self, symbol: 'SymbolName', timeframe: 'Timeframe', count: 'int') -> 'Sequence[Candle]'"
    ),
    "get_historical_data": (
        "(self, symbol: 'SymbolName', timeframe: 'Timeframe', start: 'Timestamp', "
        "end: 'Timestamp | None' = None) -> 'Sequence[Candle]'"
    ),
    "get_open_positions": "(self) -> 'Sequence[Position]'",
    "get_orders": "(self, symbol: 'SymbolName | None' = None) -> 'Sequence[Order]'",
    "get_positions": "(self, symbol: 'SymbolName | None' = None) -> 'Sequence[Position]'",
    "get_symbol": "(self, symbol: 'SymbolName') -> 'Symbol'",
    "get_symbols": "(self) -> 'Sequence[Symbol]'",
    "get_tick": "(self, symbol: 'SymbolName') -> 'Tick'",
    "get_ticks": "(self, symbols: 'Sequence[SymbolName]') -> 'Mapping[SymbolName, Tick]'",
    "health": "(self) -> 'Connection'",
    "is_connected": "(self) -> 'bool'",
    "latency": "(self) -> 'LatencyMilliseconds'",
    "margin_available": "(self) -> 'Money'",
    "margin_required": (
        "(self, symbol: 'SymbolName', side: 'OrderSide', volume: 'Volume', "
        "price: 'Price | None' = None) -> 'NonNegativeMoney'"
    ),
    "modify_order": (
        "(self, order_id: 'OrderID', *, price: 'Price | Unset | None' = UNSET, "
        "stop_price: 'Price | Unset | None' = UNSET, "
        "stop_loss: 'Price | Unset | None' = UNSET, "
        "take_profit: 'Price | Unset | None' = UNSET, "
        "volume: 'Volume | Unset' = UNSET) -> 'Order'"
    ),
    "ping": "(self) -> 'bool'",
    "place_order": "(self, request: 'OrderRequest') -> 'Order'",
    "reconnect": "(self) -> 'Connection'",
    "server_time": "(self) -> 'Timestamp'",
    "subscribe_candles": (
        "(self, symbols: 'Sequence[SymbolName]', timeframe: 'Timeframe', "
        "handler: 'CandleHandler') -> 'SubscriptionID'"
    ),
    "subscribe_ticks": (
        "(self, symbols: 'Sequence[SymbolName]', handler: 'TickHandler') -> 'SubscriptionID'"
    ),
    "unsubscribe_candles": "(self, subscription_id: 'SubscriptionID') -> 'None'",
    "unsubscribe_ticks": "(self, subscription_id: 'SubscriptionID') -> 'None'",
    "version": "(self) -> 'BrokerVersion'",
}

# Referenced by the port's docstrings, delivered by a later task. The port must
# not name an exception that is not in this plan.
PLANNED_EXCEPTIONS: Final = frozenset(
    {
        "BrokerError",
        "BrokerConnectionError",
        "BrokerNotConnectedError",
        "BrokerTimeoutError",
        "BrokerAuthenticationError",
        "BrokerRequestError",
        "BrokerSymbolNotFoundError",
        "BrokerOrderNotFoundError",
        "BrokerPositionNotFoundError",
        "BrokerOrderRejectedError",
        "BrokerInsufficientMarginError",
        "BrokerDataUnavailableError",
        "BrokerUnsupportedOperationError",
    }
)

#: Raised by an implementation for an argument that is wrong before the venue
#: is involved, so it is permitted alongside the planned hierarchy.
PERMITTED_BUILTIN_EXCEPTIONS: Final = frozenset({"ValueError"})

_EXCEPTION_NAME = re.compile(r"\b([A-Z]\w*Error)\b")

PERMITTED_IMPORT_ROOTS: Final = frozenset(
    {"__future__", "abc", "collections", "enum", "typing", "pydantic", "atlas"}
)

FORBIDDEN_IMPORT_ROOTS: Final = frozenset(
    {
        "MetaTrader5",
        "mt5",
        "ccxt",
        "ib_insync",
        "oandapyV20",
        "requests",
        "httpx",
        "aiohttp",
        "socket",
        "asyncio",
        "sqlalchemy",
        "psycopg",
        "redis",
    }
)

# Venue names that must never appear in the port's source. The port is
# vendor-neutral; naming one in a signature or a default is how that stops
# being true. Prose in a docstring is excluded below.
VENDOR_TOKENS: Final = ("MetaTrader5", "mt5", "MqlTick", "MqlTradeRequest", "oanda", "ib_insync")


def _imported_roots(path: Path) -> Iterator[str]:
    """Yield the top-level module of every import in a source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            yield node.module.split(".")[0]


def _port_class_node() -> ast.ClassDef:
    """Return the AST of the BrokerAdapter class body."""
    tree = ast.parse(ADAPTER_PATH.read_text(encoding="utf-8"), filename=str(ADAPTER_PATH))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "BrokerAdapter":
            return node
    pytest.fail("BrokerAdapter class not found in adapter.py")


def _method_nodes() -> list[ast.FunctionDef]:
    return [node for node in _port_class_node().body if isinstance(node, ast.FunctionDef)]


METHOD_NODES: Final = _method_nodes()


def _docstring_of(name: str) -> str:
    doc: str | None = getattr(BrokerAdapter, name).__doc__
    assert doc is not None, f"{name} has no docstring"
    return doc


def _noop(self: BrokerAdapter, *args: object, **kwargs: object) -> None:
    """Stand in for an abstract method so the class can be instantiated."""


def _complete_implementation() -> type[BrokerAdapter]:
    """Build a subclass that overrides every abstract method and nothing else."""
    body: dict[str, object] = dict.fromkeys(BrokerAdapter.__abstractmethods__, _noop)
    body["__doc__"] = "Structural stand-in used to prove the abstract set is satisfiable."
    return type("CompleteImplementation", (BrokerAdapter,), body)


class TestAbstractness:
    def test_the_port_is_abstract(self) -> None:
        assert inspect.isabstract(BrokerAdapter)

    def test_the_port_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            BrokerAdapter()  # type: ignore[abstract]

    def test_a_partial_implementation_cannot_be_instantiated(self) -> None:
        # Without this, `isabstract` could pass on a class whose methods were
        # not actually registered as abstract.
        partial = type("PartialAdapter", (BrokerAdapter,), {"connect": _noop})

        with pytest.raises(TypeError, match="abstract"):
            partial()

    def test_a_complete_implementation_can_be_instantiated(self) -> None:
        # Proves the abstract set is satisfiable and that nothing else in the
        # port blocks construction.
        assert _complete_implementation()() is not None

    @pytest.mark.parametrize("name", ALL_MANDATED)
    def test_every_method_is_abstract(self, name: str) -> None:
        assert getattr(BrokerAdapter, name).__isabstractmethod__

    def test_the_port_defines_no_concrete_method(self) -> None:
        concrete = [
            node.name
            for node in METHOD_NODES
            if not any(
                isinstance(decorator, ast.Name) and decorator.id == "abstractmethod"
                for decorator in node.decorator_list
            )
        ]

        assert not concrete, f"the port must be pure contract, found: {concrete}"


class TestMethodInventory:
    @pytest.mark.parametrize("name", ALL_MANDATED)
    def test_the_mandated_method_exists(self, name: str) -> None:
        assert callable(getattr(BrokerAdapter, name, None))

    def test_the_abstract_set_is_exactly_the_mandated_set(self) -> None:
        # Catches a method quietly added to the port as well as one dropped.
        assert BrokerAdapter.__abstractmethods__ == frozenset(ALL_MANDATED)

    def test_the_mandated_list_has_no_duplicates(self) -> None:
        assert len(ALL_MANDATED) == len(set(ALL_MANDATED))

    def test_the_port_exposes_no_other_public_surface(self) -> None:
        public = {
            name
            for name in vars(BrokerAdapter)
            if not name.startswith("_") and callable(getattr(BrokerAdapter, name))
        }

        assert public == set(ALL_MANDATED)


class TestSignatureStability:
    def test_every_mandated_method_is_pinned(self) -> None:
        # A method added to the port without a pin would otherwise be free to
        # change shape forever.
        assert set(PINNED_SIGNATURES) == set(ALL_MANDATED)

    @pytest.mark.parametrize("name", ALL_MANDATED)
    def test_the_signature_matches_its_pin(self, name: str) -> None:
        assert str(inspect.signature(getattr(BrokerAdapter, name))) == PINNED_SIGNATURES[name]

    @pytest.mark.parametrize("name", ALL_MANDATED)
    def test_the_return_type_is_declared(self, name: str) -> None:
        annotation = inspect.signature(getattr(BrokerAdapter, name)).return_annotation

        assert annotation is not inspect.Signature.empty
        assert annotation

    @pytest.mark.parametrize("name", ALL_MANDATED)
    def test_every_parameter_is_annotated(self, name: str) -> None:
        parameters = inspect.signature(getattr(BrokerAdapter, name)).parameters
        unannotated = [
            parameter.name
            for parameter in parameters.values()
            if parameter.name != "self" and parameter.annotation is inspect.Parameter.empty
        ]

        assert not unannotated, f"{name} has unannotated parameters: {unannotated}"


class TestReturnTypes:
    @pytest.mark.parametrize("name", ALL_MANDATED)
    def test_the_return_type_is_never_any(self, name: str) -> None:
        annotation = str(inspect.signature(getattr(BrokerAdapter, name)).return_annotation)

        assert "Any" not in annotation

    @pytest.mark.parametrize("name", ALL_MANDATED)
    def test_the_return_type_is_never_a_bare_container(self, name: str) -> None:
        # `dict` and `list` as return types are how a typed contract decays
        # into a bag of strings. Read-only Mapping/Sequence are the contract.
        annotation = str(inspect.signature(getattr(BrokerAdapter, name)).return_annotation)

        assert not annotation.startswith(("dict", "list", "tuple", "set"))

    @pytest.mark.parametrize("name", ALL_MANDATED)
    def test_no_signature_names_a_vendor_type(self, name: str) -> None:
        signature = str(inspect.signature(getattr(BrokerAdapter, name))).lower()
        offenders = [token for token in VENDOR_TOKENS if token.lower() in signature]

        assert not offenders, f"{name} leaks a vendor type: {offenders}"


class TestDocumentation:
    @pytest.mark.parametrize("name", ALL_MANDATED)
    def test_the_method_documents_its_return(self, name: str) -> None:
        assert "Returns:" in _docstring_of(name)

    @pytest.mark.parametrize("name", ALL_MANDATED)
    def test_the_method_documents_what_it_raises(self, name: str) -> None:
        assert "Raises:" in _docstring_of(name)

    @pytest.mark.parametrize("name", ALL_MANDATED)
    def test_the_method_carries_notes(self, name: str) -> None:
        assert "Notes:" in _docstring_of(name)

    @pytest.mark.parametrize("name", ALL_MANDATED)
    def test_the_method_documents_its_arguments(self, name: str) -> None:
        parameters = [
            parameter
            for parameter in inspect.signature(getattr(BrokerAdapter, name)).parameters
            if parameter != "self"
        ]
        docstring = _docstring_of(name)

        if not parameters:
            assert "Args:" not in docstring, f"{name} takes no arguments but documents some"
            return
        assert "Args:" in docstring
        for parameter in parameters:
            assert f"{parameter}:" in docstring, f"{name} does not document {parameter}"

    def test_the_port_is_documented(self) -> None:
        assert adapter_module.__doc__
        assert BrokerAdapter.__doc__

    def test_the_package_ships_a_readme(self) -> None:
        readme = PACKAGE_DIR / "README.md"

        assert readme.is_file()
        assert readme.read_text(encoding="utf-8").strip()


class TestPlannedExceptionHierarchy:
    def test_the_exception_extractor_can_fire(self) -> None:
        # A scanner that matches nothing would pass every test below while
        # reading no contract at all.
        assert _EXCEPTION_NAME.findall(_docstring_of("connect"))

    @pytest.mark.parametrize("name", ALL_MANDATED)
    def test_only_planned_exceptions_are_named(self, name: str) -> None:
        named = set(_EXCEPTION_NAME.findall(_docstring_of(name)))
        unplanned = named - PLANNED_EXCEPTIONS - PERMITTED_BUILTIN_EXCEPTIONS

        assert not unplanned, f"{name} documents unplanned exceptions: {sorted(unplanned)}"

    @pytest.mark.parametrize("planned", sorted(PLANNED_EXCEPTIONS))
    def test_the_hierarchy_is_written_down(self, planned: str) -> None:
        assert adapter_module.__doc__ is not None
        assert planned in adapter_module.__doc__

    def test_the_port_implements_no_exception_class(self) -> None:
        # The hierarchy is referenced, not defined: it belongs to a later task,
        # and an exception defined here would be one the port could not raise.
        tree = ast.parse(ADAPTER_PATH.read_text(encoding="utf-8"))
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

        assert classes == ["BrokerAdapter"]


class TestZeroImplementation:
    @pytest.mark.parametrize("node", METHOD_NODES, ids=lambda node: node.name)
    def test_the_method_body_is_only_a_docstring(self, node: ast.FunctionDef) -> None:
        # The strongest available reading of "no implementation logic": the
        # body must contain no statement other than the docstring itself.
        assert len(node.body) == 1, f"{node.name} has {len(node.body)} statements in its body"
        statement = node.body[0]
        assert isinstance(statement, ast.Expr)
        assert isinstance(statement.value, ast.Constant)
        assert isinstance(statement.value.value, str)

    def test_the_body_scanner_covers_every_method(self) -> None:
        assert {node.name for node in METHOD_NODES} == set(ALL_MANDATED)

    def test_the_module_defines_no_module_level_logic(self) -> None:
        tree = ast.parse(ADAPTER_PATH.read_text(encoding="utf-8"))
        permitted = (ast.Expr, ast.ImportFrom, ast.Import, ast.If, ast.ClassDef, ast.Assign)
        offenders = [type(node).__name__ for node in tree.body if not isinstance(node, permitted)]

        assert not offenders, f"unexpected module-level statements: {offenders}"


class TestBrokerIndependence:
    """The port must not acquire a dependency on any venue or transport."""

    def test_the_import_scanner_finds_something(self) -> None:
        assert PORT_SOURCES
        found = {root for path in PORT_SOURCES for root in _imported_roots(path)}
        assert "atlas" in found

    @pytest.mark.parametrize("path", PORT_SOURCES, ids=lambda path: path.name)
    def test_the_source_file_exists(self, path: Path) -> None:
        assert path.is_file()

    @pytest.mark.parametrize("path", PORT_SOURCES, ids=lambda path: path.name)
    def test_no_module_imports_outside_the_permitted_set(self, path: Path) -> None:
        offenders = sorted(set(_imported_roots(path)) - PERMITTED_IMPORT_ROOTS)

        assert not offenders, f"{path.name} imports {offenders}"

    @pytest.mark.parametrize("path", PORT_SOURCES, ids=lambda path: path.name)
    def test_no_module_imports_a_broker_sdk_or_transport(self, path: Path) -> None:
        offenders = sorted(set(_imported_roots(path)) & FORBIDDEN_IMPORT_ROOTS)

        assert not offenders, f"{path.name} imports {offenders}"

    @pytest.mark.parametrize("path", PORT_SOURCES, ids=lambda path: path.name)
    def test_no_module_depends_on_another_atlas_package(self, path: Path) -> None:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        atlas_imports = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.startswith("atlas")
        ]

        for module in atlas_imports:
            assert module.startswith("atlas.broker"), f"{path.name} imports {module}"

    def test_the_permitted_and_forbidden_sets_do_not_overlap(self) -> None:
        assert not (PERMITTED_IMPORT_ROOTS & FORBIDDEN_IMPORT_ROOTS)
