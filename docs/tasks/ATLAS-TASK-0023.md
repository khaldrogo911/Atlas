# ATLAS-TASK-0023 — Construct the broker adapter at startup

**Status:** Specified, not implemented
**Date:** 2026-08-15
**Baseline:** `a83f9984446b2b0c871fa2274af39ecfd14f7fd8`
**Decision record:** [ADR 0015](../adr/0015-broker-adapter-selection.md) —
*The application selects `MT5BrokerAdapter` and constructs it at startup*
(Accepted, 2026-08-15).

This task implements ADR-0015 and nothing else. ADR-0015 decided that
`apps/atlas-core` selects `MT5BrokerAdapter`, translates `BrokerSettings`
into `MT5Config` at its own composition boundary, constructs the adapter
during startup and hands it to a `BrokerOwner`, and that an unusable broker
configuration fails startup at the translation. This task performs that
translation, that construction and that handoff. It opens no session, runs
no loop, and hands the adapter to nothing downstream.

ADR-0015 left the mechanism of the translation open on purpose — "it names
no function, method, class or module that will carry it beyond those the
repository already establishes". This task settles the module, the function
and the error surface, because a specification cannot be implemented without
them. Everything else ADR-0015 left open stays open and is listed in §21.

`docs/ROADMAP.md` is not modified by this task. See §24.

---

## 1. Title

**ATLAS-TASK-0023 — Construct the broker adapter at startup.**

---

## 2. Status

Specified, not implemented. No branch, pull request or CI run exists for the
implementation of this task, and none is cited anywhere in this document.

The baseline is `a83f9984446b2b0c871fa2274af39ecfd14f7fd8` on `main`, with a
clean working tree and level with `origin/main`. That commit indexed
ADR-0015; `8db18fcd37b940c0cb5e6bad46fb5a5b33c57510` accepted it. The
implementer must confirm that state before making any change (§19.1).

At the baseline the full suite collects **3614 tests**: 191 in
`tests/contract`, 757 across the four package boundary tests, 183 in
`tests/unit/test_core_broker_boundary.py`, 17 in
`tests/unit/test_core_broker_ownership.py` and 5 in
`tests/unit/test_core_entrypoint.py`.

---

## 3. Architectural authority

**ADR-0015 is the sole decision this task implements.** Its Decision reads:

> **`apps/atlas-core` selects `MT5BrokerAdapter` as this runtime's broker
> implementation, translates `BrokerSettings` into `MT5Config` at its own
> composition boundary, constructs the adapter during startup, and hands it
> to a `BrokerOwner`. An unusable broker configuration fails startup at the
> translation.**

ADR-0015 also fixes five properties that this task must preserve rather than
re-derive:

| Property | ADR-0015 | This task |
|---|---|---|
| No discriminator in configuration | "No `provider`, `venue`, `broker` or `adapter` field, no enum, no string key" | §6.3, §20 AC-16 |
| No `atlas.config → atlas.broker` edge | "`atlas.config` must not import `atlas.broker`" | §14 CB-2 |
| Construction is not connection | "Deciding that an adapter is *constructed* at startup therefore decides nothing about when a session is *opened*" | §9, §17 C-7 |
| `BrokerOwner` is unchanged | "This record redefines none of its semantics" | §12, §14 CB-4 |
| The startup record keeps eight keys | "No broker key, no broker value and no credential enters `build_startup_record`" | §12, §17 E-4 |

Five further ADRs constrain this task and none is amended, footnoted or
superseded by it: ADR-0003, ADR-0006, ADR-0007, ADR-0013 and ADR-0014. Their
bearing is set out in §23.

---

## 4. Problem statement

Every part of the seam exists and nothing joins them.

```
AtlasSettings.broker  ──▶  MT5Config  ──▶  MT5BrokerAdapter  ──▶  BrokerOwner
    exists                  exists            exists               exists
    TASK-0022               ADR-0006          ADR-0006             TASK-0020

              ✗  no process performs any arrow in this chain
```

`BrokerOwner` is instantiated only in tests. No module under `apps/`
imports `atlas.broker.mt5`, names `MT5Config` or names `MT5BrokerAdapter`;
`tests/unit/test_core_broker_boundary.py` asserts that it is so. The four
values an `MT5Config` cannot default are configured, validated and
CI-covered, and nothing reads them.

ATLAS-TASK-0022 named the cause precisely and declined to remove it: its
**TR-3** recorded that "the wiring point is not chosen, named or located",
and its **TR-4** handed the meaning of a validation rejection to "the task
that builds the translation". ADR-0015 has now decided both.

**The problem this task removes is that nothing constructs an adapter.** It
does not remove the absence of a run loop, a supervisor, a pipeline, a
downstream recipient or a live session, and it must not appear to.

---

## 5. Scope

This task adds one composition module to `apps/atlas-core`, calls it from
the existing entrypoint, updates the application boundary contract to the
single edge ADR-0015 authorises, corrects the one operational statement the
change falsifies, and adds the tests that prove all of it.

In scope:

1. **S-1.** One new module,
   `apps/atlas-core/src/atlas/apps/core/composition.py`, holding the
   `BrokerSettings → MT5Config` translation, the construction of
   `MT5BrokerAdapter` and the handoff to `BrokerOwner`.
2. **S-2.** `apps/atlas-core/src/atlas/apps/core/__main__.py` invokes the
   builder inside the `try` that already produces `startup_failed`.
3. **S-3.** A translation rejection becomes the existing
   `ConfigurationError`, reaching the existing handler and the existing
   exit code.
4. **S-4.** `tests/unit/test_core_broker_boundary.py` updated to permit the
   single authorised edge while preserving every other prohibition.
5. **S-5.** One pre-existing test updated:
   `test_valid_configuration_exits_zero_and_emits_one_json_line` in
   `tests/unit/test_core_entrypoint.py`. §9.3.
6. **S-6.** New tests: §17.
7. **S-7.** `.env.example` lines 99-101 corrected. §16 DOC-1.
8. **S-8.** Nothing else.

---

## 6. Non-goals

Each of these is out of scope because ADR-0015 leaves it open or forbids it,
not because it is merely unbuilt. Nothing in this task's diff may decide,
prepare for, or read as presuming any of them.

- **6.1 Opening a session.** `BrokerOwner.start()` is not called, and
  `connect()` is not called. §9.2.
- **6.2 A run loop, supervisor, scheduler or reconnect policy.** ADR-0013
  `:258-260` withholds all four and ADR-0015 does not claim them.
- **6.3 Adapter-selection configuration.** No `venue`, `provider`,
  `broker_type`, `kind` or `enabled` field; no enum; no environment branch.
  ADR-0015 rejected the environment branch explicitly.
- **6.4 `MockBrokerAdapter` as a fallback.** Nothing selects, defaults to,
  or branches toward the mock. ADR-0015: "`MockBrokerAdapter` is not a
  fallback."
- **6.5 A dependency-injection framework, service locator, registry or
  factory abstraction.** ADR-0015 defines none and none may be inferred.
- **6.6 New configuration.** No new field, no new invariant, no new
  environment variable, and no change to a `BrokerSettings` default.
- **6.7 Exposing `timeout_ms`, `portable` or `server_utc_offset`.** All
  three keep `MT5Config`'s defaults. §8.
- **6.8 `BrokerOwner` changes.** `broker_ownership.py` is not modified, and
  neither is its test file. §12.
- **6.9 Startup-record expansion.** No key, no value, no credential. §12.2.
- **6.10 Handing the adapter downstream.** `atlas.execution`,
  `atlas.strategy` and `atlas.risk` are not imported, named or reached.
- **6.11 A general `apps/` import rule.** ADR-0013 `:242-249` leaves it
  undecided and ADR-0015 explicitly does not create one. No `PERMITTED_*`
  tuple is introduced. §11.4.
- **6.12 Broadening `apps/dashboard` or `apps/research`.** ADR-0015 "grants
  nothing" to either.
- **6.13 Any change to `packages/`.** Not one file, not one line.
- **6.14 ADR modification.** Every ADR is immutable
  (`docs/adr/README.md:4-6`), including the index.
- **6.15 Unrelated documentation debt.** §16.
- **6.16 Roadmap completion bookkeeping.** §24.

---

## 7. Decision A — the composition module

### 7.1 The module

```
apps/atlas-core/src/atlas/apps/core/composition.py
```

One public function:

```python
def build_broker_owner(settings: AtlasSettings) -> BrokerOwner:
```

- **M-1.** `__all__ = ["build_broker_owner"]`.
- **M-2.** No module-level state of any kind, cached or otherwise —
  `__all__` is the only module-scope binding, mirroring what
  `test_the_ownership_module_binds_nothing_at_module_scope_but_its_exports`
  already asserts of `broker_ownership.py`.
- **M-3.** No `lru_cache` or `cache` decorator. The `get_settings`
  precedent is deliberately not followed here either: a cached builder is
  importable from anywhere, which is acquisition upward wearing the
  composition layer's clothes.
- **M-4.** It is **not** re-exported from
  `apps/atlas-core/src/atlas/apps/core/__init__.py`. That file keeps
  `__all__: list[str] = []`, on the precedent that ATLAS-TASK-0020 did not
  re-export `BrokerOwner` either.
- **M-5.** Imports, and only these: `MT5BrokerAdapter` and `MT5Config` from
  `atlas.broker.mt5`; `BrokerOwner` from
  `atlas.apps.core.broker_ownership`; `ConfigurationError` from
  `atlas.config`; `ValidationError` from `pydantic`, aliased
  `PydanticValidationError` exactly as `settings.py:26` aliases it;
  `AtlasSettings` from `atlas.config` under a `TYPE_CHECKING` guard,
  exactly as `__main__.py:22-23` takes it.
- **M-6.** It does **not** name `BrokerAdapter`. The return annotation is
  `BrokerOwner`. This keeps
  `test_one_module_names_the_abstraction_and_it_is_the_same_one` true
  without amendment, and keeps ADR-0015's count of three contradicted
  assertions honest.

### 7.2 Why the name

`composition` is the repository's own word for this layer, not a new one.
`apps/atlas-core/src/atlas/apps/core/__init__.py:6-8` already declares the
package's boundary as "Composition and process lifecycle only", and
ADR-0015 places the translation "at its own composition boundary". A new
module for a new concern beside `__main__.py` is the shape ATLAS-TASK-0020
established when it added `broker_ownership.py`.

### 7.3 Why not inline in `__main__.py`

Two mechanical reasons, not a preference.

`__main__.py` also owns the exit codes and the startup record. An
implementation exemption granted to that file is inherited by every future
change to either, which is wider than the "bounded by its purpose"
authorisation ADR-0015 wrote.

`test_core_broker_boundary.py:351-360`,
`test_a_guarded_port_import_is_caught_in_a_module_that_has_none`, uses
`__main__.py` **because** it has no port import — it splices a guarded
import into that file's real source to prove the scanner sees through
`if TYPE_CHECKING:`. Translating inline makes the test's premise and its
name false while its assertions still pass, which is a test that has
stopped measuring what it claims to. Under this specification `__main__.py`
imports `atlas.apps.core.composition` and not `atlas.broker`, so that test
stays true and unmodified.

---

## 8. Decision B — the translation contract

Exactly this, and nothing more:

```
BrokerSettings.login          →  MT5Config.login
BrokerSettings.password       →  MT5Config.password
BrokerSettings.server         →  MT5Config.server
BrokerSettings.terminal_path  →  MT5Config.terminal_path
```

- **TC-1.** The three MT5-only fields — `timeout_ms`, `portable`,
  `server_utc_offset` — are **omitted from the constructor call**. They are
  not passed with their default values. Passing `timeout_ms=60_000`
  explicitly would be inventing a mapping ADR-0015 declined to make, and
  would silently pin a default that belongs to `MT5Config`. §20 AC-6 is the
  test that catches it.
- **TC-2.** `BrokerSettings.password` is a `SecretStr` and `MT5Config.password`
  is a `SecretStr`. The value passes through **unchanged**.
  `get_secret_value()` must not appear anywhere under `apps/`. §20 AC-7.
- **TC-3.** No coercion, defaulting, trimming, normalisation or
  substitution is applied to any of the four values. What
  `AtlasSettings.broker` resolved to is what `MT5Config` receives.
- **TC-4.** The translation is the only place the mapping exists. It is not
  duplicated in a comment, a docstring, a `TypedDict`, a protocol or a
  `.to_*()` helper anywhere else, and ATLAS-TASK-0022's **TR-2** — the
  mapping does not appear in `packages/config/src` in any form — stays in
  force.

---

## 9. Decision C — the startup sequence

### 9.1 Order

`main()` performs, in this order:

1. `load_settings()`.
2. `build_broker_owner(settings)`.
3. `sys.stdout.write(json.dumps(build_startup_record(settings)) + "\n")`.
4. `return EXIT_OK`.

- **SC-1.** `load_settings()` stays first. `test_core_entrypoint.py:81-98`
  asserts that a production process without a database password exits 2
  with `"postgres.password"` in the failure record; that test must keep
  failing at configuration resolution, before the broker is reached.
- **SC-2.** Construction precedes the startup record. A translation failure
  must leave stdout **empty**, which is what `test_core_entrypoint.py:95`
  already asserts of the configuration-failure path.
- **SC-3.** `build_broker_owner(settings)` is called as a bare statement.
  Its result is not bound, stored, returned, cached or registered, because
  there is no run loop and no downstream recipient to hand it to. Inventing
  storage or a lifecycle for it is §6.2 and §6.10.
- **SC-4.** `main()`'s return type, both exit codes, and the eight startup
  record keys are unchanged.

### 9.2 What startup does not do

`start()` is not called. `connect()` is not called. No session is opened,
no terminal is contacted and no vendor SDK is imported.

This is ADR-0015 read exactly: its stage table separates "Adapter
construction — `MT5BrokerAdapter(config)` — no terminal contact" from
"Terminal connection — `connect()`, via `BrokerOwner.start()`", and the
record decides the former. Three facts make it the only implementable
reading. `MT5BrokerAdapter.__init__` performs no I/O and imports no vendor
module (§15). CI runs `ubuntu-latest` and installs no `mt5` extra, so
`connect()` can only raise there. And making `main()` connectable under
test would require injecting an `MT5Session`, which is the
dependency-injection mechanism §6.5 forbids.

### 9.3 The one pre-existing test this changes

`tests/conftest.py:38-41`: the `isolated_env` fixture deletes every
`ATLAS_*` variable, so `BrokerSettings` resolves to `login=0` and
`server=""`. `MT5Config` rejects that pair (§15). Any `main()` that
constructs at startup therefore returns `EXIT_CONFIG_ERROR` under that
fixture, and
`TestMain::test_valid_configuration_exits_zero_and_emits_one_json_line`
must supply valid broker configuration in order to keep asserting what it
was written to assert.

There is no ADR-0015-compliant way to avoid this. Skipping construction
when the broker is unconfigured is the "construction-optional mode" the
record names and forbids, and its Costs section states the consequence
directly: "Today `ATLAS_ENV=development` with no `ATLAS_BROKER__*` set
resolves settings and exits 0. After this decision is implemented, it will
not."

**This is the only pre-existing test the task may modify.** A second one
is stop condition 6.

---

## 10. Decision D — failure semantics

### 10.1 The mechanism

`MT5Config` raises `pydantic.ValidationError` when the translated values are
unusable. The composition boundary catches it and raises the existing
`ConfigurationError`, mirroring `settings.py:392-396` exactly:

```python
except PydanticValidationError as exc:
    msg = f"invalid broker configuration:\n{exc}"
    raise ConfigurationError(msg) from exc
```

`main()`'s existing `except ConfigurationError` handler then writes
`{"event": "atlas.core.startup_failed", "error": ...}` to stderr and
returns `EXIT_CONFIG_ERROR`.

- **FC-1.** **No new exception type.** `ConfigurationError` is an existing
  `RuntimeError` subclass whose docstring already covers this case:
  "Configuration could not be located, parsed, or is internally
  inconsistent. Raised eagerly at start-up rather than tolerated, so that a
  misconfigured process fails before it can act on incorrect settings."
- **FC-2.** **No new exit code.** `EXIT_CONFIG_ERROR` is 2 and stays 2.
- **FC-3.** **No new event name.** `atlas.core.startup_failed` is reused
  verbatim.
- **FC-4.** **No new failure mechanism.** No logging call, no handler, no
  retry, no partial-start mode.
- **FC-5.** The `except` clause in `main()` is not broadened beyond
  `ConfigurationError`. The composition module is what narrows a pydantic
  failure into it.

`pydantic` is a declared dependency of the single root distribution
(`pyproject.toml:24`), of which `apps/atlas-core/src` is a source root
(`pyproject.toml:76`). Importing it in the composition module adds no
dependency and requires no change to `pyproject.toml`.

### 10.2 What the message must and must not contain

- **FC-6.** The message identifies the broker configuration as the source
  and names the offending field, following the precedent that
  `test_core_entrypoint.py:98` asserts `"postgres.password"` appears in the
  failure record. The pydantic body names `login` or `server`; the prefix
  names `broker`.
- **FC-7.** The message must never contain the broker password. It is
  built from the caught exception, never from the settings object, and
  never by interpolating `BrokerSettings`. §17 C-8 and E-3 are the tests
  that hold this, and they exist because this is the one path in the task
  that stands between a credential and a stream.

---

## 11. Decision E — the boundary change

### 11.1 What is now permitted

**Exactly one module under `apps/` may import `atlas.broker.mt5` and name
`MT5Config` and `MT5BrokerAdapter`, and it is
`apps/atlas-core/src/atlas/apps/core/composition.py`.**

That is the whole of the authorisation ADR-0015 granted: "It is bounded by
its purpose: it permits naming the selected implementation for translation
and construction."

### 11.2 What remains forbidden

Everywhere under `apps/`, the composition module included:

- `atlas.broker.mock`, in any form, including under a `TYPE_CHECKING` guard;
- the names `MockBrokerAdapter`, `MockVenue` and `BaseBrokerAdapter`;
- every `UNCALLED_PORT_OPERATIONS` entry — the supervision surface, the
  polling surface, trading and account state;
- every `PIPELINE_PACKAGES` entry — `atlas.strategy`, `atlas.risk`,
  `atlas.execution`;
- any module-level assignment binding an adapter;
- the name `BrokerAdapter` anywhere except `broker_ownership.py`.

And, for `apps/dashboard` and `apps/research` specifically: no broker
import and no implementation name of any kind. ADR-0015 grants them
nothing.

Keeping the mock forbidden in the composition module is deliberate and is
the mechanical form of ADR-0015's "`MockBrokerAdapter` is not a fallback".
A module that may name the selected implementation still may not name the
one it was selected over.

### 11.3 The constants this requires

`CONCRETE_ADAPTER_NAMES` is split, so that the authorisation is bounded by
*which* implementation rather than by a general permission:

```python
SELECTED_IMPLEMENTATION_NAMES: Final = ("MT5BrokerAdapter", "MT5Config")
UNSELECTED_IMPLEMENTATION_NAMES: Final = (
    "MockBrokerAdapter",
    "MockVenue",
    "BaseBrokerAdapter",
)
CONCRETE_ADAPTER_NAMES: Final = (
    SELECTED_IMPLEMENTATION_NAMES + UNSELECTED_IMPLEMENTATION_NAMES
)
COMPOSITION_MODULE: Final = CORE_SRC / "atlas" / "apps" / "core" / "composition.py"
```

`CONCRETE_ADAPTER_NAMES` is retained as the union so that
`test_the_implementation_rule_can_actually_fire` keeps proving the scanner
fires on all five names.

### 11.4 What this is still not

- **BC-1.** No `PERMITTED_*` tuple is introduced.
  `test_this_file_declares_no_allowlist` is retained **verbatim** and must
  keep passing.
- **BC-2.** No general `apps/` import rule is created, implied or
  prefigured. ADR-0015: "The general `apps/` import rule remains exactly as
  undecided as ADR-0013 `:242-249` left it." The file states one bounded
  permission, granted by one named record, for one named purpose.
- **BC-3.** The file's docstring `:10-19` currently reads "nothing is
  permitted by this file". That stops being true and must be rewritten to
  say what is: one permission exists, ADR-0015 granted it, it is bounded to
  the selected implementation for translation and construction, and no
  general rule follows from it. The docstring's existing account of why the
  rule "would begin with a decision record rather than with a test file" is
  the sentence this change satisfies, and should be kept and pointed at
  ADR-0015.
- **BC-4.** `test_this_file_states_no_positive_permission_for_an_application`
  pins the file's module-scope names to an exact set and must be updated to
  the 17 the file then binds: `REPO_ROOT`, `APPS_ROOT`, `CORE_SRC`,
  `APP_SOURCES`, `CORE_SOURCES`, `OWNERSHIP_MODULE`, `COMPOSITION_MODULE`,
  `ADAPTER`, `PIPELINE_PACKAGES`, `CONCRETE_ADAPTER_PACKAGES`,
  `CONCRETE_ADAPTER_NAMES`, `SELECTED_IMPLEMENTATION_NAMES`,
  `UNSELECTED_IMPLEMENTATION_NAMES`, `UNCALLED_PORT_OPERATIONS`,
  `CACHING_DECORATORS`, `WHOLE_MODULE`, `pytestmark`. Its name and its
  docstring change with it: what it guards is no longer "no positive
  permission" but "one permission, named, bounded and traceable".

### 11.5 The three assertions that change

ADR-0015 named exactly three, and §15 confirms exactly three by running the
shipped scanners. They are:

| Test | Line | Becomes |
|---|---|---|
| `test_one_module_imports_the_port_and_it_is_the_ownership_module` | `:376` | Two named modules reach `atlas.broker`: the ownership module for the port, the composition module for the implementation. Asserted as a set of names, not as a count. |
| `test_no_app_module_imports_an_implementation_package` | `:406` | `atlas.broker.mt5` permitted in the composition module only; `atlas.broker.mock` forbidden everywhere. |
| `test_no_app_module_names_an_implementation` | `:416` | `SELECTED_IMPLEMENTATION_NAMES` permitted in the composition module only; `UNSELECTED_IMPLEMENTATION_NAMES` forbidden everywhere. |

No other boundary assertion changes. If a fourth appears to need changing,
stop condition 6 applies.

---

## 12. Decision F — `BrokerOwner` and the startup record

### 12.1 `BrokerOwner`

- **OW-1.** `broker_ownership.py` is byte-identical.
- **OW-2.** `tests/unit/test_core_broker_ownership.py` is byte-identical and
  still reports 17 tests.
- **OW-3.** Its semantics are unchanged: `start()` connects and raises
  `RuntimeError` on a second call; `stop()` is a no-op unless started;
  `adapter` raises `BrokerNotConnectedError` before start and after stop;
  construction connects nothing.
- **OW-4.** The owner learns nothing about which implementation it holds.
  `__init__` still takes a `BrokerAdapter`, and the composition module
  hands it one without telling it what it is. ADR-0015: "Construction is
  upstream of ownership."

### 12.2 The startup record

- **SR-1.** `build_startup_record` keeps exactly its eight keys: `event`,
  `app_name`, `environment`, `debug`, `logging`, `postgres`, `redis`,
  `duckdb`.
- **SR-2.** No broker key, no broker value, no login and no password enters
  it, on any path, including when the broker is configured and valid.
- **SR-3.** `test_core_entrypoint.py:43-63`,
  `test_record_omits_the_broker_section_entirely`, is not modified and must
  keep passing. §17 E-4 extends it to the record `main()` actually emits.

---

## 13. Security and secret handling

- **SEC-1.** The broker password keeps the single route ADR-0003 defines and
  ADR-0014 extended: a `SecretStr` supplied through the process
  environment. No TOML password, no secrets service, no `safe_*` accessor,
  no logging policy.
- **SEC-2.** `get_secret_value()` appears nowhere under `apps/`. The
  translation passes the `SecretStr` through and never unwraps it.
- **SEC-3.** No stream — stdout or stderr — carries the password on any
  path, success or failure. §17 C-8, E-3.
- **SEC-4.** `tests/unit/risk/test_risk_boundary.py` is byte-identical. Its
  credential denylist scans `packages/risk` modules only and is unaffected
  by an `apps/` change; widening it can produce a false positive and is
  stop condition 7 of ATLAS-TASK-0022, which stands.

---

## 14. Boundary preservation

- **CB-1.** `packages/` is not modified — no package, no file, no line.
  `MT5Config` keeps its seven fields, its `frozen=True` and its
  `extra="forbid"`. This task makes `connection.py:339` ("Constructed by
  the composition root from `atlas.config`") true for the first time by
  building the caller that sentence anticipated, without touching the
  sentence.
- **CB-2.** `atlas.config` does not import `atlas.broker`, name `MT5Config`
  or gain a translating member. ADR-0014's decision and ATLAS-TASK-0022's
  **TR-2** are untouched: the translation lives in `apps/`, in both
  directions of that rule.
- **CB-3.** The four package boundary tests' `PERMITTED_ATLAS_PACKAGES`
  tuples are not widened: `test_adapter_contract.py:187`,
  `test_risk_boundary.py:66`, `test_strategy_boundary.py:63-67`,
  `test_execution_boundary.py:67`. All 757 tests pass unmodified.
  `atlas.broker`'s own permitted set stays `("atlas.broker", "atlas.common")`
  — this task creates an edge *into* the broker package, never out of it.
- **CB-4.** `broker_ownership.py` and
  `tests/unit/test_core_broker_ownership.py` are byte-identical. §12.
- **CB-5.** `tests/contract/test_repository_structure.py` is not modified
  and still reports exactly 191. `LEAF_MODULES` derives from `__init__.py`
  files (`:90-93`) and no `__init__.py` is added, so the new module changes
  nothing there.
- **CB-6.** The six feature-package edges at
  `docs/architecture/overview.md:61-64` are unchanged in number and
  direction. This task adds no edge between feature packages; the edge it
  adds runs from an application.
- **CB-7.** `apps/dashboard` and `apps/research` are not modified and gain
  nothing. §11.2.
- **CB-8.** `pyproject.toml`, `.github/workflows/ci.yml` and `scripts/` are
  not modified. No new source root, dependency, job, marker or script.

---

## 15. Verified evidence this specification rests on

Each of these was measured against the baseline, not inferred. An
implementer who finds any of them false has hit stop condition 10 or 11.

**The three contradicted assertions are exactly three.** Loading the real
helper functions out of `tests/unit/test_core_broker_boundary.py` and
running them over a hypothetical composition module reports
`test_one_module_imports_the_port_and_it_is_the_ownership_module`,
`test_no_app_module_imports_an_implementation_package` and
`test_no_app_module_names_an_implementation` as failing, and
`test_one_module_names_the_abstraction_and_it_is_the_same_one`,
`test_no_app_module_names_an_operation_the_owner_does_not_call`,
`test_no_module_level_assignment_binds_an_adapter` and
`test_no_atlas_core_module_imports_a_pipeline_package` as passing.

**`MT5Config` rejects exactly two of the four defaults.**
`BrokerSettings()` resolves to `login=0`, `password=SecretStr('')`,
`server=''`, `terminal_path=Path('.')`. Building `MT5Config` from those
raises `ValidationError` with two errors: `('login',) Input should be
greater than 0` and `('server',) String should have at least 1 character`.

**An empty password and `terminal_path='.'` are accepted.** Verified by
constructing `MT5Config(login=1, server='X-Demo', password=SecretStr(''),
terminal_path=Path('.'))` successfully. §21.2 records the gap this leaves,
which this task must not close.

**Construction imports no vendor SDK.** `MetaTrader5` is absent from
`sys.modules` both before and after `MT5BrokerAdapter(config)`, and the
constructed adapter reports `is_connected() is False`.

**`ValidationError` is a `ValueError`; `ConfigurationError` is a
`RuntimeError`.** They share no branch of the hierarchy, so the narrowing
in §10.1 is a real conversion and not an accident of inheritance.

**The boundary file's parametrisation is understood.** Its 183 collected
tests decompose as 34 scanner tests, 21 mutation tests, 9 pipeline, 3
single-module, 35 implementation, 71 supervision, 8 instance-holding and 2
self-guard. One new module under `CORE_SRC` adds 29 (4 + 3 + 7 + 14 + 1),
so the file collects at least 212 before the §11 restructure is counted.

---

## 16. Required documentation truths

After implementation these must be true, and the implementer must not
create them by editing a document this task forbids (§22.2):

- **DOC-1.** `.env.example` lines 99-101 no longer state that "a process
  with this block unset still starts, and still cannot trade". The first
  clause becomes operationally false the moment this task merges, and this
  file is instruction to a deployer rather than commentary — shipping a
  false one is a configuration hazard, not documentation drift. The
  corrected text says what becomes true: the four values are required, a
  process without usable ones exits 2 at startup, and `login` and `server`
  are the two the translation actually rejects.
- **DOC-2.** No statement is added anywhere claiming that a session is
  opened, that a run loop exists, that the adapter is handed to a
  consumer, or that the trading pipeline is joined. None of the four is
  true after this task.
- **DOC-3.** `config/README.md` is not modified. Its rules already cover
  the broker section without amendment.
- **DOC-4.** The living-document corrections this task creates are **not**
  made here. §21.3.

---

## 17. Test requirements

**No pre-existing test is modified, renamed, moved, deleted or
re-parameterised, except the one §9.3 names.**

### 17.1 The composition boundary — `tests/unit/test_core_composition.py`

A new file, following the class-per-concern structure the neighbouring core
test files use.

- **C-1.** Default settings raise `ConfigurationError`, and the message
  names `broker`.
- **C-2.** `login=0` with a valid server raises `ConfigurationError`.
- **C-3.** `server=""` with a valid login raises `ConfigurationError`.
- **C-4.** Valid settings return a `BrokerOwner`, and the adapter it holds
  is an `MT5BrokerAdapter`.
- **C-5.** The four values arrive intact: `login`, the password's
  `get_secret_value()` **read in the test only**, `server` and
  `terminal_path`.
- **C-6.** The three MT5-only fields keep `MT5Config`'s defaults —
  `timeout_ms == 60_000`, `portable is False`,
  `server_utc_offset == timedelta(0)`. This is the test that catches TC-1
  being violated by a well-meaning explicit pass-through.
- **C-7.** No connection occurs: `MetaTrader5` is absent from
  `sys.modules`, the owner is not started, and `owner.adapter` raises
  `BrokerNotConnectedError`.
- **C-8.** With a sentinel password set and the configuration otherwise
  invalid, the raised `ConfigurationError`'s message contains neither the
  sentinel nor the string `SecretStr(`.
- **C-9.** The module binds nothing at module scope but `__all__`, and
  carries no caching decorator — the same two properties
  `test_core_broker_boundary.py:443-450` asserts of the ownership module.

### 17.2 The entrypoint — `tests/unit/test_core_entrypoint.py`

- **E-0.** *(modified)*
  `test_valid_configuration_exits_zero_and_emits_one_json_line` supplies
  valid broker configuration and keeps asserting exactly what it asserted
  before: `EXIT_OK`, empty stderr, one JSON line, `event` and
  `environment`. Prefer a small fixture in this file over repeating four
  `monkeypatch.setenv` calls per test.
- **E-1.** An unconfigured process returns `EXIT_CONFIG_ERROR`, writes
  **nothing** to stdout, and writes one `atlas.core.startup_failed` record
  to stderr.
- **E-2.** That record's `error` names the broker configuration and the
  offending field.
- **E-3.** With a sentinel broker password set and the configuration
  otherwise invalid, the sentinel appears in neither stream.
- **E-4.** With valid broker configuration, the record `main()` emits still
  has exactly the eight keys, no `broker` key, and neither the login nor
  the password anywhere in the rendered line.

### 17.3 The application boundary — `tests/unit/test_core_broker_boundary.py`

- **B-1.** `atlas.broker.mt5` is imported by exactly one module under
  `apps/`, and it is the composition module.
- **B-2.** `atlas.broker.mock` is imported by **no** module under `apps/`,
  the composition module included.
- **B-3.** No module under `apps/` names any
  `UNSELECTED_IMPLEMENTATION_NAMES` entry, the composition module
  included.
- **B-4.** Exactly two modules under `apps/atlas-core` import
  `atlas.broker`, and they are the ownership module and the composition
  module — asserted by name, as a set, never as a count.
- **B-5.** `BrokerAdapter` is named by exactly one module under `apps/`,
  and it is still `broker_ownership.py`.
- **B-6.** The composition module names no `UNCALLED_PORT_OPERATIONS`
  entry. It constructs; it does not connect, poll, supervise or trade.
- **B-7.** New "can actually fire" cases for B-1 and B-3, in the manner the
  file already requires of every rule: a scanner that cannot be shown to
  fail is not a test.
- **B-8.** The self-guards, updated per §11.4:
  `test_this_file_declares_no_allowlist` verbatim, and the module-scope
  name pin updated to the 17 names BC-4 lists.

### 17.4 What must still pass, unmodified

- **T-1.** `tests/unit/test_core_broker_ownership.py` — 17 tests,
  byte-identical.
- **T-2.** `tests/contract/test_repository_structure.py` — 191 tests,
  unchanged, and still 191.
- **T-3.** The four package boundary tests — 757 tests, unchanged.
- **T-4.** `tests/unit/test_config_settings.py` — 66 tests, unchanged.
- **T-5.** The four `test_core_entrypoint.py` tests other than E-0,
  unchanged. In particular
  `test_record_omits_the_broker_section_entirely` and
  `test_invalid_configuration_exits_two_and_reports_on_stderr`.
- **T-6.** Every other boundary assertion in
  `test_core_broker_boundary.py` not named in §11.5.

---

## 18. Stop conditions

Stop and report rather than deciding, if:

1. **A dependency-injection mechanism appears necessary.** §6.5. ADR-0015
   defines none and none should be inferred.
2. **A factory, registry or service locator appears necessary.** §6.5.
3. **A discriminator appears necessary** — a `venue`, `provider`,
   `broker_type`, `kind` or `enabled` field, or an environment branch.
   §6.3. ADR-0015 rejected the environment branch by name.
4. **`packages/broker` or `packages/config` requires modification.** §14
   CB-1, CB-2.
5. **`MT5Config` seems to need relaxing** to accept what `BrokerSettings`
   permits. The asymmetry is deliberate; ADR-0015 decided its meaning is
   refusal.
6. **A second pre-existing test appears to require modification**, beyond
   the one §9.3 authorises — including a fourth boundary assertion beyond
   the three §11.5 names.
7. **A general allowlist appears necessary.** §11.4 BC-1, BC-2.
8. **`BrokerOwner` requires modification.** §12.
9. **Connecting at startup appears necessary.** §9.2.
10. **The baseline has moved** from
    `a83f9984446b2b0c871fa2274af39ecfd14f7fd8`, or ADR-0015 is absent or
    differs from the accepted record `8db18fcd`.
11. **The collected test count before any change is not 3614.**
12. **Anything in §6 or §21 would be decided in passing** to finish the
    work.

In every case: report both pieces of conflicting evidence and explain the
conflict. Do not silently reconcile them.

---

## 19. Verification commands

Existing tooling only. No new script, target, marker or CI job is added.

### 19.1 Before making any change

```bash
git rev-parse HEAD                      # a83f9984446b2b0c871fa2274af39ecfd14f7fd8
git status --porcelain                  # empty
./.venv/Scripts/python.exe -m pytest -q --collect-only | tail -1   # 3614 tests
```

### 19.2 After implementation

```bash
./.venv/Scripts/python.exe -m pytest -q

./.venv/Scripts/python.exe -m pytest tests/contract -q                       # 191
./.venv/Scripts/python.exe -m pytest \
  tests/unit/broker/test_adapter_contract.py \
  tests/unit/risk/test_risk_boundary.py \
  tests/unit/strategy/test_strategy_boundary.py \
  tests/unit/execution/test_execution_boundary.py -q                         # 757
./.venv/Scripts/python.exe -m pytest tests/unit/test_core_broker_ownership.py -q   # 17
./.venv/Scripts/python.exe -m pytest tests/unit/test_core_broker_boundary.py -q
./.venv/Scripts/python.exe -m pytest tests/unit/test_core_composition.py -q
./.venv/Scripts/python.exe -m pytest tests/unit/test_core_entrypoint.py -q

./.venv/Scripts/python.exe -m ruff check .
./.venv/Scripts/python.exe -m black --check --diff .
./.venv/Scripts/python.exe -m mypy .
```

### 19.3 Diff verification

```bash
git diff --stat -- packages/ config/ docs/adr/ docs/architecture/    # empty
git diff --stat -- docs/ROADMAP.md .github/ pyproject.toml scripts/  # empty
git diff -- tests/unit/test_core_broker_ownership.py                 # empty
git diff -- tests/unit/risk/test_risk_boundary.py                    # empty
git diff -- apps/atlas-core/src/atlas/apps/core/broker_ownership.py  # empty
git diff -- apps/atlas-core/src/atlas/apps/core/__init__.py          # empty
```

### 19.4 Secret verification

```bash
grep -rn "get_secret_value" apps/                                    # no matches
```

---

## 20. Acceptance criteria

- **AC-1.** `main()` with the four `ATLAS_BROKER__*` variables set returns
  `EXIT_OK`, writes exactly one JSON line to stdout, and leaves stderr
  empty.
- **AC-2.** `main()` with no broker configuration returns
  `EXIT_CONFIG_ERROR`, stdout is empty, and stderr carries one
  `atlas.core.startup_failed` record.
- **AC-3.** The `error` string in AC-2 names the broker configuration and
  the offending field, following `test_core_entrypoint.py:98`.
- **AC-4.** No stream on any path contains the broker password.
- **AC-5.** `build_startup_record` returns exactly the same eight keys, and
  `"broker" not in record` even when the broker is configured and valid.
- **AC-6.** The constructed `MT5Config` has `timeout_ms == 60_000`,
  `portable is False` and `server_utc_offset == timedelta(0)`.
- **AC-7.** `MT5Config.password` receives the `SecretStr` unchanged, and
  `get_secret_value()` appears nowhere under `apps/`.
- **AC-8.** `MetaTrader5` is absent from `sys.modules` after a successful
  `main()`.
- **AC-9.** The constructed `BrokerOwner` is not started, and
  `owner.adapter` raises `BrokerNotConnectedError`.
- **AC-10.** Exactly one module under `apps/` names `MT5Config` or
  `MT5BrokerAdapter`, and it is the composition module.
- **AC-11.** Zero modules under `apps/` name `MockBrokerAdapter`,
  `MockVenue` or `BaseBrokerAdapter`, or import `atlas.broker.mock`.
- **AC-12.** `apps/dashboard` and `apps/research` name no implementation
  and import no broker package.
- **AC-13.** Exactly one module under `apps/` names `BrokerAdapter`, and it
  is `broker_ownership.py`.
- **AC-14.** `tests/unit/test_core_broker_boundary.py` declares no
  module-scope name beginning with `PERMITTED`.
- **AC-15.** `tests/contract` reports exactly 191; the four package
  boundary tests report exactly 757; `test_core_broker_ownership.py`
  reports exactly 17 and is byte-identical.
- **AC-16.** `git diff --stat` shows zero lines under `packages/`,
  `config/`, `docs/adr/`, `docs/architecture/`, `docs/ROADMAP.md`,
  `.github/`, `pyproject.toml` and `scripts/`.
- **AC-17.** `ruff check .`, `black --check .` and `mypy .` are clean under
  the repository's strict configuration, with no `# type: ignore` added.
- **AC-18.** The full suite is green and collects 3614 + N. No pre-existing
  test is skipped, renamed or deleted, and exactly one is modified:
  `test_valid_configuration_exits_zero_and_emits_one_json_line`.
- **AC-19.** The diff touches exactly the files §22.1 lists, and none of
  the paths §22.2 prohibits.
- **AC-20.** The diff contains no statement that decides, prepares for, or
  presumes an answer to anything in §6 or §21 — including in a docstring, a
  comment, a `TODO` or a name.

---

## 21. Deferred decisions and known gaps

### 21.1 What ADR-0015 left open, and what this task does with each

| ADR-0015 open item | This task |
|---|---|
| The module carrying the translation | **Resolved.** §7 — `composition.py`. |
| The function carrying it | **Resolved.** §7 — `build_broker_owner`. |
| Which exception reaches `main()`, and the exit code | **Resolved.** §10 — the existing `ConfigurationError` and exit 2. |
| Whether `start()` is called at startup | **Resolved.** §9.2 — it is not. |
| Reconnect policy | **Open.** §6.2. |
| Health checks and the supervision timer | **Open.** §6.2. |
| Failover, multiple adapters, venues or accounts | **Open.** §6.3. |
| Whether `apps/dashboard` may hold a `BrokerAdapter` | **Open.** §6.12. |
| External configuration or secrets services | **Open.** ADR-0003 `:82-85`. |
| Exposing `server_utc_offset`, `timeout_ms`, `portable` | **Open.** §6.7. |
| Startup-record expansion | **Open.** §12.2; the record is unchanged, which is the status quo and not a rule. |
| A DI framework, service locator, registry or factory | **Open.** §6.5. |
| The general `apps/` import rule | **Open.** §11.4 BC-2, ADR-0013 `:242-249`. |
| The run loop and what receives the adapter | **Open.** §6.2, §6.10. |

### 21.2 Gaps this task preserves, deliberately

- **The unusable-but-accepted configuration gap.** Verified in §15:
  `MT5Config` accepts `password=SecretStr('')` and
  `terminal_path=Path('.')`. A deployment that sets only
  `ATLAS_BROKER__LOGIN` and `ATLAS_BROKER__SERVER` therefore starts,
  constructs an adapter, and fails at the first connect instead of at
  startup. Closing this means adding a validation rule, which is a new
  invariant and a new configuration requirement — §6.6, and ADR-0015's "No
  new field, no new invariant, no new environment variable". **The gap is
  recorded, not closed.**
- **The `server_utc_offset` gap.** Inherited unchanged from
  ATLAS-TASK-0022 §21.3: a deployment against a trade server that does not
  publish UTC cannot be corrected through this configuration surface.
- **The discarded owner.** §9 SC-3 builds a `BrokerOwner` and does not
  retain it, because no run loop and no downstream recipient exist to hand
  it to. What the construction buys is what `__main__.py`'s own docstring
  says the entrypoint is for — proving "that contract holds in the
  environment it was deployed into". This is named rather than hidden, and
  it is the shape of the process until a run loop is decided.

### 21.3 Created by this task, and named here

- **The living-document corrections.**
  `docs/architecture/overview.md:117-122` states that "although
  `apps/atlas-core` owns the `BrokerAdapter`, no adapter is constructed
  outside that suite for it to hold", and `:191-193` states that the
  entrypoint "resolves configuration, enforces the environment's
  invariants, emits a JSON startup record and exits". Both become
  inaccurate when this task merges. Both belong in a follow-up
  documentation task, per the precedent of ATLAS-TASK-0015, 0016, 0019 and
  0021, and per ADR-0013 `:280-283`. §22.2 forbids touching that file here.
- **The ADR-0015 non-guarantee coming due.** ADR-0015's closing sentence —
  "No adapter is constructed, no translation exists, no boundary test
  changes" — was true of the record and stops being true of the
  repository. That correction belongs in the roadmap and the living
  documents, never in ADR-0015 itself.

### 21.4 Inherited and still outstanding

Not this task's, and not fixed here: ADR-0011 `:101-103` ("there is no
broker or venue surface anywhere in it"), inaccurate since
ATLAS-TASK-0022; and `docs/ROADMAP.md:100` ("this file declares no
ATLAS-TASK-0023, no ADR-0015 and no work after them"), inaccurate since
`8db18fcd`. §24.

---

## 22. Files expected to change

### 22.1 Expected

| Path | Change |
|---|---|
| `apps/atlas-core/src/atlas/apps/core/composition.py` | New. Translation, construction, handoff. §7, §8. |
| `apps/atlas-core/src/atlas/apps/core/__main__.py` | Call the builder inside the existing `try`; exit-code docstring updated. §9. |
| `tests/unit/test_core_composition.py` | New. §17.1. |
| `tests/unit/test_core_entrypoint.py` | E-0 modified; E-1 to E-4 added. §17.2. |
| `tests/unit/test_core_broker_boundary.py` | §11, §17.3. |
| `.env.example` | Lines 99-101 corrected. §16 DOC-1. |

Six files. If a seventh needs to change, §18 applies.

### 22.2 Prohibited

| Path | Why |
|---|---|
| `packages/**` | §6.13, CB-1, CB-2. Zero lines, every package. |
| `apps/atlas-core/src/atlas/apps/core/broker_ownership.py` | §12, CB-4. |
| `apps/atlas-core/src/atlas/apps/core/__init__.py` | §7 M-4. |
| `apps/dashboard/**`, `apps/research/**` | §6.12, CB-7. |
| `tests/unit/test_core_broker_ownership.py` | §12 OW-2, CB-4. |
| `tests/unit/risk/test_risk_boundary.py` | §13 SEC-4. |
| The four package boundary test files | CB-3. |
| `tests/contract/**` | CB-5. |
| `config/**` | §16 DOC-3. |
| `docs/adr/**` | ADRs are immutable (`docs/adr/README.md:4-6`), index included. |
| `docs/ROADMAP.md` | §24. |
| `docs/architecture/overview.md` | §21.3 — a separate task. |
| `pyproject.toml`, `.github/workflows/ci.yml`, `scripts/**` | CB-8. |

---

## 23. Relationship to the ADRs

**Fifteen ADRs are Accepted and immutable. This task implements one and
edits none.**

| ADR | Bearing on this task | Effect |
|---|---|---|
| ADR-0003 | Secrets in the environment; fail fast at startup | §13; extended in reach, unchanged in rule |
| ADR-0006 | Business logic cannot discover which adapter it holds | Preserved — selection is confined to composition and what leaves it is a `BrokerAdapter` |
| ADR-0007 | Two locks; `connect`/`disconnect`/`reconnect` finality | Untouched; its caller still opens no session (§9.2) |
| ADR-0011 | `AtlasSettings` has no broker surface (`:101-103`) | Already inaccurate since ATLAS-TASK-0022; corrected in a follow-up, never in ADR-0011 (§21.4) |
| ADR-0012 | Revisit condition — "when a single wiring point exists and can be pointed at" (`:274-280`) | **Satisfied by this task.** The wiring point exists and is `composition.py`. Acting on it is a separate decision and is not taken here |
| ADR-0013 | The application constructs, holds, governs and sequences the adapter | The first three become real; sequencing and supervision stay unimplemented (§6.2) |
| ADR-0014 | The section is restated, not imported; no `atlas.config → atlas.broker` edge | Preserved exactly (CB-2); its drift cost becomes a runtime concern, as it predicted |
| ADR-0015 | The decision this task implements | §3 |

ADR-0012's revisit condition being satisfied is a fact this task creates,
not a licence it exercises. Whether risk should be handed its limits from
the wiring point that now exists is a separate decision, requiring a
separate record.

---

## 24. Roadmap

`docs/ROADMAP.md` is not modified by this task, and was not modified by its
specification.

The precedent is ATLAS-TASK-0021, whose specification commit `ad766252`
staged exactly one file, and ATLAS-TASK-0022, whose `e9596ac3` did the
same. The roadmap's status table records completed work citing the commit
it reached `main` on, and this task has no implementation and no commit to
cite. Its row is written when it is implemented and merged, the way every
row above it was.

Two consequences are recorded rather than fixed. `docs/ROADMAP.md:100`
states that the file "declares no ATLAS-TASK-0023, no ADR-0015 and no work
after them"; ADR-0015 was accepted in `8db18fcd` and this specification
exists, so both halves of that sentence are now inaccurate. And ADR-0015
has no row in the status table and will not acquire one — that table
records tasks, and a decision is not a task. Correcting the first is
roadmap bookkeeping, which §6.16 excludes from this task and which the
roadmap's own convention places at merge time.
