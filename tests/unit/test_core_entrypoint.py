"""Unit tests for the atlas-core process entrypoint."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, NamedTuple

import pytest

from atlas.apps.core import __main__ as entrypoint
from atlas.apps.core.__main__ import (
    EXIT_BROKER_ERROR,
    EXIT_CONFIG_ERROR,
    EXIT_OK,
    build_startup_record,
    main,
)
from atlas.apps.core.broker_ownership import BrokerOwner
from atlas.broker import BrokerConnectionError
from atlas.broker.mock import MockBrokerAdapter
from atlas.config import load_settings

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from atlas.config import AtlasSettings

pytestmark = pytest.mark.unit

BROKER_LOGIN = "987654"
BROKER_SERVER = "Provider-Demo"
BROKER_TERMINAL_PATH = r"C:\Program Files\Provider MT5\terminal64.exe"
# Named for what it is rather than for what it stands in for: a name carrying
# "password" makes this line a hardcoded-credential finding in every scanner.
BROKER_SENTINEL = "not-a-real-credential-9f2c1a"

RECORD_KEYS = {
    "event",
    "app_name",
    "environment",
    "debug",
    "logging",
    "postgres",
    "redis",
    "duckdb",
}

#: The event ADR-0017's failure record carries, pinned to the literal.
#:
#: The record required the name to differ from ``atlas.core.startup_failed`` and
#: left the string itself to the implementing task. Asserting only the
#: difference would let the string drift on every edit, and a log stream keyed
#: on it is a published interface the moment anything reads it.
BROKER_FAILURE_EVENT = "atlas.core.broker_connect_failed"


@pytest.fixture
def configured_broker(isolated_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Configure a broker section a session could be opened from.

    ATLAS-TASK-0023 made start-up build the adapter, so a process without these
    four values no longer reaches the startup record.

    Returns:
        The hermetic working directory.
    """
    monkeypatch.setenv("ATLAS_BROKER__LOGIN", BROKER_LOGIN)
    monkeypatch.setenv("ATLAS_BROKER__PASSWORD", BROKER_SENTINEL)
    monkeypatch.setenv("ATLAS_BROKER__SERVER", BROKER_SERVER)
    monkeypatch.setenv("ATLAS_BROKER__TERMINAL_PATH", BROKER_TERMINAL_PATH)
    return isolated_env


class BrokerSession(NamedTuple):
    """What a run of :func:`main` over a mock venue exposes to a test."""

    adapter: MockBrokerAdapter
    owner: BrokerOwner
    builds: list[BrokerOwner]
    events: list[str]
    connected_at_record: list[bool]


@pytest.fixture
def broker_session(configured_broker: Path, monkeypatch: pytest.MonkeyPatch) -> BrokerSession:
    """Hand the entrypoint a real owner over a real mock adapter.

    ADR-0017 made start-up open a session, so a test that let the entrypoint
    build what its settings describe would try to reach a MetaTrader 5 terminal
    from the suite. Composition is the only step replaced. Everything after it
    is real — a real :class:`BrokerOwner` sequencing a real ``MockBrokerAdapter``
    — which is the seam ``test_core_broker_ownership.py`` already uses, and
    which takes the adapter's own failure path when the venue is told to refuse.

    ``start``, ``stop`` and the record are wrapped rather than replaced: each
    appends its name and then does the real thing, so ``events`` is the order
    the entrypoint actually called them in and not a restatement of the order it
    was supposed to.

    Returns:
        The adapter and owner the entrypoint will use, and the lists recording
        what it did with them.
    """
    assert configured_broker.exists()
    adapter = MockBrokerAdapter()
    owner = BrokerOwner(adapter)
    builds: list[BrokerOwner] = []
    events: list[str] = []
    connected_at_record: list[bool] = []

    def announcing(step: str, call: Callable[[], None]) -> Callable[[], None]:
        def announced() -> None:
            events.append(step)
            call()

        return announced

    def build(_settings: AtlasSettings) -> BrokerOwner:
        builds.append(owner)
        return owner

    def record(settings: AtlasSettings) -> dict[str, Any]:
        events.append("record")
        connected_at_record.append(adapter.is_connected())
        return build_startup_record(settings)

    monkeypatch.setattr(owner, "start", announcing("start", owner.start))
    monkeypatch.setattr(owner, "stop", announcing("stop", owner.stop))
    monkeypatch.setattr(entrypoint, "build_broker_owner", build)
    monkeypatch.setattr(entrypoint, "build_startup_record", record)
    return BrokerSession(adapter, owner, builds, events, connected_at_record)


class TestBuildStartupRecord:
    def test_record_is_json_serialisable(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_POSTGRES__PASSWORD", "super-secret")

        rendered = json.dumps(build_startup_record(load_settings()))

        assert json.loads(rendered)["event"] == "atlas.core.startup"

    def test_record_never_carries_a_credential(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_POSTGRES__PASSWORD", "super-secret")
        monkeypatch.setenv("ATLAS_REDIS__PASSWORD", "also-secret")

        rendered = json.dumps(build_startup_record(load_settings()))

        assert "super-secret" not in rendered
        assert "also-secret" not in rendered
        assert "***" in rendered

    def test_record_omits_the_broker_section_entirely(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The record gained no key when ``AtlasSettings`` gained a section.

        ATLAS-TASK-0022 left the record untouched: ``risk`` is already a section
        it omits, no rule anywhere says which sections appear, and inventing one
        here would put a live-trading credential a masking bug away from a log
        line. This test is what fails if the section is ever added silently.
        """
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_BROKER__LOGIN", "987654")
        monkeypatch.setenv("ATLAS_BROKER__PASSWORD", "broker-secret")
        monkeypatch.setenv("ATLAS_BROKER__SERVER", "Provider-Demo")

        record = build_startup_record(load_settings())
        rendered = json.dumps(record)

        assert "broker" not in record
        assert "broker-secret" not in rendered
        assert "987654" not in rendered


class TestMain:
    def test_valid_configuration_exits_zero_and_emits_one_json_line(
        self, broker_session: BrokerSession, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert broker_session.adapter.is_connected() is False

        exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == EXIT_OK
        assert captured.err == ""
        record = json.loads(captured.out.strip())
        assert record["event"] == "atlas.core.startup"
        assert record["environment"] == "development"

    def test_invalid_configuration_exits_two_and_reports_on_stderr(
        self,
        isolated_env: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert isolated_env.exists()
        # Production without a database password violates a start-up invariant.
        monkeypatch.setenv("ATLAS_ENV", "production")

        exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == EXIT_CONFIG_ERROR
        assert captured.out == ""
        failure = json.loads(captured.err.strip())
        assert failure["event"] == "atlas.core.startup_failed"
        assert "postgres.password" in failure["error"]


class TestStartUpNeedsABrokerSectionASessionCouldBeOpenedFrom:
    """ADR-0015 moved the refusal from wherever a connection is assembled to here.

    A process whose broker section opens nothing used to start and emit its
    record. It now fails the same way every other configuration failure does,
    through the handler that was already there, and reaches stdout at all only
    once the adapter it describes has been built.
    """

    def test_an_unconfigured_process_fails_before_it_writes_a_record(
        self, isolated_env: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert isolated_env.exists()

        exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == EXIT_CONFIG_ERROR
        assert captured.out == ""
        failure = json.loads(captured.err.strip())
        assert failure["event"] == "atlas.core.startup_failed"

    def test_the_failure_names_the_broker_section_and_the_offending_field(
        self,
        isolated_env: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A deployment has to be told which value to supply, not merely that one is missing."""
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_BROKER__LOGIN", BROKER_LOGIN)
        monkeypatch.setenv("ATLAS_BROKER__TERMINAL_PATH", BROKER_TERMINAL_PATH)

        assert main() == EXIT_CONFIG_ERROR

        failure = json.loads(capsys.readouterr().err.strip())
        assert "broker" in failure["error"]
        assert "server" in failure["error"]

    def test_a_failing_start_up_leaks_no_credential_on_either_stream(
        self,
        isolated_env: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_BROKER__PASSWORD", BROKER_SENTINEL)

        assert main() == EXIT_CONFIG_ERROR

        captured = capsys.readouterr()
        assert BROKER_SENTINEL not in captured.out
        assert BROKER_SENTINEL not in captured.err

    def test_a_process_without_a_password_fails_before_it_writes_a_record(
        self,
        isolated_env: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_BROKER__LOGIN", BROKER_LOGIN)
        monkeypatch.setenv("ATLAS_BROKER__SERVER", BROKER_SERVER)
        monkeypatch.setenv("ATLAS_BROKER__TERMINAL_PATH", BROKER_TERMINAL_PATH)

        exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == EXIT_CONFIG_ERROR
        assert captured.out == ""
        failure = json.loads(captured.err.strip())
        assert failure["event"] == "atlas.core.startup_failed"
        assert "broker" in failure["error"]
        assert "password" in failure["error"]

    def test_a_process_without_a_terminal_path_fails_before_it_writes_a_record(
        self,
        isolated_env: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_BROKER__LOGIN", BROKER_LOGIN)
        monkeypatch.setenv("ATLAS_BROKER__PASSWORD", BROKER_SENTINEL)
        monkeypatch.setenv("ATLAS_BROKER__SERVER", BROKER_SERVER)

        exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == EXIT_CONFIG_ERROR
        assert captured.out == ""
        failure = json.loads(captured.err.strip())
        assert failure["event"] == "atlas.core.startup_failed"
        assert "broker" in failure["error"]
        assert "terminal_path" in failure["error"]

    def test_a_failure_beside_a_valid_password_leaks_no_credential(
        self,
        isolated_env: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Report a different field while a real secret is in hand.

        The password here is the one value that would pass, so the rejected
        model holds a live secret while another field is being reported.
        """
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_BROKER__LOGIN", BROKER_LOGIN)
        monkeypatch.setenv("ATLAS_BROKER__PASSWORD", BROKER_SENTINEL)
        monkeypatch.setenv("ATLAS_BROKER__SERVER", BROKER_SERVER)

        assert main() == EXIT_CONFIG_ERROR

        captured = capsys.readouterr()
        assert captured.out == ""
        assert BROKER_SENTINEL not in captured.err
        assert "SecretStr(" not in captured.err

    def test_a_configured_broker_adds_nothing_to_the_startup_record(
        self, broker_session: BrokerSession, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The record is what ATLAS-TASK-0001 defined, whether or not a broker is configured."""
        assert broker_session.adapter.is_connected() is False

        assert main() == EXIT_OK

        line = capsys.readouterr().out.strip()
        record = json.loads(line)
        assert set(record) == RECORD_KEYS
        assert len(record) == 8
        assert "broker" not in record
        assert BROKER_LOGIN not in line
        assert BROKER_SENTINEL not in line


class TestStartUpOpensASessionVerifiesItAndClosesIt:
    """ADR-0017: opening the session is the check, and the process keeps nothing.

    The record used to mean "these settings describe a session". It now means
    "a session was opened with them and closed again", which is a different and
    stronger claim, and these are the tests that make it the stronger one.
    """

    def test_a_reachable_venue_starts_then_stops_then_records_and_exits_zero(
        self, broker_session: BrokerSession, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The whole decided sequence, in order, from one run."""
        exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == EXIT_OK
        assert broker_session.events == ["start", "stop", "record"]
        assert captured.err == ""
        assert json.loads(captured.out.strip())["event"] == "atlas.core.startup"

    def test_the_record_is_built_only_after_the_session_is_closed(
        self, broker_session: BrokerSession, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Ordering asserted on the session itself, not on the call sequence.

        ``stop`` could be called and still leave a session open. This reads the
        adapter at the moment the record is built, so a record emitted while the
        venue was still connected fails here even if the call order was right.
        """
        assert main() == EXIT_OK

        assert capsys.readouterr().out != ""
        assert broker_session.connected_at_record == [False]
        assert broker_session.adapter.is_connected() is False

    def test_the_owner_is_retained_and_is_the_one_composition_returned(
        self, broker_session: BrokerSession, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Built once, held, and used — not constructed and dropped.

        Before ADR-0017 the entrypoint discarded the owner it built. The events
        below were recorded on the exact instance composition handed back, so an
        entrypoint that dropped it and built its own would record nothing.
        """
        assert main() == EXIT_OK

        assert capsys.readouterr().out != ""
        assert broker_session.builds == [broker_session.owner]
        assert broker_session.events == ["start", "stop", "record"]

    def test_a_refused_session_still_stops_the_owner_and_writes_no_record(
        self, broker_session: BrokerSession, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Cleanup is unconditional, so the failure path runs it too."""
        failure = BrokerConnectionError("the venue refused the session")
        broker_session.adapter.venue.schedule_failure("connect", failure)

        exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == EXIT_BROKER_ERROR
        assert broker_session.events == ["start", "stop"]
        assert broker_session.connected_at_record == []
        assert captured.out == ""

    def test_a_refused_session_exits_three_with_one_json_object_on_stderr(
        self, broker_session: BrokerSession, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A distinct outcome needs a distinct code and a distinct event.

        Exit ``2`` means "fix the configuration". This one means the
        configuration was usable and the venue was not, which no edit to a
        settings file resolves, so it must not arrive wearing the same name.
        """
        broker_session.adapter.venue.schedule_failure(
            "connect", BrokerConnectionError("the venue refused the session")
        )

        exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == EXIT_BROKER_ERROR
        assert exit_code != EXIT_CONFIG_ERROR
        assert len(captured.err.strip().splitlines()) == 1
        failure = json.loads(captured.err.strip())
        assert failure["event"] == BROKER_FAILURE_EVENT
        assert failure["event"] != "atlas.core.startup_failed"
        assert "the venue refused the session" in failure["error"]

    def test_a_refused_session_leaks_no_credential_on_either_stream(
        self, broker_session: BrokerSession, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """ADR-0015's restriction holds on the outcome ADR-0017 added."""
        broker_session.adapter.venue.schedule_failure(
            "connect", BrokerConnectionError(f"refused for {BROKER_LOGIN}")
        )

        assert main() == EXIT_BROKER_ERROR

        captured = capsys.readouterr()
        assert BROKER_SENTINEL not in captured.out
        assert BROKER_SENTINEL not in captured.err
        assert BROKER_TERMINAL_PATH not in captured.err

    def test_one_refusal_ends_the_check_because_nothing_tries_again(
        self, broker_session: BrokerSession, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Exactly one attempt, proved by the venue that would have allowed a second.

        ``schedule_failure`` queues a single refusal, after which the venue
        behaves normally again. Anything that tried twice would spend the refusal
        on the first attempt and succeed on the second, exiting ``0``. The
        connect at the end succeeds against that same venue, which is what makes
        the exit code above a statement about the number of attempts rather than
        about a venue that happened to stay down.
        """
        broker_session.adapter.venue.schedule_failure(
            "connect", BrokerConnectionError("refused once")
        )

        assert main() == EXIT_BROKER_ERROR

        assert capsys.readouterr().out == ""
        assert broker_session.events == ["start", "stop"]
        broker_session.adapter.connect()
        assert broker_session.adapter.is_connected() is True
        broker_session.adapter.disconnect()

    def test_an_unexpected_failure_is_not_swallowed_and_writes_no_record(
        self, broker_session: BrokerSession, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`BrokerError` is handled; anything else leaves by the top of the process.

        The failure is real rather than injected: ``BrokerOwner.start`` raises
        ``RuntimeError`` on a second start, so starting the owner here makes the
        entrypoint's own call the second one. An ``except Exception`` would
        convert that into a JSON record and an exit code — a crash reported as a
        diagnosis nothing actually made — which is what leaving exit `1` to
        CPython avoids. Cleanup still runs on the way out.
        """
        broker_session.owner.start()
        assert broker_session.adapter.is_connected() is True

        with pytest.raises(RuntimeError, match="already started"):
            main()

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""
        assert broker_session.events == ["start", "start", "stop"]
        assert broker_session.adapter.is_connected() is False

    def test_a_configuration_failure_never_reaches_the_venue(
        self,
        isolated_env: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Exit ``2`` is still decided before anything opens a session."""
        assert isolated_env.exists()
        adapter = MockBrokerAdapter()
        monkeypatch.setattr(
            entrypoint, "build_broker_owner", lambda _settings: BrokerOwner(adapter)
        )
        # Production without a database password violates a start-up invariant.
        monkeypatch.setenv("ATLAS_ENV", "production")

        exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == EXIT_CONFIG_ERROR
        assert captured.out == ""
        assert json.loads(captured.err.strip())["event"] == "atlas.core.startup_failed"
        assert adapter.is_connected() is False
