"""Unit tests for configuration directory discovery."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from atlas.config import CONFIG_DIR_ENV_VAR, ConfigurationError, resolve_config_dir

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit


def test_explicit_override_is_used_verbatim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    explicit = tmp_path / "somewhere" / "config"
    explicit.mkdir(parents=True)
    monkeypatch.setenv(CONFIG_DIR_ENV_VAR, str(explicit))

    assert resolve_config_dir() == explicit


def test_override_pointing_at_a_missing_directory_fails_loudly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(CONFIG_DIR_ENV_VAR, str(tmp_path / "does-not-exist"))

    with pytest.raises(ConfigurationError, match="not a directory"):
        resolve_config_dir()


def test_override_pointing_at_a_file_fails_loudly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "config.toml"
    target.write_text("", encoding="utf-8")
    monkeypatch.setenv(CONFIG_DIR_ENV_VAR, str(target))

    with pytest.raises(ConfigurationError, match="not a directory"):
        resolve_config_dir()


def test_blank_override_falls_through_to_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(CONFIG_DIR_ENV_VAR, "   ")
    monkeypatch.chdir(tmp_path)

    assert resolve_config_dir() is None


def test_discovery_walks_up_to_the_repository_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(CONFIG_DIR_ENV_VAR, raising=False)
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "config").mkdir()
    nested = tmp_path / "apps" / "atlas-core"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    assert resolve_config_dir() == tmp_path / "config"


def test_repository_root_without_a_config_tree_yields_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(CONFIG_DIR_ENV_VAR, raising=False)
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert resolve_config_dir() is None


def test_the_repository_itself_is_discoverable(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(CONFIG_DIR_ENV_VAR, raising=False)
    monkeypatch.chdir(repo_root)

    assert resolve_config_dir() == repo_root / "config"
