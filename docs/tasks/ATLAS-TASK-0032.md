# ATLAS-TASK-0032 — Implement close_position over order_send and history_deals_get

**Status:** Specified, not implemented
**Date:** 2026-08-22
**Baseline:** `a1092c2895b63a671ba382fc3f517d0128199d88`
**Decision record:** [ADR 0021](../adr/0021-filling-mode-and-deviation-are-configured-not-chosen.md) —
*Filling mode and deviation are configured, not chosen* (Accepted, 2026-08-21).

This is the second trading method ADR-0021's acceptance unblocked, after
`place_order` (`ATLAS-TASK-0031`). No new decision record is needed here —
`close_position`'s own docstring already fully specifies what it requires
(an opposing order, and a read of the resulting deals for a volume-weighted
average), and both mechanisms already exist: `order_send` and
`history_deals_get` are both already declared on the `Terminal` protocol,
and `history_deals_get` is already used identically for commission
read-back in `get_positions`.

Two identity questions the port's own docstring leaves open, decided here
rather than left implicit:

- **`Execution.execution_id`** for a close that fills across several deals:
  no single real venue ticket exists for an aggregate. This task uses the
  **last deal's ticket** (by `time_msc`) — the one that actually completed
  the close.
- **`Execution.timestamp`**: the same deal's `time_msc`, for the same reason.

## 1. Title

**ATLAS-TASK-0032 — Implement `close_position` over `order_send` and `history_deals_get`.**

## 2. Status

Specified, not implemented. No file below reflects this task's changes yet.

## 3. Architectural authority

`close_position`'s own existing docstring in `packages/broker/src/atlas/broker/mt5/adapter.py`,
and the abstract port's docstring in `packages/broker/src/atlas/broker/adapter.py`.
No ADR is created or reopened by this task.

## 4. Problem statement

`MT5BrokerAdapter.close_position` raises `NotImplementedError` unconditionally.
The two things its own docstring named as missing — the opposing order and
the deal read-back — are both now implementable using mechanisms `ATLAS-TASK-0031`
and `get_positions` already established. Nothing else changes that.

## 5. Scope

- Resolve `position_id` via `terminal.positions_get()` (unfiltered — no
  ticket-filter parameter exists on this method) and find the entry whose
  `ticket` matches, client-side. If none matches: `BrokerPositionNotFoundError`.
- If `volume` is given and exceeds the position's open size: `ValueError`,
  matching the abstract port's documented contract exactly.
- Build and send an opposing order via `order_send`, reusing
  `ATLAS-TASK-0031`'s exact pattern: `TRADE_ACTION_DEAL`, the configured
  `deviation_points`, the filling mode looked up for the position's
  instrument (same refusal — `BrokerOrderRejectedError` — if unmapped), the
  MT5 `position` field set to the position's ticket so the terminal closes
  rather than opens. Side is the position's opposite (`OrderSide.opposite`
  already exists on the model). On a failing `retcode`, raise
  `error_from_retcode(...)`, exactly as `place_order` does.
- On a successful `retcode`, call `history_deals_get(position=position_id)`
  and filter the result to deals whose `.order` equals the closing order's
  own ticket (`raw.ticket` from the `order_send` result) — not every deal
  the filter returns. `history_deals_get(position=...)` returns every deal
  tied to the position across its life, including its original opening
  deal(s); aggregating unfiltered would silently mix historical fills into
  this close's reported Execution. Aggregate the filtered set into one
  Execution: volume summed, price volume-weighted, commission and swap
  summed, execution_id and timestamp from the filtered deal with the
  latest time_msc. If the filtered set is empty after a successful
  retcode, raise BrokerDataUnavailableError.
- Tests: a full close (single deal) returns a correctly translated
  `Execution`; a partial close specifying a smaller `volume` than the
  position holds; a `volume` exceeding the position's size raises
  `ValueError` before any call reaches the terminal; an unknown
  `position_id` raises `BrokerPositionNotFoundError` before any call
  reaches the terminal; a close that fills across multiple deals aggregates
  volume, price (weighted), commission, and swap correctly, and reports the
  last deal's ticket and timestamp; an unmapped instrument's filling mode
  refuses without reaching the terminal, mirroring `place_order`'s existing
  test; a rejecting `retcode` translates through `error_from_retcode`.

## 6. Non-goals

- `modify_order`, `cancel_order` — each remains `NotImplementedError`, each
  is its own future task.
- Any change to `place_order`, `ExecutionPolicy`, `OrderRequest`, or the
  `deviation_points`/`filling_mode_by_instrument` configuration shape
  `ATLAS-TASK-0031` already established.
- Any strategy, backtesting, or runtime-wiring change.
- Retry or reconnection behaviour for a trading call.

## 7. What exists

Nothing yet. This task's implementation has not been written in advance of
its spec.

## 8. Files expected to change

### 8.1 Expected
- `packages/broker/src/atlas/broker/mt5/adapter.py` (modified — `close_position`)
- `tests/unit/broker/mt5/test_mt5_adapter.py` (modified)
- `tests/unit/broker/mt5/conftest.py` (modified, if a fake multi-deal
  history fixture is needed beyond what `TASK-0031` already added — confirm
  before assuming a new fixture is required)
- `docs/tasks/ATLAS-TASK-0032.md` (this file, new)
- `docs/ROADMAP.md` (modified — at merge time, per precedent)

### 8.2 Prohibited
- `modify_order`, `cancel_order` — no implementation.
- `ExecutionPolicy`, `OrderRequest`, or anything in `atlas.execution`.
- Any change to `place_order`'s own implementation.
- Any concrete filling-mode or deviation value in `config/`.

## 9. Relationship to the ADRs

Consumes ADR-0021's existing authorization for `close_position` specifically.
Creates no new ADR. Touches no other ADR.

## 10. Roadmap

Not modified by this specification. Written at merge time, citing the real
commit, per precedent.
