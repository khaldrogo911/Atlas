# ATLAS-TASK-0029 — Give `atlas-core` a runtime entrypoint

**Status:** Implemented, not committed
**Date:** 2026-08-20
**Baseline:** `43a8e876e5ddee63e9f1fc1e52458ae28199d25d`
**Decision record:** [ADR 0019](../adr/0019-a-runtime-entrypoint-owns-the-session-and-the-pipeline.md) —
*`atlas-core` gains a runtime entrypoint; the runtime owns the session, the
loop and the pipeline* (Accepted, 2026-08-16).

This task implements ADR-0019 and nothing else. ADR-0019 decided a second
entrypoint in `atlas.apps.core`, distinct from ADR-0017's verification
entrypoint, that holds one `BrokerOwner` session open for the life of the
runtime process and drives a serialised market → strategy → risk → execution
→ submission pipeline over it. It named six port operations
(`RUNTIME_PORT_OPERATIONS`) and three pipeline packages under a closed
six-symbol grant (`PIPELINE_NAME_GRANT`) as the only widening of
`apps/atlas-core`'s permissions, both bounded to one named module.

This task is unusual among the numbered tasks in this directory, and that is
named here rather than smoothed over. `apps/atlas-core/src/atlas/apps/core/runtime.py`,
`tests/unit/test_core_runtime.py` and the `RUNTIME_MODULE` grants added to
`tests/unit/test_core_broker_boundary.py` already exist in the working tree,
written and passing, and two of those three files already cite
"ATLAS-TASK-0029" by name — the module docstring in `test_core_runtime.py`
and a comment above `RUNTIME_MODULE` in `test_core_broker_boundary.py` — as
if this specification already existed. It did not: no `docs/tasks/ATLAS-TASK-0029.md`
file existed until this draft, and `docs/ROADMAP.md` had no mention of "0029"
anywhere. TASK-0018, TASK-0024, TASK-0027 and TASK-0028 were each authorised
and implemented directly, with no specification file ever written for them.
This task is the reverse of that shape: the implementation came first, citing
a number, and this file is the specification arriving after it to close the
gap the citation created.

`docs/ROADMAP.md` is not modified by this task's specification, per the
ATLAS-TASK-0026 §22 precedent. See §17.

---

## 1. Title

**ATLAS-TASK-0029 — Give `atlas-core` a runtime entrypoint.**

## 2. Status

Implemented, not committed. `runtime.py`, `test_core_runtime.py` and the
boundary-test grants exist only in the working tree (`git status --porcelain`
shows them untracked/modified against `main` at `43a8e87`). No branch, pull
request or CI run is cited anywhere in this document, and none exists yet.

## 3. Architectural authority

ADR-0019, Accepted 2026-08-16. Its "Implementation authority" section grants,
to `runtime.py` and no other module:

- `PIPELINE_NAME_GRANT`: `Strategy` from `atlas.strategy`; `TradeIntent`,
  `RiskVerdict`, `evaluate_exposure` from `atlas.risk`; `ExecutionPolicy`,
  `build_order_request` from `atlas.execution`.
- `RUNTIME_PORT_OPERATIONS`: `is_connected`, `health`, `ping`, `reconnect`,
  `get_account`, `place_order` — narrowed out of `UNCALLED_PORT_OPERATIONS`,
  which drops from fourteen names to eight.
- One name from `atlas.broker`: `BrokerError`, the same single grant
  ADR-0017 gave `__main__.py`.

ADR-0019's own "Dependency and implementation sequencing" section names its
first hard prerequisite as itself, "accepted... and represented in the
roadmap" — not yet true before this task closes it (§17).

## 4. Problem statement

ADR-0017 gave `atlas-core` an entrypoint that opens a session, proves it, and
closes it — deliberately not a process that trades. ADR-0018 then forbade
building the long-lived shape until a dedicated record decided it. Nothing
in the repository could hold a session open across more than one round trip.

## 5. Scope

- `CoreRuntime[ObservationT]` and `run_runtime`, implementing construction,
  session lifecycle (`run`, `request_stop`), the ordered pipeline cycle
  (`_cycle`), and supervision (`_supervise`), exactly as ADR-0019 decided them.
- The four permissions ADR-0019 authorised, added to the boundary-test file
  as `RUNTIME_MODULE`-scoped grants, and nothing wider.
- Tests proving construction, session lifecycle, pipeline order, supervision,
  and `run_runtime`'s composition path (`tests/unit/test_core_runtime.py`,
  26 tests).

## 6. Non-goals

Everything ADR-0019 itself declined to decide, restated here rather than
re-litigated:

- **The polling values.** The traded instrument and the poll interval are
  required keyword parameters with no defaults (`observe`,
  `poll_interval_seconds`). ADR-0020 proposes how they would be supplied;
  it is `Proposed`, not `Accepted`, and this task does not depend on it,
  implement it, or index it. `docs/adr/0020-*.md` is untouched by this task.
- **The strategy.** `Strategy[ObservationT]` is a parameter, not an
  implementation. No concrete strategy is added.
- **The execution policy.** `ExecutionPolicy` is a parameter. No policy, no
  configuration for one, is added.
- **Order lifecycle beyond submission**, routing, fills, reconciliation,
  idempotency, persistence, multi-venue failover and process restart — all
  explicitly named as not-owned in `runtime.py`'s own module docstring.
- **A `RetryPolicy` value**, a health/staleness threshold, and any widening
  of `UNCALLED_PORT_OPERATIONS` beyond the six ADR-0019 named.

## 7. What exists

- `apps/atlas-core/src/atlas/apps/core/runtime.py` (242 lines).
- `tests/unit/test_core_runtime.py` (789 lines, 26 tests, all passing).
- `tests/unit/test_core_broker_boundary.py`, extended from two module-scoped
  grants to four (`SELECTED_IMPLEMENTATION_NAMES`, `HANDLED_PORT_ERROR`,
  `PIPELINE_NAME_GRANT`, `RUNTIME_PORT_OPERATIONS`), each bounded to
  `RUNTIME_MODULE` and to no other module under `apps/`.

## 8. Verified evidence this specification rests on

Freshly rerun at the baseline above:

- `ruff check .` — All checks passed.
- `black --check .` — 106 files would be left unchanged.
- `mypy .` — Success: no issues found in 106 source files.
- `pytest -q` — 3837 passed.
- `pytest -v tests/unit/test_core_runtime.py` — 26 passed.

## 9. Deferred decisions and known gaps

- The two-item gap this task's own citation created (§ intro) — closed by
  this file's existence, not by editing `runtime.py` or the test files.
- Everything in ADR-0019's "What this record does not decide" — repeated
  there, not repeated here.
- ADR-0020's proposal remains `Proposed`. Nothing here treats it as decided.

## 10. Files expected to change

### 10.1 Expected
- `apps/atlas-core/src/atlas/apps/core/runtime.py` (new)
- `tests/unit/test_core_runtime.py` (new)
- `tests/unit/test_core_broker_boundary.py` (modified)
- `docs/adr/0019-a-runtime-entrypoint-owns-the-session-and-the-pipeline.md` (new)
- `docs/adr/README.md` (modified — ADR-0019 index row)
- `docs/tasks/ATLAS-TASK-0029.md` (this file, new)
- `docs/ROADMAP.md` (modified — status-table row and the two "no work after
  ATLAS-TASK-0028" sentences, at merge time only, per §17)

### 10.2 Prohibited
- `docs/adr/0020-the-runtime-polls-a-configured-instrument-on-a-configured-interval.md`
  — Proposed, unaccepted, out of scope.
- Any concrete strategy, execution policy, or polling configuration field.

## 11. Relationship to the ADRs

Implements ADR-0019 in full. Touches no other ADR. Does not accept, index,
implement, or otherwise act on ADR-0020.

## 12. Roadmap

`docs/ROADMAP.md` is not modified by this task's specification, matching the
ATLAS-TASK-0026 §22 precedent. Its row, and the correction of the two
sentences currently asserting "no work after ATLAS-TASK-0028," are written
at merge time, citing the commit(s) this work actually lands on.
