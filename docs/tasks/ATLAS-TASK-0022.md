# ATLAS-TASK-0022 — Implement the broker configuration surface

**Status:** Specified, not implemented
**Date:** 2026-08-15
**Baseline:** `9bd447ab72087010ea6accf254e33f232fc3134a`
**Decision record:** [ADR 0014](../adr/0014-broker-settings-are-restated-not-imported.md) —
*Broker settings are restated in the configuration package, not imported*
(Accepted, 2026-08-15).

This task implements ADR-0014 and nothing else. ADR-0014 decided that
`AtlasSettings` owns a broker section written in `atlas.config`'s own
primitives, that `atlas.config` does not import `atlas.broker`, and that the
application translates those values into `MT5Config` at a wiring point that does
not exist. This task builds the section. It does not build the translation, does
not construct an adapter, and does not choose one.

ADR-0014 left nine things undecided. This task settles exactly three of them —
the section name, whether the optional MT5 fields are exposed, and the
validation mechanism — because a specification cannot be implemented without
them. The other six remain open and are listed in §21.

`docs/ROADMAP.md` is not modified by this task. See §22.

---

## 1. Title

**ATLAS-TASK-0022 — Implement the broker configuration surface.**

---

## 2. Status

Specified, not implemented. No branch, commit, pull request or CI run exists for
this task, and none is cited anywhere in this document.

The baseline is `9bd447ab72087010ea6accf254e33f232fc3134a` on `main`, with a
clean working tree and one commit ahead of `origin/main` — the ADR-0014
acceptance commit, which is not yet pushed. The implementer must confirm that
state before making any change (§19.1).

At the baseline the full suite collects **3589 tests**: 191 in `tests/contract`,
757 across the four package boundary tests, and 42 in
`tests/unit/test_config_settings.py`.

---

## 3. Architectural authority

**ADR-0014 is the sole decision this task implements.** Its Decision reads:

> **`AtlasSettings` owns a dedicated broker/venue section, and that section is
> written in `atlas.config`'s own primitives. `atlas.config` does not import
> `atlas.broker`, and `MT5Config` is neither embedded in the settings model nor
> named by it.**

and it names the four values the section restates: `login: int`,
`password: SecretStr`, `server: str`, `terminal_path: Path`.

ADR-0014 also fixes three properties that this task must preserve rather than
re-derive:

| Property | ADR-0014 | This task |
|---|---|---|
| No `atlas.config → atlas.broker` edge | "No edge … is created, because none is needed" | §14 CB-1, §17 T-14 |
| The section names no venue | "A section of `int`, `SecretStr`, `str` and `Path` … commits to nothing" | §7, §17 T-15 |
| Credentials are ADR-0003's, unchanged | "The password is `SecretStr` supplied through the process environment" | §12, §13 |

Four further ADRs constrain this task and none is amended, footnoted or
superseded by it: ADR-0003 (layered configuration), ADR-0011, ADR-0012 and
ADR-0013. Their bearing is set out in §20.

---

## 4. Problem statement

`AtlasSettings` carries five sections — `logging`, `postgres`, `redis`,
`duckdb`, `risk` (`packages/config/src/atlas/config/settings.py:207-211`) — and
no broker section. Searching `packages/config/src` for `broker`, `venue` or
`mt5` returns nothing.

ATLAS-TASK-0020 named the consequence precisely, and its §11.4 drew it:

```
AtlasSettings   ──✗──▶   MT5Config   ──▶   MT5BrokerAdapter   ──▶   BrokerAdapter
     ▲                                                                    ▲
  no broker section                                        the owner can hold this
  (settings.py:207-211)                                    the moment it is handed one
```

ATLAS-TASK-0020 was forbidden from removing that break — its §16 stop condition
1 called it "the single most likely failure mode of this task" — because the
decision had not been made. ADR-0014 has now made it.

**The problem this task removes is that `AtlasSettings` cannot express what an
MT5 session needs.** It does not remove the absence of a translation, a wiring
point, an adapter, a run loop or a pipeline, and it must not appear to.

---

## 5. Scope

This task adds one section model to `atlas.config`, wires it into
`AtlasSettings` as a sixth section, documents its environment variables, and
adds the tests that prove its shape, its defaults, its precedence behaviour, its
secret handling and the boundaries it does not cross.

In scope:

1. **S-1.** One new section model, `BrokerSettings`, in
   `packages/config/src/atlas/config/settings.py`, beside the five that exist.
2. **S-2.** One new field on `AtlasSettings`: `broker`.
3. **S-3.** The export of `BrokerSettings` from `atlas.config`, exactly as
   `RiskSettings` is exported.
4. **S-4.** Documentation of the four environment variables in `.env.example`.
5. **S-5.** Tests: §17.
6. **S-6.** Nothing else.

---

## 6. Non-goals

Each of these is out of scope because an accepted decision leaves it open, not
because it is merely unbuilt. Nothing in this task's diff may decide, prepare
for, or read as presuming any of them.

- **6.1 `MT5BrokerAdapter` construction.** No adapter is constructed anywhere in
  source by this task.
- **6.2 `MockBrokerAdapter` selection.** Nothing selects, defaults to, or
  branches toward the mock.
- **6.3 Adapter-selection policy.** ADR-0013 `:240-264` and ADR-0014 leave it
  open. A branch on `AtlasSettings.environment` that picks an implementation is
  the same decision wearing a different hat, and is excluded.
- **6.4 A composition root.** ADR-0013 `:205-208` records that none exists.
  ADR-0012 `:274-280` set the revisit condition — "when a single wiring point
  exists and can be pointed at" — and this task does not satisfy it.
- **6.5 `BrokerOwner` wiring.** `apps/atlas-core/src/atlas/apps/core/broker_ownership.py`
  is not modified, not imported by new code, and not instantiated.
- **6.6 Startup construction.** Nothing is constructed at process start.
- **6.7 `__main__.py` changes.** Not modified. §14.
- **6.8 The `BrokerSettings → MT5Config` translation.** Its contract is
  *described* in §15 and implemented by nobody. No function, method, adapter,
  converter or `.to_mt5_config()` is written.
- **6.9 Execution changes.** `packages/execution` is untouched.
- **6.10 Risk behaviour changes.** `packages/risk` is untouched, and the risk
  boundary is not broadened. §13.3.
- **6.11 An external configuration or secrets service.** ADR-0003 `:82-85`
  defers it on a trigger that has not fired, and ADR-0014 kept it deferred.
- **6.12 ADR modification.** Every ADR is immutable
  (`docs/adr/README.md:4-6`), including the index.
- **6.13 Roadmap completion bookkeeping.** §22.
- **6.14 A venue-identity or discriminator field.** No `venue`, `provider`,
  `broker_type`, `kind` or `enabled` field is added. §7.3.
- **6.15 Any change to `packages/broker`.** Not one file, not one line.

---

## 7. Decision A — the section name

### 7.1 The name

**The section attribute is `broker`. The model class is `BrokerSettings`.**

The environment prefix that follows from it is `ATLAS_BROKER__` (§11).

### 7.2 Why `broker`

Derived from repository terminology, not preference:

- **The naming pattern is mechanical.** `PostgresSettings → postgres`,
  `RedisSettings → redis`, `DuckDBSettings → duckdb`, `LoggingSettings →
  logging`, `RiskSettings → risk`. `BrokerSettings → broker` is the same
  transformation with no exception.
- **It matches the consumer.** The package that will eventually receive these
  values is `atlas.broker`; the port is `BrokerAdapter`; the owner type is
  `BrokerOwner`. The repository already calls this concept "broker" in source.
- **It matches ADR-0014's own title** — *Broker settings are restated in the
  configuration package, not imported* — and the roadmap and ADR-0011 `:101-103`
  phrase the absence as "no broker or venue surface".
- **`venue` is the weaker of the two words available.** It appears in the ADRs
  only in the paired phrase "broker or venue", and in source only as `MockVenue`
  — a simulated counterparty inside the mock adapter, which is a different thing
  from a configuration section. Reusing it would collide with an existing name.
- **`mt5` is prohibited.** ADR-0014 fixed that the section names no venue.

### 7.3 What the name does not do

Naming the section `broker` does not create a venue-identity field, does not
imply one, and does not reserve room for one. ADR-0014 decided the section
carries primitives; a discriminator saying *which* broker is adapter selection
(§6.3), and §18 stop condition 3 applies to anyone who finds themselves adding
one.

---

## 8. Decision B — required fields

The section exposes exactly four fields, all of them `atlas.config`-owned
primitives. **`MT5Config` is not imported, named, referenced in an annotation,
or mentioned in any docstring in `packages/config/src`.**

| Field | Type | Default | Constraint | Corresponds to |
|---|---|---|---|---|
| `login` | `int` | `0` | `ge=0` | `MT5Config.login` (`gt=0`) |
| `password` | `SecretStr` | `SecretStr("")` | — | `MT5Config.password` |
| `server` | `str` | `""` | — | `MT5Config.server` (`min_length=1`) |
| `terminal_path` | `Path` | `Path()` | — | `MT5Config.terminal_path` |

- **F-1.** The model is `class BrokerSettings(BaseModel)` with
  `model_config = _SECTION_CONFIG` — the shared frozen, `extra="forbid"` config
  at `settings.py:52`. It is not a `BaseSettings`, does not read the
  environment itself, and defines no `model_config` of its own.
- **F-2.** The four fields are declared in the order above.
- **F-3.** `ge=0` on `login` mirrors `RiskSettings.max_margin_utilisation`'s
  `ge=0` (`settings.py:172`): the default is the not-configured value and a
  negative one is meaningless. It is deliberately **not** `gt=0` — `gt=0` would
  make the default invalid and the section unconstructible, which §9 shows an
  existing test forbids.
- **F-4.** Each field carries a `description=` string, following
  `RiskSettings.max_margin_utilisation` (`settings.py:174-179`). The
  `password` description must not contain an example value.
- **F-5.** No field is added beyond these four. No `venue`, no `enabled`, no
  `type`, no `account_name`, no `timeout`, no retry setting, no path to a log.

---

## 9. Decision C — the optional MT5 fields

**None of `timeout_ms`, `portable` or `server_utc_offset` is exposed.**

The section is four fields. This is the smallest surface that satisfies
ADR-0014, whose Decision says the section "restates the four values `MT5Config`
cannot default".

Derivation, per field:

- **`timeout_ms`** — `MT5Config` defaults it to 60 000 with `gt=0`
  (`connection.py:358`). Nothing in the repository asks for a different value.
  Exposing it would be inventing a requirement.
- **`portable`** — defaults to `False` (`connection.py:361`). Same reasoning.
- **`server_utc_offset`** — defaults through
  `default_factory=lambda: ServerClock().offset` (`connection.py:364`), which is
  `timedelta(0)` (`mapper.py:114`).

`server_utc_offset` is the one that deserves an explicit argument, because
ADR-0014 recorded under *Costs* that it "is not cosmetic": `ServerClock`'s
docstring (`mapper.py:103-107`) says the offset "cannot be discovered and must
be configured" and that zero "is correct only for a server that publishes UTC".

It is still excluded here, for three reasons:

1. **`MT5Config` already holds the correct behaviour.** Its default is the
   deliberate not-configured value, chosen because "a wrong non-zero guess is
   worse than an explicit 'not configured'". Nothing about that is improved by a
   settings field that no code reads.
2. **Nothing consumes it.** This task builds no translation (§6.8) and
   constructs no adapter (§6.1). A field added now is a field with no reader, no
   caller and no test that can exercise its effect.
3. **ADR-0014 listed the question as open, not as a requirement.** Implementing
   a decision does not include resolving what it deferred.

**The consequence is recorded rather than hidden:** a deployment against a
server that does not publish UTC cannot be corrected through this section as
specified. The first task that builds the `BrokerSettings → MT5Config`
translation must decide whether to widen the section or to pass the offset some
other way. That is named here so the gap is inherited deliberately (§21).

---

## 10. Decision D — the validation mechanism

ADR-0012 `:165-174` left three mechanisms open — a required field, a
conservative default, or a production invariant — and fixed only the principle:
"Absence is not permission."

**The mechanism is conservative defaults. No production invariant is added by
this task.**

### 10.1 Why a required field is ruled out by an existing test

Every section on `AtlasSettings` is declared
`Field(default_factory=SectionModel)` (`settings.py:207-211`), and
`default_factory` calls the model with no arguments. A required field inside
`BrokerSettings` would make `BrokerSettings()` raise, which would make
`AtlasSettings()` raise.

`tests/unit/test_config_settings.py:43` —
`test_settings_resolve_without_any_configuration_source` — asserts that settings
resolve with no configuration source at all, and it passes at the baseline.

A required broker field would break it. This is not a preference; it is the
existing suite ruling the option out. `broker` is therefore
`Field(default_factory=BrokerSettings)`, and all four fields carry defaults.

### 10.2 Why the defaults are safe — absence is not permission

The defaults are not merely conservative, they are **provably incapable of
constructing a valid `MT5Config`**:

- `login = 0` violates `MT5Config.login`'s `gt=0` (`connection.py:347`).
- `server = ""` violates `MT5Config.server`'s `min_length=1`
  (`connection.py:349`).

An unconfigured broker section cannot produce a session, in any environment,
whether or not anyone remembered to set an invariant. That is a stronger
guarantee than an environment-gated check, and it is the same shape as
`RiskSettings.max_margin_utilisation`, whose default of `0` "permits nothing at
all" (`settings.py:154`).

### 10.3 Why no production invariant is added

`_enforce_production_invariants` (`settings.py:244-281`) refuses to start "a
live-shaped process with unsafe settings". A broker invariant added now would
refuse to start every production process for want of configuration for an
adapter that this task explicitly does not construct.

This is not hypothetical. `Dockerfile:55-56` sets `ATLAS_ENV=production` by
default, and `docker-compose.yml:87-100` passes no broker variables. An
invariant here would turn a working container into a failing one, with no
safety gained: a process that constructs no adapter is not made unsafe by an
absent broker credential.

**The invariant becomes correct when something constructs an adapter, and the
task that does that adds it.** §21 carries it forward. This task must add a test
that pins the current behaviour so the invariant cannot arrive by accident
(§17 T-9).

### 10.4 What the mechanism is not

- It is not a claim that a default-configured process may trade. It cannot; see
  §10.2.
- It is not a relaxation of ADR-0003's fail-closed stance. The failure moves
  from start-up to the point of use, and there is no point of use yet.
- It is not a decision about `demo`. `risk.max_margin_utilisation` is enforced
  under `demo` as well as `production`; no broker invariant is enforced under
  either, in this task.

---

## 11. Decisions E and F — configuration sources and environment variables

### 11.1 Precedence

`BrokerSettings` is an ordinary section and participates in the existing
six-level precedence with no special handling, no new source and no change to
`settings_customise_sources` (`settings.py:213-242`):

```
constructor  →  process environment  →  .env  →  config/<ATLAS_ENV>/*.toml
             →  config/default/*.toml  →  field defaults
```

- **P-1.** No new settings source is added. `LayeredTomlSource` keeps its
  ranking below the environment sources (`settings.py:236-242`,
  `test_config_settings.py:500`).
- **P-2.** The nested delimiter is the existing `__`
  (`settings.py:188`). No alias, no `validation_alias`, no `AliasChoices`. The
  `environment` field is the only one in the model with an alias and it stays
  the only one.
- **P-3.** `extra="forbid"` on the section (`_SECTION_CONFIG`) means a mistyped
  key inside `[broker]` is a start-up error, exactly as
  `test_config_settings.py:239` asserts for the existing sections.

### 11.2 The exact environment variables

| Variable | Field | May appear in TOML? |
|---|---|---|
| `ATLAS_BROKER__LOGIN` | `login` | Yes (§12) |
| `ATLAS_BROKER__PASSWORD` | `password` | **Never** |
| `ATLAS_BROKER__SERVER` | `server` | Yes (§12) |
| `ATLAS_BROKER__TERMINAL_PATH` | `terminal_path` | Yes (§12) |

- **P-4.** These four names are exact. `case_sensitive=False`
  (`settings.py:191`) means the lookup is case-insensitive, and the documented
  form is upper-case, as every existing variable is.
- **P-5.** All four are documented in `.env.example` under a new `Broker`
  heading, following the structure of the existing sections and the precedent of
  ATLAS-TASK-0017, whose implementation commit `4147f12` added an 18-line block
  for `risk`. `ATLAS_BROKER__PASSWORD` is documented **commented out and with no
  value**, and the block states that it is the only one of the four that may not
  be committed to a TOML layer.

---

## 12. Decision G — TOML representation

- **TG-1.** `login`, `server` and `terminal_path` are structural values and the
  schema permits them in any layer under `config/`.
- **TG-2.** `password` may never appear in any file under `config/`. ADR-0003
  `:25`: "No file in `config/` may contain a credential." This is not merely
  discouraged; `tests/contract/test_repository_structure.py` already walks every
  `*.toml` under `config/`, and §17 T-12 adds the assertion.
- **TG-3.** **This task writes no `[broker]` block into any layer.** Not
  `config/default/`, not `config/development/`, not `config/demo/`, not
  `config/production/`.

  The precedent is exact and it is `risk`: no layer contains a `[risk]` section,
  and `config/production/atlas.toml:11-15` gives the reason — the value "is
  deliberately absent from every layer in this tree, because any value for it is
  a trading policy and belongs to the deployment, not to the repository."

  A login, a server name and a terminal path are deployment facts in the same
  way. A committed default would be either wrong everywhere or a real account
  number in a repository.

- **TG-4.** No file under `config/` is modified by this task at all. The four
  layers are byte-identical after it.

---

## 13. Decision H — security and secret handling

### 13.1 The secret

- **SEC-1.** `password` is `SecretStr`, matching `PostgresSettings.password`
  (`settings.py:73`) and `RedisSettings.password` (`settings.py:120`). It is the
  third of its kind and introduces no new mechanism.
- **SEC-2.** `SecretStr` masks in both `repr` and `str`, and §17 T-7 asserts
  both, following `test_config_settings.py:174-183`.
- **SEC-3.** **No composite accessor is added.** `PostgresSettings` has
  `dsn`/`safe_dsn` and `RedisSettings` has `url`/`safe_url` because each builds
  a connection string that embeds the secret. `BrokerSettings` builds no
  composite, so it needs neither, and adding a `safe_*` property with nothing to
  mask would invent a requirement. `test_risk_boundary.py:157-159` states the
  principle from the other side: the existence of `safe_dsn` "is precisely the
  evidence that `dsn` and `url` do not" mask.
- **SEC-4.** No `get_secret_value()` call is added anywhere in
  `packages/config/src` by this task. The existing call inside
  `_enforce_production_invariants` (`settings.py:267`) is for
  `postgres.password` and is unchanged.

### 13.2 The startup record — Decision I

- **SEC-5.** `build_startup_record` is **unchanged**, and
  `apps/atlas-core/src/atlas/apps/core/__main__.py` is not modified. The record
  keeps its exact current keys.

  This follows the repository rather than a preference: `risk` is already a
  section that does not appear in the startup record, and no rule anywhere says
  which sections do. Adding `broker` would be inventing that rule while also
  putting a live-trading credential one masking bug away from a log line.

- **SEC-6.** §17 T-8 asserts positively that a rendered startup record contains
  neither a broker key nor a broker password, following the pattern of
  `test_core_entrypoint.py:30-41`.

### 13.3 The risk-boundary credential denylist

**`tests/unit/risk/test_risk_boundary.py` is not modified by this task.**

The mechanical analysis, which the implementer must not redo differently:

- `_credential_references` is `_referenced_names(source) & set(CREDENTIAL_SYMBOLS)`
  (`:282`), and `_referenced_names` collects `ast.Attribute.attr` (`:265-266`).
- A risk module reaching a broker credential would have to write
  `get_settings().broker.password`, whose attribute names include `password` —
  already in `CREDENTIAL_SYMBOLS` (`:163`). **The credential is already
  covered.**
- Adding `"broker"` to `CREDENTIAL_SYMBOLS` would be a broadening, and a
  dangerous one: `_referenced_names` also adds `node.name.rsplit(".", 1)[-1]`
  for `ast.alias` (`:267-268`), so any module writing `import atlas.broker`
  would register the name `broker`. `atlas.risk` is permitted to import
  `atlas.broker` (`:66`) and does so legitimately. The denylist entry could
  therefore fail a module that touches no credential at all.
- `PERMITTED_CONFIG_ACCESS` (`:174`) is unchanged. Risk still reaches exactly
  `get_settings().risk.max_margin_utilisation` and nothing else.

**What does go stale is a comment.** The docstring at `:150-159` derives
`CREDENTIAL_SYMBOLS` from "the two sections that lead anywhere
credential-bearing", and after this task there are three. **It is not corrected
here**, because correcting it means modifying a test file this task otherwise
does not touch, and because the sentence describes the derivation of a tuple
that is still correct. It is recorded as a finding for the living-document
correction that follows this task, in the manner of ATLAS-TASK-0015, 0016, 0019
and 0021.

---

## 14. Boundary preservation

- **CB-1.** `atlas.config` does not import `atlas.broker`, in any form,
  including under a `TYPE_CHECKING` guard. ADR-0014's Decision. §17 T-14.
- **CB-2.** `packages/broker` is not modified. `MT5Config` keeps its seven
  fields and its docstring. This task does not make `connection.py:339`
  ("Constructed by the composition root from `atlas.config`") true — it supplies
  the values that sentence anticipates and builds no composition root.
- **CB-3.** The four boundary tests' `PERMITTED_ATLAS_PACKAGES` tuples are not
  widened: `test_adapter_contract.py:187`, `test_risk_boundary.py:66`,
  `test_strategy_boundary.py:63-67`, `test_execution_boundary.py:67`. All 757
  tests pass unmodified.
- **CB-4.** `tests/unit/test_core_broker_boundary.py` is not modified.
  `CONCRETE_ADAPTER_NAMES` (`:76-82`) still lists `MT5Config`, and no module
  under `apps/` names it. This task adds nothing under `apps/`, so the test's
  parameterisation over `APPS_ROOT.rglob("*.py")` (`:49`) is unchanged.
- **CB-5.** The six feature-package edges at
  `docs/architecture/overview.md:61-64` are unchanged in number and direction.
  This task adds no edge at all.
- **CB-6.** `apps/atlas-core` is not modified — neither `__main__.py` (§13.2)
  nor `broker_ownership.py` (§6.5).

---

## 15. Decision J — the translation boundary

ADR-0014 assigns the translation to the application. This section records the
correspondence so the later task inherits it, and **implements none of it**.

The eventual contract, when a wiring point exists:

```
BrokerSettings.login          →  MT5Config.login
BrokerSettings.password       →  MT5Config.password
BrokerSettings.server         →  MT5Config.server
BrokerSettings.terminal_path  →  MT5Config.terminal_path
                              →  MT5Config.timeout_ms         (MT5Config default)
                              →  MT5Config.portable           (MT5Config default)
                              →  MT5Config.server_utc_offset  (MT5Config default; §9)
```

- **TR-1.** No code in this task performs, prepares or names this mapping. No
  function, method, property, `TypedDict`, protocol or `.to_*()` helper.
- **TR-2.** The mapping does not appear in `packages/config/src` in any form,
  including in a comment or docstring — naming `MT5Config` there would violate
  ADR-0014 and CB-1's spirit even where the import does not exist.
- **TR-3.** The wiring point is not chosen, named or located. ADR-0013
  `:205-208` and ADR-0012 `:274-280` both remain unsatisfied.
- **TR-4.** Validation asymmetry is deliberate and must be preserved: the
  settings section accepts `login=0` and `server=""`; `MT5Config` rejects them.
  The task that builds the translation decides what a rejection means at that
  point. This task does not pre-empt it, and must not add a settings-side
  validator that duplicates `MT5Config`'s.

---

## 16. Required documentation truths

After implementation these must be true, and the implementer must not create
them by editing a document this task forbids (§22.2):

- **DOC-1.** `.env.example` documents all four variables (§11.2 P-5).
- **DOC-2.** No statement is added anywhere claiming that an adapter can now be
  constructed, that the chain is joined, or that a composition root exists.
- **DOC-3.** `config/README.md` is not modified. Its rules already cover the new
  section without amendment: the precedence, the layer list and "No file in this
  directory may contain a credential" all apply as written.

---

## 17. Test requirements

Every test below is new, in `tests/unit/test_config_settings.py`, following the
class-per-concern structure that file already uses. **No existing test is
modified, renamed, moved, deleted or re-parameterised.**

### 17.1 Shape and defaults

- **T-1.** `BrokerSettings()` constructs with no arguments, and its four fields
  equal `0`, `SecretStr("")`, `""` and `Path()` respectively (§10.1).
- **T-2.** The model has exactly four fields, asserted against
  `BrokerSettings.model_fields` — so a fifth field added later fails a test
  rather than passing silently (§8 F-5, §9).
- **T-3.** `BrokerSettings` is frozen: assignment to a field raises
  (`_SECTION_CONFIG`).
- **T-4.** An unknown key inside the section is rejected, mirroring
  `test_config_settings.py:239` (`extra="forbid"`).
- **T-5.** A negative `login` is rejected (`ge=0`, §8 F-3).
- **T-6.** `AtlasSettings` exposes `broker`, and a default `AtlasSettings`
  carries a default `BrokerSettings` — `AtlasSettings` now has **six** sections.

### 17.2 Secret handling

- **T-7.** A configured broker password appears in neither `repr()` nor `str()`
  of the settings object, following `test_config_settings.py:174-183` (§13.1
  SEC-2).
- **T-8.** With `ATLAS_BROKER__PASSWORD` set to a known sentinel,
  `json.dumps(build_startup_record(load_settings()))` contains neither the
  sentinel nor the key `broker`, following `test_core_entrypoint.py:30-41`
  (§13.2 SEC-6). This test lives in `tests/unit/test_core_entrypoint.py`, which
  is the file that owns the startup record — it is an **addition** to that file,
  not a modification of an existing test in it.

### 17.3 Environment loading and precedence

- **T-9.** A `production` process starts with no broker configuration at all.
  This is the pin that stops a production invariant arriving by accident
  (§10.3). It must be written so that it fails if one is added.
- **T-10.** Each of the four variables loads through its exact
  `ATLAS_BROKER__*` name (§11.2), including `terminal_path` coercing a string to
  `Path` and `login` coercing a string to `int`.
- **T-11.** A `[broker]` block in a TOML layer is overridden by the
  corresponding environment variable, following
  `test_config_settings.py:155`. The layer is written by the test's own
  `isolated_env` fixture — **not** into `config/` (§12 TG-3, TG-4).

### 17.4 Boundary assertions

- **T-12.** No file under `config/` contains the string `password` inside a
  `[broker]` block — or, more simply and more strongly, no `*.toml` under
  `config/` contains a `[broker]` section at all (§12 TG-3). This is the
  mechanical form of ADR-0003 `:25` for this section.
- **T-13.** No module under `packages/config/src` contains the string
  `MT5Config`, `mt5`, `MetaTrader` or `BrokerAdapter` (§15 TR-2, §8).
- **T-14.** No module under `packages/config/src` imports `atlas.broker`, in any
  form, including under `TYPE_CHECKING` — asserted by walking the AST, in the
  manner of the four boundary tests (§14 CB-1, ADR-0014).
- **T-15.** `BrokerSettings`'s field names and its docstring contain no venue
  name (§7.3, §6.14).

T-13 and T-14 are the enforcement of ADR-0014's central constraint. They are
**not** a general `atlas.config` import rule: they define no
`PERMITTED_ATLAS_PACKAGES` tuple, permit nothing, and make no statement about
what `atlas.config` may import in general. If an implementer finds themselves
writing an allowlist, §18 stop condition 6 applies.

### 17.5 What must still pass, unmodified

- **T-16.** All 42 existing tests in `tests/unit/test_config_settings.py`.
- **T-17.** The four package boundary tests — 757 tests, unchanged (CB-3).
- **T-18.** `tests/contract/test_repository_structure.py` — 191 tests,
  unchanged, and **still 191**. No new module and no new `__init__.py` is
  created, so `LEAF_MODULES` is unchanged.
- **T-19.** `tests/unit/test_core_broker_boundary.py` and
  `tests/unit/test_core_broker_ownership.py`, unchanged (CB-4, §6.5).

---

## 18. Stop conditions

Stop and report rather than deciding, if:

1. **The work appears to require importing `atlas.broker` from `atlas.config`.**
   It does not. ADR-0014 decided against it, and CB-1 forbids it.
2. **The work appears to require constructing an adapter** to prove the section
   works. §6.1, §6.2. The section is provable on its own terms; every test in
   §17 runs without an adapter.
3. **A venue, discriminator or `enabled` field seems necessary.** §7.3, §6.14.
   That is adapter selection.
4. **A production invariant seems necessary.** §10.3. If a genuine argument
   exists that one is needed now, that argument is about when an adapter is
   constructed, which is deferred — report it.
5. **`MT5Config` seems to need changing** to match the section. §14 CB-2. The
   asymmetry in §15 TR-4 is intentional.
6. **A test being written needs an allowlist of what `atlas.config` may
   import.** §17.4. That is a general boundary rule for the configuration
   package and no decision creates one.
7. **`test_risk_boundary.py` seems to need its denylist widened.** §13.3. The
   credential is already covered, and widening it can produce a false positive.
8. **`__main__.py`, `broker_ownership.py`, or anything under `apps/` seems to
   need modifying.** §6.5, §6.7, §13.2.
9. **A `[broker]` block seems to belong in a layer under `config/`.** §12 TG-3.
10. **The baseline has moved**, or a task after ATLAS-TASK-0022 exists, or
    `docs/adr/0014-broker-settings-are-restated-not-imported.md` is absent or
    differs from the accepted record.
11. **The collected test count before any change is not 3589.**
12. **Anything in §6 or §21 would be decided in passing** to finish the work.

In every case: report both pieces of conflicting evidence and explain the
conflict. Do not silently reconcile them.

---

## 19. Verification commands

Existing tooling only. No new script, target, marker or CI job is added.

### 19.1 Before making any change

```bash
git rev-parse HEAD                      # 9bd447ab72087010ea6accf254e33f232fc3134a
git status --porcelain                  # empty
./.venv/Scripts/python.exe -m pytest -q --collect-only | tail -1   # 3589 tests
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
./.venv/Scripts/python.exe -m pytest tests/unit/test_core_entrypoint.py -q
./.venv/Scripts/python.exe -m pytest tests/unit/test_core_broker_boundary.py -q

./.venv/Scripts/python.exe -m ruff check .
./.venv/Scripts/python.exe -m black --check --diff .
./.venv/Scripts/python.exe -m mypy .
```

### 19.3 Diff verification

```bash
git diff --stat -- packages/broker/ packages/risk/ packages/execution/  # empty
git diff --stat -- apps/ config/ docs/ pyproject.toml                   # empty
git diff --stat -- .github/                                             # empty
git diff -- tests/unit/risk/test_risk_boundary.py                       # empty
```

---

## 20. Acceptance criteria

- **AC-1.** `AtlasSettings` has a `broker` field of type `BrokerSettings`,
  declared `Field(default_factory=BrokerSettings)`, and six sections in total.
- **AC-2.** `BrokerSettings` has exactly four fields with exactly the names,
  types, defaults and constraints in §8, and `BrokerSettings` is exported from
  `atlas.config` exactly as `RiskSettings` is (`__init__.py:30`, `:48`).
- **AC-3.** `packages/config/src` contains no occurrence of `MT5Config`, `mt5`,
  `MetaTrader` or `BrokerAdapter`, and imports `atlas.broker` nowhere (T-13,
  T-14).
- **AC-4.** `git diff --stat` shows zero lines under `packages/broker/`,
  `packages/risk/`, `packages/execution/`, `apps/`, `config/`, `docs/`,
  `.github/` and `pyproject.toml`.
- **AC-5.** No ADR is changed, added or superseded, and `docs/adr/README.md` is
  unchanged.
- **AC-6.** `tests/unit/risk/test_risk_boundary.py` is byte-identical (§13.3).
- **AC-7.** `apps/atlas-core/src/atlas/apps/core/__main__.py` is byte-identical,
  and `build_startup_record`'s keys are unchanged (SEC-5).
- **AC-8.** The suite collects **3589 + N** tests, where N is the number added by
  §17, and all 3589 pre-existing tests still pass. No pre-existing test is
  modified, skipped, deleted or renamed.
- **AC-9.** `tests/contract/test_repository_structure.py` still reports exactly
  191 tests, and the four boundary tests still report exactly 757, with no
  `PERMITTED_ATLAS_PACKAGES` tuple widened.
- **AC-10.** A `production` process starts with no broker configuration (T-9),
  and `_enforce_production_invariants` contains no broker clause.
- **AC-11.** No `*.toml` under `config/` contains a `[broker]` section, and the
  four layers are byte-identical (T-12, TG-4).
- **AC-12.** `ruff check .`, `black --check .` and `mypy .` are clean under the
  repository's strict configuration, with no `# type: ignore` added.
- **AC-13.** The diff contains no statement that decides, prepares for, or
  presumes an answer to anything in §6 or §21 — including in a docstring, a
  comment, a `TODO` or a name.
- **AC-14.** The diff touches exactly the files §22.1 lists, and none of the
  paths §22.2 prohibits.

---

## 21. Deferred decisions

### 21.1 What ADR-0014 left open, and what this task does with each

| ADR-0014 open item | This task |
|---|---|
| The exact section name | **Resolved.** §7 — `broker`. |
| Whether `timeout_ms`, `portable`, `server_utc_offset` are exposed | **Resolved.** §9 — none. |
| The validation mechanism | **Resolved.** §10 — conservative defaults, no invariant. |
| Adapter selection | **Open.** §6.3. |
| When an adapter is constructed | **Open.** §6.1. |
| Where the composition/wiring point exists | **Open.** §6.4. |
| Whether construction occurs at startup | **Open.** §6.6. |
| Whether broker settings appear in the startup record | **Open** as a general rule; this task keeps the record unchanged (§13.2), which is the status quo and not a rule. |
| External configuration services | **Open.** §6.11, ADR-0003 `:82-85`. |

### 21.2 What ADR-0013 left open, all of it still open

None of these is touched, prepared for or prefigured by this task: the `apps/`
import rule (`:242-249`); whether `apps/dashboard` may hold or invoke a
`BrokerAdapter` (`:250-252`); any mechanism for granting access (`:253-257`);
the run loop, supervisor implementation and threading design (`:258-260`); order
identity, idempotency, routing, fills and reconciliation (`:261-262`); and
account or portfolio state ownership (`:263-264`).

ADR-0012's revisit condition — "when a single wiring point exists and can be
pointed at" (`:274-280`) — remains unsatisfied. Supplying the values a wiring
point would read is not building one.

### 21.3 Created by this task, and named here

- **The `server_utc_offset` gap.** §9. A deployment against a server that does
  not publish UTC cannot be corrected through this section as specified.
- **The stale derivation comment** at `test_risk_boundary.py:150-159`. §13.3.
- **The living-document correction.** ADR-0011 `:101-103` — "there is no broker
  or venue surface anywhere in it" — becomes inaccurate when this task merges,
  and `docs/architecture/overview.md`'s configuration section will describe five
  sections where there are six. Both belong in a follow-up documentation task,
  per the precedent of ATLAS-TASK-0015, 0016, 0019 and 0021, and per ADR-0013
  `:280-283`: the correction "belongs in the roadmap and the living documents,
  never in ADR-0011 itself."

---

## 22. Files expected to change

### 22.1 Expected

| Path | Change |
|---|---|
| `packages/config/src/atlas/config/settings.py` | `BrokerSettings` model; `broker` field on `AtlasSettings`. |
| `packages/config/src/atlas/config/__init__.py` | Export `BrokerSettings`, as `RiskSettings` is. |
| `.env.example` | New Broker block documenting four variables (§11.2 P-5). |
| `tests/unit/test_config_settings.py` | §17.1, §17.2 T-7, §17.3, §17.4. |
| `tests/unit/test_core_entrypoint.py` | §17.2 T-8 only — one added test, no existing test modified. |

Nothing else. If a sixth file needs to change, §18 applies.

### 22.2 Prohibited

| Path | Why |
|---|---|
| `packages/broker/**` | §6.15, CB-2. Zero lines. |
| `packages/risk/**`, `packages/execution/**` | §6.9, §6.10. |
| `tests/unit/risk/test_risk_boundary.py` | §13.3, AC-6. |
| `tests/unit/test_core_broker_boundary.py`, `tests/unit/test_core_broker_ownership.py` | CB-4, §6.5. |
| `apps/**` | §6.5, §6.7, §13.2, CB-6. |
| `config/**` | §12 TG-3, TG-4, DOC-3. |
| `docs/adr/**` | ADRs are immutable (`docs/adr/README.md:4-6`), index included. |
| `docs/ROADMAP.md` | §24. |
| `docs/architecture/overview.md` | The living-document correction is a separate task. §21.3. |
| `pyproject.toml`, `.github/workflows/ci.yml`, `scripts/**` | No new source root, dependency, job or script. |

---

## 23. Relationship to the ADRs

**Fourteen ADRs are Accepted and immutable. This task implements one and edits
none.**

| ADR | Bearing on this task | Effect |
|---|---|---|
| ADR-0003 | Structure in files, secrets in the environment; no credential under `config/`; fail fast | §11, §12, §13; unchanged and extended by one section |
| ADR-0006 | Business logic cannot discover which adapter it holds | Preserved — the section names no venue (§7.3) |
| ADR-0011 | `AtlasSettings` has no broker surface (`:101-103`) | Becomes inaccurate on merge; corrected in a follow-up, never in ADR-0011 (§21.3) |
| ADR-0012 | Section defined in `atlas.config`, not the feature package (`:124-125`); absence is not permission (`:165-174`); revisit condition (`:274-280`) | Followed (§8), satisfied by §10.2, still unsatisfied (§21.2) |
| ADR-0013 | The application owns the adapter and assembles its configuration | Untouched; this task supplies what the assembly will read (§15) |
| ADR-0014 | The decision this task implements | §3 |

---

## 24. Roadmap

`docs/ROADMAP.md` is not modified by this task, and was not modified by its
specification.

The precedent is ATLAS-TASK-0021, whose specification commit `ad766252` staged
exactly one file — the specification itself. The roadmap's status table records
completed work citing the commit it reached `main` on, and this task has no
implementation and no commit to cite. Its row is written when it is implemented
and merged, the way every row above it was.

One consequence is recorded rather than fixed: `docs/ROADMAP.md:88` currently
states that the file "declares no ATLAS-TASK-0022, no ADR-0014 and no work after
them". ADR-0014 was accepted in `9bd447ab` and this specification exists, so
that sentence is now inaccurate. Correcting it is roadmap bookkeeping, which
§6.13 excludes from this task and which the roadmap's own convention places at
merge time.
