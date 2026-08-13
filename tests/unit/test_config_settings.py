"""Unit tests for settings resolution, precedence and invariants."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, cast

import pytest
from pydantic import SecretStr, ValidationError

from atlas.config import (
    AtlasSettings,
    ConfigurationError,
    Environment,
    LayeredTomlSource,
    PostgresSettings,
    get_settings,
    load_settings,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic_settings import PydanticBaseSettingsSource

pytestmark = pytest.mark.unit

DEFAULT_LAYER_TOML = """
app_name = "atlas-core"
debug = false

[logging]
level = "INFO"
format = "json"

[postgres]
host = "localhost"
pool_max_size = 10
"""


class TestDefaults:
    def test_settings_resolve_without_any_configuration_source(self, isolated_env: Path) -> None:
        assert isolated_env.exists()
        settings = load_settings()

        assert settings.environment is Environment.DEVELOPMENT
        assert settings.app_name == "atlas-core"
        assert settings.debug is False
        assert settings.logging.level == "INFO"
        assert settings.postgres.port == 5432
        assert settings.redis.database == 0

    def test_settings_are_immutable(self, isolated_env: Path) -> None:
        assert isolated_env.exists()
        settings = load_settings()

        with pytest.raises(ValidationError):
            settings.debug = True  # type: ignore[misc]

    def test_get_settings_returns_the_same_instance(self, isolated_env: Path) -> None:
        assert isolated_env.exists()
        assert get_settings() is get_settings()


class TestEnvironmentVariables:
    def test_scalar_field_is_read_from_the_environment(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_APP_NAME", "atlas-research")

        assert load_settings().app_name == "atlas-research"

    def test_nested_field_uses_the_double_underscore_delimiter(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_POSTGRES__HOST", "db.internal")
        monkeypatch.setenv("ATLAS_POSTGRES__PORT", "6543")

        settings = load_settings()

        assert settings.postgres.host == "db.internal"
        assert settings.postgres.port == 6543

    def test_atlas_env_selects_the_environment(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_ENV", "demo")
        # Demo carries the risk-limit invariant, so selecting it alone no longer
        # resolves. The limit is supplied here to keep this test about selection.
        monkeypatch.setenv("ATLAS_RISK__MAX_MARGIN_UTILISATION", "0.5")

        assert load_settings().environment is Environment.DEMO

    def test_unknown_atlas_variables_are_ignored(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_SOMETHING_UNMODELLED", "value")

        assert load_settings().app_name == "atlas-core"

    def test_an_invalid_environment_name_is_rejected(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_ENV", "staging")

        with pytest.raises(ConfigurationError):
            load_settings()


class TestPrecedence:
    def test_toml_layers_are_applied(
        self, config_tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (config_tree / "default" / "atlas.toml").write_text(DEFAULT_LAYER_TOML, encoding="utf-8")
        monkeypatch.setenv("ATLAS_ENV", "development")

        settings = load_settings()

        assert settings.postgres.pool_max_size == 10
        assert settings.logging.format == "json"

    def test_environment_layer_overrides_the_default_layer(
        self, config_tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (config_tree / "default" / "atlas.toml").write_text(DEFAULT_LAYER_TOML, encoding="utf-8")
        (config_tree / "development" / "atlas.toml").write_text(
            'debug = true\n\n[logging]\nformat = "console"\n', encoding="utf-8"
        )
        monkeypatch.setenv("ATLAS_ENV", "development")

        settings = load_settings()

        assert settings.debug is True
        assert settings.logging.format == "console"
        # Untouched keys survive the overlay.
        assert settings.postgres.pool_max_size == 10

    def test_a_non_selected_layer_is_not_applied(
        self, config_tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (config_tree / "default" / "atlas.toml").write_text(DEFAULT_LAYER_TOML, encoding="utf-8")
        (config_tree / "demo" / "atlas.toml").write_text(
            'app_name = "demo-only"\n', encoding="utf-8"
        )
        monkeypatch.setenv("ATLAS_ENV", "development")

        assert load_settings().app_name == "atlas-core"

    def test_environment_variables_beat_toml_layers(
        self, config_tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (config_tree / "default" / "atlas.toml").write_text(DEFAULT_LAYER_TOML, encoding="utf-8")
        monkeypatch.setenv("ATLAS_ENV", "development")
        monkeypatch.setenv("ATLAS_POSTGRES__HOST", "from-environment")

        assert load_settings().postgres.host == "from-environment"

    def test_explicit_arguments_beat_environment_variables(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_APP_NAME", "from-environment")

        assert load_settings(app_name="explicit").app_name == "explicit"


class TestSecretHandling:
    def test_password_does_not_appear_in_repr(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_POSTGRES__PASSWORD", "super-secret")

        settings = load_settings()

        assert "super-secret" not in repr(settings)
        assert "super-secret" not in str(settings)

    def test_safe_dsn_masks_the_password_and_dsn_exposes_it(self) -> None:
        postgres = PostgresSettings(password=SecretStr("hunter2"))

        assert postgres.safe_dsn == "postgresql://atlas:***@localhost:5432/atlas"
        assert "hunter2" in postgres.dsn

    def test_redis_url_omits_credentials_when_no_password_is_set(self, isolated_env: Path) -> None:
        assert isolated_env.exists()
        settings = load_settings()

        assert settings.redis.url == "redis://localhost:6379/0"
        assert settings.redis.safe_url == "redis://localhost:6379/0"

    def test_redis_safe_url_masks_a_configured_password(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_REDIS__PASSWORD", "topsecret")

        settings = load_settings()

        assert settings.redis.safe_url == "redis://:***@localhost:6379/0"
        assert "topsecret" in settings.redis.url


class TestValidation:
    def test_pool_maximum_below_minimum_is_rejected(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_POSTGRES__POOL_MIN_SIZE", "10")
        monkeypatch.setenv("ATLAS_POSTGRES__POOL_MAX_SIZE", "2")

        with pytest.raises(ConfigurationError, match="pool_max_size"):
            load_settings()

    def test_out_of_range_port_is_rejected(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_POSTGRES__PORT", "70000")

        with pytest.raises(ConfigurationError):
            load_settings()

    def test_malformed_memory_limit_is_rejected(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_DUCKDB__MEMORY_LIMIT", "as much as you can spare")

        with pytest.raises(ConfigurationError):
            load_settings()

    def test_unknown_key_inside_a_section_is_rejected(
        self, config_tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (config_tree / "default" / "atlas.toml").write_text(
            '[postgres]\nhozt = "typo"\n', encoding="utf-8"
        )
        monkeypatch.setenv("ATLAS_ENV", "development")

        with pytest.raises(ConfigurationError):
            load_settings()


class TestProductionInvariants:
    @staticmethod
    def _configure_valid_production(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ATLAS_ENV", "production")
        monkeypatch.setenv("ATLAS_POSTGRES__PASSWORD", "supplied-by-secret-store")
        monkeypatch.setenv("ATLAS_LOGGING__FORMAT", "json")
        monkeypatch.setenv("ATLAS_DEBUG", "false")
        monkeypatch.setenv("ATLAS_RISK__MAX_MARGIN_UTILISATION", "0.5")

    def test_a_correctly_configured_production_process_starts(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        self._configure_valid_production(monkeypatch)

        settings = load_settings()

        assert settings.environment is Environment.PRODUCTION
        assert settings.environment.is_live is True

    def test_debug_is_refused_in_production(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        self._configure_valid_production(monkeypatch)
        monkeypatch.setenv("ATLAS_DEBUG", "true")

        with pytest.raises(ConfigurationError, match="debug must be false"):
            load_settings()

    def test_a_missing_database_password_is_refused_in_production(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        self._configure_valid_production(monkeypatch)
        monkeypatch.setenv("ATLAS_POSTGRES__PASSWORD", "")

        with pytest.raises(ConfigurationError, match=r"postgres\.password"):
            load_settings()

    def test_console_logging_is_refused_in_production(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        self._configure_valid_production(monkeypatch)
        monkeypatch.setenv("ATLAS_LOGGING__FORMAT", "console")

        with pytest.raises(ConfigurationError, match=r"logging\.format"):
            load_settings()

    def test_every_violation_is_reported_at_once(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_ENV", "production")
        monkeypatch.setenv("ATLAS_DEBUG", "true")
        monkeypatch.setenv("ATLAS_LOGGING__FORMAT", "console")

        with pytest.raises(ConfigurationError) as caught:
            load_settings()

        message = str(caught.value)
        assert "debug must be false" in message
        assert "postgres.password" in message
        assert "logging.format" in message

    def test_non_production_environments_are_not_constrained(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_ENV", "development")
        monkeypatch.setenv("ATLAS_DEBUG", "true")
        monkeypatch.setenv("ATLAS_LOGGING__FORMAT", "console")

        settings = load_settings()

        assert settings.debug is True
        assert settings.environment.is_live is False


class TestTheRiskLimitInvariant:
    """The one invariant that covers demo as well as production.

    Demo exists to be indistinguishable from production in everything except the
    money at risk, and a risk limit is topology rather than money. The three
    original invariants are about live credentials and live diagnostics and stay
    where they were.
    """

    def test_production_without_a_limit_refuses_to_start(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_ENV", "production")
        monkeypatch.setenv("ATLAS_POSTGRES__PASSWORD", "supplied-by-secret-store")
        monkeypatch.setenv("ATLAS_LOGGING__FORMAT", "json")

        with pytest.raises(ConfigurationError, match=r"risk\.max_margin_utilisation"):
            load_settings()

    def test_demo_without_a_limit_refuses_to_start(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_ENV", "demo")

        with pytest.raises(ConfigurationError, match=r"risk\.max_margin_utilisation"):
            load_settings()

    def test_a_limit_of_exactly_zero_is_refused_where_it_matters(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Supplying the default explicitly is not supplying a limit."""
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_ENV", "demo")
        monkeypatch.setenv("ATLAS_RISK__MAX_MARGIN_UTILISATION", "0")

        with pytest.raises(ConfigurationError, match=r"risk\.max_margin_utilisation"):
            load_settings()

    def test_development_starts_without_any_risk_configuration(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A development process starts on a limit that permits nothing.

        Refusing to start would make the default useless for local work; the
        control's own strictness is what keeps the default safe.
        """
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_ENV", "development")

        settings = load_settings()

        assert settings.risk.max_margin_utilisation == Decimal("0")

    def test_every_violation_including_the_risk_limit_is_reported_at_once(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_ENV", "production")
        monkeypatch.setenv("ATLAS_DEBUG", "true")
        monkeypatch.setenv("ATLAS_LOGGING__FORMAT", "console")

        with pytest.raises(ConfigurationError) as caught:
            load_settings()

        message = str(caught.value)
        assert "debug must be false" in message
        assert "postgres.password" in message
        assert "logging.format" in message
        assert "risk.max_margin_utilisation" in message

    def test_demo_is_not_constrained_by_the_three_production_invariants(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The test that catches "covering demo" by redefining ``is_live``.

        Widening :attr:`Environment.is_live` to include demo would satisfy the
        risk-limit tests above and silently impose the live-credential rules on
        every demo deployment.
        """
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_ENV", "demo")
        monkeypatch.setenv("ATLAS_RISK__MAX_MARGIN_UTILISATION", "0.5")
        monkeypatch.setenv("ATLAS_DEBUG", "true")
        monkeypatch.setenv("ATLAS_LOGGING__FORMAT", "console")

        settings = load_settings()

        assert settings.environment is Environment.DEMO
        assert settings.environment.is_live is False
        assert Environment.PRODUCTION.is_live is True
        assert settings.debug is True
        assert not settings.postgres.password.get_secret_value()


class TestTheRiskLimitField:
    def test_the_default_is_exactly_zero(self, isolated_env: Path) -> None:
        assert isolated_env.exists()

        assert load_settings().risk.max_margin_utilisation == Decimal("0")

    def test_a_negative_limit_is_rejected(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_RISK__MAX_MARGIN_UTILISATION", "-0.5")

        with pytest.raises(ConfigurationError, match="max_margin_utilisation"):
            load_settings()

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
    def test_a_non_finite_limit_is_rejected(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        """Supplied as a string, which is how an operator would actually get one in."""
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_RISK__MAX_MARGIN_UTILISATION", value)

        with pytest.raises(ConfigurationError, match="max_margin_utilisation"):
            load_settings()

    def test_an_enormous_finite_limit_is_accepted(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """There is no upper bound, and this is the test that fails if one appears.

        Any bound above zero would be a policy number nobody chose.
        """
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_RISK__MAX_MARGIN_UTILISATION", "1E+999999")

        assert load_settings().risk.max_margin_utilisation == Decimal("1E+999999")

    def test_a_quoted_toml_limit_round_trips_exactly(
        self, config_tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (config_tree / "default" / "atlas.toml").write_text(
            '[risk]\nmax_margin_utilisation = "0.30000000000000000001"\n', encoding="utf-8"
        )
        monkeypatch.setenv("ATLAS_ENV", "development")

        limit = load_settings().risk.max_margin_utilisation

        assert limit == Decimal("0.30000000000000000001")

    def test_a_bare_toml_limit_loses_precision_before_the_model_sees_it(
        self, config_tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The operator-facing hazard, asserted rather than merely documented.

        TOML has no decimal type, so ``tomllib`` parses a bare value as a Python
        ``float`` and the digits are gone at parse time — before any validation
        runs. Pydantic's ``float`` to ``Decimal`` conversion is ``str``-mediated
        and adds no binary artefact of its own, so what arrives is a silently
        truncated value rather than a visibly wrong one, which is worse.
        """
        (config_tree / "default" / "atlas.toml").write_text(
            "[risk]\nmax_margin_utilisation = 0.30000000000000000001\n", encoding="utf-8"
        )
        monkeypatch.setenv("ATLAS_ENV", "development")

        limit = load_settings().risk.max_margin_utilisation

        assert limit == Decimal("0.3")
        assert limit != Decimal("0.30000000000000000001")


class TestSettingsSourceWiring:
    def test_the_toml_source_is_ranked_below_the_environment_sources(self) -> None:
        init, env, dotenv, secrets = (_marker() for _ in range(4))

        sources = AtlasSettings.settings_customise_sources(
            AtlasSettings,
            init_settings=init,
            env_settings=env,
            dotenv_settings=dotenv,
            file_secret_settings=secrets,
        )

        assert len(sources) == 5
        # Order is precedence: the TOML layers must sit below every other source.
        assert sources[:4] == (init, env, dotenv, secrets)
        assert isinstance(sources[4], LayeredTomlSource)


def _marker() -> PydanticBaseSettingsSource:
    """Return an identity-comparable stand-in for a settings source."""
    return cast("PydanticBaseSettingsSource", object())
