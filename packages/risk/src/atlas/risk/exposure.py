"""The portfolio margin-utilisation limit — the first control in :mod:`atlas.risk`.

One function, one metric: portfolio ``Account.margin`` over ``Account.equity``,
compared against the maximum this process is configured to permit. Below the
maximum the intent is approved unchanged; at or above it, or on an account state
the metric is undefined on, it is rejected with
:attr:`~atlas.risk.RejectionReason.EXPOSURE_LIMIT`. There is no third answer and
no reduction path — risk approves what was asked for or refuses it.

Five decisions are load bearing:

The verdict does not depend on the size of the intent
    ADR-0012 forbids risk from calling the port, so this control cannot ask what
    the intent would cost in margin. It judges the exposure the account
    *already* carries. A 0.01-lot intent and a 100-lot intent against the same
    ``Account`` therefore receive the same answer. That is a real limitation of
    a portfolio-level control that may not consult the venue, and it is written
    here rather than left for a reader to discover from the code.

The limit is read, never held
    The maximum is read from the process's configuration on every call and is
    not an argument. Nothing here caches a settings object, a section or a
    limit, and nothing is captured at import time, so the control always uses
    whatever the process's currently-resolved settings say. It reads exactly one
    value — its own maximum — and nothing else in the settings tree. It never
    reads a database password, a Redis credential or a connection string, and
    ``tests/unit/risk/test_risk_boundary.py`` enforces that by scanning this
    module rather than by trusting this sentence.

The comparison is exact integer arithmetic, not decimal arithmetic
    ``margin / equity < limit`` rounds the quotient to the ambient decimal
    context and can round *onto* or *past* the limit — at the interpreter's
    default precision it approves cases that should reject. ``margin < limit *
    equity`` rounds the product instead, and raises ``decimal.Overflow`` on a
    large finite limit. Both are wrong for the same underlying reason: they
    borrow a precision from a context nothing in this repository sets. Comparing
    the two ratios as unbounded integers has no rounding step, no precision, no
    context and no trap, and is total on every finite ``Decimal``.

An unusable account state is not a reason to permit new exposure
    Non-positive equity and a non-finite amount both fail closed. Neither
    raises: a control that threw where it was asked to judge would be
    bypassable by an exception handler one layer up.

A rejection says which of the two it was
    ``status`` and ``reason`` are identical for every refusal this control makes
    — ``EXPOSURE_LIMIT`` is the only reason it may return — so ``detail`` is the
    only field that can tell an operator whether the limit was reached or the
    account state was unusable. It is also the only observable difference the
    equity guard makes, because the exact comparison rejects a non-positive
    equity either way.

Boundary:
    Judges an intent; builds nothing. The three ``atlas`` packages a module here
    imports are :mod:`atlas.risk` itself, :mod:`atlas.broker` for the observed
    account, and :mod:`atlas.config` for one name — ``get_settings``. See
    ``tests/unit/risk/test_risk_boundary.py``, which asserts all of that by
    walking the AST of every module here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from atlas.config import get_settings
from atlas.risk.contracts import RejectionReason, RiskVerdict, VerdictStatus

if TYPE_CHECKING:
    from decimal import Decimal

    from atlas.broker.models import Account
    from atlas.risk.contracts import TradeIntent

__all__ = ["evaluate_exposure"]


def _rejected(intent: TradeIntent, detail: str) -> RiskVerdict:
    """Build the only kind of refusal this control makes.

    Args:
        intent: The intent being judged.
        detail: Human-readable context distinguishing this refusal from the
            other kind.

    Returns:
        A rejected verdict carrying the intent and ``EXPOSURE_LIMIT``.
    """
    return RiskVerdict(
        intent=intent,
        status=VerdictStatus.REJECTED,
        reason=RejectionReason.EXPOSURE_LIMIT,
        detail=detail,
    )


def _is_strictly_below(margin: Decimal, equity: Decimal, limit: Decimal) -> bool:
    """Whether ``margin / equity`` is exactly less than ``limit``.

    Every operand is converted to an exact numerator/denominator pair and the
    comparison is cross-multiplied, so it is decided in unbounded integer
    arithmetic: no rounding, no precision, no decimal context and no trap. The
    identity holds only for a positive ``equity`` — multiplying an inequality
    through by a non-positive number does not preserve its direction — which is
    why the caller establishes that first.

    Args:
        margin: Funds the venue reports as pledged. Must be finite.
        equity: Account equity. Must be finite and strictly positive.
        limit: The configured maximum utilisation. Must be finite.

    Returns:
        ``True`` when new exposure is permitted by the limit.
    """
    margin_numerator, margin_denominator = margin.as_integer_ratio()
    limit_numerator, limit_denominator = limit.as_integer_ratio()
    equity_numerator, equity_denominator = equity.as_integer_ratio()
    return (
        margin_numerator * limit_denominator * equity_denominator
        < limit_numerator * equity_numerator * margin_denominator
    )


def evaluate_exposure(intent: TradeIntent, account: Account) -> RiskVerdict:
    """Judge an intent against the portfolio margin-utilisation limit.

    The intent is approved, unchanged, if and only if all three hold: the
    account's margin, its equity and the configured maximum are finite; equity
    is strictly positive; and ``margin / equity`` is exactly less than the
    maximum. Anything else is a rejection carrying ``EXPOSURE_LIMIT``.

    The order of the three checks is not an implementation preference. A
    non-finite ``Decimal`` has no integer ratio and cannot be compared with
    zero, and the cross-multiplication in :func:`_is_strictly_below` is valid
    only where equity is positive.

    Nothing here raises. A blown account, a fully-drawn one and a venue
    reporting a non-finite amount are all refusals, not errors.

    Args:
        intent: The recommendation to judge. Its requested volume does not
            affect the verdict; see the module docstring.
        account: The venue's own report of the portfolio's state.

    Returns:
        An approval carrying exactly the requested volume, or a rejection
        carrying ``EXPOSURE_LIMIT`` and a detail saying which refusal it is.
    """
    limit = get_settings().risk.max_margin_utilisation

    if not (account.margin.is_finite() and account.equity.is_finite() and limit.is_finite()):
        return _rejected(
            intent,
            f"account state is not usable for an exposure check: margin {account.margin}, "
            f"equity {account.equity}, maximum {limit} — one of them is not a finite amount",
        )

    if account.equity <= 0:
        return _rejected(
            intent,
            f"account state is not usable for an exposure check: equity {account.equity} "
            "is not positive, so portfolio margin utilisation is undefined",
        )

    if _is_strictly_below(account.margin, account.equity, limit):
        return RiskVerdict(
            intent=intent,
            status=VerdictStatus.APPROVED,
            approved_volume=intent.requested_volume,
        )

    return _rejected(
        intent,
        f"portfolio margin utilisation is not below the configured maximum of {limit}",
    )
