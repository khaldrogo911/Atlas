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

from atlas.broker.models import ConnectionState
from atlas.broker.mt5 import connection as connection_module
from atlas.broker.mt5.connection import (
    MT5AuthenticationError,
    MT5Config,
    MT5ConnectionError,
    MT5DataUnavailableError,
    MT5Error,
    MT5NotConnectedError,
    MT5Session,
    MT5TimeoutError,
    load_terminal,
)
from atlas.broker.mt5.constants import (
    RES_E_AUTH_FAILED,
    RES_E_AUTO_TRADING_DISABLED,
    RES_E_FAIL,
    RES_E_INTERNAL_FAIL_CONNECT,
    RES_E_INTERNAL_FAIL_TIMEOUT,
    RES_E_NOT_FOUND,
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

        with pytest.raises(MT5AuthenticationError, match="could not initialise the terminal"):
            session.connect()

        assert session.state is ConnectionState.DISCONNECTED
        assert session.is_connected() is False

    def test_a_terminal_that_starts_without_an_account_is_torn_down(
        self, session: MT5Session, terminal: FakeTerminal
    ) -> None:
        terminal.account = None
        terminal.error = (RES_E_AUTH_FAILED, "Authorization failed")

        with pytest.raises(MT5AuthenticationError, match="is not available"):
            session.connect()

        assert terminal.shutdown_count == 1
        assert session.state is ConnectionState.DISCONNECTED

    def test_a_request_before_connecting_is_refused(self, session: MT5Session) -> None:
        with pytest.raises(MT5NotConnectedError, match="call connect"):
            session.terminal()

    def test_a_factory_that_is_not_callable_is_reported_as_a_connection_fault(
        self, config: MT5Config
    ) -> None:
        broken = MT5Session(config, terminal_factory="not a factory")

        with pytest.raises(MT5ConnectionError, match="is not callable"):
            broken.connect()


class TestDisconnecting:
    def test_disconnecting_clears_the_session(
        self, session: MT5Session, terminal: FakeTerminal
    ) -> None:
        session.connect()

        session.disconnect()

        assert terminal.shutdown_count == 1
        assert session.state is ConnectionState.DISCONNECTED
        with pytest.raises(MT5NotConnectedError):
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
            (RES_E_AUTH_FAILED, MT5AuthenticationError),
            (RES_E_AUTO_TRADING_DISABLED, MT5AuthenticationError),
            (RES_E_INTERNAL_FAIL_TIMEOUT, MT5TimeoutError),
            (RES_E_INTERNAL_FAIL_CONNECT, MT5ConnectionError),
            (RES_E_NOT_FOUND, MT5DataUnavailableError),
        ],
    )
    def test_a_terminal_code_becomes_the_matching_exception(
        self,
        session: MT5Session,
        terminal: FakeTerminal,
        code: int,
        expected: type[MT5Error],
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

        assert type(error) is MT5Error

    def test_the_message_carries_the_context_and_the_terminal_code(
        self, session: MT5Session, terminal: FakeTerminal
    ) -> None:
        session.connect()
        terminal.error = (RES_E_FAIL, "Generic failure")

        error = session.error_from_terminal("could not read the account")

        assert "could not read the account" in str(error)
        assert "-1" in str(error)
        assert "Generic failure" in str(error)

    def test_classifying_without_a_session_is_refused(self, session: MT5Session) -> None:
        with pytest.raises(MT5NotConnectedError):
            session.error_from_terminal("while testing")


class TestExceptionHierarchy:
    """The temporary hierarchy ATLAS-TASK-0005 replaces.

    The shape is tested, not the classes: a caller writing ``except MT5Error``
    today should still catch everything after the rename, so the relationships
    below are what the replacement has to preserve.
    """

    @pytest.mark.parametrize(
        ("subclass", "parent"),
        [
            (MT5ConnectionError, MT5Error),
            (MT5NotConnectedError, MT5ConnectionError),
            (MT5TimeoutError, MT5ConnectionError),
            (MT5AuthenticationError, MT5Error),
            (MT5DataUnavailableError, MT5Error),
        ],
    )
    def test_the_hierarchy_is_catchable_from_the_root(
        self, subclass: type[MT5Error], parent: type[MT5Error]
    ) -> None:
        assert issubclass(subclass, parent)

    @pytest.mark.parametrize(
        "exception_type",
        [
            MT5Error,
            MT5ConnectionError,
            MT5NotConnectedError,
            MT5TimeoutError,
            MT5AuthenticationError,
            MT5DataUnavailableError,
        ],
    )
    def test_every_temporary_exception_names_its_replacement(
        self, exception_type: type[MT5Error]
    ) -> None:
        # The rename is the whole plan for these classes. A class that does not
        # say what replaces it is the one that survives the cleanup by accident.
        assert exception_type.__doc__ is not None
        assert "ATLAS-TASK-0005" in exception_type.__doc__


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
