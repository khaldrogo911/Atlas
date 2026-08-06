"""Terminal session ownership: configuration, the vendor import, state and errors.

Four things live here, and they are together because they are the four parts of
"Atlas has a session with a terminal".

The vendor import
    :func:`load_terminal` is the only place in Atlas that imports
    ``MetaTrader5``, and it does so inside the function body rather than at
    module scope. That is a hard requirement, not a preference: the repository's
    structural tests import every package under ``atlas`` on Linux CI, where the
    MetaTrader5 wheel does not exist, and a module-level import would fail the
    build of a package that is merely present.

The configuration
    :class:`MT5Config` carries what a session needs and nothing else. The
    password is a :class:`~pydantic.SecretStr`, so it does not appear in a
    repr, a log line or a traceback frame.

The session
    :class:`MT5Session` owns the connection state machine and the terminal
    handle. The adapter delegates to it rather than calling the terminal
    directly, which is what keeps the vendor surface reachable from exactly one
    object.

The error translation
    Failure arrives from MetaTrader 5 as an integer, and this is where it
    becomes a ``BrokerError``. The tables live next to the session that
    produces the integers, so no call site anywhere decides what a code means.

Error translation
-----------------
The two integer spaces are classified separately and must never share a table.

``last_error()`` describes the terminal's own IPC layer — it answers "did the
request reach a server". :meth:`MT5Session.error_from_terminal` classifies it.

An order result's ``retcode`` is a trade server's verdict — it answers "what did
the server do with the order". :func:`error_from_retcode` classifies it.

Both classifications are total: every code produces an exception, and an
unrecognised one falls back to the broadest honest type rather than to a guess
that would tell a caller to retry something it should not.
"""

from __future__ import annotations

import contextlib
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, SecretStr

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
from atlas.broker.mt5.constants import (
    AUTHENTICATION_ERROR_CODES,
    CONNECTION_ERROR_CODES,
    MT5_RETCODE_DESCRIPTIONS,
    NOT_FOUND_ERROR_CODES,
    RETCODE_AUTHENTICATION_CODES,
    RETCODE_CONNECTION_CODES,
    RETCODE_INSUFFICIENT_MARGIN_CODES,
    RETCODE_POSITION_NOT_FOUND_CODES,
    RETCODE_SUCCESS_CODES,
    RETCODE_TIMEOUT_CODES,
    TIMEOUT_ERROR_CODES,
)
from atlas.broker.mt5.mapper import ServerClock

if TYPE_CHECKING:
    from collections.abc import Sequence

    from atlas.broker.mt5.mapper import (
        MT5AccountInfo,
        MT5Deal,
        MT5Order,
        MT5Position,
        MT5RateRow,
        MT5SymbolInfo,
        MT5Tick,
    )

__all__ = [
    "VENUE",
    "MT5Config",
    "MT5Session",
    "MT5TerminalInfo",
    "Terminal",
    "error_from_retcode",
    "load_terminal",
]

#: Recorded on every exception this module raises, so a log line covering more
#: than one adapter says which venue produced the failure.
VENUE: Final = "MetaTrader 5"


# --- Error translation --------------------------------------------------------


#: Maps a terminal result code onto the exception that reports it. Consulted in
#: order; anything unmatched becomes a plain
#: :class:`~atlas.broker.exceptions.BrokerError`, because inventing a category
#: for an unknown code would mislead a caller deciding whether to retry.
_ERROR_CODE_GROUPS: Final[tuple[tuple[frozenset[int], type[BrokerError]], ...]] = (
    (AUTHENTICATION_ERROR_CODES, BrokerAuthenticationError),
    (TIMEOUT_ERROR_CODES, BrokerTimeoutError),
    (CONNECTION_ERROR_CODES, BrokerConnectionError),
    (NOT_FOUND_ERROR_CODES, BrokerDataUnavailableError),
)

#: Maps a trade server retcode onto the exception that reports it. Consulted in
#: order.
#:
#: The fallback here is the opposite of the one above: an unrecognised *retcode*
#: becomes :class:`~atlas.broker.exceptions.BrokerOrderRejectedError` rather
#: than a bare ``BrokerError``, because reaching this table already establishes
#: that a trade server saw the order and declined it. Which of its several dozen
#: reasons applies changes the message, not what the caller must do.
_RETCODE_GROUPS: Final[tuple[tuple[frozenset[int], type[BrokerError]], ...]] = (
    (RETCODE_TIMEOUT_CODES, BrokerTimeoutError),
    (RETCODE_CONNECTION_CODES, BrokerConnectionError),
    (RETCODE_AUTHENTICATION_CODES, BrokerAuthenticationError),
    (RETCODE_INSUFFICIENT_MARGIN_CODES, BrokerInsufficientMarginError),
    (RETCODE_POSITION_NOT_FOUND_CODES, BrokerPositionNotFoundError),
)


def error_from_retcode(retcode: int, comment: str | None = None) -> BrokerError:
    """Translate a trade server's verdict on an order into a broker exception.

    Args:
        retcode: The ``retcode`` field of a MetaTrader 5 order result.
        comment: The server's own comment on the result, if it sent one. Kept
            verbatim on the exception; it is the only place a venue-specific
            reason survives translation.

    Returns:
        The exception to raise, carrying ``retcode`` as its
        :attr:`~atlas.broker.exceptions.BrokerError.code`. Returned rather than
        raised so the call site reads ``raise error_from_retcode(...)`` and
        static analysis can see that control flow ends there.

    Raises:
        ValueError: If ``retcode`` is one of the success codes. A caller that
            reaches here with ``TRADE_RETCODE_DONE`` has confused a filled order
            for a failed one, and turning that into a plausible-looking
            exception would hide the bug behind a spurious rejection.

    Notes:
        Total over every failing retcode, including ones MetaTrader 5 may add
        later: unrecognised codes are rejections, and the number survives on the
        exception either way.
    """
    if retcode in RETCODE_SUCCESS_CODES:
        msg = f"MetaTrader 5 retcode {retcode} reports success, not a failure"
        raise ValueError(msg)

    description = MT5_RETCODE_DESCRIPTIONS.get(retcode, "unrecognised retcode")
    message = f"MetaTrader 5 trade request failed: {description} (retcode {retcode})"
    if comment:
        message = f"{message}: {comment}"

    for codes, exception_type in _RETCODE_GROUPS:
        if retcode in codes:
            return exception_type(message, venue=VENUE, code=retcode)
    return BrokerOrderRejectedError(
        message, reason=comment or description, venue=VENUE, code=retcode
    )


# --- The vendor surface Atlas depends on --------------------------------------


class MT5TerminalInfo(Protocol):
    """The fields Atlas reads from ``MetaTrader5.terminal_info()``."""

    name: str
    connected: bool
    ping_last: int


class Terminal(Protocol):
    """Every ``MetaTrader5`` function Atlas calls, and no others.

    This protocol is the complete statement of Atlas's dependency on the vendor
    package. A function absent here is a function the adapter does not use, and
    a signature that changes upstream breaks a declared contract rather than
    failing at an attribute lookup deep inside a market-data call.

    It also makes the adapter testable: a test supplies an object with these
    methods and never imports MetaTrader5 at all.
    """

    def initialize(
        self,
        path: str,
        *,
        login: int,
        password: str,
        server: str,
        timeout: int,
        portable: bool,
    ) -> bool:
        """Start the terminal and log in."""
        ...

    def shutdown(self) -> None:
        """Close the terminal connection."""
        ...

    def last_error(self) -> tuple[int, str]:
        """Return the code and description of the last failure."""
        ...

    def version(self) -> tuple[int, int, str] | None:
        """Return terminal version, build and release date."""
        ...

    def terminal_info(self) -> MT5TerminalInfo | None:
        """Return the running terminal's status."""
        ...

    def account_info(self) -> MT5AccountInfo | None:
        """Return the logged-in account's state."""
        ...

    def symbols_get(self) -> Sequence[MT5SymbolInfo] | None:
        """Return every instrument the terminal offers."""
        ...

    def symbol_info(self, symbol: str) -> MT5SymbolInfo | None:
        """Return one instrument's specification."""
        ...

    def symbol_info_tick(self, symbol: str) -> MT5Tick | None:
        """Return one instrument's latest quote."""
        ...

    def symbol_select(self, symbol: str, enable: bool) -> bool:
        """Add or remove an instrument from Market Watch."""
        ...

    def copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> Sequence[MT5RateRow] | None:
        """Return bars counted back from the most recent."""
        ...

    def copy_rates_range(
        self, symbol: str, timeframe: int, date_from: float, date_to: float
    ) -> Sequence[MT5RateRow] | None:
        """Return bars whose open time falls in a period."""
        ...

    def positions_get(self, **filters: str) -> Sequence[MT5Position] | None:
        """Return open positions, optionally filtered by ``symbol``.

        Takes keyword filters rather than a declared optional parameter because
        the vendor distinguishes "argument omitted" from "argument is None":
        passing ``symbol=None`` explicitly returns nothing rather than
        everything.
        """
        ...

    def orders_get(self, **filters: str) -> Sequence[MT5Order] | None:
        """Return working orders, optionally filtered by ``symbol``."""
        ...

    def history_deals_get(self, **filters: int) -> Sequence[MT5Deal] | None:
        """Return deals, selected by a ``position`` or ``ticket`` filter.

        Only the filtered form is declared. The date-range form exists at the
        vendor but Atlas does not use it: closed-trade history is a reporting
        concern that the broker port deliberately excludes.
        """
        ...

    def order_calc_margin(
        self, action: int, symbol: str, volume: float, price: float
    ) -> float | None:
        """Return the margin the venue would take for a hypothetical position."""
        ...


def load_terminal() -> Terminal:
    """Import and return the ``MetaTrader5`` module.

    Returns:
        The vendor module, typed as :class:`Terminal`.

    Raises:
        BrokerConnectionError: If the package is not installed. Raised as a
            connection fault rather than allowed to surface as
            ``ModuleNotFoundError`` because to every caller above the port it is
            the same condition: this venue cannot be reached from this process.

    Notes:
        The import is deliberately inside the function. See the module
        docstring: a module-level import would break every Linux CI run.

        The ``cast`` is the single point where Atlas asserts that the untyped
        vendor module satisfies :class:`Terminal`. The wheel ships no
        ``py.typed``, so every attribute of it is ``Any``; confining that to one
        expression is what stops ``Any`` from spreading through the adapter.
        ``tests/unit/broker/mt5/test_mt5_connection.py`` checks the assertion
        against the real module wherever the SDK can be imported.
    """
    try:
        import MetaTrader5  # noqa: PLC0415  lazy by design; see the module docstring
    except ImportError as error:  # pragma: no cover - depends on the host platform
        msg = (
            "the MetaTrader5 package is not installed; it publishes Windows wheels "
            "only and Atlas declares it as the optional 'mt5' extra "
            "(poetry install --extras mt5)"
        )
        raise BrokerConnectionError(msg, venue=VENUE) from error

    return cast("Terminal", MetaTrader5)


# --- Configuration ------------------------------------------------------------


class MT5Config(BaseModel):
    """What a MetaTrader 5 session needs in order to be established.

    Constructed by the composition root from :mod:`atlas.config` and handed to
    the adapter. This package deliberately does not read the environment
    itself: an adapter that sources its own credentials cannot be pointed at a
    second account in a test, and Atlas would have two configuration systems.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    login: int = Field(gt=0, description="Trading account number.")
    password: SecretStr = Field(description="Account password, held so it cannot be logged.")
    server: str = Field(min_length=1, description="Trade server name, such as 'ICMarkets-Demo'.")
    terminal_path: Path = Field(
        description=(
            "Absolute path to terminal64.exe. Required rather than left to the "
            "vendor's auto-discovery: a host commonly has several terminals "
            "installed, one per broker, and letting the SDK choose makes which "
            "account Atlas trades a property of the filesystem."
        )
    )
    timeout_ms: int = Field(
        default=60_000, gt=0, description="How long the terminal waits for the trade server."
    )
    portable: bool = Field(
        default=False, description="Whether to start the terminal in portable mode."
    )
    server_utc_offset: timedelta = Field(
        default_factory=lambda: ServerClock().offset,
        description=(
            "How far the trade server's clock runs ahead of UTC. Zero assumes a "
            "server that publishes UTC; see ServerClock for why this cannot be "
            "discovered and must be configured."
        ),
    )

    @property
    def clock(self) -> ServerClock:
        """The clock that converts this server's timestamps to UTC."""
        return ServerClock(offset=self.server_utc_offset)


# --- Session ------------------------------------------------------------------


class MT5Session:
    """Owns the terminal handle and the connection state machine.

    Separate from the adapter because they answer to different contracts: the
    adapter satisfies :class:`~atlas.broker.adapter.BrokerAdapter`, while this
    class satisfies MetaTrader 5. Keeping them apart is what allows the
    adapter's market-data code to contain no session bookkeeping and this class
    to contain no domain models.

    Not thread safe on its own. The port requires adapters to be callable from
    several threads, and :class:`~atlas.broker.base.BaseBrokerAdapter` is where
    that locking belongs, because every adapter needs the same discipline. That
    class does not lock yet; it owns the session bookkeeping only.
    """

    def __init__(self, config: MT5Config, terminal_factory: object = load_terminal) -> None:
        """Create a session that is not yet connected.

        Args:
            config: Credentials and terminal location.
            terminal_factory: Callable returning the vendor module. Injected so
                that tests supply a stub and never import MetaTrader5. Typed
                loosely because the default is a module-returning function and a
                test's replacement is usually a lambda.
        """
        self._config = config
        self._terminal_factory = terminal_factory
        self._terminal: Terminal | None = None
        self._state = ConnectionState.DISCONNECTED

    @property
    def config(self) -> MT5Config:
        """The configuration this session was built with."""
        return self._config

    @property
    def state(self) -> ConnectionState:
        """The session's current lifecycle state."""
        return self._state

    @property
    def clock(self) -> ServerClock:
        """The clock that converts this server's timestamps to UTC."""
        return self._config.clock

    def is_connected(self) -> bool:
        """Report whether a session is established, without a round trip.

        Returns:
            ``True`` when the last known state can carry a request.
        """
        return self._state.is_usable

    def terminal(self) -> Terminal:
        """Return the live terminal handle.

        Returns:
            The connected terminal.

        Raises:
            BrokerNotConnectedError: If no session is established. Every data
                path goes through here, so this is the single place the
                precondition is enforced.
        """
        if self._terminal is None or not self._state.is_usable:
            msg = "no MetaTrader 5 session is established; call connect() first"
            raise BrokerNotConnectedError(msg, venue=VENUE)
        return self._terminal

    def connect(self) -> None:
        """Start the terminal, log in, and confirm the account is reachable.

        Returns:
            Nothing. The caller builds the domain
            :class:`~atlas.broker.models.Connection` from the session's state.

        Raises:
            BrokerAuthenticationError: If the terminal rejected the credentials.
            BrokerConnectionError: If the terminal could not be started or the
                package is not installed.
            BrokerTimeoutError: If the terminal did not answer in time.

        Notes:
            Calling this on a connected session is not an error and does
            nothing, as the port requires.

            Success is confirmed by reading the account rather than by trusting
            ``initialize()``. The terminal can report a successful start while
            the trade server has not authorised the login, and a session that
            claims to be up but cannot see an account is the state that produces
            the most confusing downstream failures.
        """
        if self._state.is_usable:
            return

        self._state = ConnectionState.CONNECTING
        terminal = self._load()

        started = terminal.initialize(
            str(self._config.terminal_path),
            login=self._config.login,
            password=self._config.password.get_secret_value(),
            server=self._config.server,
            timeout=self._config.timeout_ms,
            portable=self._config.portable,
        )
        if not started:
            self._state = ConnectionState.DISCONNECTED
            raise self._error_from_terminal(terminal, "could not initialise the terminal")

        if terminal.account_info() is None:
            terminal.shutdown()
            self._state = ConnectionState.DISCONNECTED
            raise self._error_from_terminal(
                terminal, f"terminal started but account {self._config.login} is not available"
            )

        self._terminal = terminal
        self._state = ConnectionState.CONNECTED

    def disconnect(self) -> None:
        """Close the session, whatever state it is in.

        Returns:
            Nothing.

        Notes:
            Never raises. The port requires this to be safe on a cleanup path
            that cannot know the current state, so a terminal that is already
            gone, or was never loaded, is not an error. A failure inside
            ``shutdown()`` is deliberately swallowed: there is no corrective
            action available and re-raising would mask the original error that
            sent the caller into cleanup.
        """
        if self._terminal is not None:
            self._state = ConnectionState.DISCONNECTING
            with contextlib.suppress(Exception):  # see the docstring
                self._terminal.shutdown()

        self._terminal = None
        self._state = ConnectionState.DISCONNECTED

    def _load(self) -> Terminal:
        """Obtain the vendor module through the injected factory.

        Returns:
            The terminal handle.

        Raises:
            BrokerConnectionError: If the factory is not callable.
        """
        factory = self._terminal_factory
        if not callable(factory):
            msg = f"terminal factory {factory!r} is not callable"
            raise BrokerConnectionError(msg, venue=VENUE)
        loaded: Terminal = factory()
        return loaded

    def _error_from_terminal(self, terminal: Terminal, context: str) -> BrokerError:
        """Build the exception matching the terminal's last error.

        Args:
            terminal: The terminal to interrogate.
            context: What Atlas was attempting, for the message.

        Returns:
            The exception to raise, carrying the terminal's own code. Returned
            rather than raised so that the call site reads as ``raise
            self._error_from_terminal(...)`` and static analysis can see the
            control flow ends there.
        """
        code, description = terminal.last_error()
        message = f"{context}: MetaTrader 5 error {code} ({description})"

        for codes, exception_type in _ERROR_CODE_GROUPS:
            if code in codes:
                return exception_type(message, venue=VENUE, code=code)
        return BrokerError(message, venue=VENUE, code=code)

    def error_from_terminal(self, context: str) -> BrokerError:
        """Build the exception matching the connected terminal's last error.

        Args:
            context: What Atlas was attempting, for the message.

        Returns:
            The exception to raise.

        Raises:
            BrokerNotConnectedError: If no session is established.
        """
        return self._error_from_terminal(self.terminal(), context)
