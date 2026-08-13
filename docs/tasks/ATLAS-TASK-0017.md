# ATLAS-TASK-0017 — The first risk control: a portfolio margin-utilisation limit

**Status:** Specified, not implemented
**Date:** 2026-08-13
**Baseline:** `cc784aadf93478592fd54b18669f588938a89aaf`
**Decision record:** [ADR-0012 — Risk is handed its state and reads its own limits](../adr/0012-risk-is-handed-its-state-and-reads-its-own-limits.md)

---

## 1. Status

This document specifies ATLAS-TASK-0017. Nothing in it has been implemented.

The task implements the first control in `atlas.risk` that actually reaches a
decision: a portfolio-wide margin-utilisation limit, read from configuration,
that turns a `TradeIntent` into a `RiskVerdict`. It also corrects the
documentation and the test docstrings that this makes false.

The task is bounded by eight owner decisions (§7) and by ADR-0012, which was
accepted before this specification was written. Where ADR-0012 fixed a
principle and left the mechanism to "the task that writes it", this document is
that task, and it records how each mechanism was **derived** from repository
evidence rather than chosen (§7 D-6, §7 D-7, §7.10, §7.11, §7.12).

ADR-0012 exists on disk and is **untracked** at the baseline. This task brings
it under version control byte-for-byte unchanged (§8 F-16). Committing an
unmodified file is not modifying it, and the distinction is load-bearing
throughout this document: **"no ADR modification" is not "no ADR may be
committed".**

Two things this task is not: it is not a risk *engine*, and it is not a
pipeline. After it lands, a function exists that reaches a verdict, and still
nothing calls it outside the test suite.

**Amendment, 2026-08-13.** This document was amended once after its final audit
and after the implementation pass had completed. The implementation pass found a
fourteenth statement this task makes false — the boundary-test sentence at
`docs/architecture/overview.md:74-76` — and correctly declined to touch it,
because §8 F-13 authorised only P-2 and P-3. The amendment records it as **P-14**
(§4.2), authorises exactly that sentence in F-13, and carries the range forward
in §5, §13.1 and AC-12. It reopens no owner decision, changes no architectural
decision, alters no implementation requirement, and adds no acceptance criterion.
Every other statement in this document stands as audited.

---

## 2. Purpose

`atlas.risk` has been declared "authoritative and non-bypassable" since
ATLAS-TASK-0001 and has held the two contracts since ATLAS-TASK-0011, but it has
never contained a control. `RejectionReason` names four of them and
`packages/risk/src/atlas/risk/contracts.py:90` says plainly that "None of them
is implemented yet". Every claim of authority the repository makes about risk is
therefore a claim about a package that cannot currently refuse anything.

This task implements one of the four — `EXPOSURE_LIMIT` — in the narrowest form
that is still a real control:

* it reads the account state it is handed, and no more;
* it reads its limit from the process's own configuration, not from its caller;
* it approves the requested intent unchanged, or it rejects;
* it fails closed when the configuration is absent and when the account state is
  arithmetically unusable.

The purpose is to make one sentence in the repository true: that there is a
function in `atlas.risk` which turns a `TradeIntent` into a `RiskVerdict` on
evidence. Everything else in scope exists to keep the surrounding documents from
lying about what that function is.

---

## 3. Context

### 3.1 What ADR-0012 settled

ADR-0012 is accepted and immutable in content. It is also untracked at the
baseline (B-25) — accepted, present on disk, and absent from Git. It settled the
following, all of which this task depends on:

| ADR-0012 | What it settled |
|---|---|
| `:59-65` | Risk is **handed** its state as arguments (`Account`, `Position`, `Symbol`) and **reads** its limits from its own configuration. |
| `:73-80` | No new portfolio-state contract is invented. The broker's observation models are reused as they are. |
| `:88-101` | `BrokerAdapter` remains unreachable from `atlas.risk`. Risk "never calls `get_account`, `get_positions`, `margin_required`, `margin_available` or `can_trade`". |
| `:105`, `:176-188` | `atlas.risk` may import `atlas.config`. The edge is admitted "for one thing", an allowlist is required, and "Which names are admitted is the implementing task's to enumerate." |
| `:109-113`, `:142-163` | The limit is **not a parameter**. A caller cannot raise it by passing a bigger number. The guarantee is that the decision uses the *process's configured* limit — not that the limit is unforgeable. |
| `:165-174` | **"Absence is not permission."** Whether that is achieved "by a required field, by a conservative default, or by a production invariant … is a matter for the task that writes it. The principle is fixed here; the mechanism is not." |
| `:238-261` | Costs accepted: a sixth edge, the first into `config`; `atlas.risk` stops being only contracts; the limit is only as good as the deployment. |

### 3.2 What the owner decided

Eight decisions, approved before this specification was authored, are reproduced
verbatim and made authoritative in §7. This document adds no architectural
decision beyond them. Where §7 records a mechanism the owner did not name, it is
because ADR-0012 or an owner decision explicitly delegated the mechanism to this
task **and required the derivation to be written down** — and each such
derivation is shown, with its evidence, rather than asserted.

### 3.3 What ATLAS-TASK-0016 established about documents

ATLAS-TASK-0016 established that the repository's descriptive documents are
living statements of what is true now, and that `docs/ROADMAP.md` is a dated
historical narrative closed out after a merge. That split governs §4: a
falsified sentence in a living document is in scope; the same phrase inside a
dated roadmap entry is not.

ATLAS-TASK-0016 also established the style rule repeated in §5: this document
states the **truth** that must hold, not the sentence that must be written.

### 3.4 What is true at the baseline, verified from source

Every row below was read from the working tree at
`cc784aadf93478592fd54b18669f588938a89aaf`.

| # | Fact | Evidence |
|---|---|---|
| B-1 | `atlas.risk` contains exactly two modules: `__init__.py` and `contracts.py`. | `packages/risk/src/atlas/risk/` |
| B-2 | `atlas.risk.__all__` is exactly `{RISK_MODEL_CONFIG, RejectionReason, RiskVerdict, TradeIntent, VerdictStatus}`. | `packages/risk/src/atlas/risk/__init__.py:36-42` |
| B-3 | `RejectionReason` has four members: `EXPOSURE_LIMIT`, `DRAWDOWN_LIMIT`, `CORRELATION_CAP`, `KILL_SWITCH`. Its docstring says "None of them is implemented yet". | `packages/risk/src/atlas/risk/contracts.py:88-102` |
| B-4 | `RiskVerdict` carries `intent`, `status`, `approved_volume`, `reason`, `detail`. `detail` is documented as "Human-readable context for the decision, **such as the limit that was reached**". | `packages/risk/src/atlas/risk/contracts.py:170-192` |
| B-5 | `TradeIntent` carries `symbol`, `side`, `requested_volume`, `stop_loss`, `take_profit`. | `packages/risk/src/atlas/risk/contracts.py:129-147` |
| B-6 | `Account` carries `equity: Money` (may be negative) and `margin: NonNegativeMoney`. | `packages/broker/src/atlas/broker/models/account.py:39-40` |
| B-7 | `Account.margin_level` is *equity as a percentage of margin* — the reciprocal of the metric this task uses — and is `None` when no margin is pledged. Its validator exists because "any rule of the form `margin_level < threshold` fires on a flat account". | `packages/broker/src/atlas/broker/models/account.py:44-62` |
| B-8 | `Account` is **not** in `atlas.broker.__all__`; it is imported from `atlas.broker.models`. | `packages/broker/src/atlas/broker/__init__.py` |
| B-9 | The `atlas.risk → atlas.broker` edge currently carries the names `OrderSide`, `Price`, `SymbolName`, `Volume`. | AST census over all source roots |
| B-10 | `tests/unit/risk/test_risk_boundary.py` permits `("atlas.risk", "atlas.broker", "atlas.common")` and forbids twelve packages **including `atlas.config`**. It applies a *package* permit with **no name allowlist**. | `tests/unit/risk/test_risk_boundary.py:55, 67-80, 117-122` |
| B-11 | `tests/unit/execution/test_execution_boundary.py` already implements a name allowlist against `atlas.broker`, including the `WHOLE_MODULE` treatment of `import atlas.broker`. | `tests/unit/execution/test_execution_boundary.py:105, 128, 161-191` |
| B-12 | **Three** files assert `atlas.risk.__all__` by set equality, in three different packages' boundary tests. All three assert the same five-name set. | `tests/unit/risk/test_risk_boundary.py:225-232`; `tests/unit/execution/test_execution_boundary.py:423-430`; `tests/unit/strategy/test_strategy_boundary.py:366-373` |
| B-12a | The third is inside `TestTheRiskBoundaryWasNotWidened`, whose docstring is "The cheap way to pass the tests above is to move the problem next door." The execution copy lives in an identically-motivated class, `TestTheBoundariesNextDoorWereNotWidened`. Both exist precisely to notice a change to `atlas.risk`'s surface. | `tests/unit/strategy/test_strategy_boundary.py:363-364`; `tests/unit/execution/test_execution_boundary.py:420-421` |
| B-13 | Every field in the `AtlasSettings` tree has a default. There is no required field anywhere in configuration today. | `packages/config/src/atlas/config/settings.py` |
| B-14 | The repository's fail-closed configuration pattern is **an inert-value default plus a live-environment invariant that rejects the inert value**: `password: SecretStr = SecretStr("")` with `if not self.postgres.password.get_secret_value(): violations.append(...)`. | `packages/config/src/atlas/config/settings.py` (`PostgresSettings`, `_enforce_production_invariants`) |
| B-15 | All three existing production invariants test a **value**, not whether a field was set. | `_enforce_production_invariants` |
| B-16 | `Environment.is_live` is true for `production` only, and the invariant block returns early when it is false. | `packages/config/src/atlas/config/settings.py` |
| B-17 | `get_settings` **is** in `atlas.config.__all__` (16 names). `from atlas.config import get_settings` therefore satisfies `no_implicit_reexport`. | `packages/config/src/atlas/config/__init__.py` |
| B-18 | All four section classes — `LoggingSettings`, `PostgresSettings`, `RedisSettings`, `DuckDBSettings` — are exported from `atlas.config`. | `packages/config/src/atlas/config/__init__.py` |
| B-19 | `config/production/atlas.toml`'s header enumerates the three production invariants for operators and states "A process that violates any of these refuses to start." | `config/production/atlas.toml:1-11` |
| B-20 | `config/README.md` describes the `demo/` layer as "production topology, non-funded account"; `config/demo/atlas.toml`'s header says demo "exists to be indistinguishable from production in everything except the money at risk." | `config/README.md`; `config/demo/atlas.toml:1-6` |
| B-21 | `.env.example` is the only operator-facing catalogue of `ATLAS_*` variables. It documents optional knobs as commented-out entries (`# ATLAS_CONFIG_DIR=/app/config`). | `.env.example:25-27` |
| B-22 | No committed configuration layer sets any risk value; there is no `[risk]` section anywhere. | `config/*/atlas.toml` |
| B-23 | Five edges exist between feature packages. Baseline suite: **3296 tests collected**. | AST census; `docs/ROADMAP.md:743` |
| B-24 | `docs/adr/README.md`'s index lists ADR-0001 through ADR-0011 only. ADR-0012 is absent. | `docs/adr/README.md` |
| B-25 | ADR-0012 is present on disk and **untracked**. `git hash-object` on it yields `497ab06f8bfb5aad3b5344fd27319c34d3dd6537` — the blob it will have when added, and therefore the anchor against which "unchanged" is checkable before the file is ever staged. | `git status --porcelain`; `git hash-object docs/adr/0012-…md` |
| B-26 | `Account.margin` is `NonNegativeMoney = Annotated[Decimal, Field(ge=0)]`. A negative margin is **unrepresentable** through validation. | `packages/broker/src/atlas/broker/models/primitives.py:159`; `account.py:40` |
| B-27 | `Account.currency` is documented "Deposit currency; **every amount below is in it**." `margin` and `equity` are therefore in the same unit and their quotient is dimensionless. | `packages/broker/src/atlas/broker/models/account.py:37` |
| B-28 | Credential-bearing configuration is confined to two sections. Fields: `PostgresSettings.password: SecretStr` (`:71`), `RedisSettings.password: SecretStr` (`:118`). Unwrap: `.get_secret_value()` (`:100`, `:126`, `:133`, `:222`). Composites that **embed** the secret in a plain string: `PostgresSettings.dsn` — "a libpq connection string including the password" (`:93-101`) — and `RedisSettings.url` — "a Redis URL including the password when one is configured" (`:120-129`). Masked and therefore *not* credential-bearing: `safe_dsn` (`:104-108`), `safe_url` (`:130-135`). `LoggingSettings` (`:53`) and `DuckDBSettings` (`:137`) carry no credential at all. | `packages/config/src/atlas/config/settings.py` |
| B-29 | `tests/unit/risk/test_risk_boundary.py` already contains `_referenced_names(source)`, which walks the AST and collects `ast.Name.id`, **`ast.Attribute.attr`** and `ast.alias` names, deliberately skipping string constants "because the modules under test discuss `OrderRequest` in their docstrings in order to say that they do not build one". It already has liveness tests proving it ignores prose and catches a real reference. | `tests/unit/risk/test_risk_boundary.py:126-145`, `:173-176` |
| B-30 | The repository sets **no** decimal context anywhere. No `getcontext`, `localcontext`, `decimal.Context` or `.prec` appears in `packages/`, `apps/` or `tests/`. Whatever context a process has is the interpreter default, and no code has ever asserted otherwise. | exhaustive grep over all three trees |
| B-31 | `tests/conftest.py:26-51` provides `isolated_env`: it deletes every `ATLAS_*` variable, `chdir`s into an empty `tmp_path` so no `.env` is discovered, pins `ATLAS_CONFIG_DIR` at an empty tree, and calls `get_settings.cache_clear()` **both before and after** the test. `config_tree` (`:53-67`) layers a real four-directory config tree on top of it. | `tests/conftest.py` |
| B-32 | `get_settings` is `@lru_cache(maxsize=1)` and its docstring says "Tests that mutate the environment must call `get_settings.cache_clear()` first". `load_settings` — which the configuration tests use — is **uncached** and rebuilds `AtlasSettings` on every call. | `packages/config/src/atlas/config/settings.py:246-292` |
| B-33 | `atlas.config.__all__` has 16 names and includes both `get_settings` **and** `load_settings`, plus `AtlasSettings`, `LayeredTomlSource`, `ConfigurationError` and the four section classes. Every one of them is a genuinely importable name, so a name allowlist that admits only `get_settings` has fifteen real counter-examples available. | `packages/config/src/atlas/config/__init__.py` |
| B-34 | **No test asserts `atlas.config.__all__`.** The files that assert an `__all__` are in `broker`, `execution`, `risk` and `strategy` only. | grep for `__all__` across `tests/` |
| B-35 | No test reads any committed `config/*/atlas.toml`. The configuration tests write their own layers into `tmp_path` via the `config_tree` fixture. `.env.example` is named in `REQUIRED_ROOT_FILES` — an **existence** check, not a content check. | `tests/unit/test_config_settings.py:116-238`; `tests/contract/test_repository_structure.py:33` |

---

## 4. Problem statement

### 4.1 The gap

`atlas.risk` is declared authoritative and contains no control. That is the gap
this task closes.

### 4.2 Statements this task makes false

Each row is a statement — in the prose of a **living** document, or in a test
assertion — that is true at the baseline and false after implementation. Each
must be corrected. Line numbers are as at the baseline.

| # | Location | Current text | Why it becomes false |
|---|---|---|---|
| P-1 | `README.md:110-114` | "there is no sizing rule, **no exposure limit**, no drawdown control, no kill switch and no real strategy. Nothing outside the test suite produces a `TradeIntent`, **nothing anywhere turns one into a `RiskVerdict`**" | An exposure limit exists, and a function turns an intent into a verdict. The remaining clauses — no sizing rule, no drawdown control, no kill switch, no real strategy, nothing *produces* a `TradeIntent` outside the tests, no layer owns a `BrokerAdapter` — stay true and must stay stated. |
| P-2 | `docs/architecture/overview.md:59-62` | "**Five edges** between feature packages exist in the graph today … `atlas.risk` imports `atlas.broker` …" | There are six, and the enumeration omits `atlas.risk → atlas.config`. |
| P-3 | `docs/architecture/overview.md:114-117` | "Nothing outside the test suite produces a `TradeIntent`, **no function anywhere turns one into a `RiskVerdict`**" | A function does. The first and third clauses stay true. |
| P-4 | `packages/risk/src/atlas/risk/README.md:156-160` | "**This is the one edge ATLAS-TASK-0011 creates**, `atlas.risk → atlas.broker`, and it runs downward. The boundary test enumerates the permitted set …" | The clause is historically accurate but the section presents `atlas.risk → atlas.broker` as the package's only outward edge, and "the permitted set" is now two packages with a name allowlist on one of them. |
| P-5 | `packages/risk/src/atlas/risk/README.md:166-170` | "`atlas.risk` **holds the two contracts and none of the controls** … There is no sizing algorithm, **no exposure limit**, no drawdown control, no correlation cap and no kill switch" | It holds one control. The other three absences stay true. |
| P-6 | `packages/risk/src/atlas/risk/README.md:179-186` | "The behavioural half still waits on a pipeline to observe — nothing outside the test suite produces an intent, and **nothing anywhere turns one into a verdict** — and `tests/unit/risk/test_risk_boundary.py` says so in its own docstring" | The second clause is false. The behavioural half genuinely does still wait on a pipeline, and that must remain stated. The cross-reference must stay accurate against whatever the docstring becomes (P-8). |
| P-7 | `packages/risk/src/atlas/risk/__init__.py:18-23` | "ATLAS-TASK-0011 delivered the first of it: the two contracts … **The controls that reach a verdict — sizing, the exposure and drawdown limits, the correlation cap, the kill switches — arrive with the tasks that implement them**" | The exposure limit arrives with *this* task, not a later one. |
| P-8 | `tests/unit/risk/test_risk_boundary.py:3, :12-13` | "ATLAS-TASK-0011 introduces **exactly one edge**, `atlas.risk -> atlas.broker`"; "**nothing anywhere turns one into a `RiskVerdict`**, so there is no pipeline to observe" | Two edges; something turns an intent into a verdict. "No pipeline to observe" remains true and must remain stated. |
| P-9 | `tests/unit/strategy/test_strategy_boundary.py:19-21` | "There is no engine, no registry and **nothing that turns an intent into a verdict**" | The third clause is false. The first two are true, and the conclusion — that only the structural half is asserted — is unchanged. **This same file also carries the third `atlas.risk.__all__` assertion (B-12) at `:366-373`, which P-13 covers.** |
| P-10 | `packages/risk/src/atlas/risk/contracts.py` — the sentence at `:90-91`, inside the `RejectionReason` docstring that spans **`:86-97`** | "The four members are the controls `atlas.risk` is declared to own … **None of them is implemented yet**" | One of the four is implemented. |
| P-11 | `config/production/atlas.toml:1-11` | An enumeration of the invariants a production process must satisfy, closing "A process that violates any of these refuses to start." | A fourth invariant exists that the list omits, and it also applies under `ATLAS_ENV=demo`. An operator following this file would satisfy every documented requirement and the process would still refuse to start. |
| P-12 | `.env.example` | The catalogue of `ATLAS_*` variables. | This task creates the first variable that a demo or production process cannot start without, and the catalogue does not mention it. Left alone, the repository ships a mandatory start-up requirement with no documented cure. |
| P-13 | `tests/unit/risk/test_risk_boundary.py:225-232`, `tests/unit/execution/test_execution_boundary.py:423-430`, `tests/unit/strategy/test_strategy_boundary.py:366-373` | Three copies of `set(atlas.risk.__all__) == {five names}` | `atlas.risk` gains a sixth export. All three assertions fail. They are not redundant and none may be deleted: each is the tripwire its own package's boundary test relies on (B-12a). This is the only row that is a **test assertion** rather than prose, which is why §4.2's preamble names both. |
| P-14 | `docs/architecture/overview.md:74-76` | "`tests/unit/risk/test_risk_boundary.py` **asserts that the edge did not become several**, that no risk module can reach an order, and that `atlas.broker` still contains no import of `atlas.risk`" | The edge did become two. What the boundary test asserts is no longer singularity but a **permitted set** — `atlas.broker`, and `atlas.config` under a name allowlist — together with the credential scan that the allowlist cannot reach (§7.12). The other two clauses are unaffected and must stay stated. This row authorises the sentence and nothing around it: the paragraph's account of *why* the risk contracts are stated in the port's own `SymbolName`, `OrderSide`, `Price` and `Volume` is untouched by this task, as is its ADR-0010 cross-reference. Added by the §1 amendment of 2026-08-13, after this document's final audit. |

### 4.3 Statements checked and deliberately **not** changed

Recorded so that a reviewer can see they were considered rather than missed.

| Location | Text | Why it stays |
|---|---|---|
| `docs/architecture/overview.md:154-159` | "the behavioural half, that a running pipeline routes every intent through risk, now waits on an engine alone … what is still absent is anything that **drives a strategy, reaches a verdict and calls the translation in sequence**" | The sentence describes one subject doing all three in sequence. Nothing does. Still true, and more pointedly true after this task. |
| `docs/architecture/overview.md:132` (risk row) | "Sizing, exposure limits, drawdown control, kill switches — *(authoritative and non-bypassable)*" | A statement of responsibility, not of implementation status. Unchanged by this task. |
| `packages/risk/src/atlas/risk/__init__.py:1-4` | "Position sizing, per-instrument and portfolio exposure limits, drawdown controls, correlation caps and the kill switches …" | Same: the declared responsibility, not a claim about what exists. |
| `README.md:115-118` | "Every package below other than those named above is an importable unit with a documented responsibility and no implementation" | `atlas.risk` is one of "those named above". Unaffected. |
| `docs/ROADMAP.md:435, 669, 679, 730, 743` | The same phrases inside dated entries. | Dated historical narrative. Out of scope by the ATLAS-TASK-0016 precedent; the roadmap is a post-merge closeout, not part of implementation. |
| `config/demo/atlas.toml` | Layer header. | It makes no enumerative claim about invariants, so nothing in it becomes false. Adding the fact here would put it in a fourth place. D-6.3 makes the invariant cover demo as well, so the `config/production/atlas.toml` correction (P-11) must not imply the requirement is production-only — that wording is the substance of §13.1's human-review item for this file. |
| `config/README.md` | Layer table and precedence rules. | Describes the layering mechanism generically. Nothing in it becomes false. |
| `tests/unit/risk/test_risk_boundary.py` — absence of a *name* allowlist on the `atlas.risk → atlas.broker` edge | — | ADR-0012 requires an allowlist on the `config` edge only. Adding one to the broker edge would change an assertion this task has no mandate to change. |
| `docs/adr/README.md` | Index omitting ADR-0012. | Pre-existing debt, created when ADR-0012 was written. Recorded separately — see §17. |

---

## 5. Scope

In scope, and nothing else:

1. One new module in `atlas.risk` implementing the margin-utilisation control.
2. Its export from `atlas.risk`.
3. A new configuration section carrying the limit, and the start-up invariant
   that makes its absence fatal in live-money-shaped environments.
4. Admission of the `atlas.risk → atlas.config` edge in the boundary test, under
   a name allowlist.
5. Tests: behaviour of the control, the widened boundary, the credential-access
   guard, the new configuration invariant.
6. Correction of P-1 … P-14.
7. Bringing the already-accepted ADR-0012 under version control, **unmodified**
   (§8 F-16). This is a repository-integrity action, not an architectural one.

**Style rule (carried from ATLAS-TASK-0016).** Where this document states a
truth that must hold, it states the truth and not the sentence. The implementer
chooses wording. Where this document says a passage must not change, it means
byte-for-byte.

---

## 6. Non-goals

Numbered so they can be cited in review.

1. **No risk engine.** No orchestrator, no registry, no chain of controls, no
   dispatcher that runs every control in turn. One function.
2. **No pipeline.** Nothing calls the control outside the test suite. This task
   does not join the chain end to end and must not claim to.
3. **No second control.** `DRAWDOWN_LIMIT`, `CORRELATION_CAP` and `KILL_SWITCH`
   stay unimplemented. No new `RejectionReason` member.
4. **No per-instrument exposure control** (owner decision L-2).
5. **No volume reduction and no headroom path** (owner decision L-3). Risk
   approves the requested volume unchanged or rejects.
6. **No new portfolio-state contract.** `Account`, `Position` and `Symbol`
   remain broker-owned observations (ADR-0012:73-80).
7. **No broker call.** Risk does not obtain, construct, hold or call a
   `BrokerAdapter`, and names none of its operations.
8. **No caller-supplied limit.** The limit does not appear in the signature.
9. **No persistence and no historical state.** The control is a pure function of
   its arguments and the process's configuration.
10. **No credential-bearing configuration reaches risk** (owner decision L-7).
    This is a non-goal with teeth: it is enforced by the scanner of §7.12 and
    §12.2.1, not merely asserted here. It is **not** a general prohibition on
    configuration access — risk reads its own `RiskSettings` through
    `get_settings()`, and the guard must permit exactly that.
11. **No new edge** beyond `atlas.risk → atlas.config`. In particular
    `atlas.config` acquires no import of any feature package.
12. **No committed policy number.** No configuration layer in `config/` gains a
    value for the limit.
13. **No ADR's content is created or modified**, including ADR-0012 and
    `docs/adr/README.md`. This task nevertheless **commits ADR-0012**, which is
    accepted but untracked at the baseline (B-25), byte-for-byte as it stands.
    *No ADR modification* is not *no ADR may be committed* — the first is
    forbidden, the second is required (§8 F-16, AC-18).
14. **No roadmap edit.** `docs/ROADMAP.md` is post-merge closeout, out of scope
    here.
15. **No unrelated documentation cleanup** (owner decision L-8). The ADR-0012
    index omission is recorded in §17 and **not** fixed by this task.
16. **No async.** The control is synchronous, like everything else in the
    repository.

---

## 7. Authoritative decisions

The eight decisions below are the owner's, quoted, and are not open for
reinterpretation. Under each, *Evidence* records why it is implementable as
stated and *What must not happen* records the failure mode it forecloses.
D-6 and D-7 additionally carry the derivations the owner **required** to be
written down, and §7.10–§7.12 carry the three that needed probe evidence.

### D-1 (L-1) — The metric is portfolio margin utilisation

> "The exposure metric is portfolio-wide `Account.margin` / `Account.equity`
> against a configured maximum limit."

*Evidence.* Both fields exist on `Account` (B-6) and are `Decimal`-backed. The
quotient is well defined and equal to zero on a flat account, which is why this
metric is usable where `Account.margin_level` is not: `margin_level` is `None`
when no margin is pledged, and the model's own validator exists because "any
rule of the form `margin_level < threshold` fires on a flat account" (B-7).

*Consequence that must be stated, not hidden.* Because ADR-0012:99-101 forbids
risk from calling `margin_required`, the control cannot know what the intent
would cost. **The verdict therefore does not depend on the intent's size**: a
0.01-lot intent and a 100-lot intent against the same `Account` receive the same
answer. This follows directly from D-1 and D-7 and must be documented in the
module and asserted by a test (§12, T-9), not left for a reader to discover.

*What must not happen.* Substituting `margin_level`, `free_margin`, or a
notional computed from `Position` and `Symbol`. Adding a second metric.

### D-2 (L-2) — Portfolio-wide only

> "No per-instrument exposure control in TASK-0017."

*Evidence.* The metric in D-1 is an account-level quotient; nothing
per-instrument is required to compute it.

*What must not happen.* Accepting `Position` or `Symbol` arguments "for later".
A per-symbol cap, a concentration rule, or a correlation proxy.

### D-3 (L-3) — Reject-only

> "Do not implement the approved_volume reduction/headroom path in this task.
> Risk either approves the requested intent unchanged or rejects it."

*Evidence.* `RiskVerdict.approved_volume` permits equality with
`requested_volume`; `is_reduced` is then `False`.

*What must not happen.* Computing a permitted volume. Scaling the request.
Returning an approval whose `approved_volume` differs from
`intent.requested_volume`.

### D-4 (L-4) — Gross, not netted

> "Treat exposure conservatively/grossly where position exposure semantics are
> relevant. With margin utilisation as L-1, position-direction netting is
> effectively not part of the selected metric."

*Evidence.* `Account.margin` is the venue's own report of funds pledged; the
control performs no aggregation of its own, so there is no place a netting
choice could enter.

*What must not happen.* Introducing a netting rule, or aggregating `Position`
volumes to second-guess the reported margin.

### D-5 (L-5) — Non-positive equity fails closed

> "If equity is non-positive, the control must fail closed with a REJECTED
> RiskVerdict using RejectionReason.EXPOSURE_LIMIT. It must not raise an
> arithmetic exception or approve."

*Evidence.* `Account.equity` is `Money`, which permits zero and negative values
(B-6); a blown or fully-drawn account is representable, and the metric of D-1 is
undefined on it.

*The guard is mandatory for a reason that is not the obvious one.* Under §7.10's
exact arithmetic the control never divides, so non-positive equity produces no
`DivisionByZero` and — measured, not assumed — no exception of any kind, and it
already yields REJECTED. The guard is required anyway, and §7.10 records why: for
`equity ≤ 0` the cross-multiplication is no longer computing `margin / equity`
at all, and it reaches the right verdict by coincidence. A coincidence is not a
control, and this one silently inverts if the comparison is ever rewritten.
Because the guard changes no verdict, it can only be tested through the
rejection's `detail`: T-3a requires an unusable-state `detail` distinguishable
from a limit-breach `detail`, and that single assertion is what fails when the
guard is deleted (§12.1, validation 10f).

*What must not happen.* `DivisionByZero`, `InvalidOperation`, a `ValueError`, a
`None` return, or an approval. Ordering the code so that the arithmetic runs
before the guard. Omitting the guard on the grounds that the arithmetic "already
rejects".

### D-6 (L-6) — Conservative default plus a start-up invariant covering production **and** demo

> "The configuration must fail closed. Use the repository's established
> production-invariant pattern, but ensure the invariant covers both production
> AND demo/funded-like execution environments as appropriate. **IMPORTANT: Do
> not invent a hidden trading policy. The exact conservative default and
> invariant mechanism must be explicitly derived and recorded in the task
> specification. If a detail remains genuinely undecided, STOP and report it
> rather than silently choosing it.**"

The three details this delegates are derived below. **None required a STOP.**

#### D-6.1 — The default is `Decimal("0")`

*Derivation.* ADR-0012:165-174 fixes "absence is not permission" and leaves the
mechanism open between a required field, a conservative default, and a
production invariant. B-13 shows the repository has no required configuration
field anywhere, and B-14 shows its established idiom is precisely the third and
second combined: an **inert value** as the default, plus an invariant that
rejects the inert value where it matters — `password: SecretStr = SecretStr("")`
paired with `if not …get_secret_value()`.

The inert value for a margin-utilisation cap is the one that expresses no
opinion about how much exposure is acceptable. Every positive number is a
trading policy — the owner's instruction forbids inventing one. Zero is the only
value that is not a policy, and under D-6.2 it permits nothing. It is therefore
both the conservative default and the inert marker, exactly as `SecretStr("")`
is both.

*Consequence.* A `development` process starts with the default and rejects every
intent. That is correct: development has no funded account, and a control that
silently approved there would be the "hidden trading policy" the owner forbade.

#### D-6.2 — The comparison is strict, and this is forced rather than chosen

*Derivation.* With `<=`, a limit of `Decimal("0")` would **approve** on a flat
account: `margin` is zero, so utilisation is zero, and `0 <= 0` is true. The
inert default would then be the most permissive setting possible for exactly the
account state a fresh deployment is in. Only `<` makes the default reject
everything, which is what D-6.1 requires it to do.

The rule is therefore: utilisation must be **strictly below** the configured
limit for new exposure to be permitted.

*Exactness.* Strictness settles the **direction** of the comparison. It does not
settle how the comparison is computed, and the two are independent problems.
**How** it is computed is derived, with probe evidence, in §7.10 — which
disqualifies both of the obvious formulations.

#### D-6.3 — The invariant requires a value **greater than zero** in `production` and `demo`

*Derivation, part one — why a value test rather than a set-ness test.* All three
existing invariants check a value, never whether a field was supplied (B-15);
after construction, a Pydantic model cannot distinguish a default from an
explicitly-supplied identical value without machinery the repository does not
have. A value test is the pattern, and `> 0` is the value test that expresses
"absence is not permission" given D-6.1.

*Derivation, part two — why `demo` as well.* The owner requires the invariant
cover "demo/funded-like execution environments as appropriate". `config/README.md`
calls demo "production topology, non-funded account" and `config/demo/atlas.toml`
says demo "exists to be indistinguishable from production in everything except
the money at risk" (B-20). A risk limit is not money at risk; it is topology.

*Constraint on the mechanism.* `Environment.is_live` is true for `production`
only, and the three existing invariants return early when it is false (B-16).
**`Environment.is_live` must keep that meaning** — changing it would silently
extend the debug, logging-format and database-password invariants to demo, which
is not in scope. How the additional demo condition is expressed is the
implementer's choice subject to that truth (T-13).

#### D-6.4 — Units and range, forced by D-1

The metric in D-1 is a quotient, so the limit is a **ratio**, not a percentage:
`Decimal("0.5")` means fifty per cent. The field is constrained `ge=0` — a
negative maximum is a typo, not a policy, and the repository already range-
constrains fields (`port: int = Field(default=5432, ge=1, le=65535)`). **No
upper bound is imposed**, because every bound above zero would be a policy
number. The field additionally carries `allow_inf_nan=False`, derived in §7.11 —
that is a finiteness constraint, not a magnitude constraint, and it leaves every
finite value including `Decimal("1E+999999")` acceptable.

*How the value reaches the field, and why the route matters.* An environment
variable is a **string** and converts to `Decimal` exactly. A TOML value does not
necessarily: `tomllib` parses a bare `0.30000000000000000001` as the Python float
`0.3`, and the model then receives `Decimal("0.3")` — silently, with no error.
Quoting the TOML value (`"0.30000000000000000001"`) preserves it exactly. This is
recorded because P-12 documents the environment variable to operators, and the
environment-variable route is the one with no rounding step in it (T-16).

*What must not happen.* Committing a value into any `config/*/atlas.toml`.
Choosing a "sensible" default such as `0.5`, `0.3` or `0.8`. Making the
invariant fire in `development`. Redefining `Environment.is_live`.

### D-7 (L-7) — The `atlas.config` allowlist is `get_settings` and nothing else

> "Risk may import atlas.config only through the explicitly permitted
> get_settings name. Do not admit load_settings, AtlasSettings,
> PostgresSettings, RedisSettings, or credential-bearing configuration symbols.
> **If mypy --strict genuinely requires the risk configuration section class to
> be imported, STOP and report that requirement before widening the allowlist.**"

**The stop condition does not trigger.** Verified: `get_settings()` carries a
return annotation, so `mypy --strict` resolves the attribute chain from the call
site without any further import; and `get_settings` is present in
`atlas.config.__all__` (B-17), so `from atlas.config import get_settings`
satisfies `no_implicit_reexport`. The allowlist is exactly `("get_settings",)`.

*Evidence for the mechanism.* `tests/unit/execution/test_execution_boundary.py`
already implements a name allowlist with the `WHOLE_MODULE` sentinel that
reports a bare `import atlas.config` as its own offence, because binding the
module puts every attribute on it within reach and no name allowlist can admit
that (B-11). That mechanic is ported, not reinvented.

*A note on symmetry.* The new section class is exported from `atlas.config`
exactly as the four existing section classes are (B-18). Exporting it does
**not** admit it to the risk allowlist, and the boundary test must prove that by
rejecting an import of it (§12.2).

**The allowlist is necessary and not sufficient, and this is the reason §7.12
exists.** `get_settings()` returns the whole `AtlasSettings` tree. Once that one
permitted name is in hand, `get_settings().postgres.password.get_secret_value()`
is reachable with **no further import**, and `mypy --strict` type-checks it
cleanly — verified against the real package, not reasoned about. An import
allowlist cannot see that line, because there is no import in it. The escape path
is attribute access, so the guard has to be an attribute-level guard (§7.12).

*What must not happen.* `import atlas.config`. `from atlas.config import
AtlasSettings`. `from atlas.config import load_settings`. `from
atlas.config.settings import …`. Reaching a section class through
`atlas.config.RiskSettings` at runtime. Caching the settings object in a
module-level global inside `atlas.risk`.

### D-8 (L-8) — Correct what this task falsifies, and nothing else

> "Correct documentation that TASK-0017 makes factually false. Do not perform
> unrelated documentation cleanup. The ADR-0012 index omission is pre-existing
> debt and must be recorded separately rather than silently folded into
> TASK-0017."

*Evidence.* §4.2 enumerates the falsified statements; §4.3 enumerates what was
checked and left alone; §17 records the debt.

*What must not happen.* Editing `docs/adr/README.md`. Rewording a document
because it reads better. Touching `docs/ROADMAP.md`.

### 7.9 Names this document fixes — convention-derived, not architectural

These are **not** architectural decisions. They are fixed here only so the
acceptance criteria are mechanically checkable, and each is derived from an
existing repository convention. Any of them may be changed by the owner without
touching any of the eight owner decisions D-1 … D-8.

| Thing | Name | Convention it follows |
|---|---|---|
| Configuration section | `risk` | `logging`, `postgres`, `redis`, `duckdb` |
| Section class | `RiskSettings` | `LoggingSettings`, `PostgresSettings`, … |
| Field | `max_margin_utilisation` | `pool_max_size`, `max_volume`; British spelling verified across the repository (`normalised`, `authorised`, `canonicalise`) |
| Environment variable | `ATLAS_RISK__MAX_MARGIN_UTILISATION` | `env_nested_delimiter="__"` |
| Module | `packages/risk/src/atlas/risk/exposure.py` | `contracts.py` — named for what it holds |
| Function | `evaluate_exposure` | `build_order_request` — verb first |

### 7.10 The arithmetic — exact rational comparison (derived, with probe evidence)

D-1 fixes the metric and D-6.2 fixes the direction. Neither fixes how the
comparison is **computed**, and that turns out not to be a free choice: the two
formulations a reader would reach for first are both wrong. This section records
what was measured.

**The two obvious formulations, and why each is disqualified.** Every figure
below is probe output, run against this interpreter, at `prec` ∈ {3, 5, 10, 20,
28, 60}.

| Formulation | Result |
|---|---|
| `margin < limit * equity` | **Disqualified twice.** (a) Not precision-independent: with `margin = Decimal("30000.000000000000000001")`, `limit = Decimal("0.30000000000000000001")`, `equity = Decimal("100000")` it returns `True` at `prec` 20, 28 and 60 and `False` at `prec` 10, 5 and 3 — the product rounds and the answer flips. (b) Not total: with `limit = Decimal("1E+999999")` it raises `decimal.Overflow` at **every** precision, because the default context traps `Overflow` and `Emax` is 999999. MAJOR-4's ruling keeps `1E+999999` a valid operator-selected value, so a formulation that cannot evaluate it is not merely slow, it is wrong. |
| `margin / equity < limit` | **Disqualified, and worse than it looks.** Division rounds to the context's `prec`, so the quotient can round *onto* or *past* the limit. With `margin = 1`, `equity = 3`, `limit = Decimal("0." + "3" * 33)` the exact answer is `False` (⅓ exceeds thirty-three threes) but the expression returns `True` at `prec` 3, 10 **and 28** — that is, it approves at the repository's *default* context where the correct answer is to reject. It also flips direction between `prec` 28 and 34. Three of four adversarial cases came out wrong. |

**The formulation this task requires.** Compare the two ratios exactly, in
integer arithmetic. For a finite `Decimal`, `as_integer_ratio()` returns an exact
numerator/denominator pair with a strictly positive denominator. Writing
`margin = mn/md`, `limit = ln/ld`, `equity = en/ed`, and given `en > 0` (which
D-5's guard has already established):

```
margin / equity < limit    ⟺    mn · ld · ed  <  ln · en · md
```

Every operand is exact, every operation is Python **integer** arithmetic, and
integers are unbounded. There is no rounding step, no precision, no context and
no trap. `fractions.Fraction(margin) / Fraction(equity) < Fraction(limit)` is the
same comparison expressed differently and is equally acceptable; the probe
compared the two over 4000 random triples plus every adversarial case and found
**zero** disagreements.

**Decimal-context assumptions: none, and that is the requirement.** The
repository sets no context anywhere (B-30), so the ambient context is whatever
the interpreter default happens to be, and any dependence on it would be
accidental — exactly what the owner forbade. Integer arithmetic has no context to
depend on. The probe demonstrates this positively rather than by assertion: under
`prec=1` with **both** `Inexact` and `Rounded` trapped — a context designed to
raise on any rounding whatsoever — the exact form still returns the correct
answer, while the quotient form raises `decimal.Inexact`.

**Totality has a precondition, and the two requirements are coupled.**
`as_integer_ratio()` is total on every *finite* `Decimal` but raises on
non-finite input — `OverflowError` for `±Infinity`, `ValueError` for `NaN`. The
finiteness guard of §7.11 must therefore run **before** this arithmetic. Neither
requirement may be dropped in favour of the other: without §7.11 this arithmetic
can raise, and without this arithmetic §7.11 guards a computation that was
already wrong.

**Required order of operations inside the control.** This ordering is part of the
specification, not an implementation preference:

1. finiteness of `margin`, `equity` and the configured limit (§7.11);
2. `equity > 0` (D-5);
3. the exact comparison above.

Any other order hands a non-finite value to `as_integer_ratio()`, or evaluates
the comparison outside the domain on which it is valid, or both.

**Why step 2 is mandatory even though step 3 never divides — and what this means
for mutation testing.** The identity above requires `en > 0`. Multiplying an
inequality through by `en` preserves its direction only for a positive `en`, and
for `en = 0` the metric is undefined. Probed behaviour with the guard removed:

| `equity` | `margin` | `limit` | Cross-multiplication | True quotient `< limit` |
|---|---|---|---|---|
| `-1000` | `100` | `0.5` | `False` → reject | `True` — would approve |
| `-1` | `5000` | `0.5` | `False` → reject | `True` — would approve |
| `0` | `100` | `0.5` | `False` → reject | undefined |

It raises nothing and it rejects — the outcome D-5 wants — but it is answering a
different question than the one it appears to answer. **A consequence that must
be stated rather than discovered: removing the equity guard changes no verdict,
so a behavioural mutation test for it is impossible and must not be specified.**
What is observable is the *reason*: §10 T-3a requires an unusable-account-state
rejection to carry a `detail` distinguishable from a limit-breach rejection, and
that is the assertion which fails when the guard goes. Specifying a mutation test
that cannot fail would be worse than specifying none.

**Cost, stated rather than discovered.** Measured twice, on separate runs, and
quoted as the spread rather than as a single figure that would imply a precision
timing does not have: **2–3 µs** on realistic operands, **8–10 µs** at
`limit = Decimal("1E+100")`, and **0.36–0.43 s** at
`limit = Decimal("1E+999999")`, because that operand is a million-digit integer.
The order of magnitude is the load-bearing part; the third digit is noise. This is accepted and recorded, not engineered away: D-6.4 and MAJOR-4
both forbid an upper bound on finite limits, so the cost is the price of totality
at an operand no sane deployment will choose. It is written down here so that the
one test which exercises it (§12.1) is not mistaken for a hang and quietly
deleted. An implementation may short-circuit only if it produces identical
results on every case in §12.1.

### 7.11 Non-finite Decimals (derived, with probe evidence)

`NaN`, `Infinity` and `-Infinity` are representable `Decimal` values, and the
control must have a stated answer for them rather than inheriting whatever the
framework does this release.

**What validation already does — verified, not assumed.** Pydantic rejects all
three for a bare `Decimal` annotation *and* for `Annotated[Decimal, Field(ge=0)]`.
So `Account(equity=Decimal("NaN"))` raises `ValidationError` today, and so would
a non-finite configured limit. `Decimal("1E+999999")` is **finite** and is
accepted by both — the owner's ruling survives untouched.

**Why the control must still guard.** Three reasons, and any one is sufficient:

* `model_construct()` bypasses validation entirely. `Account.model_construct(
  equity=Decimal("NaN"))` succeeds — verified. It is also the only route by which
  a test can build one, which is what makes the guard testable at all.
* `packages/broker/**` is forbidden to this task (§9). The control cannot change
  `Account`'s field types, so it cannot strengthen the guarantee it depends on;
  it can only decline to rely on it.
* Without the guard the failure is not a wrong answer but a **leaked exception**:
  `as_integer_ratio()` raises on non-finite input (§7.10), and `Decimal("NaN") >
  0` raises `InvalidOperation` under the default context, which traps it. D-5
  requires that this control never raises.

**The rule.** If `Account.margin`, `Account.equity` or the configured limit is
not finite, the verdict is **REJECTED** with `RejectionReason.EXPOSURE_LIMIT`,
and nothing is raised. This is the same fail-closed answer D-5 gives to
non-positive equity, for the same reason: an unusable account state is not a
reason to permit new exposure.

**The configuration-level mechanism.** The limit field carries
`allow_inf_nan=False` explicitly. The probe confirms Pydantic accepts the flag on
a `Decimal` field and that it does not change which values are accepted here —
`ge=0` alone already rejects all three. It is stated anyway because the
repository's own convention is to be explicit rather than to inherit a framework
default: `LatencyMilliseconds = Annotated[float, Field(ge=0,
allow_inf_nan=False)]` at `primitives.py:175-178` carries a comment saying the
flag "is explicit because" the default differs. The owner's instruction — "do not
rely silently on Pydantic's current framework behaviour" — and the repository's
precedent point the same way.

**What must not happen.** Introducing an upper bound on finite limits in order to
dodge the non-finite case. Relying on `Account`'s validation instead of guarding.
Letting `InvalidOperation` or `OverflowError` escape. Returning `None`.

### 7.12 The credential-access guard (derived from the real configuration tree)

D-7's allowlist admits `get_settings`. `get_settings()` returns the whole
`AtlasSettings` tree, so the allowlist bounds what may be **imported** and says
nothing about what may be **reached**. This section derives the second guard.

**The escape path, verified against the real package.** With `get_settings` as
the only import, `get_settings().postgres.password.get_secret_value()` resolves
under `mypy --strict` with no error and no further import. That is the whole
attack surface: attribute access, invisible to any import scanner.

**The forbidden set, derived from B-28 rather than from name-guessing.**

| Identifier | Why it is in the set |
|---|---|
| `postgres`, `redis` | The only two section accessors that lead anywhere credential-bearing. Blocking them blocks every path below them. |
| `password` | The credential field itself, on both sections. |
| `get_secret_value` | The unwrap. Without it a `SecretStr` will not print its contents; with it the secret is a plain `str`. |
| `SecretStr` | The type. Naming it in `atlas.risk` means handling secrets, whatever the route. |
| `dsn`, `url` | Composites that **embed** the password in a plain connection string (B-28). Structurally they are already unreachable once `postgres` and `redis` are blocked; they are listed anyway because they are the two names that leak a credential without the word "password" appearing anywhere. |

**Deliberately *not* forbidden**, because the set is derived from what leaks and
not from what sounds sensitive:

* `safe_dsn`, `safe_url` — masked by construction (B-28). Their existence is
  precisely the evidence that `dsn` and `url` are not.
* `logging`, `duckdb`, and every field on them — no credential (B-28).
* `get_settings`, `risk`, `max_margin_utilisation` — **explicitly permitted**.
  The guard must not become a general prohibition on configuration access; risk
  reading its own limit is the entire point of the edge ADR-0012 admitted.

**The mechanism already exists and must be reused, not reinvented.**
`_referenced_names` (B-29) walks the AST and collects `ast.Attribute.attr`, which
is exactly what `.password` and `.get_secret_value` are. It deliberately skips
string constants, which matters here for a reason worth stating: the control's
own documentation **should** say that it never reads a database credential, and a
scanner that read prose would fail on the sentence documenting the rule. The
existing `OrderRequest` scan has the identical property and the identical
justification.

---

## 8. Files permitted to change

Nothing outside this table may be created, modified or deleted.

| # | Path | Change |
|---|---|---|
| F-1 | `packages/risk/src/atlas/risk/exposure.py` | **New.** The control. |
| F-2 | `packages/risk/src/atlas/risk/__init__.py` | Export the control; correct P-7. |
| F-3 | `packages/risk/src/atlas/risk/contracts.py` | Correct P-10 — the `RejectionReason` docstring at **`:86-97`** and nothing else. No field, member, validator or model config may change. `:86-97` is the single authoritative range for this passage everywhere in this document. |
| F-4 | `packages/config/src/atlas/config/settings.py` | Add `RiskSettings`; add the `risk` field to `AtlasSettings`; extend `_enforce_production_invariants` per D-6.3; extend `__all__`. |
| F-5 | `packages/config/src/atlas/config/__init__.py` | **Convention, not mechanically required.** Re-export `RiskSettings`; extend `__all__`. No acceptance criterion depends on this file: no test asserts `atlas.config.__all__` (B-34), and `mypy --strict` resolves `get_settings().risk.max_margin_utilisation` without the class being importable (D-7). It is listed because all four existing section classes are exported (B-18) and the asymmetry would be a consistency defect. If it is skipped, nothing in §12 or §14 fails — say so in the report rather than leaving it unexplained. |
| F-6 | `packages/risk/src/atlas/risk/README.md` | Correct P-4, P-5, P-6. |
| F-7 | `tests/unit/risk/test_exposure.py` | **New.** Behaviour of the control. |
| F-8 | `tests/unit/risk/test_risk_boundary.py` | Widen the boundary per D-7; correct P-8; update the `__all__` assertion. |
| F-9 | `tests/unit/execution/test_execution_boundary.py` | The `atlas.risk.__all__` set assertion at `:423-430` **only**. Nothing else in this file may change. |
| F-10 | `tests/unit/test_config_settings.py` | Update the two tests the new invariant breaks; add coverage for it. |
| F-11 | `tests/unit/strategy/test_strategy_boundary.py` | **Exactly two passages, and nothing else.** (a) The module docstring clause at `:19-21` (P-9). (b) The `atlas.risk.__all__` set literal inside `test_risk_still_exports_exactly_what_it_exported` at `:366-373` (P-13, B-12) — the set gains the control's name and nothing more. No other assertion, no constant, no helper, no import and no test name may change. In particular `INTENT_PRIMITIVES`, `RISK_SOURCES` and every `atlas.strategy` assertion are untouched. |
| F-12 | `README.md` | Correct P-1. |
| F-13 | `docs/architecture/overview.md` | Correct P-2, P-3, P-14. **Exactly three passages, and nothing else** — the edge count at `:59-62`, the pipeline sentence at `:114-117`, and the boundary-test sentence at `:74-76`. Every statement in §4.3 drawn from this file stays byte-for-byte. |
| F-14 | `.env.example` | Correct P-12 — a **commented-out** entry only. |
| F-15 | `config/production/atlas.toml` | Correct P-11 — the **header comment only**. No key or value may be added, removed or changed. |
| F-16 | `docs/adr/0012-risk-is-handed-its-state-and-reads-its-own-limits.md` | **Tracked, not modified.** The file is added to Git exactly as it stands on disk. Its content must not change by one byte: `git hash-object` must still yield `497ab06f8bfb5aad3b5344fd27319c34d3dd6537` (B-25) at the moment it is staged. This is the only entry in this table whose permitted change is *to version control* rather than *to content*. |

---

## 9. Files explicitly forbidden to change

| Path | Why |
|---|---|
| `docs/adr/**` — the **content** of every file, **including ADR-0012 and `docs/adr/README.md`** | ADRs are immutable once accepted. The index omission is §17's, not this task's. **Read this row together with F-16:** what is forbidden is editing bytes. Adding ADR-0012 to version control unchanged is required, and is not an edit. `docs/adr/README.md` is forbidden outright — neither edited nor otherwise touched. |
| `docs/ROADMAP.md` | Post-merge closeout, out of scope. |
| `docs/tasks/ATLAS-TASK-0014.md`, `-0015.md`, `-0016.md` | Closed specifications. |
| `docs/tasks/ATLAS-TASK-0017.md` | This document is the authority; it does not edit itself. |
| `packages/broker/**` | ADR-0012:73-80 — the observation models are reused as they are. |
| `packages/execution/**` | ADR-0011 is untouched by this task. |
| `packages/common/**`, `packages/strategy/**`, and every other package | Not in scope. |
| `config/default/atlas.toml`, `config/development/atlas.toml`, `config/demo/atlas.toml`, `config/README.md` | Non-goal 12 and §4.3. |
| `pyproject.toml`, `.github/workflows/**`, `docker-compose.yml` | No packaging, tooling or CI change is required. |
| Every test file not named in §8 | Not in scope. |

### 9.1 Protected passages

These must be **byte-for-byte identical** after implementation. Blob SHAs are at
the baseline.

| File | Baseline blob | What is protected |
|---|---|---|
| `docs/adr/0010-the-risk-boundary-is-a-verdict-on-an-intent.md` | `6f20807a73496c087a252145696dea4a3330d55b` | Whole file |
| `docs/adr/0011-execution-builds-the-request-another-layer-owns-the-port.md` | `45600504bd9212db0a5efcf1eb4d85ebfc1595ed` | Whole file |
| `docs/adr/0012-risk-is-handed-its-state-and-reads-its-own-limits.md` | `497ab06f8bfb5aad3b5344fd27319c34d3dd6537` | **Whole file — and it is nevertheless delivered.** The SHA is from `git hash-object`, not from a commit: the file is untracked at the baseline (B-25), so this is the blob it *will* have when added. It is the anchor that makes "unchanged" checkable before the file has ever been staged. |
| `docs/adr/README.md` | `ea3ddd5ad955ac79f3da6a1aa23f9d8983b76a63` | Whole file |
| `docs/ROADMAP.md` | `a33e034904e37bdf7908bfeb30a950507a0d84b8` | Whole file |
| `packages/risk/src/atlas/risk/contracts.py` | `921e5a633488b07232127cc43b603b7aa08cc3b0` | Everything except the `RejectionReason` docstring at `:86-97` |
| `tests/unit/execution/test_execution_boundary.py` | `f4bdfdead80146a433558996241e8c4ca38ffe46` | Everything except the assertion body at `:423-430` |
| `tests/unit/strategy/test_strategy_boundary.py` | `954d59087ebd443fb41900dc42ec4f9a77a84f37` | Everything except the docstring clause at `:19-21` **and** the `atlas.risk.__all__` set literal at `:366-373` (F-11) |
| `config/production/atlas.toml` | `b284772e542d5a4196c22bf07620b5b919e7c49d` | Every non-comment line |
| `config/default/atlas.toml` | `be593319d9cae02bf5b5ff00b367d0d29e86e385` | Whole file |

**A note on the ADR-0012 row.** It is the only row whose file is expected to
appear in `git status` — as `A` (added), never as `AM` (added, then modified). A
protected passage and a delivered file are orthogonal properties, and this row is
both.

---

## 10. Exact truths after implementation

Truths, not sentences. Each is mechanically checkable.

**The control**

* **T-1** — `atlas.risk` contains a callable that takes a `TradeIntent` and an
  `Account` and returns a `RiskVerdict`. It takes no other argument. In
  particular it takes no limit, no `Position`, no `Symbol`, no `BrokerAdapter`
  and no settings object.
* **T-2** — On approval the verdict's `status` is `VerdictStatus.APPROVED`, its
  `approved_volume` equals `intent.requested_volume` exactly, its `reason` is
  `None`, and `is_reduced` is `False`.
* **T-3** — On rejection the verdict's `status` is `VerdictStatus.REJECTED`, its
  `reason` is `RejectionReason.EXPOSURE_LIMIT`, its `approved_volume` is `None`,
  and its `detail` is a non-empty string. `detail` is used because the field
  exists for it — "such as the limit that was reached" (B-4).
* **T-3a** — A rejection caused by an unusable account state — non-positive
  equity (T-6), or a non-finite `margin`, `equity` or limit (T-27) — carries a
  `detail` that is **distinguishable** from the `detail` of a limit-breach
  rejection (T-5, T-7). `status` and `reason` are identical in both cases and
  must stay identical: O-A makes `EXPOSURE_LIMIT` the only reason this control
  may return, and D-1 keeps the verdict surface unchanged. Only `detail` differs.
  This truth is not decoration. §7.10 shows that removing the D-5 equity guard
  changes no verdict, so nothing else in this specification can detect its
  removal; the discriminating `detail` is what makes the guard observable, and
  the test in §12.1 that asserts it is the only test the guard's removal fails.
  The specification does not fix the wording of either string — an implementation
  satisfies T-3a by making the two distinguishable, and the test must assert the
  distinction, not a literal message.
* **T-4** — Every verdict carries the intent it judges: `verdict.intent` is the
  intent that was passed in.
* **T-5** — The intent is approved **if and only if** all three hold: `margin`,
  `equity` and the limit are finite; `Account.equity` is strictly positive; and
  the exact rational value of `Account.margin / Account.equity` is strictly less
  than the process's configured maximum margin utilisation. "Exact" is §7.10's
  integer cross-multiplication, evaluated in the order §7.10 requires.
* **T-6** — Equity of exactly zero rejects. Negative equity rejects. Neither
  raises.
* **T-7** — Utilisation exactly equal to the limit rejects.
* **T-8** — The decision is unchanged by `decimal.getcontext()` — by any `prec`,
  any rounding mode and any trap setting, including a context that traps
  `Inexact` and `Rounded`. The control performs no `Decimal` arithmetic that can
  round, and depends on no property of the ambient context. No `float` appears
  anywhere in the computation.
* **T-9** — The verdict does not vary with `intent.requested_volume`: two
  intents differing only in requested volume, judged against the same `Account`,
  receive the same `status` and the same `reason`. This limitation is stated in
  the module's own documentation.
* **T-10** — The control holds no limit and no settings object of its own. It
  obtains the limit by calling `get_settings()` on **every** invocation, and no
  module-level global in `atlas.risk` caches a settings object, a section object
  or a limit; nothing is captured at import time. This does **not** mean the
  environment is re-read per call: `get_settings` is `@lru_cache(maxsize=1)`
  (B-32), so settings are resolved once per process. The two are different
  claims and only the first is this task's. What the control guarantees is that
  it uses whatever the process's currently-resolved settings say — never a value
  it captured earlier and never a value a caller supplied.

**Configuration**

* **T-11** — `AtlasSettings` has a `risk` section carrying a `Decimal` maximum
  margin utilisation, defaulting to `Decimal("0")`, constrained `ge=0` and
  `allow_inf_nan=False` (§7.11), with **no upper bound**: every finite value,
  including `Decimal("1E+999999")`, is accepted.
* **T-12** — A process whose environment is `production` **or** `demo` and whose
  limit is not strictly greater than zero refuses to start, raising
  `ConfigurationError` through `load_settings`.
* **T-13** — `Environment.is_live` is true for `production` only, exactly as at
  the baseline, and the debug, logging-format and postgres-password invariants
  continue to apply to `production` alone.
* **T-14** — A `development` process starts with the default and needs no risk
  configuration.
* **T-15** — When several invariants are violated at once, all of them are still
  reported together in one error.
* **T-16** — A limit supplied through the layered TOML path arrives as a
  `Decimal`, never a `float`, and a **quoted** TOML value round-trips exactly.
  The recorded reason is the one that is actually true (§7 D-6.4): TOML has no
  decimal type, so `tomllib` parses a bare value as a Python `float` and the
  precision is lost **at parse time**, before the model sees it —
  `0.30000000000000000001` becomes `Decimal("0.3")` silently. Pydantic's
  `float → Decimal` conversion is `str`-mediated and introduces no binary
  artefact of its own, so `0.3` does *not* become
  `Decimal("0.299999999999999988897769753748")`. The hazard is silent truncation,
  not a float artefact, and the test must assert the behaviour that exists.
* **T-17** — No file under `config/` sets a value for the limit.

**Boundary**

* **T-18** — `atlas.risk` imports exactly two `atlas` packages other than
  itself: `atlas.broker` and `atlas.config`.
* **T-19** — The only name `atlas.risk` imports from `atlas.config` is
  `get_settings`. A bare `import atlas.config` anywhere in `atlas.risk` is an
  offence in its own right.
* **T-20** — `atlas.config` imports no feature package. The new edge did not
  become bidirectional.
* **T-21** — No module in `atlas.risk` names `BrokerAdapter`, `OrderRequest`,
  `OrderType`, `OrderStatus`, `place_order`, `modify_order`, `cancel_order` or
  `close_position`.
* **T-22** — No module in `atlas.risk` names `get_account`, `get_positions`,
  `margin_required`, `margin_available` or `can_trade` (ADR-0012:88-101).
* **T-23** — `atlas.broker` still imports nothing from `atlas.risk`.
* **T-24** — `atlas.risk.__all__` is the five baseline names plus the control,
  and nothing else. **All three** files that assert this set (B-12) agree, and
  all three still assert it — none is deleted, weakened or turned into a subset
  check.
* **T-25** — The names on the `atlas.risk → atlas.broker` edge are exactly
  `Account`, `OrderSide`, `Price`, `SymbolName`, `Volume`. `Account` is new and
  is imported from `atlas.broker.models`, because it is not in
  `atlas.broker.__all__` (B-8).
* **T-26** — No module in `atlas.risk` references any credential-bearing
  configuration name. The forbidden set is §7.12's — `postgres`, `redis`,
  `password`, `get_secret_value`, `SecretStr`, `dsn`, `url` — and the permitted
  set includes `get_settings`, `risk` and `max_margin_utilisation`. This is an
  attribute-level property, not an import-level one, and is enforced by a scanner
  that has been shown to fail on a real violating line.

**Non-finite values**

* **T-27** — A non-finite `Account.margin`, `Account.equity` or configured limit
  yields **REJECTED** with `EXPOSURE_LIMIT` and raises nothing. `InvalidOperation`,
  `OverflowError` and `ValueError` never escape the control.
* **T-28** — Configuration rejects `NaN`, `Infinity` and `-Infinity` for the
  limit, and accepts every finite value including `Decimal("1E+999999")`. No
  upper bound exists, and the control returns a verdict for such a limit without
  raising.

---

## 11. Dependency-graph requirements

The graph must be **derived from the AST**, not counted by hand and not read
from any document. Three conditions carried forward from ATLAS-TASK-0016 §11,
each of which has silently produced a wrong answer before:

1. **Parse the AST.** Do not `grep '^from atlas'`. Indented, conditional and
   parenthesised imports are edges too.
2. **Count `TYPE_CHECKING`-guarded imports as real edges.** `ast.walk` descends
   into the guard; a type-only import is still a coupling the boundary tests
   police.
3. **Derive the owning package from the source-root directory**, not by
   searching the path for the segment `atlas`. Under
   `packages/<pkg>/src/atlas/<pkg>/` the first `atlas` segment is the PEP 420
   namespace directory, and keying on it collapses every package into one owner.

### 11.1 Required state of the graph

| | Baseline | After |
|---|---|---|
| Edges between feature packages | 5 | **6** |
| New edge | — | `atlas.risk → atlas.config` |
| `atlas.risk` outward edges | `atlas.broker` | `atlas.broker`, `atlas.config` |
| Names on `atlas.risk → atlas.broker` | `OrderSide`, `Price`, `SymbolName`, `Volume` | + `Account` |
| Names on `atlas.risk → atlas.config` | — | `get_settings` only |
| `atlas.config` outward edges to feature packages | none | **none** |
| Cycles | none | **none** |

The census output must be recorded in the implementation report, and the figure
6 must come from that output rather than from this table.

---

## 12. Test requirements

### 12.1 Behaviour of the control — `tests/unit/risk/test_exposure.py` (new)

Every test constructs a real `Account` and a real `TradeIntent`.

**Hermetic settings — use the fixture that exists.** Every test in this file
takes the repository's `isolated_env` fixture (B-31), which deletes every
`ATLAS_*` variable, moves into an empty directory so no stray `.env` is
discovered, pins `ATLAS_CONFIG_DIR` at an empty tree, and calls
`get_settings.cache_clear()` **before and after** the test. Without it these
tests would read the developer's ambient environment and pass or fail for
reasons unrelated to the code. Do not hand-roll a substitute.

**Clearing the cache is not optional and not automatic.** `get_settings` is
`@lru_cache(maxsize=1)` (B-32). `isolated_env` clears it at the fixture
boundaries only. Any test that changes `ATLAS_RISK__MAX_MARGIN_UTILISATION`
*inside* the test body — which T-10's test does by design — must call
`get_settings.cache_clear()` again after the change, or the second call returns
the first call's cached object and the test asserts nothing.

Required coverage, one test per truth:

| Covers | Case |
|---|---|
| T-2, T-5 | Utilisation strictly below the limit → approved, `approved_volume == requested_volume`, `is_reduced is False`, `reason is None`. |
| T-3, T-5 | Utilisation above the limit → rejected with `EXPOSURE_LIMIT`, `approved_volume is None`, non-empty `detail`. |
| T-7 | Utilisation exactly equal to the limit → rejected. |
| T-6 | `equity == 0` → rejected with `EXPOSURE_LIMIT`, no exception. |
| T-6 | `equity < 0` → rejected with `EXPOSURE_LIMIT`, no exception. |
| T-3a, D-5 | **The only test that can detect the equity guard's removal.** Judge two accounts that both reject: one for a limit breach (`margin`/`equity` above the limit, `equity > 0`) and one for an unusable state (`equity == 0`). Assert `status` and `reason` are equal — both `REJECTED`/`EXPOSURE_LIMIT` — and that the two `detail` strings differ. Assert the difference, never a literal message. §7.10 proves the guard changes no verdict, so without this row nothing in the suite fails when D-5's guard is deleted. Repeat for a non-finite input against the §7.11 guard. |
| D-6.1, D-6.2 | Flat account (`margin == 0`) with the **default** limit of `Decimal("0")` → rejected. This is the test that fails if `<` is weakened to `<=`. |
| T-4 | The verdict carries the intent that was passed in. |
| T-8 | **Precision independence, on the two cases that actually discriminate.** Both run inside `decimal.localcontext()` at each of `prec` ∈ {3, 10, 28, 60} and give one answer throughout. (a) `margin = Decimal("30000.000000000000000001")`, `equity = Decimal("100000")`, `limit = Decimal("0.30000000000000000001")` → **approved** at every precision. This is the case on which `margin < limit * equity` flips to rejected at `prec ≤ 10`. (b) `margin = Decimal(1)`, `equity = Decimal(3)`, `limit = Decimal("0." + "3" * 33)` → **rejected** at every precision. This is the case on which `margin / equity < limit` wrongly approves at the default `prec = 28`. A test that uses only round numbers proves nothing here: all three formulations agree on those. |
| T-8 | **Context independence beyond precision.** The same inputs inside a `localcontext()` with `prec = 1` and both `Inexact` and `Rounded` trapped give the same verdict and raise nothing. This is the test that fails if any `Decimal` arithmetic remains in the comparison path. |
| T-28 | `limit = Decimal("1E+999999")` with an ordinary account → a verdict, no exception. This is the case on which `margin < limit * equity` raises `decimal.Overflow`. **It costs 0.36–0.43 s** (§7.10) because the operand is a million-digit integer; that is expected, is not a hang, and is the price of the totality T-28 requires. Do not delete it and do not "fix" it with an upper bound. |
| T-27 | Non-finite `equity` → rejected with `EXPOSURE_LIMIT`, nothing raised. Built with `Account.model_construct(...)`, which is the only route past validation (§7.11) and must be commented as such so a reader does not think validation is being bypassed carelessly. Repeat for non-finite `margin`, and for a non-finite limit. |
| T-9 | Two intents differing only in `requested_volume`, same `Account`, same `status` and `reason`. Named so a reader sees it is a documented limitation, not an oversight. |
| T-10 | Two calls against the same `Account`, with the configured limit changed **and `get_settings.cache_clear()` called** between them, return different verdicts. What this proves is that the control captured nothing at import time; the `cache_clear()` is what makes the second resolution happen, and without it the test would assert nothing. It does **not** prove — and must not be named as if it proved — that the environment is re-read per call. |

**Cases deliberately not tested, and why.** Recorded so a reviewer can see they
were considered rather than missed.

| Case | Why there is no test |
|---|---|
| Negative `Account.margin` | **Unrepresentable.** `margin` is `NonNegativeMoney = Annotated[Decimal, Field(ge=0)]` (B-26). A test would have to `model_construct` a state the broker port cannot report, and would assert behaviour for an input that cannot arrive. Do not add one. |
| Currency conversion between `margin` and `equity` | **Moot.** `Account.currency` is the deposit currency and "every amount below is in it" (B-27). The two operands share a unit, the quotient is dimensionless, and there is no conversion to get wrong. |
| An upper bound on the limit | **There is none** (D-6.4, T-28). A test asserting one would encode a policy number the owner forbade. |

**Mutation sensitivity.** The suite must fail if: `<` becomes `<=`; the
finiteness guard is removed or moved after the arithmetic — caught by T-27,
because `as_integer_ratio()` then raises (§7.11); **the equity guard is removed
or moved after the arithmetic — caught by the T-3a row and by nothing else**,
for the reason §7.10 establishes: with exact cross-multiplication the verdict is
unchanged either way, so only the discriminating `detail` makes the removal
observable. The two guards are not symmetric and must not be described as if
they were. The suite must also fail if the exact comparison is replaced by `margin < limit * equity` or by `margin /
equity < limit` (the T-8 cases are chosen so that each of these substitutions
breaks at least one test under the default context); `EXPOSURE_LIMIT` is swapped
for another `RejectionReason`; `approved_volume` is set to anything other than
`intent.requested_volume`; the default limit is changed to a positive number.

**A mutation this suite deliberately does not claim to catch.** Deleting the
equity guard and leaving *no* discriminating `detail` behind is caught. Deleting
the guard while hand-writing a different `detail` at the same site is not a
mutation of the guard at all — it is the guard, re-expressed. That is the honest
limit of what T-3a buys, and it is stated so no one later reads the T-3a row as
proving more than it does.

### 12.2 Boundary — `tests/unit/risk/test_risk_boundary.py`

* `PERMITTED_ATLAS_PACKAGES` gains `atlas.config`; `FORBIDDEN_ATLAS_PACKAGES`
  loses it. **These are the same edit and must be made together** — leaving
  `atlas.config` in both lists makes the two tests contradict each other.
* A name allowlist for `atlas.config` is added, containing exactly
  `get_settings`, using the `WHOLE_MODULE` mechanic ported from
  `tests/unit/execution/test_execution_boundary.py:128, 161-191` so that
  `import atlas.config` is reported as its own offence.
* **Scanner liveness — the allowlist can fire.** Each of these constructed
  counter-examples must be reported as an offence. Every one names a symbol that
  genuinely exists and is genuinely importable (B-33), so none is a strawman:

  | Counter-example | What it would otherwise smuggle in |
  |---|---|
  | `from atlas.config import load_settings` | The **uncached** loader. It is in `atlas.config.__all__`, it type-checks, and it is one character away from being mistaken for the permitted name. It would let risk rebuild settings behind `get_settings`'s back. |
  | `from atlas.config import AtlasSettings` | The whole settings tree as a type, and with it every section. |
  | `from atlas.config import RiskSettings` | The section class — exported by convention (F-5) and still not admitted (D-7). |
  | `from atlas.config.settings import get_settings` | The module path around the package's `__all__`, defeating `no_implicit_reexport`. |
  | `import atlas.config` | Every attribute at once, which no name allowlist can bound — hence the `WHOLE_MODULE` sentinel. |

  A scanner that has never been shown to fail is not a test.
* **Scanner liveness — the edge exists.** Some module in `atlas.risk` must
  actually be observed importing `atlas.config`, so the allowlist is not
  vacuously satisfied by an absent edge.
* **The exported section class is still rejected.** `RiskSettings` is exported
  from `atlas.config` (D-7) and must still be an offence for `atlas.risk` to
  import.
* T-22: no module in `atlas.risk` names `get_account`, `get_positions`,
  `margin_required`, `margin_available` or `can_trade`.
* The `atlas.risk.__all__` set assertion is updated (T-24).
* The module docstring is corrected (P-8), keeping the true half: there is still
  no pipeline to observe.

### 12.2.1 The credential-access guard — same file (T-26)

This is the guard the import allowlist cannot provide (§7.12). It is mandatory,
and all four parts below are mandatory: a scanner nobody has watched fail is not
evidence of anything.

1. **The scan.** For every path in `RISK_SOURCES`, the intersection of
   `_referenced_names(source)` (B-29) with the forbidden set of §7.12 —
   `postgres`, `redis`, `password`, `get_secret_value`, `SecretStr`, `dsn`,
   `url` — is empty. The forbidden set lives in a module-level constant so it is
   greppable and reviewable, in the style of the existing
   `ORDER_CONSTRUCTION_SYMBOLS`.
2. **Positive clean-source test.** The real permitted access —
   `get_settings().risk.max_margin_utilisation` — scans clean. This is the test
   that fails if someone "hardens" the guard into a general ban on configuration
   access. It encodes the owner's constraint directly: risk must still be able to
   read its own limit.
3. **Negative mutated-source test — mutation sensitivity.** Each of these real
   violating lines, scanned as source, is reported as an offence:
   `get_settings().postgres.password.get_secret_value()`;
   `get_settings().redis.url`; `get_settings().postgres.dsn`;
   `from pydantic import SecretStr`. At least one of them must additionally be
   **injected into the actual text of `exposure.py`** and shown to make the scan
   in (1) fail — not merely scanned as a standalone string. That is the
   difference between demonstrating the scanner works and demonstrating it is
   wired to the thing it is supposed to protect.
4. **Prose immunity.** A docstring saying the control never reads a database
   password does **not** trip the scanner, because `_referenced_names` skips
   string constants (B-29). Assert it, for the same reason the existing
   `OrderRequest` liveness test at `:173-176` asserts it: the module's
   documentation should be free to describe the rule it obeys.

*Note on redundancy, stated so it is not later "simplified" away.* `dsn` and
`url` are unreachable once `postgres` and `redis` are blocked. They are in the
set anyway because they are the two names that leak a credential without the word
"password" appearing anywhere, and a guard that only catches the obvious spelling
is a guard that will be defeated by the unobvious one. `safe_dsn` and `safe_url`
are deliberately absent: they mask (B-28), and their absence is what shows the
set was derived from what leaks rather than from what sounds alarming.

### 12.3 Execution boundary — `tests/unit/execution/test_execution_boundary.py`

Only the `atlas.risk.__all__` set at `:423-430`. The class it lives in exists to
catch exactly this — "the cheap way to pass the tests above is to move the
problem next door" — so it must be updated deliberately, not deleted.

### 12.4 Strategy boundary — `tests/unit/strategy/test_strategy_boundary.py`

Two passages, per F-11, and nothing else:

* the docstring clause at `:19-21` (P-9);
* the `atlas.risk.__all__` set literal at `:366-373` (P-13), which gains the
  control's name and nothing more.

This file's copy of the assertion is not redundant with the other two. It sits in
`TestTheRiskBoundaryWasNotWidened`, whose docstring is "The cheap way to pass the
tests above is to move the problem next door" (B-12a) — it is the strategy
package's own tripwire on `atlas.risk`'s surface, and deleting it to avoid
updating it would remove exactly the check that caught this. No other assertion,
constant, helper or test name in the file changes.

### 12.5 Configuration — `tests/unit/test_config_settings.py`

**Which settings function these tests call, and why it matters.** The existing
tests in this file call `load_settings()`, which is **uncached** and rebuilds
`AtlasSettings` on every call (B-32). The control calls `get_settings()`, which
is cached. New tests here follow the file's existing convention and use
`load_settings()` with `isolated_env` or `config_tree`; that is why they can set
an environment variable and immediately observe its effect without touching the
cache. A test that mixes the two — setting a variable and then calling
`get_settings()` — must call `get_settings.cache_clear()` in between.

Two existing tests **break** and must be updated, not deleted:

| Test | Why it breaks | Required outcome |
|---|---|---|
| `TestProductionInvariants::test_a_correctly_configured_production_process_starts` | Its helper sets `ATLAS_ENV`, the postgres password, the log format and debug — but not the risk limit, so the new invariant fires. | Supply the risk limit; the test must still assert a successful start. |
| `test_atlas_env_selects_the_environment` (`:86`) | It selects `demo` with nothing else set, which the new invariant now refuses. | Supply the risk limit, or select an environment the invariant does not cover — but the demo coverage itself must remain asserted elsewhere. |

New coverage:

* Production without a risk limit → `ConfigurationError` (T-12).
* Demo without a risk limit → `ConfigurationError` (T-12).
* Development without a risk limit → starts (T-14).
* The default is exactly `Decimal("0")` (T-11).
* A negative limit is refused by the field constraint (D-6.4).
* `NaN`, `Infinity` and `-Infinity` are each refused by the field constraint
  (T-28, §7.11). Supplied as strings through the environment, which is how an
  operator would actually get one in.
* A finite `Decimal("1E+999999")` is **accepted** — the boundary of T-28's "no
  upper bound", and the test that fails if someone adds one (D-6.4).
* All violations still reported together, now including the risk limit (T-15).
* A **quoted** TOML limit round-trips exactly, and a bare TOML float is rounded
  at parse time before the model sees it (T-16). Both halves are asserted: the
  second documents a real operator-facing hazard, and asserting only the first
  would leave the specification's stated reason unverified.
* `Environment.is_live` is unchanged, and the three original invariants still do
  not fire in `demo` (T-13). This is the test that catches an implementation
  that "covers demo" by redefining `is_live`.

### 12.6 Suite arithmetic

The baseline is **3296** collected tests (B-23). The final count must be
**reconciled**, not discovered.

**`RISK_SOURCES` is defined in three boundary-test files, and two of them
parametrise on it.** That is the whole subtlety, and getting it wrong understates
the delta:

| File | `RISK_SOURCES` defined at | Parametrised by it? | Delta from one new risk module |
|---|---|---|---|
| `tests/unit/risk/test_risk_boundary.py` | `:41-42` | Yes — `:182` (permitted imports) and `:213-214` (× 8 `ORDER_CONSTRUCTION_SYMBOLS`) | **+9** |
| `tests/unit/strategy/test_strategy_boundary.py` | `:49-50` | Yes — `:383` (`test_no_risk_module_imports_the_layer_above_it`) | **+1** |
| `tests/unit/execution/test_execution_boundary.py` | `:52-53` | **No** — used only in aggregate assertions (`:233`, `:367`) | **0** |

Contributions:

| Change | Delta |
|---|---|
| `atlas.config` removed from `FORBIDDEN_ATLAS_PACKAGES` (parametrised, `:186`) | **−1** |
| `exposure.py` joins `RISK_SOURCES` — risk boundary permitted-import test (`:182`) | **+1** |
| `exposure.py` × the eight `ORDER_CONSTRUCTION_SYMBOLS` (`:213-214`) | **+8** |
| `exposure.py` joins `RISK_SOURCES` — **strategy** boundary test (`:383`) | **+1** |
| New tests in §12.1–§12.5, including §12.2.1's credential guard | +N |

The source-module contribution is therefore **+10**, not +9.

The implementation report must state the final count and show that it equals
**`3296 − 1 + 10 + N`** for the N it actually added. N is whatever the
implementation writes; this document does not predict it, and a specification
that named a final number would be inventing one. A count that does not
reconcile means a test was silently dropped.

**Aggregate assertions are not counted here and must still be checked.** The
three files also assert over `RISK_SOURCES` in non-parametrised tests
(`test_risk_boundary.py:156-160, 191`; `test_strategy_boundary.py:234, 311`;
`test_execution_boundary.py:233, 367`). Those test counts do not change, but
their *content* now covers a new module, and a failure in one of them is a real
boundary violation rather than an arithmetic surprise.

---

## 13. Validation requirements

Every command's output must be recorded in the implementation report. `py -m
pytest` does not work in this repository — the virtual environment's interpreter
must be used.

1. `./.venv/Scripts/python.exe -m pytest -q` — full suite, and the collected
   count reconciled per §12.6.
2. `./.venv/Scripts/python.exe -m pytest tests/unit/risk tests/unit/execution tests/unit/strategy tests/unit/test_config_settings.py -q`
3. `./.venv/Scripts/python.exe -m mypy --strict packages/risk/src packages/config/src`
4. `./.venv/Scripts/python.exe -m ruff check .`
5. `./.venv/Scripts/python.exe -m black --check .`
6. The AST dependency census of §11, run over all source roots, with its raw
   output recorded.
7. `git status --porcelain` — every path must appear in §8.
8. `git diff --stat` — no file outside §8.
9. For each protected passage in §9.1, the blob SHA or the exact diff
   demonstrating the passage is byte-for-byte unchanged.
10. Mutation checks. Each is applied, observed to fail, then reverted, and the
    suite re-run green before the report is written. Every one must break at
    least one test:
    a. `<` → `<=` (§12.1).
    b. The exact comparison → `margin < limit * equity` (must break a T-8 case
       and the T-28 case).
    c. The exact comparison → `margin / equity < limit` (must break T-8 case
       (b), which is chosen to fail at the default precision).
    d. The finiteness guard removed (must break T-27, because
       `as_integer_ratio()` then raises).
    e. A real credential line injected into `exposure.py` (must break §12.2.1).
    f. The equity guard removed. **This one must break exactly one test — the
       T-3a row — and no other.** If it breaks a `status` or `reason`
       assertion, the arithmetic is not the exact form of §7.10 and something
       is wrong. If it breaks nothing, T-3a was not written as specified and
       the guard is untested. Both outcomes are stop conditions, not
       observations to write up afterwards.
11. `git grep -n "no exposure limit"` and
    `git grep -n "turns one into a"` — every surviving hit must be either a
    corrected sentence or a `docs/ROADMAP.md` line, per §4.3.
12. `git grep -n "risk\.__all__"` — the enumeration must return the **three**
    asserting files of B-12 and no fourth. If a fourth exists, stop (§15).
13. `git hash-object docs/adr/0012-risk-is-handed-its-state-and-reads-its-own-limits.md`
    must print `497ab06f8bfb5aad3b5344fd27319c34d3dd6537` (B-25) **before** the
    file is staged, and `git status --porcelain` must show it as `A`, never `AM`.

### 13.1 What is mechanically checked, and what is not

Stated so that no reviewer mistakes a human judgement for a passing test.

| Requirement | How it is actually verified |
|---|---|
| Everything in §12; validation 1–6, 10 | **Mechanically tested.** A failure is a red suite. |
| §9.1 protected passages; the ADR-0012 blob; the file scope of §8 | **Mechanically checked** by blob SHA and `git status` / `git diff --stat` (validation 7, 8, 9, 13). Not by a test, but not by judgement either. |
| `.env.example` (P-12) | **Existence only is structurally validated** — the file is named in `REQUIRED_ROOT_FILES` at `tests/contract/test_repository_structure.py:33` (B-35). Its *content* is asserted nowhere. The correctness of the new commented-out entry is **human-reviewed**. |
| `config/production/atlas.toml` header (P-11) | **Human-reviewed.** No test reads any committed `config/*/atlas.toml`; the configuration tests write their own layers into `tmp_path` (B-35). |
| P-1 … P-14 wording (AC-12) | **Human-reviewed**, assisted by validation 11. `git grep` is a presence check on a phrase; it can prove a false sentence still exists, but it cannot prove a replacement sentence is true. P-14 is the standing demonstration: it was found by reading, after every mechanical check in §13 had passed. |

Two consequences follow and must not be glossed over. First, the operator-facing
half of this task — the two files that tell a human how to start a process that
will otherwise refuse to boot — is the half with the weakest automated backing.
Second, AC-12 must not be reported as "proved by validation 11": the grep is
evidence, not proof.

---

## 14. Acceptance criteria

Mechanically checkable. Each cites what proves it.

| # | Criterion | Proved by |
|---|---|---|
| AC-1 | `atlas.risk` exports one control with the signature in T-1, and `atlas.risk.__all__` matches T-24 in **all three** asserting files (B-12), all three of which still assert it. | §12.2, §12.3, §12.4, validation 12 |
| AC-2 | Approval returns the requested volume unchanged; no reduction path exists. | T-2, D-3 |
| AC-3 | Rejection carries `EXPOSURE_LIMIT` and a non-empty `detail`, and an unusable-state rejection's `detail` is distinguishable from a limit-breach rejection's while `status` and `reason` stay identical. | T-3, T-3a |
| AC-4 | The comparison is strict, and is exact integer arithmetic per §7.10 — independent of every property of the ambient decimal context, and total on every finite `Decimal` including `1E+999999`. Neither disqualified formulation survives in the code. | T-7, T-8, T-28, validation 10a–10c |
| AC-5 | Non-positive equity rejects without raising; the guard precedes the arithmetic (there is no division to precede — §7.10); and its removal is detected by exactly one test. | T-6, T-3a, validation 10f |
| AC-6 | The default limit is exactly `Decimal("0")` and no `config/` file sets a value. | T-11, T-17 |
| AC-7 | A `production` process and a `demo` process both refuse to start without a positive limit; a `development` process starts. | T-12, T-14 |
| AC-8 | `Environment.is_live` is unchanged and the three original invariants still apply to `production` alone. | T-13 |
| AC-9 | The AST census reports six feature-package edges, the name sets of T-25 and T-19, and no cycle. | §11, validation 6 |
| AC-10 | The boundary scanner for `atlas.config` is proved able to fail, and the edge it polices is proved to exist. | §12.2 |
| AC-11 | `atlas.risk` names no port operation and no order-construction symbol. | T-21, T-22 |
| AC-12 | P-1 … P-14 are corrected, and every true clause inside those passages survives. **Human-reviewed** (§13.1); validation 11 is supporting evidence, not proof. | §4.2, §13.1, validation 11 |
| AC-13 | Nothing in §4.3 changed. | validation 8 |
| AC-14 | Every protected passage in §9.1 is byte-for-byte unchanged, ADR-0012 included. | validation 9, 13 |
| AC-15 | `git status --porcelain` and `git diff --stat` show only §8 paths — F-16 among them, as an addition. | validation 7, 8 |
| AC-16 | The final collected count reconciles to **`3296 − 1 + 10 + N`**. | §12.6 |
| AC-17 | `mypy --strict`, `ruff` and `black --check` are clean. | validation 3, 4, 5 |
| AC-18 | No ADR's content was created or modified, and `docs/adr/README.md` is untouched, so the ADR-0012 index omission is still present and still recorded in §17. **ADR-0012 is nevertheless delivered**: it is tracked, with blob `497ab06f8bfb5aad3b5344fd27319c34d3dd6537`, byte-identical to the baseline file. `docs/ROADMAP.md` is untouched. | validation 7, 13, §17 |
| AC-19 | No module in `atlas.risk` reaches credential-bearing configuration, the guard permits `get_settings().risk.max_margin_utilisation`, and the scanner has been **observed to fail** on a real violating line injected into `exposure.py`. | T-26, §12.2.1, validation 10e |
| AC-20 | Non-finite `margin`, `equity` and limit all reject with `EXPOSURE_LIMIT` and raise nothing; configuration refuses `NaN`/`±Infinity` and accepts every finite value including `1E+999999`. | T-27, T-28, §7.11, validation 10d |
| AC-21 | Every test touching settings is hermetic: it uses `isolated_env`, and any test that changes configuration mid-body clears the `get_settings` cache. | §12.1, §12.5, B-31, B-32 |

---

## 15. Stop conditions

Stop, report, and change nothing further if any of these occurs.

1. **`mypy --strict` requires importing the configuration section class** into
   `atlas.risk`. §7 D-7 records that it does not, verified at the baseline. If
   the implementation finds otherwise, **do not widen the allowlist** — report
   the exact mypy output and stop (owner decision L-7).
2. **A conservative default or invariant mechanism turns out not to be
   derivable** as §7 D-6 records it. Do not choose one silently; report and stop
   (owner decision L-6).
3. **Two pieces of repository evidence conflict.** Report both and explain the
   conflict; do not reconcile them silently.
4. **A required correction cannot be made without editing a forbidden file or a
   protected passage.** Report the collision; do not edit.
5. **A change would require modifying an ADR's content**, including ADR-0012.
   ADRs are immutable once accepted. *Committing ADR-0012 unchanged (F-16) is
   not a modification and does not trigger this condition* — but a
   `git hash-object` that does not match `497ab06f…` does, immediately.
6. **The suite count does not reconcile** per §12.6. A missing test is a defect,
   not a rounding error.
7. **The control needs `Position`, `Symbol`, or any argument beyond
   `TradeIntent` and `Account`** to satisfy a truth in §10. That would
   contradict D-1/D-2 and must be raised, not absorbed.
8. **Making the invariant cover `demo` appears to require changing
   `Environment.is_live`.** T-13 forbids it; report and stop.
9. **The implementation appears to require a new `RejectionReason` member.**
   Non-goal 3; report and stop.
10. **Anything in this specification is ambiguous at the point of writing code.**
    Report the ambiguity with the two readings; do not pick one.
11. **A fourth assertion of `atlas.risk.__all__` exists** that B-12 does not
    name (validation 12). Three were found by enumeration and one was missed
    once already; report the fourth and stop rather than widening §8 by
    inference.
12. **The exact comparison of §7.10 cannot be written without a decimal
    context**, or `Decimal.as_integer_ratio()` is unavailable. Both were probed
    at the baseline. Do not substitute a rounding formulation — report and stop.
13. **The credential guard of §7.12 cannot be expressed with
    `_referenced_names`**, or forbidding the derived set would reject a name
    `atlas.risk` legitimately needs. Report the collision; do not quietly shrink
    the forbidden set, and do not broaden it into a ban on configuration access.
14. **A finite limit is found that the arithmetic cannot evaluate.** T-28 and
    D-6.4 forbid an upper bound; an implementation that needs one has found a
    real defect in §7.10 and must report it rather than introduce a policy
    number.

---

## 16. Relationship to ADR-0010, ADR-0011 and ADR-0012

### 16.1 ADR-0010 — the risk boundary is a verdict on an intent

Unchanged and unamended. ADR-0010 established `TradeIntent` and `RiskVerdict`
and deliberately declined to invent a portfolio-state contract. This task
implements a *consumer* of those contracts and invents no state contract, so
ADR-0010 is confirmed by use rather than revisited. `contracts.py` is edited
only in the `RejectionReason` docstring (F-3); no field, member or validator
moves.

### 16.2 ADR-0011 — execution builds the request, another layer owns the port

Unchanged and unamended. Nothing in this task touches `atlas.execution` beyond a
single `__all__` set assertion in its boundary test, which exists precisely to
notice that `atlas.risk`'s surface changed. `atlas.execution` still builds a
request it cannot place, and no layer owns a `BrokerAdapter`.

### 16.3 ADR-0012 — risk is handed its state and reads its own limits

This task is ADR-0012's first implementation. Conformance:

| ADR-0012 | How this task conforms |
|---|---|
| State arrives as arguments | T-1: the control takes `TradeIntent` and `Account`. |
| No new state contract | Non-goal 6; `Account` is used as it is. |
| `BrokerAdapter` unreachable; the five operations never called | T-21, T-22, enforced by test. |
| `atlas.risk` may import `atlas.config`, under an allowlist the implementing task enumerates | D-7: exactly `("get_settings",)`. |
| The limit is not a parameter | T-1, T-10. |
| "Absence is not permission"; mechanism left to this task | D-6.1–D-6.4, derived from B-13/B-14/B-15/B-16 and recorded. |
| Sixth edge accepted | §11.1. |
| The ADR itself | Delivered under version control unmodified (F-16), blob `497ab06f…`. |

**On committing the ADR.** ADR-0012 is the authoritative decision record for this
task, and at the baseline the repository refers to a decision record that Git
does not contain. Bringing it under version control is a repository-integrity
action with no architectural content: not one byte changes, and the blob SHA in
§9.1 is what makes that checkable rather than merely asserted. It is worth being
precise about the two things being kept apart — the ADR's *content* is immutable
(§9), and the ADR's *absence from Git* is a defect this task fixes.

**One conformance note the implementer must not paper over.** ADR-0012:24-30
anticipated that an exposure control "needs the open positions, the contract size
that turns a volume into a notional, and an account value". Under the owner's
D-1 and D-2 the selected metric needs **only `Account`** — not `Position`, not
`Symbol`. This task is therefore a *narrowing* of what ADR-0012 anticipated, not
a departure from it: the ADR established that the port already reports
everything such a control could need, and this control needs less than the
maximum. The narrowing must be stated in the implementation report. It does not
amend ADR-0012 and must not be presented as doing so.

---

## 17. Pre-existing debt: ADR-0012 is missing from the ADR index

**Recorded here, deliberately not fixed by this task** (owner decision L-8).

* **What.** `docs/adr/README.md` indexes ADR-0001 through ADR-0011. ADR-0012 is
  accepted, present on disk, and absent from the index (B-24).
* **When it was created.** When ADR-0012 was written, before this specification
  existed. It is not caused by TASK-0017.
* **Why it is not fixed here.** L-8 requires it be "recorded separately rather
  than silently folded into TASK-0017". Folding it in would put an unrelated
  correction inside a change whose diff is meant to be reviewable against §8.
* **Status after this task.** Still open, and **more visible than before**.
  `docs/adr/README.md` is in the forbidden list (§9) and AC-18 requires the
  omission to still be present. Once ADR-0012 is tracked (F-16) the repository
  contains a committed ADR that its own committed index does not list — which is
  a cleaner, more findable defect than an untracked file nobody can see, but a
  defect all the same.
* **Scope of a future fix.** One row in one table. It needs no ADR of its own and
  no code change.

---

## Roadmap

`docs/ROADMAP.md` is out of scope for implementation (non-goal 14) and is
updated only in a separate post-merge closeout, per the ATLAS-TASK-0016
precedent. That closeout is where the collected-test count, the six-edge figure
and the "first risk control" milestone are recorded historically. Nothing in
this task may write to it.
