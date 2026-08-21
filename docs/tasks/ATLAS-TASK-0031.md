# ATLAS-TASK-0031 — Implement place_order over order_send

**Status:** Specified, not implemented
**Date:** 2026-08-21
**Baseline:** `9bb3d8dbcb013db668ecf4d458688565e38ecd2b`
**Decision record:** [ADR 0021](../adr/0021-filling-mode-and-deviation-are-configured-not-chosen.md) —
*Filling mode and deviation are configured, not chosen* (Accepted, 2026-08-21).

This task is the first to consume ADR-0021's authorization. It implements
`place_order` on `MT5BrokerAdapter` over `order_send`, and nothing else ADR-0021
also unblocked — `modify_order`, `cancel_order` and `close_position` remain
deferred, each to its own future task, exactly as ADR-0021's own sequencing
section permits ("may be implemented in the same task or a later one").

ADR-0021 named the ownership and the shape of two values; it deliberately left
field names, Python types and where in `MT5Config` they live to this task. Two
choices made here, each following an existing pattern rather than inventing one:

- **Two layers, not one.** `deviation_points` and `filling_mode_by_instrument`
  are added to both `BrokerSettings` (sentinel defaults — `0` and `{}` — so the
  section resolves for any process) and `MT5Config` (eager `gt=0` on
  `deviation_points`, matching `login`'s exact shape). This is the same split
  `login`/`server`/`terminal_path` already use; `build_broker_owner` refuses on
  the sentinel, `MT5Config` never sees an unconfigured value.
- **No new refusal for filling mode at construction.** Per ADR-0021's own
  reasoning, `filling_mode_by_instrument` cannot be required exhaustive without
  querying the venue during validation, which ADR-0016 forbids. The refusal for
  an instrument absent from the mapping happens inside `place_order`, at the
  call that names it.

## 1. Title

**ATLAS-TASK-0031 — Implement `place_order` over `order_send`.**

## 2. Status

Specified, not implemented. No file below reflects this task's changes yet.

## 3. Architectural authority

ADR-0021, Accepted. Also relies on ADR-0019's existing grant: `place_order` is
already one of `RUNTIME_MODULE`'s six authorised port operations (`TASK-0029`);
this task does not touch that grant, only the method it names.

## 4. Problem statement

`MT5BrokerAdapter.place_order` raises `NotImplementedError` unconditionally.
ADR-0021 removed the reason it gave for doing so. Nothing else changes that.

## 5. Scope

- `packages/broker/src/atlas/broker/mt5/constants.py`: add `ORDER_FILLING_FOK`,
  `ORDER_FILLING_IOC`, `ORDER_FILLING_RETURN`, and `TRADE_ACTION_DEAL` —
  transcribed from MetaTrader 5's public API, the same way every existing
  constant in this file already is. Reuse whatever reverse `OrderType`→MT5
  mapping already exists near `MT5_ORDER_TYPE_TO_DOMAIN` (confirm its name and
  reuse it; do not build a second one).
- `BrokerSettings` (`packages/config/src/atlas/config/settings.py`): add
  `deviation_points: int = Field(default=0, ge=0, description="...")` and
  `filling_mode_by_instrument: dict[str, str] = Field(default_factory=dict, description="...")`.
- `MT5Config` (wherever it is actually defined — confirm the file before
  editing): add `deviation_points: int = Field(gt=0, description="...")` and
  `filling_mode_by_instrument: Mapping[str, int]`, the second using this
  task's new `ORDER_FILLING_*` constants as its values.
- `build_broker_owner`: refuse with `ConfigurationError` if
  `deviation_points == 0`, matching the existing `login`/`server` sentinel
  checks exactly. A name absent from `FILLING_MODE_NAME_TO_MT5` raises
  `ConfigurationError` naming the bad value and the instrument it was set
  for — a well-formedness check on a supplied value, not the exhaustive
  per-instrument check ADR-0021 forbids requiring.
  `test_an_unrecognised_filling_mode_name_raises_a_key_error_not_a_configuration_error`
  is replaced accordingly.
- `MT5BrokerAdapter.place_order`: build the `order_send` request (symbol,
  volume, the reused reverse order-type mapping, price where applicable,
  `TRADE_ACTION_DEAL`, the configured `deviation_points`, and the filling mode
  looked up for `request.symbol`); raise `BrokerOrderRejectedError` via a
  message naming the unmapped instrument if the symbol has no configured
  filling mode; call `order_send`; on a failing `retcode`, raise
  `error_from_retcode(...)`; on success, return `to_order(raw, clock)` — the
  existing mapper function, not a new translation.
- `place_order` fetches `self._terminal()` before checking
  `filling_mode_by_instrument`, not after — every other guarded method
  (`get_tick`, `get_account`, etc.) reaches the connection guard
  unconditionally as its first substantive action, and `place_order` must
  match that convention rather than let an unmapped instrument bypass the
  connection check entirely. The fetched terminal is reused for the
  `order_send` call rather than fetched a second time.
- Tests: `BrokerSettings` resolves with the new sentinel defaults;
  `build_broker_owner` refuses when `deviation_points` is unset, alongside its
  existing refusal cases; a configured adapter places a market order and
  returns a translated `Order`; an unmapped instrument refuses without calling
  `order_send`; a rejecting `retcode` translates through `error_from_retcode`.
  Replace (not append to) `test_placing_an_order_is_deferred` and
  `test_the_deferral_no_longer_blames_a_missing_exception_hierarchy`'s
  `place_order`-specific assertions — the premise of the second ("no call
  reaches the terminal") is inverted once this lands. `MT5_DEFERRED`
  (`tests/unit/broker/test_base_adapter.py`) drops `'place_order'` — it is no
  longer deferred. The other three methods stay. The three other methods'
  deferred tests are untouched.
- `place_order` moves from `MT5_DEFERRED` into `GUARDED`
  (`tests/unit/broker/test_base_adapter.py`) — a direct consequence of the
  guard-order fix above: it now checks the connection before anything else,
  the same as every other `GUARDED` method, and the three-way partition
  this file asserts (`GUARDED`/`NEVER_REFUSES`/`MT5_DEFERRED` covering all
  of `CALLS`) requires it live somewhere. No other item in any of the four
  sets changes.
- A third name in `SELECTED_IMPLEMENTATION_NAMES`
  (`tests/unit/test_core_broker_boundary.py`): `FILLING_MODE_NAME_TO_MT5`, the
  lookup `build_broker_owner` uses to translate a configured filling-mode name
  into MT5's integer constant — a direct consequence of that translation
  living in `build_broker_owner` rather than `MT5Config` itself, the module
  ADR-0015 already grants composition.py. Check the file's own prose for any
  description of the constant's current two-item shape (mirroring how
  `PIPELINE_NAME_GRANT`'s item count is stated in prose elsewhere in that
  file) and update it alongside the constant if present. No other constant,
  helper, or assertion in that file changes.
- `modify_order`, `cancel_order` and `close_position`'s docstrings each
  cite `place_order` by name as the reason they defer (`'for the reason given
  on :meth:`place_order`'` or equivalent) — no longer true once `place_order`
  is implemented. Each is corrected to state its own actual reason directly,
  using that method's own existing docstring summary line as the source (e.g.
  modify_order's `'amendment results cannot be reported honestly'`), not by
  inventing new wording. No other content in any of the three methods
  changes — they remain `NotImplementedError`.
- `packages/broker/src/atlas/broker/mt5/README.md`'s "Current
  limitations" section (lines ~144-168) is updated to remove `place_order`
  from the list of limitations and correct the section's item count
  accordingly. No other section of the README changes.

## 6. Non-goals

- `modify_order`, `cancel_order`, `close_position` — each remains
  `NotImplementedError`, each is its own future task.
- Reading deals back to report a fill at its actual price — named in
  ADR-0021's Context as separate unscoped work; untouched here.
- Any change to `ExecutionPolicy`, `OrderRequest`, `OrderType` or `Price`.
- Any strategy, backtesting, or runtime-wiring change — `CoreRuntime` still
  requires a strategy and policy neither this task nor any prior one supplies.
- Retry or reconnection behaviour for a trading call — explicitly out of
  scope per ADR-0021.

## 7. What exists

Nothing yet. This task's implementation has not been written in advance of
its spec.

## 8. Files expected to change

### 8.1 Expected
- `packages/broker/src/atlas/broker/mt5/constants.py` (modified)
- `packages/broker/src/atlas/broker/mt5/adapter.py` (modified — `place_order`,
  `Terminal` protocol gains `order_send`)
- `MT5Config`'s actual source file (modified — confirm path before editing)
- `packages/config/src/atlas/config/settings.py` (modified — `BrokerSettings`)
- `apps/atlas-core/src/atlas/apps/core/composition.py` (modified —
  `build_broker_owner`'s new refusal case)
- `tests/unit/broker/mt5/test_mt5_adapter.py` (modified)
- `tests/unit/test_config_settings.py` (modified)
- `tests/unit/test_core_composition.py` (modified — `build_broker_owner`
  test cases)
- `packages/broker/src/atlas/broker/mt5/mapper.py` (modified — adds the
  `MT5OrderResult` protocol `to_order` needs as a structural type for
  `place_order`'s success path)
- `tests/unit/broker/mt5/conftest.py` (modified — adds `FakeOrderResult`,
  `FakeTerminal.order_send`/`order_send_args`, and the config fixture's new
  `deviation_points`/`filling_mode_by_instrument` values)
- `tests/unit/broker/test_adapter_heartbeat.py` (modified — unrelated
  existing tests updated with placeholder MT5Config values, discovered
  necessary once deviation_points/filling_mode_by_instrument became
  required fields)
- `tests/unit/broker/test_base_adapter.py` (modified — same reason)
- `tests/unit/broker/mt5/test_mt5_connection.py` (modified — same reason)
- `tests/unit/broker/test_adapter_retry.py` (modified — same reason)
- `tests/unit/test_core_broker_boundary.py` (modified — widens
  `SELECTED_IMPLEMENTATION_NAMES` from two names to three)
- `packages/broker/src/atlas/broker/mt5/README.md` (modified — Current
  limitations section)
- `docs/tasks/ATLAS-TASK-0031.md` (this file, new)
- `docs/ROADMAP.md` (modified — at merge time, per precedent)

### 8.2 Prohibited
- `modify_order`, `cancel_order`, `close_position` — no implementation.
- `ExecutionPolicy`, `OrderRequest`, or anything in `atlas.execution`.
- Any concrete filling-mode-to-instrument mapping value or deviation number
  shipped in `config/` — those remain deployment-supplied, per ADR-0021.

## 9. Relationship to the ADRs

Implements ADR-0021 in full for `place_order` only. Touches no other ADR.

## 10. Roadmap

Not modified by this specification. Written at merge time, citing the real
commit, per precedent.
