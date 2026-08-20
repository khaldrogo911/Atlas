# ATLAS-TASK-0030 — Give the runtime a polling observation source

**Status:** Specified, not implemented
**Date:** 2026-08-21
**Baseline:** `a0e239350e72c39d91ef185c06569549470bd8be`
**Decision record:** [ADR 0020](../adr/0020-the-runtime-polls-a-configured-instrument-on-a-configured-interval.md) —
*The runtime polls a configured instrument on a configured interval* (Accepted,
2026-08-19).

This task implements ADR-0020's third and final prerequisite: the polling
implementation. The first two — ADR-0019 and the runtime module committed and
roadmap-represented, and ADR-0020 itself accepted — are both satisfied as of
this baseline.

ADR-0020 fixed the principle and named what it deliberately left open: no
field name, no environment-variable name, no read verb, and no refusal
mechanism. This task makes those choices, each traceable to an existing
repository precedent rather than invented:

- **Settings shape** follows `RiskSettings`/`BrokerSettings` exactly: a frozen,
  `extra="forbid"` section on `AtlasSettings`, with unusable defaults so the
  section resolves for any process, including one that never runs the runtime.
- **The refusal** follows `composition.py`'s existing `build_broker_owner`
  pattern precisely: `BrokerSettings` resolves with defaults; `MT5Config` does
  not; a dedicated function is where that gap becomes a `ConfigurationError`.
  The same shape applies here — `PollingSettings` resolves with defaults; a
  runtime cannot be built from unconfigured ones. (The function itself does
  not live in `composition.py` — see §5.)
- **The read verb** is `get_tick`. ADR-0020's own Context section names
  `symbol_info_tick` polling as the mechanism it is building toward;
  `get_tick(symbol) -> Tick` is the port's direct wrap of exactly that call.

---

## 1. Title

**ATLAS-TASK-0030 — Give the runtime a polling observation source.**

## 2. Status

Specified, not implemented. No file below exists yet at this baseline.

## 3. Architectural authority

ADR-0020, Accepted. Grants this task the freedom to choose field names, the
environment-variable convention (inherited automatically from `AtlasSettings`'
existing `ATLAS_` / `__` scheme — no new mechanism), the read verb, and where
the refusal lives — explicitly withheld from ADR-0019 and ADR-0020 themselves.

## 4. Problem statement

`CoreRuntime.__init__` (ATLAS-TASK-0029) takes `observe` and
`poll_interval_seconds` as required parameters with no defaults. Nothing in
the repository can supply either. Two of `CoreRuntime`'s four required
collaborators remain unconstructable; this task resolves both.

## 5. Scope

- `PollingSettings` in `packages/config/src/atlas/config/settings.py`:
```python
  class PollingSettings(BaseModel):
      model_config = _SECTION_CONFIG
      instrument: str = Field(default="", description="...")
      poll_interval_seconds: float = Field(default=0.0, ge=0, description="...")
```
  Added to `AtlasSettings` as `polling: PollingSettings = Field(default_factory=PollingSettings)`.
- `build_polling_observer(owner: BrokerOwner) -> Callable[[], Tick]` in
  `apps/atlas-core/src/atlas/apps/core/broker_ownership.py`, beside
  `BrokerOwner`. Takes the owner rather than a bare `BrokerAdapter`, so the
  abstraction itself gains no new namer; the function reaches the adapter
  through `owner.adapter`. The return type `Callable[[], Tick]` does add
  `Tick` to the module's broker-derived names — unavoidable without
  weakening the annotation. Raises `ConfigurationError` if
  `settings.polling.instrument == ""` or
  `settings.polling.poll_interval_seconds <= 0` — checked together, one
  refusal point. Otherwise returns a zero-argument callable that calls
  `owner.adapter.get_tick(settings.polling.instrument)` on each invocation.
  No change-filtering, no staleness check.
- Two edits to `tests/unit/test_core_broker_boundary.py`, both additive:
  - A new bounded grant: `MARKET_DATA_PORT_OPERATIONS: Final =
    ("get_tick",)`, granted to `OWNERSHIP_MODULE`, with its own
    `_authorised_*_of` helper and a "the rule can actually fire" test —
    mirroring `RUNTIME_PORT_OPERATIONS`'s existing shape exactly.
  - `test_the_ownership_module_takes_two_names_from_the_port_and_no_others`
    widens from an exact set of two names to three (`{BrokerAdapter,
    BrokerNotConnectedError, Tick}`) and is renamed accordingly, since
    `build_polling_observer`'s return-type annotation makes `Tick` a name
    the module now legitimately takes. No other existing constant, helper,
    or assertion in the file changes.
- Tests: `PollingSettings` resolves with defaults, no exception. The observer
  refuses on each unconfigured case (instrument only, interval only, both) and
  the exception is `ConfigurationError`. A configured observer calls
  `adapter.get_tick` with the configured symbol on every invocation and
  returns the adapter's result unmodified — proven with a recording stub
  adapter, following `test_core_composition.py`'s own `_recording` pattern.

## 6. Non-goals

- No concrete instrument or interval value anywhere in `config/`. Local runs
  supply them through the environment, as `risk.max_margin_utilisation`
  already does.
- No strategy, no `ExecutionPolicy` — both remain unresolved elsewhere.
- No wiring into `run_runtime` or `__main__.py`. `CoreRuntime` still needs a
  strategy and a policy before it is constructible end-to-end; this task
  produces a pluggable, independently-tested piece, not a runnable process.
- No change to `build_broker_owner`, `BrokerOwner`'s own existing methods, or
  `composition.py` — this task adds one new function to `broker_ownership.py`
  and touches no file ADR-0015 governs.
- The only change to an existing assertion in `test_core_broker_boundary.py`
  is widening the ownership module's exact broker-name set from two to three
  and renaming that one test accordingly; every other existing constant,
  helper, and assertion in that file is untouched.

## 7. What exists

Nothing yet. This section is empty at specification time, unlike TASK-0029,
because this task's implementation has not been written in advance of its
spec.

## 8. Files expected to change

### 8.1 Expected
- `packages/config/src/atlas/config/settings.py` (modified — `PollingSettings`, `AtlasSettings.polling`)
- `apps/atlas-core/src/atlas/apps/core/broker_ownership.py` (modified — `build_polling_observer`)
- `tests/unit/test_config_settings.py` (modified — `PollingSettings` cases)
- `tests/unit/test_core_broker_ownership.py` (modified — `build_polling_observer` cases)
- `tests/unit/test_core_broker_boundary.py` (modified — the new `MARKET_DATA_PORT_OPERATIONS` grant, and widening/renaming the ownership module's exact-name test from two names to three)
- `docs/tasks/ATLAS-TASK-0030.md` (this file, new)
- `docs/ROADMAP.md` (modified — status-table row and narrative subsection, at merge time, per the ATLAS-TASK-0026 §22 / ATLAS-TASK-0029 §12 precedent)

### 8.2 Prohibited
- `apps/atlas-core/src/atlas/apps/core/runtime.py`, `__main__.py` — no wiring.
- Any concrete instrument, interval, strategy, or execution-policy value.
- A new `polling.py` module, or any other new file — the function belongs
  beside `BrokerOwner` in the module that already owns the adapter.
- Any edit to `composition.py` — this task does not touch it.
- Any change to `test_core_broker_boundary.py` beyond the two additive edits
  named in §5 — no other existing constant, helper, or assertion changes.

## 9. Relationship to the ADRs

Implements ADR-0020's third prerequisite in full. Touches no other ADR.

## 10. Roadmap

Not modified by this specification. Written at merge time, citing the real
commit, per precedent.
