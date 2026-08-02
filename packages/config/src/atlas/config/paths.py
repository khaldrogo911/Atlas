"""Discovery of the layered configuration tree on disk.

Resolution order:

1. ``ATLAS_CONFIG_DIR`` — an explicit absolute path. If set but not a
   directory, resolution fails loudly rather than silently falling back.
2. The nearest ancestor of the current working directory that contains both
   ``pyproject.toml`` and a ``config/`` directory.

Discovery deliberately starts from the working directory rather than from this
module's location: once installed into ``site-packages`` the module path says
nothing about where the deployment's configuration lives.
"""

from __future__ import annotations

import os
from pathlib import Path

from atlas.config.errors import ConfigurationError

__all__ = [
    "CONFIG_DIR_ENV_VAR",
    "DEFAULT_LAYER",
    "ENVIRONMENT_ENV_VAR",
    "resolve_config_dir",
]

CONFIG_DIR_ENV_VAR = "ATLAS_CONFIG_DIR"
"""Environment variable holding an explicit configuration directory path."""

ENVIRONMENT_ENV_VAR = "ATLAS_ENV"
"""Environment variable selecting the configuration layer to overlay."""

DEFAULT_LAYER = "default"
"""Name of the base layer applied beneath every environment layer."""

_ROOT_MARKER = "pyproject.toml"
_CONFIG_DIR_NAME = "config"


def _discover_from(start: Path) -> Path | None:
    """Walk upwards from *start* looking for a repository-local config tree.

    Args:
        start: Directory to begin the upward search from.

    Returns:
        The discovered ``config/`` directory, or ``None`` if no ancestor of
        *start* is a repository root carrying one.
    """
    for candidate in (start, *start.parents):
        if not (candidate / _ROOT_MARKER).is_file():
            continue
        config_dir = candidate / _CONFIG_DIR_NAME
        if config_dir.is_dir():
            return config_dir
    return None


def resolve_config_dir() -> Path | None:
    """Locate the layered configuration directory.

    Returns:
        The configuration directory, or ``None`` when the process runs without
        a configuration tree (settings then come from environment variables and
        field defaults alone).

    Raises:
        ConfigurationError: If ``ATLAS_CONFIG_DIR`` is set to a path that is
            not an existing directory.
    """
    override = os.environ.get(CONFIG_DIR_ENV_VAR, "").strip()
    if override:
        path = Path(override).expanduser()
        if not path.is_dir():
            msg = f"{CONFIG_DIR_ENV_VAR} points at {path!s}, which is not a directory"
            raise ConfigurationError(msg)
        return path
    return _discover_from(Path.cwd())
