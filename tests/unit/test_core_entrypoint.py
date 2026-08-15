"""Unit tests for the atlas-core process entrypoint."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from atlas.apps.core.__main__ import EXIT_CONFIG_ERROR, EXIT_OK, build_startup_record, main
from atlas.config import load_settings

if TYPE_CHECKING:
    from pathlib import Path

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
        self, configured_broker: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert configured_broker.exists()

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
        self, configured_broker: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The record is what ATLAS-TASK-0001 defined, whether or not a broker is configured."""
        assert configured_broker.exists()

        assert main() == EXIT_OK

        line = capsys.readouterr().out.strip()
        record = json.loads(line)
        assert set(record) == RECORD_KEYS
        assert "broker" not in record
        assert BROKER_LOGIN not in line
        assert BROKER_SENTINEL not in line
