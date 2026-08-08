# ATLAS-TASK-0014 — The execution boundary: consuming a `RiskVerdict`

**Status:** Specified, not implemented
**Date:** 2026-08-08
**Baseline:** `44057fb38aa746dc3a5fd21702d316aad3633f3e`
**Decision record:** [ADR-0011](../adr/0011-execution-builds-the-request-another-layer-owns-the-port.md)

This task is newly specified. It is not recovered from the repository record and
must not be described as previously planned. `docs/ROADMAP.md` does not list it,
by that file's own rule — every row in its status table is a completed task
citing a commit, and it states that it "does not speculate past them". The
roadmap row and completed-section entry are written when the task merges, the
way ATLAS-TASK-0011, 0012 and 0013 were.

---

## 1. Purpose

`atlas.execution` has been an empty stub since ATLAS-TASK-0001, and it is the
missing half of the repository's first invariant. Three separate documents
record the same gap in nearly the same words:
`docs/architecture/overview.md:81` ("`atlas.execution` remains an empty stub, so
nothing consumes a `RiskVerdict` yet"),
`packages/risk/src/atlas/risk/README.md:175` ("still an empty stub, so nothing
consumes a verdict"), and
[ADR-0010](../adr/0010-the-risk-boundary-is-a-verdict-on-an-intent.md)`:192`
("Nothing consumes a verdict").

This task gives the verdict a consumer. It defines the contract by which an
approved `RiskVerdict` becomes an `OrderRequest`, and it stops there — before
any broker is reached.

## 2. Scope

One boundary contract in `atlas.execution`, and nothing else:

- The translation of an **approved** `RiskVerdict` into an `OrderRequest`.
- The answer for a **rejected** `RiskVerdict`.
- The shape of the **execution policy** that supplies what a verdict does not
  carry: the order type and the working price.

The task is contract-only and stateless. It adds no behaviour that outlives a
call.

## 3. Non-goals

This task does not deliver, and must not begin:

- Routing, fill or partial-fill handling, reconciliation, or idempotent retry —
  the other four responsibilities in the `atlas.execution` module docstring.
- The broker-owning layer that receives an `OrderRequest` and places it.
- Any `BrokerAdapter` ownership, construction, injection or invocation.
- A strategy engine, lifecycle, registry or scheduler.
- Any risk control. `RejectionReason`'s four members remain unimplemented, and
  no member may be added — `atlas.risk` forbids inventing one ahead of the
  control it names.
- Any account or portfolio state contract.
- Any change to `atlas.risk`, `atlas.strategy` or `atlas.broker`.

## 4. Inputs

The contract receives:

1. A `RiskVerdict`, from `atlas.risk`. It carries the `TradeIntent` it judged,
   its `VerdictStatus`, the approved volume when approved, and a
   `RejectionReason` with optional detail when rejected.
2. An **execution policy**, supplied by the caller, which answers the two
   questions a verdict does not: which `OrderType` the order is presented as,
   and what working `Price` it carries, if any.

Both are arguments. Neither is constructed inside `atlas.execution`, read from
configuration, or held between calls.

## 5. Outputs

`OrderRequest | None` — the broker-owned `OrderRequest` for an approved verdict,
and nothing for a rejected one. No third value, and no wrapper type.

## 6. Approved-verdict behaviour

For a verdict whose status is approved, the contract produces an `OrderRequest`
in which:

- the **symbol** and **side** are the intent's;
- the **volume** is the **approved** volume, never the requested volume — a
  reduced approval is an approval carrying a smaller number, and reading the
  requested figure is the specific accident ADR-0010 rejected a third `REDUCED`
  status to prevent;
- the **stop loss** and **take profit** are the intent's protective levels;
- the **order type** and any **working price** come from the execution policy;
- every remaining field is left to the port's own rules for a well-formed
  request.

`atlas.execution` never adjusts a size, never substitutes a level, and never
reconsiders a verdict.

## 7. Rejected-verdict behaviour

For a verdict whose status is rejected, the contract produces **nothing**. It
does not raise, and it does not return a value that a careless consumer could
mistake for an order.

A rejected verdict is risk working, not a failure. The repository already has
this shape: `Strategy.propose` returns `TradeIntent | None`, where nothing means
the strategy has nothing to say, and its contract module gives the reason —
a sentinel or an empty object "puts a value into the pipeline that *looks*
tradeable, and the first consumer that forgets to check sends it to risk".

## 8. Execution-policy responsibility

The policy owns exactly two answers — the `OrderType` and the working `Price` —
and nothing else. It does not size, does not decide whether to trade, and does
not see the account.

It is received by `atlas.execution`, not chosen by it. `atlas.execution` holds
no default order type. A default written here would silently settle the two
questions `atlas.broker.mt5.adapter` explicitly declines to settle —
filling-mode selection per instrument and a deviation policy, of which it says
"neither has an obviously right answer" — inside the package least likely to be
reviewed as policy.

Nothing in this task implements a policy. It defines the shape of one and
requires that the contract be given one.

## 9. Relationship to the broker-owned `OrderRequest`

`OrderRequest` remains authoritative and is used as defined in
`packages/broker/src/atlas/broker/types.py`, exported from
`packages/broker/src/atlas/broker/__init__.py`. `OrderType` and `Price` remain
`atlas.broker.models` types.

No parallel order vocabulary is created. No `ExecutionInstruction` type is
introduced — that alternative is recorded and rejected in ADR-0011, because two
descriptions of one order diverge and would diverge at the conversion between
them.

The division of labour is unchanged: the port validates that a request is *well
formed*, `atlas.risk` judges whether it is *wise*, and `atlas.execution` decides
how it is *presented*.

## 10. Dependency boundary

Authorised, and exhaustive:

| Edge | Authorised | Nature |
|---|---|---|
| `atlas.execution → atlas.risk` | **Yes** | `RiskVerdict`, `TradeIntent`, `VerdictStatus` |
| `atlas.execution → atlas.broker` | **Yes** | Type/contract only: `OrderRequest`, `OrderType`, `Price` |
| `atlas.execution → atlas.common` | Not authorised by this task | — |
| any other `atlas.*` edge | **No** | — |

The `atlas.broker` edge is permission to **name** the order vocabulary. It is
not permission for broker calls, `BrokerAdapter` ownership or construction,
venue or MT5 integration, credentials or configuration, or retry
infrastructure. `atlas.execution` must not name, obtain, construct or invoke a
`BrokerAdapter`.

The primitives may not be routed around this rule: `atlas.risk` exports only
`RISK_MODEL_CONFIG`, `RejectionReason`, `RiskVerdict`, `TradeIntent` and
`VerdictStatus`, and ATLAS-TASK-0012 forbade re-exporting broker primitives
through it. `atlas.risk.__all__` must not change.

Both new edges run downward, and neither may become bidirectional:
`atlas.risk` and `atlas.broker` must still contain no import of
`atlas.execution`.

## 11. Statelessness

The contract is per call and keeps nothing between calls. This task introduces
no start/stop lifecycle, no run loop, no long-lived execution service, no
in-flight order registry, no reconciliation ledger, no in-memory state and no
persistence.

`AtlasSettings` is unchanged. No configuration key is added.

## 12. Failure semantics

No new exception type and no new retry mechanism is created.

The existing broker exception hierarchy is reused only where a broker-facing
boundary genuinely requires it; nothing in this task's scope reaches a broker,
so in practice this task raises none of them. A rejected verdict is explicitly
**not** a broker failure and must not be expressed as one —
`BrokerOrderRejectedError` describes a venue declining an order it was sent, and
no order is sent here.

`atlas.common.retry` is not used. No retry behaviour is added.

## 13. External integration

None. No MetaTrader 5, no broker connection, no venue, no datastore, no network
call, no new dependency.

`MetaTrader5` stays a Windows-only optional extra; CI stays two `ubuntu-latest`
jobs with no service containers. Neither needs to change for this task to be
implemented or verified, and neither may be changed by it.

## 14. Required boundary test

The implementation **must** add `tests/unit/execution/test_execution_boundary.py`.

It is not optional. `atlas.execution` would otherwise be the only package on the
`risk → execution → broker` path with no AST-level enforcement, and the
distinction this task rests on — that naming a port type is not calling the port
— is invisible to both the type checker and the packaging, since there are no
per-package manifests.

Modelled on `tests/unit/risk/test_risk_boundary.py` and
`tests/unit/strategy/test_strategy_boundary.py`, it must assert at least:

- the permitted `atlas` import set for `atlas.execution` is exactly
  `atlas.execution`, `atlas.risk`, `atlas.broker`;
- `BrokerAdapter` is named nowhere in the package, and neither are the port's
  four trading verbs;
- `atlas.risk` and `atlas.broker` still contain no import of
  `atlas.execution`;
- a rejected verdict yields nothing, and an approved verdict's `OrderRequest`
  carries the **approved** volume;
- the scanners can actually fail. ATLAS-TASK-0012 set this standard — 45 of its
  155 tests exist only to prove the AST scanners fail when they should, "because
  a scan that inspects nothing passes everything" — and it applies here.

A `TYPE_CHECKING` guard does not exempt an import. The existing scanners use
`ast.walk`, which descends into `if TYPE_CHECKING:` blocks; `atlas.strategy`'s
guarded import of `TradeIntent` passes only because `atlas.risk` is in its
permitted set.

## 15. Acceptance criteria

1. `atlas.execution` exposes a contract taking a `RiskVerdict` and an execution
   policy and answering `OrderRequest | None`.
2. An approved verdict yields an `OrderRequest` carrying the approved volume,
   the intent's symbol, side and protective levels, and the policy's order type
   and working price.
3. A rejected verdict yields nothing, and raises nothing.
4. `atlas.execution` imports only `atlas.risk` and `atlas.broker` from `atlas`.
5. `atlas.execution` contains no reference to `BrokerAdapter` and no broker
   call.
6. `atlas.execution` declares `__all__` and ships `py.typed`, as
   `tests/contract/test_repository_structure.py` requires of every package.
7. `tests/unit/execution/test_execution_boundary.py` exists and asserts §14.
8. No file outside `packages/execution/`, `tests/unit/execution/` and the
   documentation this task's completion requires is modified.
9. `atlas.risk`, `atlas.strategy` and `atlas.broker` are byte-for-byte
   unchanged, including `atlas.risk.__all__`.
10. `pyproject.toml`, CI, configuration, `docs/architecture/overview.md` and
    ADR-0010 are unchanged.
11. No new dependency, no configuration key, no persistence, no external
    integration.

## 16. Verification expectations

Both CI jobs must pass on the commit that is merged, which is what
`docs/ROADMAP.md` requires before a task may be called Complete:

- **Quality Gate** — `poetry check --lock`, `poetry sync --with dev,test`,
  `ruff check`, `black --check`, `mypy .` (strict), `pytest --cov`.
- **Container & Compose** — `docker compose config`, image build, image
  self-check.

`mypy` strictness is load bearing here rather than incidental: `OrderRequest`
cannot be constructed without naming its field types correctly, so a translation
that quietly drops or mistypes a field fails the gate rather than the review.

The full suite must pass, not only the new tests. The existing risk and strategy
boundary tests are the ones to watch: they assert that `atlas.risk` and
`atlas.strategy` contain no import of `atlas.execution`, and this task must not
make either of those assertions false.

## 17. Explicitly out of scope

- `docs/architecture/overview.md`, including its "Status at ATLAS-TASK-0012"
  banner. It stays as it is.
- ADR-0010. It is immutable, is not superseded by this task, and must not be
  edited. Its account/portfolio-state decision remains in force.
- ADR-015 and ADR-016. Closed as unreconstructable; not reopened.
- Any other documentation debt discovered while implementing this task. Report
  it; do not fix it here.
- `tests/integration/` and `tests/e2e/`, which hold no test files and gain none.
- The `docs/api/` documents. `docs/api/README.md` says `events.md` arrives with
  the message bus, `broker-port.md` with the broker abstraction and
  `dashboard-http.md` with the dashboard service. None of the three is this
  task.

---

## Naming is deliberately not fixed here

This specification does not name the contract, the policy type, or the modules
they live in. Those are the implementation's to choose and the review's to
judge; fixing them in a specification would settle by assertion what the code
should settle by argument.

Two existing conventions are worth weighing rather than rediscovering:
`atlas.risk` and `atlas.strategy` both put their boundary types in a
`contracts.py`, and `atlas.strategy` states its contract as a `Protocol` rather
than a base class, on the grounds that requiring inheritance would give the
package a concrete class for shared behaviour to accumulate in — "and the first
thing that lands there is a lifecycle", which this task forbids.

## Stop conditions

Stop and report, rather than deciding, if implementation reveals that:

- an `OrderRequest` field cannot be filled from a verdict plus a policy;
- the approved volume cannot be carried without touching `atlas.risk`;
- the boundary cannot be expressed without a third `atlas` edge;
- the policy shape cannot be stated without naming account or portfolio state;
- or any part of §15 cannot be met without an architectural decision that ADR-0011
  does not already make.
