"""Layered, environment-driven configuration for Project Atlas.

This package owns every configuration concern in the platform: locating the
``config/`` tree, merging its TOML layers, overlaying environment variables,
and exposing the result as a validated, immutable, fully typed object.

Example:
    >>> from atlas.config import get_settings
    >>> settings = get_settings()
    >>> settings.postgres.safe_dsn
    'postgresql://atlas:***@localhost:5432/atlas'
"""

from __future__ import annotations

from atlas.config.environment import Environment
from atlas.config.errors import ConfigurationError
from atlas.config.paths import (
    CONFIG_DIR_ENV_VAR,
    DEFAULT_LAYER,
    ENVIRONMENT_ENV_VAR,
    resolve_config_dir,
)
from atlas.config.settings import (
    AtlasSettings,
    DuckDBSettings,
    LoggingSettings,
    PostgresSettings,
    RedisSettings,
    get_settings,
    load_settings,
)
from atlas.config.sources import LayeredTomlSource, deep_merge, load_layer

__all__ = [
    "CONFIG_DIR_ENV_VAR",
    "DEFAULT_LAYER",
    "ENVIRONMENT_ENV_VAR",
    "AtlasSettings",
    "ConfigurationError",
    "DuckDBSettings",
    "Environment",
    "LayeredTomlSource",
    "LoggingSettings",
    "PostgresSettings",
    "RedisSettings",
    "deep_merge",
    "get_settings",
    "load_layer",
    "load_settings",
    "resolve_config_dir",
]
