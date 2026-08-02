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


class TestMain:
    def test_valid_configuration_exits_zero_and_emits_one_json_line(
        self, isolated_env: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert isolated_env.exists()

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
