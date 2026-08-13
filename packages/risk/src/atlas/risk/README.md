# `atlas.risk`

The package nothing may go around.

```python
from atlas.risk import RejectionReason, RiskVerdict, TradeIntent, VerdictStatus
```

---

## The boundary

```
TradeIntent ──▶ atlas.risk ──▶ RiskVerdict ──▶ atlas.execution ──▶ OrderRequest ──▶ broker
```

A strategy proposes; risk decides; execution places. Atlas is
**recommendation-first**, and this package is where that is enforced: a
`TradeIntent` is a recommendation rather than an instruction, and the only thing
that may licence an order is a `RiskVerdict` whose status is `APPROVED`.

`atlas.broker` had already drawn the line from its side. `OrderRequest` says
that whether a request is *wise* — the size against the account, the stop on the
correct side of entry, the instrument permitted by policy — "is a risk decision,
made against state neither this model nor the port can see". These are the types
that decision is expressed in.

**Risk judges an intent; it never builds an order.** Nothing here imports,
constructs or re-exports `OrderRequest`, and nothing here names an order type or
a working price. How an order is *presented to a venue* is `atlas.execution`'s
question, and a package that both sized a position and chose how to route it
would be the coupling `docs/architecture/overview.md` separates deliberately.
`tests/unit/risk/test_risk_boundary.py` asserts it by walking the AST of every
module in this package rather than by trusting the sentence above.

*[ADR-0010](../../../../../docs/adr/0010-the-risk-boundary-is-a-verdict-on-an-intent.md)*

---

## `TradeIntent` — what a strategy would like to do

```python
TradeIntent(
    symbol="EURUSD",
    side=OrderSide.BUY,
    requested_volume=Decimal("0.50"),
    stop_loss=Decimal("1.0950"),      # optional
    take_profit=Decimal("1.1100"),    # optional
)
```

Five fields: what risk needs in order to judge one. The instrument, the
direction, the size being asked for, and the levels that determine how much of
the account is at stake.

`requested_volume` is named for the ask rather than for the outcome, and the
name is the point. A field called `volume` here and a field called `volume` on
an order invite a consumer to carry the number across — which is exactly what a
reduced approval must not permit.

`stop_loss` is optional *on the contract* because whether an intent without one
may proceed is a risk control's decision, not a model's. The contract's job is
to make the intent expressible; refusing it is a control's job.

### Deliberately absent

Each absence is asserted by name in `tests/unit/risk/test_trade_intent.py`, so
adding one is a visible act rather than a plausible edit.

- **An order type and a working price.** `OrderType` is documented as "how the
  order should be presented to the venue", and presentation is execution's. An
  intent that named `LIMIT` would be instructing rather than recommending.
- **An identifier.** Who mints intent ids and whether they survive a restart is
  a question for an audit trail that does not exist yet. A field invented now
  would be a second answer competing with it.
- **A creation timestamp.** It would require a clock injected into whatever
  builds an intent, and nothing in the contract needs to know when it was built.

---

## `RiskVerdict` — what risk permits

```python
RiskVerdict(intent=intent, status=VerdictStatus.APPROVED,
            approved_volume=Decimal("0.50"))                    # full approval

RiskVerdict(intent=intent, status=VerdictStatus.APPROVED,
            approved_volume=Decimal("0.20"),
            detail="scaled to the per-instrument cap")           # reduced — still an approval

RiskVerdict(intent=intent, status=VerdictStatus.REJECTED,
            reason=RejectionReason.DRAWDOWN_LIMIT,
            detail="daily drawdown at 4.2% of 4.0%")             # refused
```

**Two states, and the number carries the nuance.** `VerdictStatus` is exactly
`APPROVED` and `REJECTED`. A reduced-size approval is `APPROVED` with a smaller
`approved_volume` — not a third status. A `REDUCED` member would force every
consumer to handle two spellings of "yes", and the first one to handle only the
first spelling is a position sized off the requested volume: silent, and wrong
only in the case the status was introduced for.

**`approved_volume` is the number execution must use** — never
`intent.requested_volume`, which is what was asked for rather than what was
allowed. It is `None` on a rejection, which is what makes ignoring the status
uninteresting rather than merely forbidden: there is no number to bypass with.

**Risk may reduce; it may never enlarge.** An `approved_volume` above the
requested one is refused at construction. A boundary that can return a larger
number than it was given is not a boundary — it is a second, unreviewed sizing
authority.

The verdict carries the whole intent rather than a reference to one. Both models
are frozen, so there is nothing to keep in sync, and "approved for less than was
asked" becomes a comparison inside a single object rather than a join two
callers might perform differently — or forget.

| | `is_approved` | `is_reduced` | `approved_volume` | `reason` |
| --- | --- | --- | --- | --- |
| Full approval | `True` | `False` | the requested volume | `None` |
| Reduced approval | `True` | `True` | below the requested volume | `None` |
| Rejection | `False` | `False` | `None` | required |

### The rules, enforced at construction

An approval requires a volume, must not exceed the requested one, and carries no
reason. A rejection carries no volume and requires a reason. `detail` is
optional in either state. Each is asserted twice in
`tests/unit/risk/test_risk_verdict.py` — once with the field that breaks it and
once with the field that satisfies it, because a rule nobody can satisfy is not
a boundary but an outage.

### `RejectionReason` — a closed vocabulary

`EXPOSURE_LIMIT`, `DRAWDOWN_LIMIT`, `CORRELATION_CAP`, `KILL_SWITCH` — one for
each control this package is declared to own. A machine reads `reason`; a person
reads `detail`. A free-text refusal is unqueryable, unstable across call sites,
and cannot be asserted on.

A new control adds a member in the task that implements it. Inventing one ahead
of the control it names would put a value in the audit trail that nothing can
ever produce.

---

## The primitives are the broker's

`SymbolName`, `OrderSide`, `Price` and `Volume` are imported from `atlas.broker`
rather than redefined, for the reason `atlas.broker.types` gives for its own
aliases: two definitions of one concept "would create two rules for one concept
and guarantee they diverge". A risk-local `Volume` that permitted zero, or a
`Price` that permitted a negative, would be a boundary that disagreed with the
port it protects — and would disagree at the moment of translation, where nobody
is looking.

This is the edge ATLAS-TASK-0011 creates, `atlas.risk → atlas.broker`, and it
runs downward; ATLAS-TASK-0017 put `Account` on it, on the same terms and for the
same reason. It is no longer the package's only outward edge. That task also
added `atlas.risk → atlas.config`, which runs downward too and carries exactly
one name — `get_settings`, enough to read this package's own limit and nothing
else. The boundary test enumerates the permitted set, two packages now with a
name allowlist on the second, scans for credential-bearing configuration names
that the allowlist cannot see because reaching them takes no import at all, and
asserts separately that `atlas.broker` still contains no import of `atlas.risk`:
the cheapest way to break a layered graph is to make a downward edge quietly
bidirectional.

---

## What this package does not do yet

`atlas.risk` holds the two contracts and one control. **Constructing an
`APPROVED` verdict does not make it true.** `evaluate_exposure` is the portfolio
margin-utilisation limit ATLAS-TASK-0017 added, and it names `EXPOSURE_LIMIT`.
There is still no sizing algorithm, no drawdown control, no correlation cap and
no kill switch; those arrive with the tasks that implement them, and each names
its own `RejectionReason`.

`atlas.strategy` holds the `Strategy` contract and `ConstantStrategy`, an
inert reference implementation of it — but no engine, lifecycle or registry, so
nothing drives a strategy and no intent is produced in practice.
`atlas.execution` consumes a verdict as of ATLAS-TASK-0014: `build_order_request`
turns an approved one into an `OrderRequest` carrying the volume this package
approved, and answers a rejected one with `None`. It builds that request and
places nothing — it neither owns nor constructs a `BrokerAdapter`, and no layer
that does yet exists. The invariant has two halves — risk cannot be bypassed,
and execution acts only on approved output — and only the structural half is
provable today: risk exposes no path to an order, and an approved volume exists
nowhere except on an approved verdict. The behavioural half still waits on a
pipeline to observe — nothing outside the test suite produces an intent, and
nothing outside it hands one to `evaluate_exposure` — and
`tests/unit/risk/test_risk_boundary.py` says so in its own docstring rather than
letting a reader infer the coverage is wider than it is.
