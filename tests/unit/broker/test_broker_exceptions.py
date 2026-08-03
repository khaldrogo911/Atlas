"""Unit tests for the broker exception hierarchy.

An exception class has no behaviour worth testing; what it has is a *shape*,
and the shape is the contract. Three things are checked here, and each of them
fails silently in production if it stops being true.

The **tree** decides what a caller catches. ``except BrokerConnectionError``
must catch a timeout and must not catch a rejected login, because a supervision
loop retries the first and cannot fix the second. The parentage is transcribed
below from the port's own documentation rather than read off the classes, so a
class reparented by accident fails here instead of quietly widening a retry
loop.

The **context** decides what a caller can act on. Detail lives in attributes,
so a sizing layer reads ``error.required`` rather than parsing a sentence that
a later edit may reword.

The **replacement** is what ATLAS-TASK-0005 was for. The MetaTrader 5 adapter
carried eight temporary ``MT5*Error`` classes; those are gone, and the scans at
the bottom of this file are what stop a ninth appearing.
"""

from __future__ import annotations

import ast
import inspect
import re
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

from atlas import broker as broker_package
from atlas.broker import exceptions as exceptions_module
from atlas.broker.exceptions import (
    BrokerAuthenticationError,
    BrokerConnectionError,
    BrokerDataUnavailableError,
    BrokerError,
    BrokerInsufficientMarginError,
    BrokerNotConnectedError,
    BrokerOrderNotFoundError,
    BrokerOrderRejectedError,
    BrokerPositionNotFoundError,
    BrokerRequestError,
    BrokerSymbolNotFoundError,
    BrokerTimeoutError,
    BrokerUnsupportedOperationError,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.unit

BROKER_DIR: Final = Path(inspect.getfile(broker_package)).parent
EXCEPTIONS_PATH: Final = BROKER_DIR / "exceptions.py"

#: The tree, transcribed from the port's documentation: child, then parent.
#:
#: Every edge is stated, including the ones that look obvious, because the
#: cost of a wrong edge is asymmetric — a class moved *up* the tree silently
#: widens every ``except`` clause that mentions its new parent.
PARENTAGE: Final[tuple[tuple[type[BrokerError], type[Exception]], ...]] = (
    (BrokerError, Exception),
    (BrokerConnectionError, BrokerError),
    (BrokerNotConnectedError, BrokerConnectionError),
    (BrokerTimeoutError, BrokerConnectionError),
    (BrokerAuthenticationError, BrokerError),
    (BrokerRequestError, BrokerError),
    (BrokerSymbolNotFoundError, BrokerRequestError),
    (BrokerOrderNotFoundError, BrokerRequestError),
    (BrokerPositionNotFoundError, BrokerRequestError),
    (BrokerOrderRejectedError, BrokerRequestError),
    (BrokerInsufficientMarginError, BrokerRequestError),
    (BrokerDataUnavailableError, BrokerError),
    (BrokerUnsupportedOperationError, BrokerError),
)

EVERY_EXCEPTION: Final = tuple(child for child, _ in PARENTAGE)

#: The venue and code every sample below is built with, so that a subclass's
#: own fields can be told apart from the two the base class always carries.
SAMPLE_VENUE: Final = "Test Venue"
SAMPLE_CODE: Final = 10019

#: A fully populated instance of each class that carries fields of its own,
#: paired with the fields it is expected to expose beyond ``venue`` and
#: ``code``. Classes absent from this table add nothing to the base.
#:
#: Built at import time on purpose: if constructing one of these could fail,
#: collecting this module would fail, which is the loudest available signal.
POPULATED: Final[tuple[tuple[BrokerError, dict[str, object]], ...]] = (
    (
        BrokerTimeoutError("failed", operation="place_order", venue=SAMPLE_VENUE, code=SAMPLE_CODE),
        {"operation": "place_order"},
    ),
    (
        BrokerSymbolNotFoundError(
            "failed", symbol="EURUSD.pro", venue=SAMPLE_VENUE, code=SAMPLE_CODE
        ),
        {"symbol": "EURUSD.pro"},
    ),
    (
        BrokerOrderNotFoundError("failed", order_id="660001", venue=SAMPLE_VENUE, code=SAMPLE_CODE),
        {"order_id": "660001"},
    ),
    (
        BrokerPositionNotFoundError(
            "failed", position_id="550001", venue=SAMPLE_VENUE, code=SAMPLE_CODE
        ),
        {"position_id": "550001"},
    ),
    (
        BrokerOrderRejectedError(
            "failed", reason="market closed", venue=SAMPLE_VENUE, code=SAMPLE_CODE
        ),
        {"reason": "market closed"},
    ),
    (
        BrokerInsufficientMarginError(
            "failed",
            required=Decimal("1250.01"),
            available=Decimal("310.55"),
            venue=SAMPLE_VENUE,
            code=SAMPLE_CODE,
        ),
        {"required": Decimal("1250.01"), "available": Decimal("310.55")},
    ),
    (
        BrokerUnsupportedOperationError(
            "failed", operation="subscribe_ticks", venue=SAMPLE_VENUE, code=SAMPLE_CODE
        ),
        {"operation": "subscribe_ticks"},
    ),
)

#: The classes that define a constructor of their own, which are the only ones
#: whose constructor body is worth reading.
OWN_CONSTRUCTORS: Final = tuple(
    exception_type for exception_type in EVERY_EXCEPTION if "__init__" in vars(exception_type)
)

#: Source files whose ``Raises:`` clauses must name a class that resolves.
#:
#: A clause naming a class that does not exist is worse than no clause: it
#: tells a caller to write an ``except`` branch that can never be entered.
DOCUMENTED_SOURCES: Final[tuple[Path, ...]] = (
    BROKER_DIR / "adapter.py",
    BROKER_DIR / "mt5" / "adapter.py",
    BROKER_DIR / "mt5" / "connection.py",
    BROKER_DIR / "mt5" / "mapper.py",
)

#: Exceptions a ``Raises:`` clause may name that are not part of the hierarchy.
PERMITTED_BUILTINS: Final = frozenset(
    {"NotImplementedError", "TypeError", "ValueError", "ValidationError"}
)

#: Prefixes that would mark a class as a stand-in for the real hierarchy.
#:
#: ``MT5`` is the one that actually existed: the adapter carried eight
#: ``MT5*Error`` classes while the port's hierarchy was unwritten. The rest are
#: named so that the next stand-in is caught by the same test rather than by a
#: reviewer noticing.
PLACEHOLDER_PREFIXES: Final = ("MT5", "Temp", "Temporary", "Placeholder", "Stub", "Fake")

_RAISES_SECTION = re.compile(r"\n\s*Raises:\n(.*?)(?=\n\s*(?:[A-Z][a-z]+:\n)|\Z)", re.DOTALL)
_RAISED_NAME = re.compile(r"^\s{2,}([A-Za-z_]\w*(?:Error|Exception)):", re.MULTILINE)


def _source_files() -> Iterator[Path]:
    """Yield every Python source file in the broker package.

    Yields:
        Each ``.py`` file under ``atlas/broker``, recursively.
    """
    yield from sorted(BROKER_DIR.rglob("*.py"))


#: Every source file in the package, and every one except the hierarchy's own.
ALL_SOURCES: Final = tuple(_source_files())
OTHER_SOURCES: Final = tuple(path for path in ALL_SOURCES if path != EXCEPTIONS_PATH)


def _source_id(path: Path) -> str:
    """Return a parametrisation id that distinguishes same-named modules.

    Args:
        path: The source file.

    Returns:
        The file name, prefixed by its directory. Three of the sources below
        are called ``adapter.py``.
    """
    return f"{path.parent.name}/{path.name}"


def _exception_classes_in(path: Path) -> list[str]:
    """Return the names of classes in a file that look like exceptions.

    Args:
        path: The source file to read.

    Returns:
        Every class whose name ends in ``Error`` or ``Exception``.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name.endswith(("Error", "Exception"))
    ]


def _constructor_body(class_name: str) -> list[ast.stmt]:
    """Return the statements in a hierarchy class's ``__init__``.

    Args:
        class_name: The class to read, which must define its own constructor.

    Returns:
        The constructor's body, docstring included.
    """
    tree = ast.parse(EXCEPTIONS_PATH.read_text(encoding="utf-8"), filename=str(EXCEPTIONS_PATH))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for child in node.body:
            if isinstance(child, ast.FunctionDef) and child.name == "__init__":
                return child.body
    pytest.fail(f"{class_name} defines no constructor in {EXCEPTIONS_PATH.name}")


def _documented_exception_names(path: Path) -> set[str]:
    """Return every exception named in a ``Raises:`` clause in a file.

    Args:
        path: The source file to read.

    Returns:
        The class names, deduplicated across all docstrings in the file.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef | ast.ClassDef | ast.Module):
            continue
        docstring = ast.get_docstring(node)
        if docstring is None:
            continue
        for section in _RAISES_SECTION.findall(f"\n{docstring}"):
            names.update(_RAISED_NAME.findall(section))
    return names


class TestHierarchy:
    @pytest.mark.parametrize(("child", "parent"), PARENTAGE, ids=lambda item: item.__name__)
    def test_the_class_has_the_documented_parent(
        self, child: type[BrokerError], parent: type[Exception]
    ) -> None:
        # Direct parentage, not `issubclass`: a class moved one level up still
        # satisfies `issubclass` against its grandparent.
        assert child.__bases__ == (parent,)

    @pytest.mark.parametrize("exception_type", EVERY_EXCEPTION)
    def test_every_exception_is_a_broker_error(self, exception_type: type[BrokerError]) -> None:
        # One `except BrokerError` at the top of a supervision loop has to be
        # enough to keep the process alive.
        assert issubclass(exception_type, BrokerError)

    def test_authentication_is_not_a_connection_fault(self) -> None:
        # The placement that costs the most if it is wrong. A retry loop that
        # catches BrokerConnectionError must not swallow rejected credentials,
        # or it will hammer the venue with a password that cannot work.
        assert not issubclass(BrokerAuthenticationError, BrokerConnectionError)

    def test_a_timeout_is_a_connection_fault(self) -> None:
        assert issubclass(BrokerTimeoutError, BrokerConnectionError)

    def test_data_unavailable_is_not_a_request_error(self) -> None:
        # Nothing was refused: the venue simply has no bars that far back. A
        # caller may treat it as "not yet" without treating it as a fault.
        assert not issubclass(BrokerDataUnavailableError, BrokerRequestError)

    def test_unsupported_is_not_a_request_error(self) -> None:
        # A permanent property of the venue, not a verdict on this request.
        assert not issubclass(BrokerUnsupportedOperationError, BrokerRequestError)

    def test_insufficient_margin_is_not_an_order_rejection(self) -> None:
        # It is the one refusal a sizing layer can answer automatically, which
        # it could not do if it arrived as the catch-all rejection.
        assert not issubclass(BrokerInsufficientMarginError, BrokerOrderRejectedError)

    def test_the_two_not_found_types_are_distinct(self) -> None:
        # Cancelling by an order ticket and closing by a position ticket fail
        # differently, and a caller reconciling one must not catch the other.
        assert not issubclass(BrokerOrderNotFoundError, BrokerPositionNotFoundError)
        assert not issubclass(BrokerPositionNotFoundError, BrokerOrderNotFoundError)


class TestModuleSurface:
    def test_the_module_exports_exactly_the_hierarchy(self) -> None:
        assert set(exceptions_module.__all__) == {
            exception_type.__name__ for exception_type in EVERY_EXCEPTION
        }

    def test_the_module_defines_no_other_exception(self) -> None:
        # An exception defined here but left out of __all__ would be raisable
        # by an adapter and uncatchable by name from `atlas.broker`.
        assert set(_exception_classes_in(EXCEPTIONS_PATH)) == set(exceptions_module.__all__)

    @pytest.mark.parametrize("exception_type", EVERY_EXCEPTION)
    def test_the_package_re_exports_the_exception(self, exception_type: type[BrokerError]) -> None:
        # `no_implicit_reexport` is on, so a name missing from the package's
        # __all__ is a type error at every call site rather than here.
        assert getattr(broker_package, exception_type.__name__) is exception_type
        assert exception_type.__name__ in broker_package.__all__

    @pytest.mark.parametrize("exception_type", EVERY_EXCEPTION)
    def test_the_exception_is_documented(self, exception_type: type[BrokerError]) -> None:
        assert exception_type.__doc__


class TestStructuredContext:
    def test_the_message_survives_as_the_string_form(self) -> None:
        error = BrokerError("the terminal went away")

        assert str(error) == "the terminal went away"
        assert error.message == "the terminal went away"

    def test_the_venue_and_code_are_attributes(self) -> None:
        error = BrokerError("failed", venue="MetaTrader 5", code=-10005)

        assert error.venue == "MetaTrader 5"
        assert error.code == -10005

    def test_context_omits_the_message(self) -> None:
        # A log record carries the message in its own right; repeating it in
        # the structured payload doubles every error line for no gain.
        error = BrokerError("failed", venue="MetaTrader 5")

        assert error.context == {"venue": "MetaTrader 5"}

    def test_context_omits_what_was_not_supplied(self) -> None:
        # A field the venue did not report must be absent, not present as
        # null. Anything resizing on `required` has to tell those apart.
        assert BrokerError("failed").context == {}

    @pytest.mark.parametrize(("error", "extras"), POPULATED, ids=lambda item: type(item).__name__)
    def test_the_extra_fields_reach_both_attributes_and_context(
        self, error: BrokerError, extras: dict[str, object]
    ) -> None:
        for name, value in extras.items():
            assert getattr(error, name) == value
        assert error.context == {**extras, "venue": SAMPLE_VENUE, "code": SAMPLE_CODE}

    def test_every_class_with_extra_fields_is_covered(self) -> None:
        # The table above is hand-written. A class given a new field but not a
        # sample here would have that field checked by nothing. Every class
        # that writes its own constructor does so to add a field — except the
        # base, whose constructor is where `message`, `venue` and `code` come
        # from in the first place.
        covered = {type(error) for error, _ in POPULATED}

        assert covered == set(OWN_CONSTRUCTORS) - {BrokerError}

    @pytest.mark.parametrize("exception_type", EVERY_EXCEPTION)
    def test_the_message_is_the_only_positional_argument(
        self, exception_type: type[BrokerError]
    ) -> None:
        # Everything else is keyword-only, so adding a field later cannot
        # silently reinterpret an existing call site's positional argument.
        parameters = list(inspect.signature(exception_type).parameters.values())
        positional = [
            parameter
            for parameter in parameters
            if parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        ]

        assert [parameter.name for parameter in positional] == ["message"]

    @pytest.mark.parametrize("exception_type", EVERY_EXCEPTION)
    def test_only_the_message_is_required(self, exception_type: type[BrokerError]) -> None:
        # These are built on a degraded path. An adapter that knows nothing but
        # what went wrong must still be able to report it.
        error = exception_type("failed")

        assert str(error) == "failed"
        assert error.context == {}

    def test_the_margin_fields_hold_decimals_unrounded(self) -> None:
        # Money is Decimal throughout the port; a float here would put binary
        # rounding into the one number a sizing layer resizes on.
        error = BrokerInsufficientMarginError(
            "not enough margin", required=Decimal("1250.01"), available=Decimal("310.55")
        )

        assert error.required == Decimal("1250.01")
        assert error.available == Decimal("310.55")


class TestLightweightConstruction:
    """Constructing one of these must not be able to fail.

    They are raised while a venue is unreachable, sometimes from inside another
    failure's handler. A constructor that validates, normalises or touches I/O
    turns a reportable fault into an unreportable one.
    """

    @pytest.mark.parametrize("exception_type", OWN_CONSTRUCTORS, ids=lambda item: item.__name__)
    def test_the_constructor_only_delegates_and_assigns(
        self, exception_type: type[BrokerError]
    ) -> None:
        # Read from the source rather than exercised, because "does not call
        # out" is not something a passing call can demonstrate. A call, a
        # comparison or a loop in here would all show up as a statement type
        # that is not an assignment or the `super().__init__` expression.
        body = _constructor_body(exception_type.__name__)
        permitted = (ast.Expr, ast.Assign, ast.AnnAssign)
        offenders = [
            type(statement).__name__ for statement in body if not isinstance(statement, permitted)
        ]

        assert not offenders, f"{exception_type.__name__}.__init__ does more: {offenders}"

    def test_the_constructor_scanner_reads_every_constructor(self) -> None:
        # A scan that found no constructors would report a clean sweep. The
        # base plus six subclasses define one; the rest inherit.
        defined = {
            node.name
            for node in ast.walk(ast.parse(EXCEPTIONS_PATH.read_text(encoding="utf-8")))
            if isinstance(node, ast.ClassDef)
            and any(
                isinstance(child, ast.FunctionDef) and child.name == "__init__"
                for child in node.body
            )
        }

        assert defined == {exception_type.__name__ for exception_type in OWN_CONSTRUCTORS}
        assert len(defined) > 1

    @pytest.mark.parametrize("exception_type", EVERY_EXCEPTION)
    def test_no_argument_is_validated_or_normalised(
        self, exception_type: type[BrokerError]
    ) -> None:
        # Deliberately nonsensical input: an empty message, a negative code and
        # a blank venue must all be accepted. Reporting a malformed failure is
        # strictly better than raising a second one on top of the first.
        error = exception_type("", venue="", code=-1)

        assert error.message == ""
        assert error.code == -1


class TestNoTemporaryExceptionsRemain:
    """The placeholder classes ATLAS-TASK-0004 shipped are gone for good.

    The adapter defined ``MT5Error``, ``MT5NotConnectedError`` and six more
    while the port's hierarchy was still unwritten. Deleting them once is easy;
    what these tests do is make a replacement fail immediately rather than
    reach a caller that has no name to catch it by.
    """

    def test_the_source_scanner_finds_something(self) -> None:
        found = [path for path in _source_files() if _exception_classes_in(path)]

        assert found == [EXCEPTIONS_PATH]

    def test_the_scanned_set_is_the_package_minus_the_hierarchy(self) -> None:
        # exceptions.py is excluded from the sweep below rather than skipped
        # inside it: a skip reports as a non-result, so a filter that quietly
        # emptied the whole list would look the same as a clean sweep.
        assert OTHER_SOURCES
        assert set(OTHER_SOURCES) == set(_source_files()) - {EXCEPTIONS_PATH}

    @pytest.mark.parametrize("path", OTHER_SOURCES, ids=lambda path: path.name)
    def test_no_module_defines_an_exception_outside_the_hierarchy(self, path: Path) -> None:
        assert _exception_classes_in(path) == []

    @pytest.mark.parametrize("path", ALL_SOURCES, ids=lambda path: path.name)
    def test_no_module_names_a_placeholder_exception(self, path: Path) -> None:
        # Catches the class in any form the source can carry it — a definition,
        # an import, a raise, a docstring reference — which is what makes this
        # different from the AST scan above.
        text = path.read_text(encoding="utf-8")
        offenders = sorted(
            {
                match
                for match in re.findall(r"\b(\w*(?:Error|Exception))\b", text)
                if match.startswith(PLACEHOLDER_PREFIXES)
            }
        )

        assert not offenders, f"{path.name} still names {offenders}"

    def test_the_placeholder_scanner_can_fire(self) -> None:
        # A pattern that matches nothing would pass the test above on an empty
        # repository. Proven against the name that actually existed.
        assert [
            match
            for match in re.findall(r"\b(\w*(?:Error|Exception))\b", "raise MT5TimeoutError(msg)")
            if match.startswith(PLACEHOLDER_PREFIXES)
        ] == ["MT5TimeoutError"]


class TestEveryRaisesClauseResolves:
    def test_the_docstring_scanner_finds_something(self) -> None:
        # Guards every parametrisation below: a regex that matched nothing
        # would report a clean sweep over an empty set.
        found = {name for path in DOCUMENTED_SOURCES for name in _documented_exception_names(path)}

        assert "BrokerNotConnectedError" in found
        assert len(found) > 5

    @pytest.mark.parametrize("path", DOCUMENTED_SOURCES, ids=_source_id)
    def test_the_documented_source_exists(self, path: Path) -> None:
        assert path.is_file()

    @pytest.mark.parametrize("path", DOCUMENTED_SOURCES, ids=_source_id)
    def test_every_named_exception_resolves_to_a_class(self, path: Path) -> None:
        named = _documented_exception_names(path)
        unresolved = sorted(
            name
            for name in named
            if name not in PERMITTED_BUILTINS and not hasattr(exceptions_module, name)
        )

        assert not unresolved, f"{path.name} documents exceptions that do not exist: {unresolved}"

    @pytest.mark.parametrize("path", DOCUMENTED_SOURCES, ids=_source_id)
    def test_every_named_exception_is_a_broker_error(self, path: Path) -> None:
        named = _documented_exception_names(path)
        for name in named - PERMITTED_BUILTINS:
            resolved = getattr(exceptions_module, name, None)

            assert isinstance(resolved, type), f"{path.name} names {name}, which does not exist"
            assert issubclass(resolved, BrokerError), f"{path.name} names a non-broker {name}"
