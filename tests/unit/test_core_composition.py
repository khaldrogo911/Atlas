"""Unit tests for the composition module that builds this process's adapter.

Two properties are worth more than the rest here. The first is that the
translation refuses: ``BrokerSettings`` resolves for a process that holds no
trading configuration, ``MT5Config`` does not, and ADR-0015 decided that the gap
between them stops start-up. The second is that building connects nothing —
asserted in a fresh interpreter, because this one may legitimately have imported
the vendor wheel already in a test that is about the wheel.

The structural properties of the module itself — that it binds nothing at module
scope and caches nothing — are asserted in ``test_core_broker_boundary.py``,
beside the identical assertions about the ownership module and the scanners they
share.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from atlas.apps.core import composition
from atlas.apps.core.broker_ownership import BrokerOwner
from atlas.apps.core.composition import build_broker_owner
from atlas.broker import BrokerNotConnectedError
from atlas.broker.mt5 import MT5BrokerAdapter, MT5Config
from atlas.config import ConfigurationError, load_settings

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.unit

LOGIN = "987654"
SERVER = "Provider-Demo"
TERMINAL_PATH = r"C:\Program Files\Provider MT5\terminal64.exe"
# Named for what it is rather than for what it stands in for: a name carrying
# "password" makes this line a hardcoded-credential finding in every scanner.
SENTINEL = "not-a-real-credential-9f2c1a"
VENDOR_MODULE = "MetaTrader5"

# Exit code the vendor probe uses to say "the module was present". Distinct from
# 1 so that a probe that crashed is not read as a probe that found the wheel.
VENDOR_PRESENT = 3


@pytest.fixture
def broker_env(isolated_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Configure the four values a session cannot be established without.

    Returns:
        The hermetic working directory, which a subprocess inherits as its cwd.
    """
    monkeypatch.setenv("ATLAS_BROKER__LOGIN", LOGIN)
    monkeypatch.setenv("ATLAS_BROKER__PASSWORD", SENTINEL)
    monkeypatch.setenv("ATLAS_BROKER__SERVER", SERVER)
    monkeypatch.setenv("ATLAS_BROKER__TERMINAL_PATH", TERMINAL_PATH)
    return isolated_env


def _config_of(owner: BrokerOwner) -> MT5Config:
    """Read the configuration the owner's adapter was constructed with.

    Reaches through two private members on purpose. The translated values reach
    no public surface — an adapter that has not connected exposes nothing about
    its credentials — and asserting on what was actually built is the only way
    to catch a field silently dropped, renamed or crossed with another.

    Args:
        owner: An owner returned by :func:`build_broker_owner`.

    Returns:
        The configuration the adapter's session holds.
    """
    adapter = owner._adapter
    assert isinstance(adapter, MT5BrokerAdapter)
    return adapter._session._config


def _recording(name: str, log: list[str]) -> Callable[..., object]:
    """Return a stand-in for a constructor that records having been called.

    Args:
        name: What to append to the log when called.
        log: Shared list the caller inspects afterwards.

    Returns:
        A callable accepting anything and returning a placeholder.
    """

    def record(*_args: object, **_kwargs: object) -> object:
        log.append(name)
        return object()

    return record


def _probe(body: str) -> subprocess.CompletedProcess[str]:
    """Run a snippet in a fresh interpreter that inherits this test's isolation.

    Args:
        body: Python source. Exits ``VENDOR_PRESENT`` to report the wheel.

    Returns:
        The completed process, whose return code carries the verdict.
    """
    return subprocess.run(  # noqa: S603  a fixed argument list, no shell
        [sys.executable, "-c", body],
        check=False,
        capture_output=True,
        text=True,
    )


class TestTheTranslationRefusesWhatCannotOpenASession:
    """Where the gap between the two configuration shapes is resolved.

    ``BrokerSettings`` accepts its own not-configured defaults so that settings
    resolve for a process that holds no trading configuration. Every test here
    is a value it accepts and a session cannot be opened from.
    """

    def test_unconfigured_settings_are_refused_and_the_section_is_named(
        self, isolated_env: Path
    ) -> None:
        assert isolated_env.exists()

        with pytest.raises(ConfigurationError) as raised:
            build_broker_owner(load_settings())

        assert "broker" in str(raised.value)

    def test_an_unset_login_is_refused_and_the_field_is_named(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_BROKER__SERVER", SERVER)
        monkeypatch.setenv("ATLAS_BROKER__TERMINAL_PATH", TERMINAL_PATH)

        with pytest.raises(ConfigurationError) as raised:
            build_broker_owner(load_settings())

        assert "login" in str(raised.value)

    def test_an_unset_server_is_refused_and_the_field_is_named(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_BROKER__LOGIN", LOGIN)
        monkeypatch.setenv("ATLAS_BROKER__TERMINAL_PATH", TERMINAL_PATH)

        with pytest.raises(ConfigurationError) as raised:
            build_broker_owner(load_settings())

        assert "server" in str(raised.value)

    def test_the_refusal_carries_no_credential(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A password is set and the rest is not, so the failure sees both."""
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_BROKER__PASSWORD", SENTINEL)

        with pytest.raises(ConfigurationError) as raised:
            build_broker_owner(load_settings())

        reported = str(raised.value)
        assert SENTINEL not in reported
        assert "SecretStr(" not in reported

    def test_an_unset_password_is_refused_and_the_field_is_named(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_BROKER__LOGIN", LOGIN)
        monkeypatch.setenv("ATLAS_BROKER__SERVER", SERVER)
        monkeypatch.setenv("ATLAS_BROKER__TERMINAL_PATH", TERMINAL_PATH)

        with pytest.raises(ConfigurationError) as raised:
            build_broker_owner(load_settings())

        reported = str(raised.value)
        assert "broker" in reported
        assert "password" in reported

    def test_an_unset_terminal_path_is_refused_and_the_field_is_named(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_BROKER__LOGIN", LOGIN)
        monkeypatch.setenv("ATLAS_BROKER__PASSWORD", SENTINEL)
        monkeypatch.setenv("ATLAS_BROKER__SERVER", SERVER)

        with pytest.raises(ConfigurationError) as raised:
            build_broker_owner(load_settings())

        reported = str(raised.value)
        assert "broker" in reported
        assert "terminal_path" in reported

    def test_a_refusal_of_another_field_still_carries_no_credential(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The harder credential case: a real password is present and valid.

        ``test_the_refusal_carries_no_credential`` above fails the password
        itself. Here the password is the one value that would pass, so the error
        Pydantic renders has a live secret in the model it is describing.
        """
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_BROKER__LOGIN", LOGIN)
        monkeypatch.setenv("ATLAS_BROKER__PASSWORD", SENTINEL)
        monkeypatch.setenv("ATLAS_BROKER__SERVER", SERVER)

        with pytest.raises(ConfigurationError) as raised:
            build_broker_owner(load_settings())

        reported = str(raised.value)
        assert "terminal_path" in reported
        assert SENTINEL not in reported
        assert "SecretStr(" not in reported

    def test_nothing_is_constructed_when_the_configuration_is_refused(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Translation precedes construction, so a refusal builds neither object."""
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_BROKER__LOGIN", LOGIN)
        monkeypatch.setenv("ATLAS_BROKER__SERVER", SERVER)
        monkeypatch.setenv("ATLAS_BROKER__TERMINAL_PATH", TERMINAL_PATH)
        built: list[str] = []
        monkeypatch.setattr(composition, "MT5BrokerAdapter", _recording("adapter", built))
        monkeypatch.setattr(composition, "BrokerOwner", _recording("owner", built))

        with pytest.raises(ConfigurationError):
            build_broker_owner(load_settings())

        assert built == []

    def test_the_construction_probe_records_a_build_that_does_happen(
        self, broker_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Prove the construction probe records a build that does happen.

        Patches that are never reached would pass the test above whatever
        ``build_broker_owner`` did with them.
        """
        assert broker_env.exists()
        built: list[str] = []
        monkeypatch.setattr(composition, "MT5BrokerAdapter", _recording("adapter", built))
        monkeypatch.setattr(composition, "BrokerOwner", _recording("owner", built))

        build_broker_owner(load_settings())

        assert built == ["adapter", "owner"]

    def test_a_refused_configuration_opens_no_session(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Run in a fresh interpreter, as the vendor checks in this file are.

        Exit 4 means the configuration was accepted, which would make the rest
        of the assertion meaningless. The control for the probe mechanism itself
        is ``test_the_vendor_probe_can_actually_report_an_import`` below.
        """
        assert isolated_env.exists()
        monkeypatch.setenv("ATLAS_BROKER__LOGIN", LOGIN)
        monkeypatch.setenv("ATLAS_BROKER__SERVER", SERVER)
        monkeypatch.setenv("ATLAS_BROKER__TERMINAL_PATH", TERMINAL_PATH)
        probe = (
            "import sys\n"
            "from atlas.apps.core.composition import build_broker_owner\n"
            "from atlas.config import ConfigurationError, load_settings\n"
            "try:\n"
            "    build_broker_owner(load_settings())\n"
            "except ConfigurationError:\n"
            "    pass\n"
            "else:\n"
            "    sys.exit(4)\n"
            f"sys.exit({VENDOR_PRESENT} if {VENDOR_MODULE!r} in sys.modules else 0)\n"
        )

        result = _probe(probe)

        assert (
            result.returncode == 0
        ), f"a refused configuration reached the vendor: {result.stderr}"


class TestTheOwnerIsBuiltFromTheSettings:
    def test_valid_settings_yield_an_owner_holding_the_selected_implementation(
        self, broker_env: Path
    ) -> None:
        assert broker_env.exists()

        owner = build_broker_owner(load_settings())

        assert isinstance(owner, BrokerOwner)
        assert isinstance(owner._adapter, MT5BrokerAdapter)

    def test_every_translated_value_arrives_intact(self, broker_env: Path) -> None:
        assert broker_env.exists()

        config = _config_of(build_broker_owner(load_settings()))

        assert config.login == int(LOGIN)
        assert config.password.get_secret_value() == SENTINEL
        assert config.server == SERVER
        assert config.terminal_path == Path(TERMINAL_PATH)

    def test_the_password_is_still_held_as_a_secret(self, broker_env: Path) -> None:
        """Translation passes the ``SecretStr`` through; it never unwraps one."""
        assert broker_env.exists()

        config = _config_of(build_broker_owner(load_settings()))

        assert SENTINEL not in repr(config)
        assert SENTINEL not in str(config)

    def test_the_fields_no_setting_corresponds_to_keep_their_defaults(
        self, broker_env: Path
    ) -> None:
        """The test that catches a well-meaning explicit pass-through.

        Nothing in ``BrokerSettings`` describes a timeout, portable mode or a
        server's UTC offset. Supplying any of the three from the application
        would invent a setting, so the translation passes none of them and these
        are the values ``MT5Config`` chose.
        """
        assert broker_env.exists()

        config = _config_of(build_broker_owner(load_settings()))

        assert config.timeout_ms == 60_000
        assert config.portable is False
        assert config.server_utc_offset == timedelta(0)


class TestConstructionIsNotConnection:
    """Building an adapter opens no session and loads no vendor code.

    This is what lets start-up construct the adapter on a host where MetaTrader
    5 is not installed, which every host running these tests other than a
    Windows one is.
    """

    def test_the_owner_is_not_started(self, broker_env: Path) -> None:
        assert broker_env.exists()

        owner = build_broker_owner(load_settings())

        with pytest.raises(BrokerNotConnectedError):
            _ = owner.adapter

    def test_building_an_owner_does_not_import_the_vendor(self, broker_env: Path) -> None:
        """Run in a fresh interpreter, following ``test_mt5_connection.py:522``.

        This interpreter is a poor witness: the wheel installs on Windows, and
        the tests that compare against the real constants import it, so whether
        it is loaded here depends on what ran first.
        """
        assert broker_env.exists()
        probe = (
            "import sys\n"
            "from atlas.apps.core.composition import build_broker_owner\n"
            "from atlas.config import load_settings\n"
            "build_broker_owner(load_settings())\n"
            f"sys.exit({VENDOR_PRESENT} if {VENDOR_MODULE!r} in sys.modules else 0)\n"
        )

        result = _probe(probe)

        assert result.returncode == 0, f"building an owner pulled in a vendor: {result.stderr}"

    def test_the_vendor_probe_can_actually_report_an_import(self) -> None:
        """The control. A probe that cannot fail proves nothing about the test above.

        Asked about a module the interpreter always has, rather than about the
        wheel, so that the control holds on a host where the wheel is absent.
        """
        probe = f"import sys\nsys.exit({VENDOR_PRESENT} if 'sys' in sys.modules else 0)\n"

        result = _probe(probe)

        assert result.returncode == VENDOR_PRESENT
