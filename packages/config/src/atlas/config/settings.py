"""Typed, immutable application settings for Project Atlas.

Precedence, highest first:

1. Values passed explicitly to :class:`AtlasSettings`.
2. Process environment variables (``ATLAS_`` prefix, ``__`` nesting delimiter).
3. The ``.env`` file, when present.
4. ``config/<environment>/*.toml``.
5. ``config/default/*.toml``.
6. Field defaults declared below.

Nothing in this module hardcodes a secret. Credentials are typed as
:class:`~pydantic.SecretStr` so that they do not leak through ``repr``,
structured logs, or tracebacks.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic import ValidationError as PydanticValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from atlas.config.environment import Environment
from atlas.config.errors import ConfigurationError
from atlas.config.paths import DEFAULT_LAYER, ENVIRONMENT_ENV_VAR, resolve_config_dir
from atlas.config.sources import LayeredTomlSource

if TYPE_CHECKING:
    from pydantic_settings import PydanticBaseSettingsSource

__all__ = [
    "AtlasSettings",
    "DuckDBSettings",
    "LoggingSettings",
    "PostgresSettings",
    "RedisSettings",
    "get_settings",
    "load_settings",
]

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["json", "console"]

_MEMORY_LIMIT_PATTERN = r"^\d+(\.\d+)?(KB|MB|GB|TB)$"
_SECTION_CONFIG = ConfigDict(frozen=True, extra="forbid")


class LoggingSettings(BaseModel):
    """How the process emits diagnostics."""

    model_config = _SECTION_CONFIG

    level: LogLevel = "INFO"
    format: LogFormat = "json"


class PostgresSettings(BaseModel):
    """Connection parameters for the PostgreSQL system of record."""

    model_config = _SECTION_CONFIG

    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = "atlas"
    user: str = "atlas"
    password: SecretStr = SecretStr("")
    pool_min_size: int = Field(default=1, ge=0)
    pool_max_size: int = Field(default=10, ge=1)

    @model_validator(mode="after")
    def _check_pool_bounds(self) -> PostgresSettings:
        """Reject pool bounds that can never be satisfied.

        Returns:
            The validated instance.

        Raises:
            ValueError: If the maximum pool size is below the minimum.
        """
        if self.pool_max_size < self.pool_min_size:
            msg = (
                f"pool_max_size ({self.pool_max_size}) must be greater than or equal to "
                f"pool_min_size ({self.pool_min_size})"
            )
            raise ValueError(msg)
        return self

    @property
    def dsn(self) -> str:
        """A libpq connection string including the password.

        Never log this value; use :attr:`safe_dsn` for diagnostics.
        """
        return (
            f"postgresql://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    @property
    def safe_dsn(self) -> str:
        """A libpq connection string with the password masked."""
        return f"postgresql://{self.user}:***@{self.host}:{self.port}/{self.database}"


class RedisSettings(BaseModel):
    """Connection parameters for Redis."""

    model_config = _SECTION_CONFIG

    host: str = "localhost"
    port: int = Field(default=6379, ge=1, le=65535)
    database: int = Field(default=0, ge=0)
    password: SecretStr = SecretStr("")

    @property
    def url(self) -> str:
        """A Redis URL including the password when one is configured.

        Never log this value; use :attr:`safe_url` for diagnostics.
        """
        secret = self.password.get_secret_value()
        credentials = f":{secret}@" if secret else ""
        return f"redis://{credentials}{self.host}:{self.port}/{self.database}"

    @property
    def safe_url(self) -> str:
        """A Redis URL with any password masked."""
        credentials = ":***@" if self.password.get_secret_value() else ""
        return f"redis://{credentials}{self.host}:{self.port}/{self.database}"


class DuckDBSettings(BaseModel):
    """Location and limits for the DuckDB analytical store."""

    model_config = _SECTION_CONFIG

    path: Path = Path("./data/atlas.duckdb")
    read_only: bool = False
    memory_limit: str = Field(default="4GB", pattern=_MEMORY_LIMIT_PATTERN)


class AtlasSettings(BaseSettings):
    """Root settings object for every Project Atlas process."""

    model_config = SettingsConfigDict(
        env_prefix="ATLAS_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        validate_default=True,
        frozen=True,
        # Unknown ATLAS_* variables (ATLAS_CONFIG_DIR among them) are consumed
        # outside the model, so extras must not be an error here.
        extra="ignore",
    )

    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        validation_alias=AliasChoices("ATLAS_ENV", "ATLAS_ENVIRONMENT"),
    )
    app_name: str = "atlas-core"
    debug: bool = False

    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    duckdb: DuckDBSettings = Field(default_factory=DuckDBSettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Append the layered TOML source beneath the environment sources.

        Args:
            settings_cls: The settings class being built.
            init_settings: Values passed to the constructor.
            env_settings: Process environment variables.
            dotenv_settings: Values read from ``.env``.
            file_secret_settings: Values read from a secrets directory.

        Returns:
            The active sources, highest precedence first.
        """
        config_dir = resolve_config_dir()
        toml_source = LayeredTomlSource(settings_cls, layers=_layer_paths(config_dir))
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            toml_source,
        )

    @model_validator(mode="after")
    def _enforce_production_invariants(self) -> AtlasSettings:
        """Refuse to start a production process with unsafe settings.

        Returns:
            The validated instance.

        Raises:
            ValueError: If a production-only invariant is violated.
        """
        if not self.environment.is_live:
            return self
        violations: list[str] = []
        if self.debug:
            violations.append("debug must be false in production")
        if not self.postgres.password.get_secret_value():
            violations.append("postgres.password must be supplied in production")
        if self.logging.format != "json":
            violations.append("logging.format must be 'json' in production")
        if violations:
            msg = "; ".join(violations)
            raise ValueError(msg)
        return self


def _layer_paths(config_dir: Path | None) -> tuple[Path, ...]:
    """Build the ordered layer directories for the active environment.

    Args:
        config_dir: Root of the configuration tree, or ``None``.

    Returns:
        Layer directories, lowest precedence first. Empty when *config_dir* is
        ``None`` or the ``ATLAS_ENV`` value does not name a known environment;
        in the latter case validation of the ``environment`` field reports the
        error, so this helper stays silent.
    """
    if config_dir is None:
        return ()
    layers = [config_dir / DEFAULT_LAYER]
    raw = os.environ.get(ENVIRONMENT_ENV_VAR, Environment.DEVELOPMENT.value).strip().lower()
    try:
        environment = Environment(raw)
    except ValueError:
        return tuple(layers)
    layers.append(config_dir / environment.value)
    return tuple(layers)


def load_settings(**overrides: Any) -> AtlasSettings:  # noqa: ANN401
    """Resolve settings from every source, validating eagerly.

    Args:
        **overrides: Values that take precedence over all other sources. Used
            by tests and by administrative scripts; production processes call
            :func:`get_settings` with no arguments. Genuinely ``Any``: the
            accepted types are those of every settings field.

    Returns:
        A fully validated, immutable settings object.

    Raises:
        ConfigurationError: If any source is unreadable or the resolved
            settings violate an invariant.
    """
    try:
        return AtlasSettings(**overrides)
    except PydanticValidationError as exc:
        msg = f"invalid Atlas configuration:\n{exc}"
        raise ConfigurationError(msg) from exc


@lru_cache(maxsize=1)
def get_settings() -> AtlasSettings:
    """Return the process-wide settings singleton.

    The result is cached for the lifetime of the process. Tests that mutate the
    environment must call ``get_settings.cache_clear()`` first.

    Returns:
        The shared settings object.

    Raises:
        ConfigurationError: If configuration cannot be resolved.
    """
    return load_settings()
