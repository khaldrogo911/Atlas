"""Unit tests for MetaTrader 5 configuration, the vendor import and the session.

No terminal is started and no account is logged into. The session takes its
terminal from an injected factory precisely so that its state machine — which is
where a connection bug actually lives — can be exercised without either.

The last class in this file is different in kind: it checks where the string
``MetaTrader5`` is allowed to appear in the repository at all. That boundary is
not a style preference. The vendor publishes Windows wheels only, so a single
module-level import anywhere on an import path would break every Linux CI run of
a package that merely exists in the tree.
"""

from __future__ import annotations

import ast
import inspect
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest
from pydantic import SecretStr, ValidationError

from atlas.broker.exceptions import (
    BrokerAuthenticationError,
    BrokerConnectionError,
    BrokerDataUnavailableError,
    BrokerError,
    BrokerInsufficientMarginError,
    BrokerNotConnectedError,
    BrokerOrderRejectedError,
    BrokerPositionNotFoundError,
    BrokerTimeoutError,
)
from atlas.broker.models import ConnectionState
from atlas.broker.mt5 import connection as connection_module
from atlas.broker.mt5.connection import (
    MT5Config,
    MT5Session,
    error_from_retcode,
    load_terminal,
)
from atlas.broker.mt5.constants import (
    MT5_RETCODE_DESCRIPTIONS,
    RES_E_AUTH_FAILED,
    RES_E_AUTO_TRADING_DISABLED,
    RES_E_FAIL,
    RES_E_INTERNAL_FAIL_CONNECT,
    RES_E_INTERNAL_FAIL_TIMEOUT,
    RES_E_NOT_FOUND,
    RETCODE_SUCCESS_CODES,
    TRADE_RETCODE_CLIENT_DISABLES_AT,
    TRADE_RETCODE_CONNECTION,
    TRADE_RETCODE_DONE,
    TRADE_RETCODE_DONE_PARTIAL,
    TRADE_RETCODE_INVALID_ORDER,
    TRADE_RETCODE_MARKET_CLOSED,
    TRADE_RETCODE_NO_MONEY,
    TRADE_RETCODE_PLACED,
    TRADE_RETCODE_POSITION_CLOSED,
    TRADE_RETCODE_SERVER_DISABLES_AT,
    TRADE_RETCODE_TIMEOUT,
)
from tests.unit.broker.mt5.conftest import SERVER_OFFSET, FakeTerminal

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.unit

VENDOR_MODULE: Final = "MetaTrader5"


def repository_root() -> Path:
    """Locate the repository root from an installed module's path.

    Returns:
        The directory holding ``pyproject.toml``.
    """
    for candidate in Path(inspect.getfile(connection_module)).parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    message = "could not locate the repository root from the broker package"
    raise AssertionError(message)


def python_sources(root: Path) -> Iterator[Path]:
    """Yield every Python source file that ships as part of the product.

    Args:
        root: The repository root.

    Yields:
        Paths under ``packages/`` and ``apps/``.
    """
    for area in ("packages", "apps"):
        yield from (root / area).rglob("*.py")


def imported_names(node: ast.AST) -> set[str]:
    """Return the module names a statement imports, if it is an import.

    Args:
        node: Any AST node.

    Returns:
        The imported module names, or an empty set for a node that imports
        nothing.
    """
    if isinstance(node, ast.Import):
        return {alias.name for alias in node.names}
    if isinstance(node, ast.ImportFrom) and node.module is not None:
        return {node.module}
    return set()


class FailingShutdownTerminal(FakeTerminal):
    """A terminal whose shutdown raises, as a crashed one would."""

    def shutdown(self) -> None:
        """Fail the way a terminal that has already died does."""
        self.calls.append("shutdown")
        self.shutdown_count += 1
        message = "the terminal process is gone"
        raise OSError(message)


class TestConfig:
    def test_the_clock_is_built_from_the_configured_offset(self, config: MT5Config) -> None:
        assert config.clock.offset == SERVER_OFFSET

    def test_the_offset_defaults_to_utc(self) -> None:
        # Correct only for a server that publishes UTC. It is a default rather
        # than a discovered value because nothing in the terminal API reports
        # it, and a wrong non-zero guess is worse than an explicit zero.
        minimal = MT5Config(
            login=1,
            password=SecretStr("x"),
            server="Example-Demo",
            terminal_path=Path("terminal64.exe"),
        )

        assert minimal.clock.offset == timedelta(0)

    def test_the_password_does_not_appear_in_the_representation(self, config: MT5Config) -> None:
        # The config is logged during composition. A plain string here would put
        # live credentials in every log aggregator the deployment has.
        assert "not-a-real-password" not in repr(config)

    def test_the_configuration_is_immutable(self, config: MT5Config) -> None:
        with pytest.raises(ValidationError):
            config.login = 42  # type: ignore[misc]

    def test_an_unknown_field_is_rejected(self) -> None:
        # A misspelled key that is silently ignored points the adapter at the
        # wrong account.
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            MT5Config(
                login=1,
                password=SecretStr("x"),
                server="Example-Demo",
                terminal_path=Path("terminal64.exe"),
                sever_utc_offset=timedelta(hours=3),  # type: ignore[call-arg]
            )

    @pytest.mark.parametrize("login", [0, -1])
    def test_an_impossible_account_number_is_rejected(self, login: int) -> None:
        with pytest.raises(ValidationError, match="greater than 0"):
            MT5Config(
                login=login,
                password=SecretStr("x"),
                server="Example-Demo",
                terminal_path=Path("terminal64.exe"),
            )

    def test_an_empty_server_name_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least 1 character"):
            MT5Config(
                login=1,
                password=SecretStr("x"),
                server="",
                terminal_path=Path("terminal64.exe"),
            )


class TestConnecting:
    def test_a_successful_connection_reaches_the_connected_state(self, session: MT5Session) -> None:
        session.connect()

        assert session.state is ConnectionState.CONNECTED
        assert session.is_connected() is True

    def test_the_credentials_reach_the_terminal(
        self, session: MT5Session, terminal: FakeTerminal, config: MT5Config
    ) -> None:
        session.connect()

        assert terminal.initialize_args == {
            "path": str(config.terminal_path),
            "login": config.login,
            "password": "not-a-real-password",
            "server": config.server,
            "timeout": config.timeout_ms,
            "portable": config.portable,
        }

    def test_success_is_confirmed_by_reading_the_account(
        self, session: MT5Session, terminal: FakeTerminal
    ) -> None:
        # initialize() can report success while the trade server has not
        # authorised the login. A session that claims to be up but cannot see an
        # account produces the most confusing downstream failures available.
        session.connect()

        assert "account_info" in terminal.calls

    def test_connecting_twice_does_not_start_a_second_terminal(
        self, session: MT5Session, terminal: FakeTerminal
    ) -> None:
        # The port requires connect() on a live session to be a no-op.
        session.connect()
        session.connect()

        assert terminal.calls.count("initialize") == 1

    def test_a_refused_login_raises_and_leaves_no_session(
        self, session: MT5Session, terminal: FakeTerminal
    ) -> None:
        terminal.initialize_result = False
        terminal.error = (RES_E_AUTH_FAILED, "Authorization failed")

        with pytest.raises(BrokerAuthenticationError, match="could not initialise the terminal"):
            session.connect()

        assert session.state is ConnectionState.DISCONNECTED
        assert session.is_connected() is False

    def test_a_terminal_that_starts_without_an_account_is_torn_down(
        self, session: MT5Session, terminal: FakeTerminal
    ) -> None:
        terminal.account = None
        terminal.error = (RES_E_AUTH_FAILED, "Authorization failed")

        with pytest.raises(BrokerAuthenticationError, match="is not available"):
            session.connect()

        assert terminal.shutdown_count == 1
        assert session.state is ConnectionState.DISCONNECTED

    def test_a_request_before_connecting_is_refused(self, session: MT5Session) -> None:
        with pytest.raises(BrokerNotConnectedError, match="call connect"):
            session.terminal()

    def test_a_factory_that_is_not_callable_is_reported_as_a_connection_fault(
        self, config: MT5Config
    ) -> None:
        broken = MT5Session(config, terminal_factory="not a factory")

        with pytest.raises(BrokerConnectionError, match="is not callable"):
            broken.connect()


class TestDisconnecting:
    def test_disconnecting_clears_the_session(
        self, session: MT5Session, terminal: FakeTerminal
    ) -> None:
        session.connect()

        session.disconnect()

        assert terminal.shutdown_count == 1
        assert session.state is ConnectionState.DISCONNECTED
        with pytest.raises(BrokerNotConnectedError):
            session.terminal()

    def test_disconnecting_an_unconnected_session_is_not_an_error(
        self, session: MT5Session, terminal: FakeTerminal
    ) -> None:
        session.disconnect()

        assert terminal.shutdown_count == 0
        assert session.state is ConnectionState.DISCONNECTED

    def test_a_terminal_that_fails_to_shut_down_does_not_break_cleanup(
        self, config: MT5Config
    ) -> None:
        # This runs on the path taken when something has already gone wrong.
        # Raising here would mask the original error that sent the caller into
        # cleanup, and there is no corrective action available anyway.
        terminal = FailingShutdownTerminal()
        session = MT5Session(config, terminal_factory=lambda: terminal)
        session.connect()

        session.disconnect()

        assert session.state is ConnectionState.DISCONNECTED
        assert terminal.shutdown_count == 1

    def test_reconnecting_after_a_failed_shutdown_still_works(self, config: MT5Config) -> None:
        terminal = FailingShutdownTerminal()
        session = MT5Session(config, terminal_factory=lambda: terminal)
        session.connect()
        session.disconnect()

        session.connect()

        assert session.state is ConnectionState.CONNECTED


class TestErrorClassification:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            (RES_E_AUTH_FAILED, BrokerAuthenticationError),
            (RES_E_AUTO_TRADING_DISABLED, BrokerAuthenticationError),
            (RES_E_INTERNAL_FAIL_TIMEOUT, BrokerTimeoutError),
            (RES_E_INTERNAL_FAIL_CONNECT, BrokerConnectionError),
            (RES_E_NOT_FOUND, BrokerDataUnavailableError),
        ],
    )
    def test_a_terminal_code_becomes_the_matching_exception(
        self,
        session: MT5Session,
        terminal: FakeTerminal,
        code: int,
        expected: type[BrokerError],
    ) -> None:
        # The classification is what a caller retries on. A timeout is worth
        # retrying, a refused credential never is.
        session.connect()
        terminal.error = (code, "description")

        assert isinstance(session.error_from_terminal("while testing"), expected)

    def test_an_unrecognised_code_is_not_given_a_category(
        self, session: MT5Session, terminal: FakeTerminal
    ) -> None:
        # Inventing a category for an unknown code would mislead a caller
        # deciding whether to retry.
        session.connect()
        terminal.error = (RES_E_FAIL, "Generic failure")

        error = session.error_from_terminal("while testing")

        assert type(error) is BrokerError

    def test_the_message_carries_the_context_and_the_terminal_code(
        self, session: MT5Session, terminal: FakeTerminal
    ) -> None:
        session.connect()
        terminal.error = (RES_E_FAIL, "Generic failure")

        error = session.error_from_terminal("could not read the account")

        assert "could not read the account" in str(error)
        assert "-1" in str(error)
        assert "Generic failure" in str(error)

    def test_the_terminal_code_survives_on_the_exception(
        self, session: MT5Session, terminal: FakeTerminal
    ) -> None:
        # The classification deliberately throws away the distinction between
        # codes in one group. Keeping the number is what lets a MetaTrader
        # 5-specific quirk still be diagnosed afterwards.
        session.connect()
        terminal.error = (RES_E_INTERNAL_FAIL_TIMEOUT, "IPC timeout")

        error = session.error_from_terminal("while testing")

        assert error.code == RES_E_INTERNAL_FAIL_TIMEOUT
        assert error.venue == connection_module.VENUE

    def test_classifying_without_a_session_is_refused(self, session: MT5Session) -> None:
        with pytest.raises(BrokerNotConnectedError):
            session.error_from_terminal("while testing")


class TestRetcodeClassification:
    """The trade server's verdict on an order, translated.

    A separate integer space from the terminal result codes above, classified by
    a separate table. The two must never be consulted for each other: they
    overlap in value and mean nothing to one another.
    """

    @pytest.mark.parametrize(
        ("retcode", "expected"),
        [
            (TRADE_RETCODE_TIMEOUT, BrokerTimeoutError),
            (TRADE_RETCODE_CONNECTION, BrokerConnectionError),
            (TRADE_RETCODE_SERVER_DISABLES_AT, BrokerAuthenticationError),
            (TRADE_RETCODE_CLIENT_DISABLES_AT, BrokerAuthenticationError),
            (TRADE_RETCODE_NO_MONEY, BrokerInsufficientMarginError),
            (TRADE_RETCODE_POSITION_CLOSED, BrokerPositionNotFoundError),
            (TRADE_RETCODE_MARKET_CLOSED, BrokerOrderRejectedError),
            (TRADE_RETCODE_INVALID_ORDER, BrokerOrderRejectedError),
        ],
    )
    def test_a_retcode_becomes_the_matching_exception(
        self, retcode: int, expected: type[BrokerError]
    ) -> None:
        # These are the distinctions a caller acts on: retry, wait for a human,
        # resize, reconcile, or give up on this order.
        assert isinstance(error_from_retcode(retcode), expected)

    @pytest.mark.parametrize(
        "retcode", sorted(set(MT5_RETCODE_DESCRIPTIONS) - RETCODE_SUCCESS_CODES)
    )
    def test_every_documented_failure_retcode_is_classified(self, retcode: int) -> None:
        # Totality is the property that matters. A retcode with no branch would
        # surface as whatever the fallthrough happened to be, which is how an
        # unhandled venue condition becomes a silent one.
        error = error_from_retcode(retcode)

        assert isinstance(error, BrokerError)
        assert error.code == retcode
        assert MT5_RETCODE_DESCRIPTIONS[retcode] in str(error)

    def test_an_unknown_retcode_is_a_rejection_rather_than_a_bare_failure(self) -> None:
        # Reaching this table already establishes that a server saw the order
        # and declined it. Only the reason is unknown, and the reason changes
        # the message rather than what the caller must do.
        error = error_from_retcode(19999)

        assert type(error) is BrokerOrderRejectedError
        assert error.code == 19999

    @pytest.mark.parametrize(
        "retcode",
        [TRADE_RETCODE_PLACED, TRADE_RETCODE_DONE, TRADE_RETCODE_DONE_PARTIAL],
    )
    def test_a_success_retcode_is_refused_rather_than_translated(self, retcode: int) -> None:
        # A partial fill is a real order with a real position behind it. Turning
        # any of these into a plausible-looking exception would hide the caller's
        # bug behind a rejection that never happened.
        with pytest.raises(ValueError, match="reports success"):
            error_from_retcode(retcode)

    def test_the_server_comment_is_kept_verbatim(self) -> None:
        # It is the only place a venue-specific reason survives translation.
        error = error_from_retcode(TRADE_RETCODE_MARKET_CLOSED, "Market closed")

        assert isinstance(error, BrokerOrderRejectedError)
        assert error.reason == "Market closed"
        assert "Market closed" in str(error)

    def test_a_rejection_falls_back_to_the_documented_reason(self) -> None:
        # A server that sends no comment still leaves the caller something
        # better than a bare number.
        error = error_from_retcode(TRADE_RETCODE_MARKET_CLOSED)

        assert isinstance(error, BrokerOrderRejectedError)
        assert error.reason == MT5_RETCODE_DESCRIPTIONS[TRADE_RETCODE_MARKET_CLOSED]

    def test_the_two_code_spaces_are_never_confused(
        self, session: MT5Session, terminal: FakeTerminal
    ) -> None:
        # RES_E_NOT_FOUND classifies as unavailable data; a trade retcode of the
        # same shape must not, and vice versa. Sharing a table would make one of
        # the two silently wrong.
        session.connect()
        terminal.error = (RES_E_NOT_FOUND, "Not found")

        assert isinstance(session.error_from_terminal("while testing"), BrokerDataUnavailableError)
        assert not isinstance(
            error_from_retcode(TRADE_RETCODE_INVALID_ORDER), BrokerDataUnavailableError
        )


class TestVendorImportBoundary:
    def test_only_the_mt5_package_imports_the_vendor(self) -> None:
        # The rule the whole design rests on. An import anywhere else makes that
        # module unimportable on a host without the wheel, and couples business
        # logic to a venue it is not supposed to know about.
        root = repository_root()
        permitted = root / "packages" / "broker" / "src" / "atlas" / "broker" / "mt5"

        offenders = [
            path.relative_to(root).as_posix()
            for path in python_sources(root)
            if permitted not in path.parents
            and any(
                VENDOR_MODULE in imported_names(node)
                for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            )
        ]

        assert offenders == []

    def test_the_vendor_is_never_imported_at_module_scope(self) -> None:
        # A module-level import would fail the build of this package on any host
        # without the wheel, which is every Linux CI runner, for a package that
        # is merely present in the tree.
        root = repository_root()
        package = root / "packages" / "broker" / "src" / "atlas" / "broker" / "mt5"

        for path in package.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            top_level = [node for node in tree.body if VENDOR_MODULE in imported_names(node)]

            assert top_level == [], f"{path.name} imports the vendor at import time"

    def test_the_vendor_is_imported_exactly_once(self) -> None:
        # One import site is what makes the boundary auditable. Two would mean
        # the second could drift out of the try/except that reports a missing
        # wheel as a connection fault.
        package = repository_root() / "packages/broker/src/atlas/broker/mt5"
        sites = [
            (path.name, node.lineno)
            for path in package.rglob("*.py")
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            # Narrowed for `lineno`, which only statement nodes carry.
            if isinstance(node, ast.Import | ast.ImportFrom)
            if VENDOR_MODULE in imported_names(node)
        ]

        assert [name for name, _ in sites] == ["connection.py"]

    def test_importing_the_package_does_not_import_the_vendor(self) -> None:
        # The behavioural form of the two checks above, and the only one that
        # covers what a transitive import would do. It runs in a fresh
        # interpreter because this one may legitimately have imported the wheel
        # already, in a test that is about the wheel.
        probe = (
            "import sys; import atlas.broker.mt5; "
            "sys.exit(1 if 'MetaTrader5' in sys.modules else 0)"
        )

        result = subprocess.run(  # noqa: S603  a fixed argument list, no shell
            [sys.executable, "-c", probe],
            check=False,
            capture_output=True,
            text=True,
        )

        pulled_in = f"importing atlas.broker.mt5 pulled in {VENDOR_MODULE}: {result.stderr}"

        assert result.returncode == 0, pulled_in


class TestAgainstTheInstalledPackage:
    """The one check that the ``cast`` in ``load_terminal`` is telling the truth.

    ``MetaTrader5`` ships no type information, so the vendor module is typed by
    assertion. Nothing but the real wheel can confirm the assertion, and the
    wheel installs on Windows only.
    """

    def test_the_loaded_module_provides_every_declared_function(self) -> None:
        pytest.importorskip(
            VENDOR_MODULE,
            reason="the MetaTrader5 wheel installs on Windows only",
        )

        terminal = load_terminal()

        for name in (
            "initialize",
            "shutdown",
            "last_error",
            "version",
            "terminal_info",
            "account_info",
            "symbols_get",
            "symbol_info",
            "symbol_info_tick",
            "symbol_select",
            "copy_rates_from_pos",
            "copy_rates_range",
            "positions_get",
            "orders_get",
            "history_deals_get",
            "order_calc_margin",
        ):
            assert callable(getattr(terminal, name, None)), f"the vendor lost {name}()"
