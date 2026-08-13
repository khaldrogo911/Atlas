"""Behavioural tests for the portfolio margin-utilisation control.

Every test here is hermetic. The control reads its limit from the process's
configuration, so a test that did not pin the environment would pass or fail on
whatever the developer happened to have exported. ``isolated_env`` (via the
:func:`configure_limit` fixture) strips every ``ATLAS_*`` variable, moves into an
empty directory so no stray ``.env`` is discovered, and clears the
``get_settings`` cache on the way in and on the way out.

The cache matters more than it looks. ``get_settings`` is ``lru_cache(maxsize=1)``,
so setting an environment variable after the first call changes nothing until the
cache is cleared. Every helper below that changes configuration clears it, and the
one test that changes the limit mid-body clears it again — without that it would
assert against the value it had already resolved and would pass no matter what the
control did.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, Inexact, Rounded, localcontext
from typing import TYPE_CHECKING, Any

import pytest

from atlas.broker.models import Account, OrderSide
from atlas.config import get_settings, load_settings
from atlas.config import settings as config_settings
from atlas.config.settings import RiskSettings
from atlas.risk import RejectionReason, TradeIntent, VerdictStatus, evaluate_exposure

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

pytestmark = pytest.mark.unit

#: The variable an operator sets to give this process a maximum.
LIMIT_ENV: str = "ATLAS_RISK__MAX_MARGIN_UTILISATION"

#: Fixed instant for every account snapshot. The control never reads it.
SNAPSHOT = datetime(2026, 1, 2, 15, 30, tzinfo=UTC)

#: Precisions the exactness tests sweep.
#:
#: 28 is the interpreter's default and the one a process actually runs at; 3 and
#: 10 are low enough to round the disqualified product formulation onto the wrong
#: side of the limit; 60 is high enough to show the answer does not drift back.
PRECISIONS = (3, 10, 28, 60)


def _fields(margin: Decimal, equity: Decimal, free_margin: Decimal) -> dict[str, Any]:
    """Return a complete set of ``Account`` field values."""
    return {
        "account_id": "5000123",
        "broker": "Test Broker",
        "server": "Test-Server-Demo",
        "currency": "USD",
        "balance": equity,
        "equity": equity,
        "margin": margin,
        "free_margin": free_margin,
        "margin_level": None,
        "leverage": 30,
        "trade_allowed": True,
        "timestamp": SNAPSHOT,
    }


def _account(margin: Decimal, equity: Decimal) -> Account:
    """Return a validated account snapshot carrying the two amounts under test."""
    return Account(**_fields(margin, equity, equity - margin))


def _unvalidated_account(margin: Decimal, equity: Decimal) -> Account:
    """Return an account snapshot that validation would refuse.

    ``model_construct`` skips validation entirely, and that is the point rather
    than a shortcut: ``margin`` and ``equity`` reject ``NaN`` and ``±Infinity``,
    so a test built through the constructor could never reach the control's
    finiteness guard. Nothing in the running system builds an ``Account`` this
    way; the guard exists because ``model_construct`` is public API and because
    the control may not rely on a guarantee it is forbidden to strengthen.

    ``free_margin`` is held at zero rather than derived, because deriving it
    would perform arithmetic on a non-finite amount inside the test helper and
    raise before the control was ever called.
    """
    return Account.model_construct(**_fields(margin, equity, Decimal("0")))


def _intent(volume: str = "1.00") -> TradeIntent:
    """Return an intent for the given requested volume."""
    return TradeIntent(symbol="EURUSD", side=OrderSide.BUY, requested_volume=Decimal(volume))


@pytest.fixture
def configure_limit(isolated_env: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
    """Return a callable that sets this process's configured maximum.

    Args:
        isolated_env: The hermetic environment every test in this file runs in.
        monkeypatch: Used to set the variable for the duration of the test.

    Returns:
        A callable taking the limit as the string an operator would export.
    """
    assert isolated_env.exists()

    def _configure(value: str) -> None:
        monkeypatch.setenv(LIMIT_ENV, value)
        get_settings.cache_clear()

    return _configure


def _force_unvalidatable_limit(monkeypatch: pytest.MonkeyPatch, limit: Decimal) -> None:
    """Configure a limit the settings model would refuse.

    ``allow_inf_nan=False`` means a non-finite limit cannot arrive through the
    environment, so reaching the control's finiteness guard takes
    ``model_construct``. The stub is installed *beneath* ``get_settings`` rather
    than in place of it, so the path the control actually walks —
    ``get_settings().risk.max_margin_utilisation`` — is the real one.

    Args:
        monkeypatch: Used to replace the loader for the duration of the test.
        limit: The non-finite limit to install.
    """
    settings = load_settings().model_copy(
        update={"risk": RiskSettings.model_construct(max_margin_utilisation=limit)}
    )
    monkeypatch.setattr(config_settings, "load_settings", lambda **_: settings)
    get_settings.cache_clear()


class TestTheVerdict:
    def test_utilisation_below_the_limit_approves_the_intent_unchanged(
        self, configure_limit: Callable[[str], None]
    ) -> None:
        configure_limit("0.5")
        intent = _intent("1.00")

        verdict = evaluate_exposure(intent, _account(Decimal("30000"), Decimal("100000")))

        assert verdict.status is VerdictStatus.APPROVED
        assert verdict.approved_volume == intent.requested_volume
        assert verdict.is_reduced is False
        assert verdict.reason is None

    def test_utilisation_above_the_limit_is_rejected(
        self, configure_limit: Callable[[str], None]
    ) -> None:
        configure_limit("0.5")

        verdict = evaluate_exposure(_intent(), _account(Decimal("60000"), Decimal("100000")))

        assert verdict.status is VerdictStatus.REJECTED
        assert verdict.reason is RejectionReason.EXPOSURE_LIMIT
        assert verdict.approved_volume is None
        assert verdict.detail

    def test_utilisation_exactly_at_the_limit_is_rejected(
        self, configure_limit: Callable[[str], None]
    ) -> None:
        """The comparison is strict: reaching the maximum is not being below it."""
        configure_limit("0.5")

        verdict = evaluate_exposure(_intent(), _account(Decimal("50000"), Decimal("100000")))

        assert verdict.status is VerdictStatus.REJECTED
        assert verdict.reason is RejectionReason.EXPOSURE_LIMIT

    def test_the_verdict_carries_the_intent_it_judged(
        self, configure_limit: Callable[[str], None]
    ) -> None:
        configure_limit("0.5")
        intent = _intent("0.37")

        approved = evaluate_exposure(intent, _account(Decimal("10000"), Decimal("100000")))
        rejected = evaluate_exposure(intent, _account(Decimal("90000"), Decimal("100000")))

        assert approved.intent is intent
        assert rejected.intent is intent

    def test_the_default_limit_permits_nothing_at_all(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A flat account is refused when no maximum has been configured.

        Absence is not permission. This is also the test that fails if the strict
        comparison is weakened: zero margin over positive equity is exactly the
        default limit, and ``<=`` would approve it.
        """
        assert isolated_env.exists()
        monkeypatch.delenv(LIMIT_ENV, raising=False)
        get_settings.cache_clear()

        assert get_settings().risk.max_margin_utilisation == Decimal("0")

        verdict = evaluate_exposure(_intent(), _account(Decimal("0"), Decimal("100000")))

        assert verdict.status is VerdictStatus.REJECTED
        assert verdict.reason is RejectionReason.EXPOSURE_LIMIT


class TestAnUnusableAccountStateFailsClosed:
    """Neither guard raises.

    A control that threw where it was asked to judge would be bypassable by an
    exception handler one layer up.
    """

    @pytest.mark.parametrize("equity", ["0", "-1000"], ids=["blown-flat", "negative"])
    def test_non_positive_equity_is_rejected_without_raising(
        self, configure_limit: Callable[[str], None], equity: str
    ) -> None:
        configure_limit("0.5")

        verdict = evaluate_exposure(_intent(), _account(Decimal("100"), Decimal(equity)))

        assert verdict.status is VerdictStatus.REJECTED
        assert verdict.reason is RejectionReason.EXPOSURE_LIMIT
        assert verdict.detail

    @pytest.mark.parametrize("amount", ["NaN", "Infinity", "-Infinity"])
    def test_a_non_finite_equity_is_rejected_without_raising(
        self, configure_limit: Callable[[str], None], amount: str
    ) -> None:
        configure_limit("0.5")

        verdict = evaluate_exposure(
            _intent(), _unvalidated_account(Decimal("100"), Decimal(amount))
        )

        assert verdict.status is VerdictStatus.REJECTED
        assert verdict.reason is RejectionReason.EXPOSURE_LIMIT

    @pytest.mark.parametrize("amount", ["NaN", "Infinity"])
    def test_a_non_finite_margin_is_rejected_without_raising(
        self, configure_limit: Callable[[str], None], amount: str
    ) -> None:
        configure_limit("0.5")

        verdict = evaluate_exposure(
            _intent(), _unvalidated_account(Decimal(amount), Decimal("100000"))
        )

        assert verdict.status is VerdictStatus.REJECTED
        assert verdict.reason is RejectionReason.EXPOSURE_LIMIT

    @pytest.mark.parametrize("amount", ["NaN", "Infinity", "-Infinity"])
    def test_a_non_finite_configured_limit_is_rejected_without_raising(
        self, isolated_env: Path, monkeypatch: pytest.MonkeyPatch, amount: str
    ) -> None:
        assert isolated_env.exists()
        _force_unvalidatable_limit(monkeypatch, Decimal(amount))

        verdict = evaluate_exposure(_intent(), _account(Decimal("100"), Decimal("100000")))

        assert verdict.status is VerdictStatus.REJECTED
        assert verdict.reason is RejectionReason.EXPOSURE_LIMIT


class TestTheTwoRefusalsAreDistinguishable:
    """The only test that detects the removal of a guard.

    Both guards reject, and the exact comparison of §7.10 rejects a non-positive
    or non-finite state too, so deleting either one changes no ``status`` and no
    ``reason``. What it changes is the ``detail``: the two refusals stop being
    told apart. The assertion is on the difference, never on a literal message —
    the wording belongs to the implementation.
    """

    def test_an_unusable_state_reads_differently_from_a_limit_breach(
        self, configure_limit: Callable[[str], None]
    ) -> None:
        configure_limit("0.5")

        breach = evaluate_exposure(_intent(), _account(Decimal("90000"), Decimal("100000")))
        unusable = evaluate_exposure(_intent(), _account(Decimal("100"), Decimal("0")))

        assert breach.status is unusable.status is VerdictStatus.REJECTED
        assert breach.reason is unusable.reason is RejectionReason.EXPOSURE_LIMIT
        assert breach.detail != unusable.detail

    def test_a_non_finite_state_reads_differently_from_a_limit_breach(
        self, configure_limit: Callable[[str], None]
    ) -> None:
        configure_limit("0.5")

        breach = evaluate_exposure(_intent(), _account(Decimal("90000"), Decimal("100000")))
        unusable = evaluate_exposure(
            _intent(), _unvalidated_account(Decimal("100"), Decimal("NaN"))
        )

        assert breach.status is unusable.status is VerdictStatus.REJECTED
        assert breach.reason is unusable.reason is RejectionReason.EXPOSURE_LIMIT
        assert breach.detail != unusable.detail


class TestTheComparisonIsExact:
    """Two cases, chosen because they are the ones that discriminate.

    Round numbers prove nothing here: the exact comparison, ``margin < limit *
    equity`` and ``margin / equity < limit`` all agree on them. Each case below
    is one on which a disqualified formulation gives the wrong answer.
    """

    @pytest.mark.parametrize("precision", PRECISIONS)
    def test_a_product_that_rounds_onto_the_limit_still_approves(
        self, configure_limit: Callable[[str], None], precision: int
    ) -> None:
        """``margin < limit * equity`` rejects this at ``prec`` 10 and below."""
        configure_limit("0.30000000000000000001")
        account = _account(Decimal("30000.000000000000000001"), Decimal("100000"))

        with localcontext() as context:
            context.prec = precision
            verdict = evaluate_exposure(_intent(), account)

        assert verdict.status is VerdictStatus.APPROVED

    @pytest.mark.parametrize("precision", PRECISIONS)
    def test_a_quotient_that_rounds_past_the_limit_still_rejects(
        self, configure_limit: Callable[[str], None], precision: int
    ) -> None:
        """``margin / equity < limit`` approves this at the *default* precision."""
        configure_limit("0." + "3" * 33)
        account = _account(Decimal("1"), Decimal("3"))

        with localcontext() as context:
            context.prec = precision
            verdict = evaluate_exposure(_intent(), account)

        assert verdict.status is VerdictStatus.REJECTED

    def test_no_decimal_arithmetic_survives_in_the_comparison_path(
        self, configure_limit: Callable[[str], None]
    ) -> None:
        """A context that raises on any rounding at all changes nothing.

        ``prec=1`` with ``Inexact`` and ``Rounded`` trapped is a context designed
        to make rounding impossible to miss: any ``Decimal`` operation that has
        to round raises instead of returning. The settings object is resolved
        first, outside the context, because what is under test is the control's
        comparison — a trap firing inside Pydantic's own parser would be a
        finding about Pydantic.
        """
        configure_limit("0." + "3" * 33)
        account = _account(Decimal("1"), Decimal("3"))
        get_settings()

        with localcontext() as context:
            context.prec = 1
            context.traps[Inexact] = True
            context.traps[Rounded] = True
            verdict = evaluate_exposure(_intent(), account)

        assert verdict.status is VerdictStatus.REJECTED

    def test_an_enormous_finite_limit_returns_a_verdict_rather_than_raising(
        self, configure_limit: Callable[[str], None]
    ) -> None:
        """The boundary of "no upper bound".

        ``margin < limit * equity`` raises ``decimal.Overflow`` here at every
        precision, because ``Emax`` is 999999 and the default context traps it.
        The exact form has no exponent limit to exceed. This case is slow — the
        limit's numerator is a million-digit integer, so the multiplication costs
        a few tenths of a second — and that is the price of totality at a value
        no sane deployment will choose. It is not a hang.
        """
        configure_limit("1E+999999")

        verdict = evaluate_exposure(_intent(), _account(Decimal("30000"), Decimal("100000")))

        assert verdict.status is VerdictStatus.APPROVED


class TestDocumentedLimitations:
    def test_the_verdict_does_not_depend_on_the_requested_volume(
        self, configure_limit: Callable[[str], None]
    ) -> None:
        """Not an oversight: ADR-0012 forbids asking the venue what an intent costs.

        The control judges the exposure the account already carries, so a
        0.01-lot intent and a 100-lot intent against the same account get the
        same answer. The module's own documentation says so, and this test is
        what keeps the two statements together.
        """
        configure_limit("0.5")
        account = _account(Decimal("30000"), Decimal("100000"))

        small = evaluate_exposure(_intent("0.01"), account)
        large = evaluate_exposure(_intent("100.00"), account)

        assert small.status is large.status
        assert small.reason is large.reason
        assert small.approved_volume == Decimal("0.01")
        assert large.approved_volume == Decimal("100.00")


class TestTheLimitIsReadNotHeld:
    def test_a_changed_limit_changes_the_next_verdict(
        self, configure_limit: Callable[[str], None]
    ) -> None:
        """The control captured nothing at import time.

        What makes the second call observe the change is the ``cache_clear`` the
        fixture performs: ``get_settings`` is cached for the life of the process,
        so this does **not** show that the environment is re-read per call, and
        must not be read as showing it. What it shows is that the control holds
        no limit of its own — it uses whatever the currently-resolved settings
        say.
        """
        account = _account(Decimal("30000"), Decimal("100000"))

        configure_limit("0.5")
        permissive = evaluate_exposure(_intent(), account)
        configure_limit("0.1")
        restrictive = evaluate_exposure(_intent(), account)

        assert permissive.status is VerdictStatus.APPROVED
        assert restrictive.status is VerdictStatus.REJECTED
