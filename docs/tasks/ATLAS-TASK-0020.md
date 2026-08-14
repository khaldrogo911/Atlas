# ATLAS-TASK-0020 — Implement application ownership of BrokerAdapter

**Status:** Specified, not implemented
**Date:** 2026-08-14
**Baseline:** `a634fa4823c2c91dfdb071c699f893261be67b3d`
**Decision record:** [ADR 0013](../adr/0013-the-application-owns-the-adapter.md) —
*The application owns the adapter; the port stays in the broker package*
(Accepted, 2026-08-14).

This task implements the part of ADR-0013 that can be implemented at the
baseline, and no more. ADR-0013 names five responsibilities — construction,
holding, governing access, lifecycle sequencing and supervision. Three of them
are implementable today. One is blocked on a configuration decision ADR-0013
deliberately did not make, and this task specifies the seam and names the
blocker rather than inventing the decision. One is out of scope by ADR-0013's
own text.

`docs/ROADMAP.md` does not list this task, by that file's own rule — every row
in its status table is a completed task citing a commit. The roadmap row is
written when this task merges, the way ATLAS-TASK-0011 through ATLAS-TASK-0019
were, and is not part of the implementation. See §17.

---

## 1. Title

**ATLAS-TASK-0020 — Implement application ownership of `BrokerAdapter`.**

---

## 2. Status

Specified, not implemented. No branch, commit, pull request or CI run exists for
this task, and none is cited anywhere in this document.

The baseline is `a634fa4823c2c91dfdb071c699f893261be67b3d` on `main`, with a
clean working tree, no divergence from `origin/main`, and exactly one untracked
file — `docs/adr/0013-the-application-owns-the-adapter.md`, this task's decision
record. The implementer must confirm that state before making any change
(§18.1).

At the baseline the full suite collects **3389 tests**.

---

## 3. Architectural authority

**ADR-0013 is the sole decision this task implements.** Its Decision, at
`docs/adr/0013-the-application-owns-the-adapter.md:60-62`, reads:

> **`apps/atlas-core` owns the `BrokerAdapter`. It constructs the instance,
> holds it for the life of the process, governs what receives access to it,
> sequences its lifecycle, and carries the supervision duty ADR-0007 assigns to
> a caller.**

and at `:64-67`:

> **The port and its implementations do not move.** `BrokerAdapter`,
> `BaseBrokerAdapter`, `MockBrokerAdapter` and `MT5BrokerAdapter` stay in
> `packages/broker`. This record decides which layer owns *an instance and its
> use*, not where the code that defines it lives.

The five responsibilities are enumerated at ADR-0013 `:73-86`. This task's
disposition of each:

| # | Responsibility | ADR-0013 | This task |
|---|---|---|---|
| 1 | Construction | `:75` | **Partially blocked.** Seam implemented; no concrete adapter is constructed in application source. See §11 and §11.4. |
| 2 | Holding | `:76-77` | **Implemented.** §12. |
| 3 | Governing access | `:78-79` | **Implemented.** §13. |
| 4 | Lifecycle sequencing | `:80-83` | **Implemented.** §12.3. |
| 5 | Supervision | `:84-86` | **Out of scope.** ADR-0013 `:258-260` does not decide a run loop, supervisor or threading design. §6.6. |

Four further ADRs constrain this task and none is amended, footnoted or
superseded by it. Their bearing is set out in §8, §9, §10 and §19.

---

## 4. Problem statement

`docs/architecture/overview.md:118-121` states the defect in the repository's
own words:

> The chain the data flow draws is not joined end to end. Nothing outside the
> test suite produces a `TradeIntent` or hands one to `atlas.risk`, and **no
> layer owns a `BrokerAdapter`** — so the request `atlas.execution` builds is,
> today, received by nothing.

At the baseline this is literally true. Every construction of a `BrokerAdapter`
in the repository is inside `packages/broker/src` or inside `tests/`. No
application module names the port. `apps/atlas-core`'s entire source is
`apps/atlas-core/src/atlas/apps/core/__main__.py` (73 lines), which resolves
configuration, emits one JSON startup record and exits; its own module docstring
records that "the core service has no trading pipeline to run".

ADR-0011 `:174-176` named the consequence when it declined to give the port to
`atlas.execution`: "The broker-owning layer this record names does not exist."
ADR-0012 `:100-101` hit the same wall from the risk side: "whoever hands it
state calls them, and that layer does not exist yet." ADR-0013 has now named the
layer. Nothing yet embodies it.

**The problem this task removes is that the owner ADR-0013 names has no site in
the code.** It does not remove the absence of a pipeline, a run loop, a
supervisor or a venue configuration, and it must not appear to.

---

## 5. Scope

This task creates, in `apps/atlas-core`, the single site at which the
application holds a `BrokerAdapter`, sequences its lifecycle, and grants access
to it — and the tests that prove those properties and prove that no package
boundary moved.

The seam is exactly this:

```
apps/atlas-core                      ← the owner (this task)
  ├── constructs   … blocked on venue configuration (§11.4)
  ├── holds        … one instance, process lifetime      (§12)
  ├── governs      … granted downward, never acquired    (§13)
  ├── sequences    … connect / disconnect, in order      (§12.3)
  └── supervises   … out of scope (§6.6)
        │
        ▼
packages/broker    ← unchanged: port, base, mock, MT5     (§8)
```

In scope:

1. **S-1.** One new application module under
   `apps/atlas-core/src/atlas/apps/core/`, holding the ownership type.
2. **S-2.** The first `apps/atlas-core → atlas.broker` import edge, in that
   module and nowhere else in the app.
3. **S-3.** Behavioural tests for the ownership type, exercised against a real
   adapter implementation (§14.1).
4. **S-4.** AST tests asserting the app-side properties this task creates
   (§14.2).
5. **S-5.** Nothing else.

---

## 6. Non-goals

Each of these is out of scope because an accepted decision leaves it open, not
because it is merely unbuilt. Nothing in this task's diff may decide, prepare
for, or read as presuming any of them.

- **6.1 A broker or venue configuration schema.** ADR-0013 `:101-105`: "**The
  broker or venue surface in `AtlasSettings` is not decided here.** … What
  section it becomes, what it is called, what fields it carries and how
  credentials reach it are a separate decision." This task adds no settings
  field, no TOML key, no environment variable and no secrets mechanism. See
  §11.4.
- **6.2 Adapter selection.** Nothing in this task decides which implementation a
  process runs, or how that would be expressed. A default is a selection policy;
  this task states none. See §11.3.
- **6.3 A registry, service container, factory or locator.** ADR-0013 `:109-112`
  defines none and says why: "naming a mechanism here would decide an
  implementation on the evidence of zero call sites."
- **6.4 A dependency-injection framework.** No accepted decision requires one and
  none is added.
- **6.5 A run loop, engine, scheduler or trading pipeline.** ADR-0013 `:204`:
  "No composition root is implemented"; `:258-260` withholds the run loop,
  supervisor and threading design.
- **6.6 Supervision.** The fifth responsibility. ADR-0013 `:84-86` assigns the
  `health()` timer to the application; ADR-0013 `:258-260` withholds its design.
  This task creates the object that will eventually run it and runs nothing.
- **6.7 An `apps/` import rule.** ADR-0013 `:242-249` records that it neither
  creates nor implies one. §14.2 explains at length why the AST tests this task
  adds are not one.
- **6.8 Dashboard adapter ownership or access.** ADR-0013 `:250-252` leaves it
  open. `apps/dashboard` is untouched.
- **6.9 Execution or risk state ownership.** ADR-0012 `:282` and ADR-0013
  `:263-264` decline account and portfolio state. No `Account`, `Position` or
  portfolio snapshot is fetched, stored or passed anywhere by this task.
- **6.10 Order identity, idempotency, routing, fills or reconciliation.**
  ADR-0013 `:261-262`. Nothing here places, tracks or retries an order.
- **6.11 `ExecutionPolicy` or `TradeIntent` production.** No application module
  constructs either. `atlas.execution` and `atlas.strategy` are not imported by
  this task's diff at all.
- **6.12 MT5 filling-mode or deviation policy.** ADR-0013's exclusions; no MT5
  module is read, imported or changed.
- **6.13 A new package.** The 15 packages and 3 apps declared in
  `pyproject.toml:61-78` are unchanged. No source root is added.
- **6.14 Any change to `packages/broker`.** §8.

---

## 7. Required dependency direction

The edge this task adds is **downward, from an application to a package**:

```
apps/atlas-core ──▶ atlas.broker        (new — this task)
apps/atlas-core ──▶ atlas.config        (exists — ATLAS-TASK-0001)
```

ADR-0013 `:112-114` states the rule the direction must satisfy: access is
"*granted downward by the owner*, never *acquired upward by a package*".

Three properties must hold after implementation:

- **DD-1.** `apps/atlas-core` imports `atlas.broker`. This is the point of the
  task.
- **DD-2.** No module under `packages/` imports `atlas.apps`, in any form,
  including under a `TYPE_CHECKING` guard. This is already true and already
  enforced for the four guarded packages, whose `PERMITTED_ATLAS_PACKAGES`
  allowlists are closed tuples that contain no `atlas.apps` entry
  (`tests/unit/broker/test_adapter_contract.py:187`,
  `tests/unit/risk/test_risk_boundary.py:66`,
  `tests/unit/strategy/test_strategy_boundary.py:63-67`,
  `tests/unit/execution/test_execution_boundary.py:67`). This task must not
  widen any of those four tuples, and must not need to.
- **DD-3.** The six feature-package edges enumerated at
  `docs/architecture/overview.md:61-64` are unchanged in number and in
  direction. This task adds no edge between packages.

**No new package-to-package edge is created, and no existing one is widened.**

---

## 8. Broker boundary preservation

`packages/broker` is not modified by this task. Not one file, not one line.

- **B-1.** `BrokerAdapter`, `BaseBrokerAdapter`, `MockBrokerAdapter` and
  `MT5BrokerAdapter` stay where they are (ADR-0013 `:64-67`). No file is moved,
  renamed, re-exported or aliased.
- **B-2.** The port stays configuration-source agnostic. ADR-0013 `:92-95`:
  "`atlas.broker` remains configuration-source agnostic: it reads no environment
  and imports no configuration package." `tests/unit/broker/test_adapter_contract.py`
  asserts this with a closed allowlist of `atlas.broker` and `atlas.common`
  (`:187`) and an explicit assertion that `atlas.config` is not permitted
  (`:505`). Both must still pass unmodified.
- **B-3.** `MT5Config` keeps its current shape — frozen, `extra="forbid"`, seven
  fields (`packages/broker/src/atlas/broker/mt5/connection.py:336-354`). Its
  docstring at `:339` already describes the arrangement ADR-0013 ratifies:
  "Constructed by the composition root from `atlas.config` and handed to the
  adapter." This task does not change that sentence, and does not make it true
  either — see §11.4.
- **B-4.** The application depends on the **port**, never on an implementation.
  ADR-0006 `:96-99` requires that the mock be exported from `atlas.broker.mock`
  and never from `atlas.broker`, "so business logic still cannot discover which
  adapter it holds". The ownership module must name `BrokerAdapter` and must not
  name `MockBrokerAdapter`, `MT5BrokerAdapter`, `MockVenue`, `MT5Config` or
  `BaseBrokerAdapter`. §14.2 T-8 enforces this.
- **B-5.** ADR-0007's locking model is untouched. The two locks stay in
  `BaseBrokerAdapter`, and no third lock is added anywhere. ADR-0007 `:156-158`
  declines a global broker lock; this task does not introduce one under another
  name. See §12.4.

---

## 9. Execution boundary preservation

`packages/execution` is not modified by this task, and gains nothing.

- **E-1.** ADR-0011 is not superseded, edited or reopened. ADR-0013 `:268`
  records this explicitly.
- **E-2.** ADR-0011 `:277-278` forbids `atlas.execution` to name, obtain,
  construct or invoke a `BrokerAdapter`. That remains true and remains enforced
  by `tests/unit/execution/test_execution_boundary.py`, whose
  `VENUE_ACCESS_SYMBOLS` tuple (`:115`) covers `BrokerAdapter`, `OrderStatus`
  and the four trading methods, and whose `PERMITTED_BROKER_NAMES` (`:105`)
  admits only `OrderRequest`, `OrderType` and `Price`.
- **E-3.** ADR-0011 `:279-280` requires the package to stay stateless, with no
  lifecycle, run loop or service object. Nothing in this task's diff gives it
  one.
- **E-4.** `build_order_request` is not called by application source in this
  task. The `OrderRequest` it builds remains, in the overview's words, "received
  by nothing". Joining that end of the chain requires an `ExecutionPolicy` and a
  `TradeIntent`, and §6.11 excludes both.

**The owner exists; it is not yet wired to the thing that would feed it.** That
is the honest state after this task, and §16 stop condition 6 exists so that an
implementer who finds themselves wiring it stops instead.

---

## 10. Risk boundary preservation

`packages/risk` is not modified by this task, and gains nothing.

- **R-1.** ADR-0012 is not superseded, edited or reopened. ADR-0013 `:287`
  records this explicitly, and ADR-0013 `:294-300` records that ADR-0012's own
  revisit condition — "when a single wiring point exists and can be pointed at",
  ADR-0012 `:274-280` — **is not satisfied by ADR-0013**. It is not satisfied by
  this task either. This task creates an ownership site for one adapter, not a
  wiring point for the system's configuration.
- **R-2.** The exposure-limit decision stays as ADR-0012 made it.
  `evaluate_exposure` continues to read its own limit through
  `get_settings().risk.max_margin_utilisation`
  (`tests/unit/risk/test_risk_boundary.py:174`). No application module reads,
  passes, overrides or duplicates that limit.
- **R-3.** ADR-0012 `:100-101` — whoever hands risk its state calls the port
  operations — remains undecided. ADR-0013 `:302` restates that it "is also not
  decided here". This task must not appear to answer it: the ownership object
  must not call `get_account`, `get_positions`, `margin_required`,
  `margin_available` or `can_trade`, which are exactly
  `tests/unit/risk/test_risk_boundary.py`'s `PORT_OPERATION_SYMBOLS`.
- **R-4.** `atlas.risk`'s permitted imports are unchanged: `atlas.risk`,
  `atlas.broker`, `atlas.config`, `atlas.common` (`:66`), with `atlas.config`
  admitted for the single name `get_settings` (`:135`).

---

## 11. Construction requirements

### 11.1 What the owner constructs

**The ownership type is constructed with a `BrokerAdapter` supplied by its
caller.** It does not build one itself, and it does not choose one.

This is what ADR-0013 `:75` ("The application builds the adapter. Nothing below
it does") permits at the baseline. `apps/atlas-core` is the layer that will
build it; the ownership type is the thing that then holds it. Collapsing the two
into one step requires deciding which implementation to build, and §11.3 and
§11.4 are why that cannot be decided here.

- **C-1.** The parameter is annotated `BrokerAdapter`, imported from
  `atlas.broker`, which exports it (`packages/broker/src/atlas/broker/__init__.py:72`).
- **C-2.** No concrete adapter class is imported, referenced or instantiated by
  any module under `apps/`. Tests may and must instantiate one (§14.1).
- **C-3.** The type is not generic, not parameterised by implementation, and
  does not inspect, branch on, or record which implementation it was given.
  ADR-0006 `:96-99` is the reason.
- **C-4.** Construction of the ownership type performs no I/O. It does not
  connect. `MockBrokerAdapter` "starts disconnected"
  (`packages/broker/src/atlas/broker/mock/adapter.py:179`); the ownership type
  preserves that, and connecting is a separate, explicit step (§12.3).

### 11.2 What the owner does not construct

- **C-5.** `apps/atlas-core/src/atlas/apps/core/__main__.py` is **not modified**.
  It constructs no adapter and no ownership object. Its startup record, its two
  exit codes and its stderr failure path are byte-identical after this task, and
  `tests/unit/test_core_entrypoint.py` passes unmodified.

  This is deliberate and it is the crux of the task. `main()` is a live process
  entrypoint. For it to construct an adapter it must choose one, and §11.3 shows
  that both available choices are wrong at the baseline.

### 11.3 Why the entrypoint cannot choose

There are two adapter implementations and neither can be defaulted to.

- **`MockBrokerAdapter()` takes no configuration at all.**
  `packages/broker/src/atlas/broker/mock/adapter.py:186` gives both parameters a
  default and creates a fresh `MockVenue` when none is passed, so the bare call
  succeeds. It is therefore
  the only adapter a process could construct today — and making a live process
  default to it would be an adapter-selection policy that no accepted decision
  makes. It would also contradict ADR-0003's fail-closed stance, under which a
  misconfigured process refuses to start rather than starting wrong. A process
  that silently trades against a simulator is the worst available failure mode,
  and ADR-0006 `:96-99` exists precisely so that nothing downstream could tell.
- **`MT5BrokerAdapter(config: MT5Config, …)`** cannot be constructed at all.
  `packages/broker/src/atlas/broker/mt5/adapter.py:172` requires an `MT5Config`,
  which requires `login`, `password`, `server`, `terminal_path` and
  `server_utc_offset`
  (`packages/broker/src/atlas/broker/mt5/connection.py:336-354`). Nothing in the
  repository can produce those values. See §11.4.

Branching on `AtlasSettings.environment` to pick between them is the same
selection decision wearing a different hat, and §6.2 excludes it.

### 11.4 The exact blocking dependency

**`AtlasSettings` carries no broker or venue configuration section.** Its fields
are `environment`, `app_name`, `debug`, `logging`, `postgres`, `redis`,
`duckdb`, `risk` (`packages/config/src/atlas/config/settings.py:200-211`).
ADR-0011 `:102-103` recorded the same absence — "there is no broker or venue
surface anywhere in it" — and ADR-0013 `:101-105` explicitly declined to add
one.

The chain therefore breaks at exactly one link, and it can be named precisely:

```
AtlasSettings   ──✗──▶   MT5Config   ──▶   MT5BrokerAdapter   ──▶   BrokerAdapter
     ▲                                                                    ▲
  no broker section                                        the owner can hold this
  (settings.py:200-211)                                    the moment it is handed one
```

`MT5Config`'s docstring names the missing party by role — "Constructed by the
composition root from `atlas.config` and handed to the adapter"
(`connection.py:339`) — and ADR-0013 has supplied the layer. What is still
missing is the source: the settings section that layer would read.

**This task must not invent that section.** Not as a `BrokerSettings` model, not
as a `venue` field, not as a TOML block under `config/`, not as an environment
variable, not as a placeholder with empty defaults, and not as a comment
describing the shape a later task should use. Every one of those is the separate
architectural decision ADR-0013 `:104-105` reserved, and writing it here decides
it by default.

**What this task delivers instead is the seam on the near side of that break.**
The owner is implemented, tested against a real adapter, and ready to hold
whatever the configuration decision later produces. When that decision is made,
the work it leaves is one call site — build the adapter, hand it to the owner —
and no change to the ownership type's shape.

---

## 12. Holding requirements

### 12.1 Where the instance lives

- **H-1.** The adapter is held as an **instance attribute of the ownership
  type**, private by name.
- **H-2.** It is **not** held in a module-level variable, a class attribute, a
  mutable default, an `lru_cache`, a `functools.cache`, a class-level registry
  or a process-global of any kind.

`atlas.config` uses `@lru_cache(maxsize=1)` for `get_settings`
(`packages/config/src/atlas/config/settings.py:331-332`), and that precedent is
**deliberately not followed here**, for two reasons.

First, a cached module-level accessor is importable from anywhere in the
process. Any future app module could reach the adapter by importing it, which is
acquisition-upward wearing the owner's clothes — the exact direction ADR-0013
`:112-114` fixes against, and a service locator under §6.3's definition.

Second, settings are an immutable validated value with no lifecycle. An adapter
is a stateful resource that connects, disconnects, holds two locks (ADR-0007)
and can fail. The two are not the same kind of thing and should not be held the
same way.

### 12.2 Lifetime

- **H-3.** One ownership object holds one adapter. It does not replace, swap or
  release it. There is no setter.
- **H-4.** The lifetime of the held instance is the lifetime of the ownership
  object, which the application scopes to the process (ADR-0013 `:76-77`).
  Nothing in this task enforces process scope, because nothing in this task
  constructs the object in a process (§11.2).

### 12.3 Lifecycle sequencing

ADR-0007 `:147-149` assigns this duty to the caller because it cannot be
discharged inside an adapter: "'Check then act' is not atomic … A caller that
must not lose a request has to sequence its own lifecycle calls." ADR-0013
`:80-83` gives the duty to the owner.

The ownership type exposes exactly two lifecycle operations:

- **H-5. Start.** Calls the held adapter's `connect()` exactly once.
- **H-6.** Starting an already-started owner **raises**; it does not silently
  reconnect and does not silently no-op. Reconnection policy is a supervision
  concern (§6.6), and a silent no-op would decide it. Failing loudly is the
  fail-closed reading, consistent with ADR-0003.
- **H-7. Stop.** Calls the held adapter's `disconnect()`.
- **H-8.** Stopping an owner that was never started, or stopping twice, is a
  **no-op and does not raise**. A teardown path that raises can leave a
  connection open, and a failed start must still be safe to unwind.
- **H-9.** The owner does not call `reconnect()`, `health()`, `ping()`,
  `latency()` or `is_connected()` on any schedule. `reconnect` and `health` are
  the supervision surface (ADR-0013 `:84-86`, `:80-83`); §6.6 defers it.
- **H-10.** The owner does not catch, translate, wrap or suppress any
  `BrokerError`. A connect failure propagates to the caller unchanged. Deciding
  what to do about a failed connection is supervision.

### 12.4 Concurrency

- **H-11.** No lock, condition, event, semaphore, thread or task is created.
  ADR-0007 `:156-158` declines a global broker lock and this task does not add
  one under another name (§8 B-5). The two locks in `BaseBrokerAdapter` are the
  whole synchronisation story and stay that way.
- **H-12.** The ownership type's own state transitions are consequently **not
  synchronised**, and the module's docstring must say so plainly. At the
  baseline the application is single-threaded — it has no run loop (§6.5) — so
  nothing calls these methods concurrently. This is a known limit that the
  supervision decision must resolve, and recording it is not a design for it.

---

## 13. Access-governance requirements

ADR-0013 `:109-114`:

> The application hands the adapter to what needs it. It does not do so through
> a registry, a service container, a factory or a locator, and this record
> defines none … What is fixed is the direction — access is *granted downward by
> the owner*, never *acquired upward by a package*.

- **A-1.** The held adapter is reachable through **exactly one** public member
  of the ownership type, and through nothing else. No public attribute, no
  property that aliases it, no `__getattr__` passthrough, no dunder that exposes
  it.
- **A-2.** That member **raises `BrokerNotConnectedError`** when the owner has
  not been started, or has been stopped.

  `BrokerNotConnectedError` is exported from `atlas.broker`
  (`packages/broker/src/atlas/broker/__init__.py:79`) and already means what is
  meant here. Defining a new application-local exception would create a second
  error vocabulary for one condition, and this task adds no exception type.
- **A-3.** The ownership type is **not importable as an instance**. There is no
  module-level object anyone can import and use (§12.1 H-2). Access requires
  holding a reference someone above handed you, which is what "granted downward"
  means in code.
- **A-4.** The ownership type does not call any port method other than
  `connect()` and `disconnect()`. In particular it calls none of
  `place_order`, `modify_order`, `cancel_order`, `close_position`,
  `get_account`, `get_positions`, `margin_required`, `margin_available` or
  `can_trade` (§9 E-2, §10 R-3).
- **A-5.** No package under `packages/` gains any way to obtain the adapter.
  This is not a new assertion — it is the four existing boundary tests, which
  must pass unmodified (§7 DD-2).
- **A-6.** No second consumer is created. Nothing in `apps/dashboard` (§6.8),
  nothing in `apps/research`, and nothing in `packages/` is handed the adapter,
  because at the baseline nothing needs it (§9 E-4).

---

## 14. Test requirements

Every test below is new. No existing test is modified, renamed, moved, deleted
or re-parameterised.

### 14.1 Behavioural tests — `tests/unit/test_core_broker_ownership.py`

Marked `pytest.mark.unit`, following `tests/unit/test_core_entrypoint.py`, which
is the repository's only precedent for testing application code.

These tests exercise the ownership type against a **real `MockBrokerAdapter`**,
not a stub, a `Mock` or a hand-written fake. ADR-0006 shipped the mock for this
(`:96-99`), and a hand-rolled double would test the double.

- **T-1.** An owner constructed with an adapter holds that exact instance
  (identity, once started).
- **T-2.** Before start, the access member raises `BrokerNotConnectedError`
  (A-2).
- **T-3.** Constructing the owner does not connect: the adapter's
  `is_connected()` is still `False` (C-4).
- **T-4.** After start, `is_connected()` is `True` and the access member returns
  the adapter (H-5).
- **T-5.** Starting twice raises, and the adapter remains connected — the failed
  second start does not disturb the first (H-6).
- **T-6.** After stop, `is_connected()` is `False` and the access member raises
  again (H-7, A-2).
- **T-7.** Stop before start does not raise, does not connect, and leaves the
  adapter disconnected (H-8).
- **T-8.** Stop twice does not raise (H-8).
- **T-9.** A `connect()` failure propagates unchanged, and the owner is left
  un-started — a subsequent stop still does not raise, and the access member
  still raises (H-10, H-8). The failure is injected through the mock venue's own
  surface, `MockVenue.schedule_failure(operation, error)`
  (`packages/broker/src/atlas/broker/mock/venue.py:981`), so the test drives the
  real adapter's real failure path rather than a double's.

### 14.2 AST tests — `tests/unit/test_core_broker_boundary.py`

These walk the AST of every module under `apps/atlas-core/src`, in the manner of
the four existing boundary tests, including imports written under a
`TYPE_CHECKING` guard.

**These are not the `apps/` import rule.** §6.7 excludes it and ADR-0013
`:242-249` records that no such rule is created or implied. The distinction is
structural and must survive review:

- The four package boundary tests hold a **closed allowlist** —
  `PERMITTED_ATLAS_PACKAGES` — which is a positive statement of everything a
  package may import. **This file defines no such tuple**, permits nothing, and
  makes no statement about what `apps/atlas-core` may import in general.
- What it asserts instead are the four properties *this task creates*, each
  traceable to an already-accepted decision: ADR-0006's abstraction (T-13),
  ADR-0013's single-owner shape (T-11, T-12), and ADR-0013's exclusion of
  supervision and of the port operations (T-14).

If an implementer finds themselves writing an allowlist, they have started the
undecided work; §16 stop condition 4 applies.

- **T-10.** No module under `apps/atlas-core/src` imports `atlas.execution`,
  `atlas.strategy` or `atlas.risk` (§6.11, §6.9).
- **T-11.** Exactly one module under `apps/atlas-core/src` imports
  `atlas.broker` at all: the ownership module (S-2).
- **T-12.** The name `BrokerAdapter` appears in exactly that one module and
  nowhere else under `apps/`.
- **T-13.** No module under `apps/` imports `atlas.broker.mock`,
  `atlas.broker.mt5`, or names `MockBrokerAdapter`, `MT5BrokerAdapter`,
  `MockVenue`, `MT5Config` or `BaseBrokerAdapter` (§8 B-4, ADR-0006 `:96-99`).
- **T-14.** No module under `apps/` names `reconnect`, `health`, `place_order`,
  `modify_order`, `cancel_order`, `close_position`, `get_account`,
  `get_positions`, `margin_required`, `margin_available` or `can_trade` (§13
  A-4, §12.3 H-9).
- **T-15.** The ownership type holds the adapter on an instance attribute only:
  no module-level assignment under `apps/` binds a `BrokerAdapter`, and the
  module contains no `lru_cache` or `cache` decorator (§12.1 H-2).

### 14.3 What must still pass, unmodified

- **T-16.** `tests/unit/test_core_entrypoint.py` — all of it, unchanged (C-5).
- **T-17.** The four package boundary tests — 757 tests, unchanged (§7 DD-2).
- **T-18.** `tests/contract/test_repository_structure.py` — 191 tests,
  unchanged, and **still 191**. `LEAF_MODULES`
  (`tests/contract/test_repository_structure.py:90-93`, `:115`) is derived from
  `__init__.py` files and parameterises four tests (`:205-219`). The new module
  must therefore be a **module**, not a subpackage; a directory with an
  `__init__.py` would add four tests and change that count.

---

## 15. Acceptance criteria

- **AC-1.** ADR-0013's responsibilities 2, 3 and 4 are implemented in
  `apps/atlas-core`, and responsibility 1 is implemented as far as §11.1 defines
  it. Truths H-1 to H-12, A-1 to A-6 and C-1 to C-5 hold.
- **AC-2.** `apps/atlas-core` imports `atlas.broker` from exactly one module,
  and that module names only `BrokerAdapter` and `BrokerNotConnectedError` from
  it (T-11, T-12, T-13).
- **AC-3.** No file under `packages/` is changed. `git diff --stat` shows zero
  lines under `packages/` (§8).
- **AC-4.** No ADR is changed, added or superseded. `docs/ROADMAP.md`,
  `docs/architecture/overview.md` and `docs/adr/README.md` are unchanged.
- **AC-5.** No file under `config/` is changed, no settings field is added, and
  `AtlasSettings`'s eight fields are the same eight
  (`packages/config/src/atlas/config/settings.py:200-211`). §11.4.
- **AC-6.** `apps/atlas-core/src/atlas/apps/core/__main__.py` is unchanged, and
  `tests/unit/test_core_entrypoint.py` passes unmodified (C-5, T-16).
- **AC-7.** The suite collects **3389 + N** tests, where N is the number added
  by §14.1 and §14.2, and all 3389 pre-existing tests still pass. No pre-existing
  test is modified, skipped, deleted or renamed.
- **AC-8.** `tests/contract/test_repository_structure.py` still reports exactly
  191 tests (T-18).
- **AC-9.** The four boundary tests still report exactly 757 tests, with no
  `PERMITTED_ATLAS_PACKAGES` tuple widened (T-17, DD-2).
- **AC-10.** `ruff check .`, `black --check .` and `mypy .` are clean. `mypy` is
  run in the repository's strict configuration; the ownership type is fully
  annotated and the module has no `# type: ignore`.
- **AC-11.** No new source root, package or app directory exists.
  `pyproject.toml` is unchanged.
- **AC-12.** The diff contains no statement that decides, prepares for, or
  presumes an answer to anything in §6 or §20 — including in a docstring, a
  comment, a `TODO` or a name.
- **AC-13.** The diff touches exactly the files §17 permits, and no others.

---

## 16. Stop conditions

Stop and report rather than deciding, if:

1. **The implementation appears to require a broker or venue configuration
   field, model, TOML key or environment variable.** It does not; §11 defines a
   seam that needs none. If it seems to, the scope has drifted from ownership to
   configuration, and that is the separate decision ADR-0013 `:104-105`
   reserved. This is the single most likely failure mode of this task.
2. **The implementation appears to require choosing which adapter a process
   runs**, or a default, or a branch on `environment`. §11.3.
3. **The implementation appears to require a registry, container, factory,
   locator or DI framework.** ADR-0013 `:109-112` defines none, on the stated
   grounds that there are zero call sites to design against. There are still
   zero.
4. **A test being written needs an allowlist of what `apps/` may import.**
   §14.2. That is the undecided `apps/` rule (§6.7), and it begins with an owner
   decision gate and a new ADR, not with a test file.
5. **A boundary test's `PERMITTED_ATLAS_PACKAGES` tuple needs widening**, or any
   existing test needs modifying to accommodate this task. Either means the task
   is changing something it declared it would not.
6. **The work appears to require calling `build_order_request`, producing a
   `TradeIntent` or an `ExecutionPolicy`, or otherwise joining the pipeline.**
   §9 E-4 and §6.11. The owner is meant to sit unwired at the end of this task.
7. **The work appears to require a thread, timer, loop or lock.** §6.5, §6.6,
   §12.4.
8. **`__main__.py` appears to need modifying.** §11.2. If a genuine argument
   exists that it must, that argument is a decision about process startup and
   adapter selection, and it is reported rather than acted on.
9. **The baseline has moved**, an ADR-0014 exists, or a task after
   ATLAS-TASK-0020 exists — any of which may have already decided something this
   specification assumes open.
10. **The collected test count before any change is not 3389**, or
    `docs/adr/0013-the-application-owns-the-adapter.md` is absent or differs from
    the accepted record.
11. **Anything in §6 or §20 would be decided in passing** to finish the work.

In every case: report both pieces of conflicting evidence and explain the
conflict. Do not silently reconcile them.

---

## 17. Files expected to change

### 17.1 Expected

| Path | Change |
|---|---|
| `apps/atlas-core/src/atlas/apps/core/<module>.py` | **New.** The ownership type. A module, not a package (T-18). |
| `tests/unit/test_core_broker_ownership.py` | **New.** §14.1. |
| `tests/unit/test_core_broker_boundary.py` | **New.** §14.2. |

The module's name is an implementation choice within `apps/atlas-core` and is
not fixed by ADR-0013. It must not be named for an excluded concept — not
`container`, `registry`, `factory`, `locator`, `engine`, `runtime`, `pipeline`
or `composition_root` — because a name is a claim, and ADR-0013 `:204` records
that no composition root is implemented.

### 17.2 Potentially expected

| Path | Condition |
|---|---|
| `apps/atlas-core/src/atlas/apps/core/__init__.py` | Only if the ownership type is re-exported. Its docstring at `:3-8` already describes the app as the layer that "wires the packages together" and is already accurate; it must not be rewritten to claim a composition root now exists (ADR-0013 `:204`). |

Nothing else. If a fourth file needs to change, §16 applies.

### 17.3 Prohibited

| Path | Why |
|---|---|
| `packages/**` | §8. Zero lines. |
| `apps/atlas-core/src/atlas/apps/core/__main__.py` | C-5, §11.2. |
| `apps/dashboard/**`, `apps/research/**` | §6.8. |
| `config/**` | §6.1, AC-5. |
| `docs/adr/**` | ADRs are immutable (`docs/adr/README.md:4-6`). Including the ADR index. |
| `docs/ROADMAP.md` | §17 preamble and the Roadmap note below. |
| `docs/architecture/overview.md` | The living-document correction is a separate task, per the pattern of ATLAS-TASK-0015, 0016 and 0019. Its `:118-121` statement that "no layer owns a `BrokerAdapter`" becomes false when this task merges, and that correction belongs in the follow-up, not here. |
| `pyproject.toml`, `.github/workflows/ci.yml`, `scripts/**` | AC-11. |
| Any existing test file | AC-7. |

---

## 18. Verification commands

Existing tooling only. No new script, target, marker or CI job is added.

Bash, from the repository root. `scripts/quality.sh` runs Ruff, Black, MyPy and
Pytest in CI's order and is the canonical gate; the individual commands below
are for narrowing a failure.

### 18.1 Before making any change

```bash
git rev-parse HEAD                      # a634fa4823c2c91dfdb071c699f893261be67b3d
git status --porcelain                  # only the untracked ADR-0013 file
./.venv/Scripts/python.exe -m pytest -q --collect-only | tail -1   # 3389 tests
```

### 18.2 After implementation

```bash
./.venv/Scripts/python.exe -m pytest -q

./.venv/Scripts/python.exe -m pytest tests/contract -q                     # 191
./.venv/Scripts/python.exe -m pytest \
  tests/unit/broker/test_adapter_contract.py \
  tests/unit/risk/test_risk_boundary.py \
  tests/unit/strategy/test_strategy_boundary.py \
  tests/unit/execution/test_execution_boundary.py -q                       # 757
./.venv/Scripts/python.exe -m pytest tests/unit/test_core_entrypoint.py -q

./.venv/Scripts/python.exe -m ruff check .
./.venv/Scripts/python.exe -m black --check --diff .
./.venv/Scripts/python.exe -m mypy .
```

`mypy` requires a target; a bare invocation errors. `.` is what
`scripts/quality.sh:57` and `.github/workflows/ci.yml:62` use.

### 18.3 Diff verification

```bash
git diff --stat                         # three files, plus §17.2 if taken
git diff --stat -- packages/            # empty (AC-3)
git diff -- apps/atlas-core/src/atlas/apps/core/__main__.py   # empty (AC-6)
git diff --stat -- config/ docs/ pyproject.toml               # empty (AC-4, AC-5, AC-11)
```

---

## 19. Relationship to the ADRs

**Thirteen ADRs are Accepted and immutable. This task implements one and edits
none.**

`docs/adr/README.md:31` defines exactly four statuses — `Proposed`, `Accepted`,
`Superseded by ADR-NNNN`, `Deprecated`. There is no amendment status, and this
task creates no ADR.

| ADR | Bearing on this task | Effect |
|---|---|---|
| ADR-0003 | Fail-closed configuration; a misconfigured process refuses to start | Cited as the reason a live default to the mock is refused (§11.3) |
| ADR-0006 | Mock exported from `atlas.broker.mock` only, so business logic cannot discover which adapter it holds (`:96-99`) | Enforced by B-4 and T-13; unchanged |
| ADR-0007 | Two locks in the base adapter and none below it; lifecycle sequencing is the caller's (`:147-149`); no global broker lock (`:156-158`) | Sequencing implemented (§12.3); locking model untouched (B-5, H-11) |
| ADR-0011 | Execution builds the request; another layer owns the port | Not superseded (ADR-0013 `:268`); §9 |
| ADR-0012 | Risk is handed its state and reads its own limits | Not superseded, not reopened (ADR-0013 `:287`); its revisit condition still unsatisfied (ADR-0013 `:294-300`); §10 |
| ADR-0013 | The decision this task implements | §3 |

`docs/adr/README.md`'s index table lists twelve entries and does not yet list
ADR-0013. That is a real gap and it is **not fixed here** — the index is under
`docs/adr/`, which §17.3 prohibits. It is recorded as a finding for whoever next
touches the ADR directory.

---

## 20. Separation from future architectural decision work

This task implements one decision and prepares none. The repository's remaining
work is still blocked behind decisions it has deliberately declined to make, and
ADR-0013 `:240-264` lists them. Nothing in this task's diff may be justified as
groundwork for any of them:

- **The broker or venue configuration surface.** ADR-0013 `:101-105`. This is
  the blocker §11.4 names, and naming a blocker is not designing its removal.
- **What kind of rule an `apps/` boundary is.** ADR-0013 `:242-249` records that
  it is not created, implied or prefigured. §14.2 states in structural terms why
  this task's AST tests are not one.
- **Adapter selection and process startup.** No ADR decides how a process learns
  which venue it trades. §11.3.
- **Supervision: the run loop, the `health()` timer, the threading model.**
  ADR-0013 `:258-260`.
- **Dashboard adapter ownership or access.** ADR-0013 `:250-252`.
- **The state contracts the remaining risk controls need.** ADR-0010 `:198`,
  ADR-0011 `:184`, ADR-0012 `:282`, ADR-0013 `:263-264`.
- **Order identity and idempotency; routing, fills and reconciliation.**
  ADR-0013 `:261-262`.

When one of these is taken up, it begins with an owner decision gate and a new
ADR, in the sequence ATLAS-TASK-0014, ATLAS-TASK-0017 and ADR-0013 followed —
not with an implementation that assumes an answer.

What this task is worth on its own terms: after it, the sentence at
`docs/architecture/overview.md:118-121` — "no layer owns a `BrokerAdapter`" —
stops being true, and every decision listed above will be argued against a
repository in which the owner exists and can be pointed at. ADR-0012 `:274-280`
set its revisit condition as "when a single wiring point exists and can be
pointed at"; this task does not satisfy it (§10 R-1), but it is the first thing
in the repository to move toward it.

---

## Roadmap

`docs/ROADMAP.md` is not modified by this task. Its row for ATLAS-TASK-0020 is
written after this specification has been reviewed and explicitly authorised,
and after the implementation has merged, following the pattern of
ATLAS-TASK-0011 through ATLAS-TASK-0019.

The living-document correction to `docs/architecture/overview.md:118-121` is
likewise a separate, later task, per §17.3 and the precedent of ATLAS-TASK-0015,
ATLAS-TASK-0016 and ATLAS-TASK-0019.
