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
from decimal import Decimal
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
    "BrokerSettings",
    "DuckDBSettings",
    "LoggingSettings",
    "PollingSettings",
    "PostgresSettings",
    "RedisSettings",
    "RiskSettings",
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


class RiskSettings(BaseModel):
    """Limits the risk controls enforce.

    ``max_margin_utilisation`` is a ratio rather than a percentage: ``0.5``
    permits new exposure only while pledged margin is below half of equity. The
    comparison is strict, so the default of ``0`` permits nothing at all. That
    is the point — every positive value here is a trading policy, and a default
    that named one would be a policy nobody chose. Absence is not permission,
    and :meth:`AtlasSettings._enforce_production_invariants` is what turns that
    from a convention into a start-up failure where real money is shaped.

    No upper bound is imposed, for the same reason: any bound above zero would
    itself be a policy number. ``allow_inf_nan=False`` is stated explicitly
    because it constrains finiteness rather than magnitude — every finite value
    remains acceptable, ``1E+999999`` included — and because the repository's
    convention is to declare such a flag rather than inherit whichever way a
    framework default happens to fall.
    """

    model_config = _SECTION_CONFIG

    max_margin_utilisation: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        allow_inf_nan=False,
        description=(
            "Maximum portfolio margin/equity ratio, exclusive. Zero permits nothing. "
            "Prefer ATLAS_RISK__MAX_MARGIN_UTILISATION, which converts to Decimal "
            "exactly; a bare TOML number is parsed as a float and loses precision "
            "before this model sees it, so quote a TOML value."
        ),
    )


class BrokerSettings(BaseModel):
    """What a trading session needs in order to be established.

    These four values are restated here in this package's own primitives rather
    than imported from the package that will consume them. ADR-0014 records the
    decision, its reason — the configuration package would otherwise import a
    feature package to learn its own shape — and its cost: two declarations of
    overlapping requirements can drift, and independence is what restating buys.

    The section names types, not a venue. Nothing here says which trading
    connection is assembled, or that one is assembled at all; that question is
    open and is answered somewhere else.

    Every field carries a default, because every section of
    :class:`AtlasSettings` is built by ``default_factory`` and a process holding
    no trading configuration must still resolve its settings. The defaults
    permit nothing all the same: ``0`` is not a usable account number and an
    empty string is not a usable server, so no session can be opened from them.
    Absence is not permission here for the same reason it is not in
    :class:`RiskSettings`. The refusal lands where a connection is assembled
    rather than in this section — and since ATLAS-TASK-0023 that place is
    start-up, because a trading adapter is assembled there unconditionally, in
    every environment. A process whose broker section describes no session that
    could be opened therefore fails at start-up rather than later. ADR-0016
    records that decision and governs which values are refused; this section
    declares the defaults, not the rules.

    The password is a :class:`~pydantic.SecretStr` supplied through the process
    environment, which is the route the other two already use. No file under
    ``config/`` may contain it, and ADR-0003 governs that without amendment.
    """

    model_config = _SECTION_CONFIG

    login: int = Field(
        default=0,
        ge=0,
        description=(
            "Trading account number. Zero is the not-configured default and opens "
            "nothing. Supply ATLAS_BROKER__LOGIN."
        ),
    )
    password: SecretStr = Field(
        default=SecretStr(""),
        description=(
            "Account password, held so it cannot be logged. Supply "
            "ATLAS_BROKER__PASSWORD through the process environment; no file under "
            "config/ may carry it."
        ),
    )
    server: str = Field(
        default="",
        description=(
            "Trade server name, as the account provider publishes it. Empty is the "
            "not-configured default and opens nothing. Supply ATLAS_BROKER__SERVER."
        ),
    )
    terminal_path: Path = Field(
        default=Path(),
        description=(
            "Absolute path to the trading terminal executable. Stated rather than "
            "left to auto-discovery: a host commonly has several terminals "
            "installed, one per account provider, and letting a vendor SDK choose "
            "makes which account Atlas trades a property of the filesystem. Supply "
            "ATLAS_BROKER__TERMINAL_PATH."
        ),
    )


class PollingSettings(BaseModel):
    """The instrument and interval the runtime polls.

    Neither value carries a default that could drive a poll: an empty
    instrument names nothing to observe, and a zero interval is not a cadence.
    Settings must still resolve with these defaults, for the same reason
    :class:`BrokerSettings` does — a process that never runs the runtime has no
    reason to fail on their absence. Absence is not permission here either, and
    the refusal lands where the observer is actually built, in
    :func:`atlas.apps.core.broker_ownership.build_polling_observer`, not here.
    """

    model_config = _SECTION_CONFIG

    instrument: str = Field(
        default="",
        description=(
            "Traded instrument code, exactly as the venue publishes it. Empty "
            "is the not-configured default and refuses at observer construction. "
            "Supply ATLAS_POLLING__INSTRUMENT."
        ),
    )
    poll_interval_seconds: float = Field(
        default=0.0,
        ge=0,
        description=(
            "Minimum gap between the start of one poll cycle and the next, in "
            "seconds. Zero is the not-configured default and refuses at "
            "observer construction. Supply ATLAS_POLLING__POLL_INTERVAL_SECONDS."
        ),
    )


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
    risk: RiskSettings = Field(default_factory=RiskSettings)
    broker: BrokerSettings = Field(default_factory=BrokerSettings)
    polling: PollingSettings = Field(default_factory=PollingSettings)

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
        """Refuse to start a live-shaped process with unsafe settings.

        Three of the four invariants apply to ``production`` alone, which is
        what :attr:`Environment.is_live` means and must keep meaning. The risk
        limit also applies to ``demo``, because demo exists to be
        indistinguishable from production in everything except the money at
        risk — and a risk limit is topology, not money.

        Every violation is collected before any is raised, so a misconfigured
        deployment learns all of them at once rather than one per restart.

        Returns:
            The validated instance.

        Raises:
            ValueError: If an invariant of the resolved environment is violated.
        """
        violations: list[str] = []
        if self.environment.is_live:
            if self.debug:
                violations.append("debug must be false in production")
            if not self.postgres.password.get_secret_value():
                violations.append("postgres.password must be supplied in production")
            if self.logging.format != "json":
                violations.append("logging.format must be 'json' in production")
        if (
            self.environment.is_live or self.environment is Environment.DEMO
        ) and self.risk.max_margin_utilisation <= 0:
            violations.append(
                "risk.max_margin_utilisation must be greater than zero in "
                f"{self.environment.value}"
            )
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
