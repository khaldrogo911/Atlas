"""Shared fixtures for the Project Atlas test suite."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from atlas.config import get_settings

if TYPE_CHECKING:
    from collections.abc import Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the repository root."""
    return REPO_ROOT


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """Run a test in a hermetic configuration environment.

    Clears every ``ATLAS_*`` variable, moves into an empty working directory so
    no ``.env`` is picked up, and pins ``ATLAS_CONFIG_DIR`` at an empty tree so
    that configuration discovery cannot reach a real repository above the
    temporary directory. Settings therefore resolve to field defaults unless a
    test says otherwise.

    Yields:
        The temporary working directory.
    """
    for key in list(os.environ):
        if key.startswith("ATLAS_"):
            monkeypatch.delenv(key, raising=False)

    empty_config = tmp_path / "empty-config"
    empty_config.mkdir()
    monkeypatch.setenv("ATLAS_CONFIG_DIR", str(empty_config))
    monkeypatch.chdir(tmp_path)

    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture
def config_tree(isolated_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide a writable, empty layered configuration tree.

    Args:
        isolated_env: The hermetic working directory.
        monkeypatch: Used to repoint ``ATLAS_CONFIG_DIR`` at the new tree.

    Returns:
        The configuration directory, containing one empty layer per environment.
    """
    root = isolated_env / "config"
    for layer in ("default", "development", "demo", "production"):
        (root / layer).mkdir(parents=True)
    monkeypatch.setenv("ATLAS_CONFIG_DIR", str(root))
    return root
