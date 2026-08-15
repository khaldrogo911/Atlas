# ATLAS-TASK-0025 — Living-document correction after broker adapter construction

**Status:** Authorised, specified, not implemented.

Authorised by owner decision: **Decision 1 = A** (this task is the next numbered
task and is a living-document correction; no ADR-0016 is created) and
**Decision 2 = B** (the broader scope — the two ATLAS-TASK-0023 §21.3 passages,
plus the living-document reflection of the ATLAS-TASK-0022 carry-forward).

No branch, commit, pull request or CI run exists for this task, and none is
cited anywhere in this document.

---

## 1. Baseline

`main`, clean working tree, no divergence from `origin/main`.

| | |
|---|---|
| `HEAD` = `origin/main` | `5a9e8d614dcf2c55d3548d162f122a1cc0259061` |
| `git status --porcelain --untracked-files=all` | empty |
| Roadmap's last Complete row | `ATLAS-TASK-0024`, citing `2c4e7e8bdbf2839b11fe25e38b7b0d9bbd8c4732` |
| Highest accepted ADR | ADR-0015, `8db18fcd` accepted, `a83f998` indexed |
| Full suite | 3699 passed |
| Contract suite | 217 passed |
| `tests/unit/risk/test_risk_boundary.py` | 100 passed |

Blobs at the baseline:

| Path | Blob |
|---|---|
| `docs/architecture/overview.md` | `6dd52fe4244dc84b61f723d9d00384b960163295` |
| `tests/unit/risk/test_risk_boundary.py` | `77e8fc0ae48c87e4437d863798dbac9e6951d076` |
| `docs/ROADMAP.md` | `59a250b91cc51498d97c169a3b5ecf51ca51d98a` |

The implementer must confirm all of it before making any change (§12.1).

### 1.1 Why ATLAS-TASK-0025 is the correct identifier

The number is derived from the repository, not chosen.

- **The sequence is dense and unbroken through 0024.** `docs/ROADMAP.md`'s
  status table holds 25 rows running `ATLAS-TASK-0001`, `0001A`, then `0002`
  through `0024` with no gap. `0024` is the highest identifier the repository
  has ever issued.
- **0025 is unissued.** A repository-wide search for `ATLAS-TASK-0025` returns
  one hit, `docs/ROADMAP.md:136`, and it is a *denial*: "this file declares no
  ATLAS-TASK-0025, no ADR-0016 and no work after them."
- **A denial is not a prohibition.** It records that no such task had been
  declared when it was written. ATLAS-TASK-0019 and ATLAS-TASK-0021 were both
  numbered against the identical sentence, and `docs/ROADMAP.md:139-142` records
  the mechanism: "ATLAS-TASK-0021 is the correction the ATLAS-TASK-0020 entry
  below calls for and declines to number … is answered by the row above." The
  sentence is replaced at closeout, by the step that writes the row — not by
  this task (§7).
- **`0024A` would be the wrong form.** `0001A` is the only suffixed identifier
  and `docs/ROADMAP.md:15` shows what it is for: a follow-up folded into an
  already-numbered task. ATLAS-TASK-0024 is complete, merged and CI-green
  (run 44, and run 45 over its closeout). This is not a review fix to it.
- **A missing spec file is not a missing number.** `docs/tasks/` holds
  `0014-0017`, `0019-0023` and neither `0018` nor `0024`. Both have roadmap rows
  without specification files. The numbering authority is the roadmap table, not
  the directory listing.

**Nothing in this section issues the number.** It identifies the number that is
correct given the authorisation in the status block above.

### 1.2 Why this task has a specification file

ATLAS-TASK-0018 and ATLAS-TASK-0024 have rows and no specification. Every
living-document correction the repository has run — ATLAS-TASK-0015, 0016, 0019
and 0021 — has one. `docs/tasks/ATLAS-TASK-0022.md:13.3` defers the correction
in §3 P-4 "to the living-document correction that follows this task, in the
manner of ATLAS-TASK-0015, 0016, 0019 and 0021", and
`docs/tasks/ATLAS-TASK-0023.md` §21.3 defers the corrections in §3 P-1 and P-2
"to a follow-up documentation task, per the precedent of ATLAS-TASK-0015, 0016,
0019 and 0021". All four named precedents carry a specification. This task
touches two files across four defects, which is wider than either task that
went without one.

---

## 2. Purpose

Three statements in `docs/architecture/overview.md` and one comment in
`tests/unit/risk/test_risk_boundary.py` are false or incomplete at the baseline
because of work the repository has already completed and accepted. This task
makes them true.

It decides nothing. Every truth it asserts is already true of the code at the
baseline, and §13 exists to stop any wording that would make that untrue.

---

## 3. Problem statement

Four defects. Line numbers are given for location only and are correct at the
baseline blobs in §1; **the implementer must match on text**, because the
numbers shift as edits are applied.

| # | Location | Defect | Authorised by |
|---|---|---|---|
| **P-1** | `docs/architecture/overview.md:118-123` | States that "although `apps/atlas-core` owns the `BrokerAdapter`, no adapter is constructed outside that suite for it to hold". False since `6f5eff81`. | Decision 2B item 1; TASK-0023 §21.3 |
| **P-2** | `docs/architecture/overview.md:191-193` | Describes the entrypoint as resolving configuration, enforcing invariants, emitting a startup record and exiting. Incomplete since `6f5eff81`: it also constructs the broker adapter and owner, before the record is written, and exits `2` when the broker section cannot be translated. | Decision 2B item 1; TASK-0023 §21.3 |
| **P-3** | `docs/architecture/overview.md:3` | Banner reads `> **Status at ATLAS-TASK-0020.**` The roadmap's last Complete row is `ATLAS-TASK-0024`. The document is four rows behind. | Repository precedent — see **D-1** |
| **P-4** | `tests/unit/risk/test_risk_boundary.py:154` | The `#:` comment derives `CREDENTIAL_SYMBOLS` from "the two sections that lead anywhere credential-bearing". There are now three: `postgres`, `redis` and `broker`. | Decision 2B item 2; TASK-0022 §13.3 |

### 3.1 The evidence for P-1 and P-2

`apps/atlas-core/src/atlas/apps/core/composition.py` defines
`build_broker_owner(settings)`, which translates `settings.broker` into an
`MT5Config`, raises `ConfigurationError` on a Pydantic validation failure, and
returns `BrokerOwner(MT5BrokerAdapter(config))`.

`apps/atlas-core/src/atlas/apps/core/__main__.py:70-82` calls it inside the
`try` block, before `build_startup_record` is serialised to stdout, and its
docstring at `:65-68` states the ordering and the reason. The call's result is
not retained; the comment at `:72-74` states why.

CI run 44 exercises both paths in a container: "Run the image configuration
self-check" (exit 0, eight-key record) and "Run the image self-check without
broker configuration" (exit 2, `atlas.core.startup_failed` on stderr).

### 3.2 Passages that are **not** defects

Each of these matches the search patterns this task works from, or looks stale
at a glance, and each is correct at the baseline. **None may be changed.**

- **`:61-64`** — "Six edges between feature packages exist in the graph today".
  Still six. `apps/atlas-core → atlas.broker.mt5`, added by ATLAS-TASK-0023, is
  an application-to-package edge, on the classification
  `docs/tasks/ATLAS-TASK-0015.md:341` and `docs/tasks/ATLAS-TASK-0016.md:457`
  both give and `docs/tasks/ATLAS-TASK-0019.md:346-350` applied. **This task
  neither changes that classification nor adds the new edge to the six.**
- **`:111-112`** — "Nothing here obtains, constructs or invokes a
  `BrokerAdapter`". "Here" is `atlas.execution`. Still true; the construction
  P-1 records is in `apps/`, not in the package.
- **`:118-119`** — "Nothing outside the test suite produces a `TradeIntent` or
  hands one to `atlas.risk`". Still true.
- **`:121-122`** — "so the request `atlas.execution` builds is, today, received
  by nothing". Still true: the owner is dropped, nothing is started, and no
  layer consumes an `OrderRequest`.
- **`:130`, `:132`, `:138-139`, `:187`** — the responsibilities and processes
  tables. ATLAS-TASK-0015 and ATLAS-TASK-0017 both ruled that these state
  charters, not implementation status. `atlas-core` "Owns the event loop and
  runs the trading pipeline" is a charter and stays.
- **`:158-165`** — "what is still absent is anything that drives a strategy,
  reaches a verdict and calls the translation in sequence". Still true.
- **`:3-18` beyond the status marker** — "Three packages hold implementation".
  ATLAS-TASK-0023 added code to an application, not to a package. The count and
  the enumeration stand; only the date moves (D-1).
- **`:201-205`, the Configuration section** — five lines, enumerating no
  sections and stating no count. See **D-4**.
- **`packages/broker/src/atlas/broker/mt5/README.md:90`** — "Composition imports
  `atlas.broker.mt5` explicitly". This became *true* with ATLAS-TASK-0023.
- **`docs/operations/README.md:20-29`** — the production invariants. Still
  exactly three, and unchanged by ATLAS-TASK-0022, 0023 and 0024. A broker
  section that cannot be translated is a composition failure, not an
  `AtlasSettings` production invariant, and the §21.2 gap that would make it one
  is deliberately open (§6.1).

---

## 4. Authoritative decisions

Four questions the implementer would otherwise have to answer are answered
here. All four are resolved from repository evidence; none invents policy.

### D-1 — The status banner is re-dated to ATLAS-TASK-0024, and it is in scope

*The decision.* `docs/architecture/overview.md:3` becomes
`> **Status at ATLAS-TASK-0024.**`, and nothing else in the banner block
`:4-22` changes.

*Why it is in scope, given that Decision 2B named two overview passages.* The
banner is not a third defect discovered here; it is the fixed second half of
this task type. `docs/tasks/ATLAS-TASK-0015.md` **D-1** established that the
banner must carry a task date, and that the date names the roadmap's last row —
"the comparison the banner exists to serve". Every living-document correction
since has re-dated it: `394df7d` (ATLAS-TASK-0019) moved it `0014 → 0018` and
its commit subject is literally "correct the overview banner"; `d7a68cb`
(ATLAS-TASK-0021) moved it `0018 → 0020` in the same two-hunk diff that
corrected the passage P-1 now supersedes. ATLAS-TASK-0021 §5 states the shape:
"Exactly two corrections, in one file: P-1 … and the stale status banner at
`:3`."

*Why omitting it would be a defect, not restraint.* `394df7d`'s message records
what happens when it is skipped: ATLAS-TASK-0017 "corrected three passages of
the architecture overview and was explicit that it corrected no others; the
status banner was not among them and is not recorded anywhere as a deferral",
leaving the banner denying the existence of the repository's only risk control.
Skipping it here reproduces that exact failure, and leaves a document dated to
ATLAS-TASK-0020 while its body describes ATLAS-TASK-0023's construction.

*The bound.* Only the four characters of the task number move. The banner's
form, its package enumeration, its "Three packages hold implementation" count
and its closing roadmap-authority paragraph at `:20-22` are untouched.

### D-2 — The `At ATLAS-TASK-0001` marker at `:191` stays, attached to "has no run loop"

*The decision.* The corrected P-2 passage keeps a dated marker pinning
`atlas-core`'s lack of a run loop to ATLAS-TASK-0001. The implementer **must
not** re-date it to 0023 or 0024 and **must not** delete it. The description of
what the entrypoint does may be separated from it — a sentence split is
permitted — so that present-tense behaviour is not scoped by a 0001 date.

*Evidence.* `docs/tasks/ATLAS-TASK-0015.md` D-1 cites this exact sentence — "At
ATLAS-TASK-0001, `atlas-core` has no run loop" — in its list of dated markers
that are "still correct, because each pins a fact that has not moved". The fact
still has not moved: `__main__.py` contains `main()`, no loop, no scheduler and
no supervisor. Re-dating a marker whose fact has not moved would falsify the
convention D-1 established; deleting it would remove the only pin in the
document that says the run loop is absent by status rather than by design.

*What has moved* is the clause list after it, and that is what P-2 corrects.

### D-3 — `"broker"` is **not** added to `CREDENTIAL_SYMBOLS`, and the corrected comment must not imply that it should be

*The decision.* The tuple at `:160-168` — its contents, its order and its
behaviour — is unchanged. The comment is corrected to describe the tuple that
exists, not to restate a derivation rule the tuple does not implement.

*Why the apparent contradiction is not one.* Read naively, "there are now three
credential-bearing sections" plus a tuple naming two of them reads like an
incomplete denylist. It is not, and `docs/tasks/ATLAS-TASK-0022.md` §13.3
already did the mechanical analysis, which this specification re-verified
against the current file:

- `_credential_references` is `_referenced_names(source) & set(CREDENTIAL_SYMBOLS)`
  (`:282`).
- Reaching the broker credential requires writing
  `get_settings().broker.password`, whose attribute names include `password` —
  already in the tuple at `:163`. **The credential is already covered.**
- Adding `"broker"` would be a broadening, and a harmful one:
  `_referenced_names` adds `node.name.rsplit(".", 1)[-1]` for every `ast.alias`
  (`:267-268`), so any module writing `import atlas.broker` registers the name
  `broker`. `atlas.risk` is permitted to import `atlas.broker` (`:66`,
  `overview.md:72-81`) and does. The entry would fail modules that touch no
  credential at all.
- `PERMITTED_CONFIG_ACCESS` (`:174`) is unchanged. Risk still reaches exactly
  `get_settings().risk.max_margin_utilisation`.

ATLAS-TASK-0022 §13.3 states the conclusion this task inherits: the sentence
"describes the derivation of a tuple that is still correct."

*What this means for the wording.* The corrected comment must convey the third
section **and** why the tuple names two — otherwise it replaces one false
sentence with a different one (§10, T-8 through T-11).

### D-4 — There is no living-document counterpart to ADR-0011 `:99-103`, and none is created

*The decision.* **No third file is edited for the broker/venue carry-forward.**
Decision 2B item 2's "stale broker/venue statement" is corrected in this task
only insofar as `overview.md` is corrected for P-1 and P-2; there is no separate
living-document sentence to fix, and this specification does not invent one.

*Evidence.* Every markdown file in the repository outside `docs/adr/` and
`docs/tasks/` was searched at the baseline — 22 files: `README.md`,
`config/README.md`, `docs/ROADMAP.md`, `docs/api/README.md`,
`docs/architecture/overview.md`, `docs/operations/README.md`,
`docs/runbooks/README.md`, `docs/runbooks/local-stack.md`, four under
`infrastructure/`, seven package READMEs, `scripts/README.md`,
`tests/e2e/README.md`, `tests/integration/README.md`.

- `AtlasSettings` appears in a living document exactly twice:
  `config/README.md:22`, in the precedence list, naming no section; and
  `docs/operations/README.md:22`, listing three production invariants that
  remain accurate (§3.2).
- No living document states, implies or enumerates that the settings model has
  no broker or venue surface. The four "no venue" hits — `overview.md:55`,
  `packages/broker/.../README.md:8`, `packages/broker/.../models/README.md:183`,
  `packages/strategy/.../README.md:152` — are about `atlas.common.retry`, the
  port package, the broker models and a stub strategy respectively. None is
  about configuration.
- The only stale broker/venue statement is **ADR-0011 `:99-103`**, which is
  immutable (§9).

*This closes the D5 question from discovery.* `docs/ROADMAP.md:1430` records
that "`docs/architecture/overview.md` describes five configuration sections
where there are six". `AtlasSettings` does hold six (`settings.py:274-279`:
`logging`, `postgres`, `redis`, `duckdb`, `risk`, `broker`), but
`overview.md`'s Configuration section enumerates none and states no count — the
prediction at `docs/tasks/ATLAS-TASK-0022.md:778-779` did not come true because
the file never carried the enumeration. **There is nothing there to correct.**
The document that names four is ADR-0011, which is the same immutable statement,
not a second one. The implementer must not add an enumeration to `:201-205` in
order to have something to fix.

---

## 5. Scope

**Four corrections across two files.**

| File | Corrections | Hunks |
|---|---|---|
| `docs/architecture/overview.md` | P-3 (`:3`), P-1 (`:118-123`), P-2 (`:191-193`) | 3 |
| `tests/unit/risk/test_risk_boundary.py` | P-4 (the `#:` comment at `:146-159`) | 1 |

Nothing else in either file changes, and no other file changes.

---

## 6. Architectural boundary

**ATLAS-TASK-0025 decides nothing.** It is a truthfulness correction to living
documentation plus one stale test comment.

### 6.1 What this task does not decide

Every item below remains an open architectural question requiring an owner
decision gate and a new ADR, in the sequence `docs/tasks/ATLAS-TASK-0021.md`
§17 `:652-654` states: "it begins with an owner decision gate and a new ADR …
not with a documentation pass". None may be decided, prepared for, prefigured or
described as settled anywhere in this task's diff.

- Broker credential validation; rejecting an empty `password`; rejecting a bare
  `terminal_path`. The ATLAS-TASK-0023 §21.2 gap stays open. ADR-0015 `:412-413`
  reserves it: "No new field, no new invariant, no new environment variable."
- `BrokerOwner` lifecycle; `BrokerOwner.start()`; when a session is opened.
- A run loop, a pipeline, an engine, a scheduler.
- Supervision; the `health()` timer; the threading model.
- Reconnect policy; failover.
- Multiple adapters, multiple venues, multiple accounts.
- Whether `apps/dashboard` or `apps/research` may hold or invoke a
  `BrokerAdapter`.
- Reopening ADR-0012 now that a composition root exists.
- The general `apps/` import rule.
- A DI framework, service locator, registry or factory abstraction.
- Any new configuration field, section, environment variable or invariant.
- Order identity, idempotency, routing, fills, reconciliation; account or
  portfolio state ownership.
- External configuration or secrets services.
- Startup-record expansion. The record keeps its eight keys.

### 6.2 Further non-goals

This task also does not:

1. Create an ADR, or edit one. **No ADR-0016.** See §9.
2. Change `docs/ROADMAP.md`, including its "Known documentation debt" section.
   See §7.
3. Change any source file.
4. Change any test's behaviour, assertion, tuple, constant, import or name.
5. Add a test, including a documentation-currency test. See §11.
6. Add, remove or reword any row of the package responsibilities table or the
   processes table.
7. Restate, summarise or relocate ADR-0013's or ADR-0015's reasoning into the
   overview. The overview may state the fact; the ADR keeps the reasoning.
8. Rewrite any passage for style, length or tone.
9. Correct, footnote or annotate any historical record — `docs/ROADMAP.md`'s
   completed entries, or any `docs/tasks/ATLAS-TASK-00NN.md`. They are dated
   accounts, not live claims.
10. Add an enumeration of configuration sections anywhere. See **D-4**.

---

## 7. Relationship to `docs/ROADMAP.md`

**`docs/ROADMAP.md` is not modified by this task, and was not modified by this
specification.**

The row for ATLAS-TASK-0025, and the replacement of the sentence at `:131-137`
which currently reads "this file declares no ATLAS-TASK-0025, no ADR-0016 and no
work after them", are a post-merge closeout step performed under separate
authorisation — exactly as for ATLAS-TASK-0011 through ATLAS-TASK-0024. A
specification is not a completed task and has no row.

Two open entries end with the phrase this task's closeout will answer:
`docs/ROADMAP.md:1434` (from ATLAS-TASK-0022) and `:1543` (from
ATLAS-TASK-0023), both reading "this file names no number for it". Both are left
exactly as written, as ATLAS-TASK-0019's, 0020's and 0021's were
(`docs/ROADMAP.md:139-151`).

---

## 8. Files permitted to change

During implementation, exactly this:

| Path | Change |
|---|---|
| `docs/architecture/overview.md` | P-3 at `:3`; P-1 at `:118-123`; P-2 at `:191-193` |
| `tests/unit/risk/test_risk_boundary.py` | P-4: the `#:` comment block at `:146-159` only |

Plus this specification file, `docs/tasks/ATLAS-TASK-0025.md`, which is not
modified by the implementation.

**The implementation diff is two files.**

---

## 9. Files explicitly forbidden to change

Any diff touching these fails the task.

**Immutable decision records.** Every file under `docs/adr/`. Each carries these
blobs at the baseline and must be unchanged afterwards:

| File | Blob |
|---|---|
| `0001-record-architecture-decisions.md` | `7a20f3dcc5f95f8f88d48546659e07820fe3a67e` |
| `0002-monorepo-with-namespace-packages.md` | `d42861223bb6b157afa3e35d60bb727093aa9c93` |
| `0003-layered-configuration.md` | `a2c84e89de5750aff839b78cdc6c43686c615ad1` |
| `0004-strict-typing-and-linting.md` | `93aba8900929fc10f8e93d6c9616fa5c40fc8a91` |
| `0005-polyglot-persistence.md` | `cfb27f81dab25f51f20fd97bb9cb15a5c6c040ea` |
| `0006-mock-adapter-simulates-bookkeeping-not-price.md` | `6cb97b3354ee953075ef37711f86a1ccad89f572` |
| `0007-two-locks-in-the-base-adapter.md` | `340bf9aad3e2013a8495ea70632ee8b883af5536` |
| `0008-time-is-injected.md` | `1c665b82528c16f25d5ac256583c90aec3492466` |
| `0009-retry-is-a-value-and-the-waiting-is-the-clocks.md` | `7479f50b50f5ac46e01cd47e9dc1e580d1e3785a` |
| `0010-the-risk-boundary-is-a-verdict-on-an-intent.md` | `6f20807a73496c087a252145696dea4a3330d55b` |
| `0011-execution-builds-the-request-another-layer-owns-the-port.md` | `45600504bd9212db0a5efcf1eb4d85ebfc1595ed` |
| `0012-risk-is-handed-its-state-and-reads-its-own-limits.md` | `497ab06f8bfb5aad3b5344fd27319c34d3dd6537` |
| `0013-the-application-owns-the-adapter.md` | `5bc9bcf27008f7f96cd50479ec0715e306a5c2b5` |
| `0014-broker-settings-are-restated-not-imported.md` | `8031f149af5f4a9906c8468e36d568e5f36afc0f` |
| `0015-broker-adapter-selection.md` | `fb265e99291545e5b266cc03a97274e00f1be859` |
| `README.md` | `6afae1e115fb88247dae3a6b4a6be510dd216b6e` |

**ADR-0011 in particular.** Its statement at `:99-103` — "`AtlasSettings` holds
`logging`, `postgres`, `redis` and `duckdb`, and there is no broker or venue
surface anywhere in it" — became inaccurate when ATLAS-TASK-0022 merged.
ADR-0013 `:280-283` pre-recorded the handling: the correction "belongs in the
roadmap and the living documents, never in ADR-0011 itself." Per **D-4**, no
living document carries a counterpart, so this task corrects the overview for
P-1 and P-2, corrects nothing for ADR-0011, and leaves ADR-0011 alone.

**ADR-0015 in particular.** Its closing sentence at `:522-524` — "Nothing in
this record is implemented. No adapter is constructed, no translation exists, no
boundary test changes, and `apps/atlas-core`'s entrypoint still resolves
configuration, emits a startup record and exits" — was true of the record and is
false of the repository. It is immutable and stays. This task must not edit it,
footnote it, or state anywhere that it has been corrected, superseded or
amended.

**`docs/ROADMAP.md`.** Blob `59a250b91cc51498d97c169a3b5ecf51ca51d98a`. See §7.

**Historical task records.** `docs/tasks/ATLAS-TASK-0014.md` through
`ATLAS-TASK-0023.md`. Each is a dated account, and several quote the exact
sentences this task corrects — `ATLAS-TASK-0023.md` §21.3 quotes both P-1 and
P-2 verbatim, and `ATLAS-TASK-0022.md` §13.3 quotes P-4. They are the files most
likely to be swept up by a repository-wide search-and-replace. **They must not
change.**

**Every source file.** In particular
`apps/atlas-core/src/atlas/apps/core/composition.py` and
`apps/atlas-core/src/atlas/apps/core/__main__.py`, which are the evidence P-1
and P-2 rest on, and `packages/config/src/atlas/config/settings.py`, which is
the evidence for D-3 and D-4.

**Every test file except `tests/unit/risk/test_risk_boundary.py`**, and within
that file every line outside the `#:` comment block at `:146-159`. See §11.

**Everything else outside §8**, in particular every file under `packages/`,
`apps/`, `.github/`, `config/`, `infrastructure/`, `scripts/`, plus
`pyproject.toml`, `poetry.lock`, `docker-compose.yml`, `.env.example` and every
`Dockerfile`.

**Every passage of `docs/architecture/overview.md` outside `:3`, `:118-123` and
`:191-193`** — including the rest of the banner block at `:4-22`, and everything
named in §3.2.

---

## 10. Exact documentation truths that must hold after implementation

Each truth must be discoverable from the corrected text. **The wording is the
implementer's; the fact is not.**

**About P-1:**

- **T-1.** The document no longer states that no adapter is constructed outside
  the test suite.
- **T-2.** It states that `apps/atlas-core` constructs a broker adapter at
  startup, and it may name ADR-0015 as the decision — by the same form
  ATLAS-TASK-0021 used when it added the ADR-0013 link to this passage. It must
  not make `MT5BrokerAdapter`, `MT5Config`, `BrokerOwner` or `composition.py`
  the document's subject: the overview has no precedent for naming an
  application's internal module or class, and ADR-0006's property — business
  logic cannot discover which adapter it holds — is a reason to keep the venue
  out of the architecture overview's prose.
- **T-3.** It preserves, in substance, that nothing outside the test suite
  produces a `TradeIntent` or hands one to `atlas.risk`, and that the
  `OrderRequest` `atlas.execution` builds is still received by nothing.
- **T-4.** The reader's conclusion is unchanged: **the chain is still not joined
  end to end.** Construction is not wiring.

**About P-2:**

- **T-5.** The document states that the entrypoint constructs the broker adapter
  the settings describe, in addition to resolving configuration, enforcing the
  environment's invariants, emitting the JSON startup record and exiting.
- **T-6.** It states or preserves that the process exits non-zero — `2` — when
  configuration is invalid, including a broker section that cannot be
  translated. It may state that the adapter is built before the record is
  written; it must not state the reverse.
- **T-7.** It preserves the `restart: "no"` explanation. A successful run still
  exits `0`, and that is still why compose does not restart it.

**About P-4:**

- **T-8.** The comment no longer says there are two sections that lead anywhere
  credential-bearing.
- **T-9.** It states that there are three — `postgres`, `redis` and `broker`.
- **T-10.** It states that `CREDENTIAL_SYMBOLS` names two of the three, and why
  `broker` is absent: `_referenced_names` registers the last segment of an
  `ast.alias`, so the entry would fire on `import atlas.broker`, which
  `atlas.risk` is permitted to write and does.
- **T-11.** It states that the broker credential is covered regardless, because
  reaching it requires `password`, `get_secret_value` or `SecretStr`, all of
  which the tuple already names.
- **T-12.** The rest of the comment — the escape-path reasoning, the
  attribute-level rationale, and the `safe_dsn` / `safe_url` note — survives in
  substance.

**About P-3:**

- **T-13.** The banner names `ATLAS-TASK-0024`, which is the roadmap's last
  Complete row at the baseline and must be re-verified as such (§12.4).
- **T-14.** The banner's package enumeration, its "Three packages hold
  implementation" count and its closing roadmap-authority paragraph are
  unchanged.

**About all four:**

- **T-15.** Nothing in the diff claims that a composition root as an
  architectural mechanism, an engine, a run loop, a scheduler, a pipeline, a
  registry, a factory or a service container exists. None does. "The application
  constructs an adapter at startup" is a fact; "Atlas has a composition root" is
  a mechanism, and no record defines one.
- **T-16.** Nothing in the diff claims that any adapter is *started*, that any
  session is opened, that anything is supervised, retried, health-checked or
  reconnected, or that the constructed owner is retained.
- **T-17.** Nothing in the diff decides, prepares for or presumes an answer to
  anything in §6.1.
- **T-18.** Nothing in the diff states or implies that any ADR has been
  corrected, superseded, amended or footnoted. None has.
- **T-19.** Every passage listed in §3.2 survives byte-for-byte.
- **T-20.** The diff names no task identifier and no ADR identifier that does
  not already exist — in particular, no `ATLAS-TASK-0025` inside
  `overview.md`, and no `ADR-0016` anywhere.

---

## 11. Test requirements

**No test is added, removed or modified.**

`tests/unit/risk/test_risk_boundary.py` is edited, but only its `#:` comment
block. `#:` comments are documentation for the constant beneath them and carry
no runtime behaviour. After the edit:

- `CREDENTIAL_SYMBOLS` at `:160-168` is byte-identical.
- `PERMITTED_CONFIG_NAMES`, `WHOLE_MODULE` and `PERMITTED_CONFIG_ACCESS` are
  byte-identical.
- Every function, class, assertion and import in the file is byte-identical.
- The file passes 100 tests before and 100 after.

**No test verifies either correction, and none is written to make one.** No test
opens, parses or asserts on `docs/architecture/overview.md` — checked across
`tests/` at the baseline; `tests/contract/test_repository_structure.py:53`
asserts that the `docs/architecture` *directory* exists and reads nothing from
it, and the only content-reading tests
(`tests/unit/broker/test_adapter_contract.py:415`,
`tests/unit/broker/test_model_invariants.py:239`) read package READMEs. No test
asserts on the text of the `#:` comment.

**Why the suite is still the right regression check.** It cannot tell a correct
comment from an incorrect one — but that is not what it is being asked. The
comment is inert, so the suite's entire value here is *negative*: it proves the
edit did not escape the comment. If the tuple, the scanner, an assertion or an
import moved by so much as a character, `test_risk_boundary.py` and the contract
suite are exactly the instruments that catch it. A count other than 3699 / 217 /
100, or any failure at all, means the diff is not what §8 permits. Acceptance
for the *content* of all four corrections rests on the mechanical checks in §12
and the truths in §10, not on a green suite.

---

## 12. Validation requirements

1. **Before any edit**, confirm: branch `main`; `HEAD` and `origin/main` both
   `5a9e8d614dcf2c55d3548d162f122a1cc0259061`;
   `git status --porcelain --untracked-files=all` empty; and both target blobs
   match §1.
2. **Re-verify P-1 and P-2 against the code, not against this document.**
   `composition.py` defines `build_broker_owner`, translates `settings.broker`
   into an `MT5Config`, raises `ConfigurationError` on validation failure and
   returns a `BrokerOwner`; `__main__.py` calls it inside the `try` block before
   writing the startup record, and returns `2` on `ConfigurationError`. If any
   of that has changed, §14.1 applies.
3. **Re-verify that the owner is still dropped.** `__main__.py` does not retain
   the return value of `build_broker_owner`, and no module outside the test
   suite calls `BrokerOwner.start`. If something does, T-4 and T-16 are wrong
   and the scope of this task is wrong — report it rather than widening the
   correction.
4. **Re-verify the banner target.** The roadmap's last Complete row is
   `ATLAS-TASK-0024`. If a later row exists, §14.2 applies.
5. **Re-verify D-3 against the file.** `_referenced_names` still adds
   `node.name.rsplit(".", 1)[-1]` for `ast.alias`, and `"password"` is still in
   `CREDENTIAL_SYMBOLS`. If either has changed, the reason `broker` is absent
   has changed with it, and §14.6 applies.
6. **After the edit**, `git diff --stat` reports exactly two files. `git diff`
   shows three hunks in `overview.md`, confined to `:3`, `:118-123` and
   `:191-193`, and one hunk in `test_risk_boundary.py` confined to the `#:`
   block.
7. **Prove the test edit is comment-only.** Every added and removed line in the
   `test_risk_boundary.py` hunk begins with `#:` after its indentation. No line
   of code appears on either side of the diff.
8. **Confirm the ADRs are untouched**: every blob in §9 unchanged. Confirm
   `docs/ROADMAP.md`'s blob is unchanged.
9. Run the full suite. Expect **3699 passed**.
10. Run `pytest tests/contract -q`. Expect **217 passed**.
11. Run `pytest tests/unit/risk/test_risk_boundary.py -q`. Expect **100
    passed**.
12. Run `ruff check .`, `black --check .` and `mypy .`. **These are required
    here and were not required by ATLAS-TASK-0021**, because that task's diff
    touched no Python and this one does. Precedent for a Python-touching task is
    ATLAS-TASK-0022 and ATLAS-TASK-0023, both of which ran all three.
13. Run `pre-commit run --all-files`. Expect green. Its `trailing-whitespace`,
    `end-of-file-fixer` and `mixed-line-ending` hooks are the ones most likely
    to react to a hand-edited comment block.
14. **Confirm the comment block still wraps to the width of its neighbours.**
    The surrounding `#:` blocks wrap at 72-80 columns; `line-length` is 100 for
    Ruff and Black, so neither tool will enforce the narrower width. A block
    that wraps at 100 passes every check in step 12 and is still wrong.
15. **Read both corrected overview passages end to end in context** —
    `:106-123` for P-1, `:183-193` for P-2 — and confirm T-1 through T-20. This
    is the only check that can catch a correction that is true in isolation and
    false in context, specifically one that contradicts `:111-112` or `:121-122`.
16. **Confirm no new task number and no ADR number appears anywhere in the
    diff** (T-20).

---

## 13. Acceptance criteria

Owner-supplied criteria first, in the owner's numbering, then the additions
repository precedent requires.

- **AC-1.** The false broker-adapter-construction statement in
  `docs/architecture/overview.md` is corrected to reflect the current
  implementation without inventing lifecycle semantics. (P-1; T-1, T-2, T-15,
  T-16.)
- **AC-2.** The incomplete `atlas-core` entrypoint description in
  `docs/architecture/overview.md` is corrected to reflect the current startup
  path. (P-2; T-5, T-6, T-7.)
- **AC-3.** No immutable ADR is modified. Every blob in §9 is unchanged. (T-18.)
- **AC-4.** The stale broker/venue living-document statement is corrected **if
  and only if** an actual living-document counterpart exists. Per **D-4**, none
  does: no third file is edited, and no enumeration is created in order to
  create one. ADR-0011 itself remains untouched.
- **AC-5.** The "two sections" comment in
  `tests/unit/risk/test_risk_boundary.py` is corrected to describe the actual
  three sections. (P-4; T-8, T-9.)
- **AC-6.** The risk-boundary test's behaviour, assertions, tuple contents and
  semantics are unchanged. `CREDENTIAL_SYMBOLS` is byte-identical, and every
  diff line in that file is a `#:` comment line. (§12.7.)
- **AC-7.** No new architectural decision is introduced. (T-17; §6.1.)
- **AC-8.** No new configuration field, invariant, lifecycle behaviour or
  ownership rule is introduced. (T-15, T-16, T-17.)
- **AC-9.** All existing tests pass: 3699.
- **AC-10.** The contract suite passes: 217.
- **AC-11.** The diff is limited to the surface §8 permits — two files, four
  hunks — and every passage in §3.2 survives byte-for-byte. (T-19.)
- **AC-12.** No generated file, CI configuration, compose configuration,
  `Dockerfile`, `pyproject.toml`, script or unrelated documentation is modified.

Required additionally by repository precedent:

- **AC-13.** The status banner at `:3` names `ATLAS-TASK-0024`, the roadmap's
  last Complete row, per **D-1**. The change is confined to the task number:
  `:4-22` is unchanged, including the package enumeration and the
  roadmap-authority paragraph. (T-13, T-14.)
- **AC-14.** The `At ATLAS-TASK-0001` marker survives, attached to
  `atlas-core`'s lack of a run loop, per **D-2**. It is neither re-dated nor
  deleted.
- **AC-15.** The corrected comment explains why `broker` is not in
  `CREDENTIAL_SYMBOLS` and that the broker credential is covered anyway, per
  **D-3**. A comment that says "three sections" beside a tuple naming two, with
  no explanation, fails this criterion. (T-10, T-11.)
- **AC-16.** `docs/ROADMAP.md` is unchanged, including its "Known documentation
  debt" section. (§7.)
- **AC-17.** Ruff, Black, MyPy and `pre-commit run --all-files` are green, and
  the corrected comment block wraps to the width of its neighbours. (§12.12-14.)
- **AC-18.** The diff introduces no task identifier and no ADR identifier.
  (T-20.)

---

## 14. Stop conditions

Stop and report rather than deciding, if:

1. `composition.py` is absent, does not construct an adapter, or `__main__.py`
   no longer calls it — the repository has moved from the baseline and the
   premise of P-1 and P-2 has changed.
2. An ADR-0016 or later exists, or a task after ATLAS-TASK-0024 exists. Either
   may already have corrected a passage or changed what is true.
3. A correction appears to require editing an ADR. It does not; see §9.
4. A correction appears to require a source change. It does not; every truth in
   §10 is already true of the code at the baseline. If a document cannot be made
   true without changing code, the document is describing something
   ATLAS-TASK-0023 did not deliver — a finding to report, not to fix.
5. Any count is other than 3699 / 217 / 100, or any check in §12 fails.
6. The evidence for **D-3** no longer holds — `_referenced_names` no longer
   registers `ast.alias` segments, or `"password"` has left the tuple. The
   reason `broker` is absent would then be different, and the comment this task
   writes would be false. Report; do not re-derive a new justification.
7. **A living-document counterpart to ADR-0011 `:99-103` is found** that §4
   D-4's sweep missed. Report it with its path and text. Do not fold it into
   this diff without owner authorisation: Decision 2B authorised correcting a
   counterpart *if one exists*, and the specification's finding is that none
   does — a contradiction between the two is the owner's to resolve.
8. **A second stale statement is found** in either file. Report it with its
   evidence; do not fold it into this diff. §3.2 is the precedent for how such a
   finding is recorded, and it already rules on the nine passages most likely to
   be mistaken for defects.
9. Correcting a passage appears to require naming a supervision mechanism, a run
   loop, a lifecycle rule, an `apps/` import rule, a validation invariant, or
   anything else in §6.1.
10. **The correction cannot be written without stating something the repository
    has not decided.** This is the architectural-invention stop: if every
    available wording either leaves a defect false or asserts something
    undecided, this specification is wrong and must be revised before
    implementation, not worked around. Report the wordings tried and what each
    would have decided.
11. The banner correction cannot be made within the bound **D-1** sets — it
    would require editing `:4-22`, changing the banner's form, or naming a task
    number the roadmap's status table does not contain.
12. The scope expands beyond documentation correction plus one comment, for any
    reason.

In every case: report both pieces of conflicting evidence and explain the
conflict. **Do not silently reconcile them.**

---

## 15. Documentation debt after this task

What this task closes:

- `docs/architecture/overview.md`'s two false or incomplete passages, and its
  stale status banner.
- The stale `#:` comment in `tests/unit/risk/test_risk_boundary.py`.
- Both open "this file names no number for it" entries —
  `docs/ROADMAP.md:1434` and `:1543` — which the closeout answers, not this
  task's diff (§7).

What remains open, deliberately, and is **not** this task's to touch:

- **ADR-0011 `:99-103`.** Immutable. No living-document counterpart exists
  (D-4), so it is recorded here and corrected nowhere.
- **ADR-0015 `:522-524`.** Immutable, now false of the repository, and stays.
- **The ATLAS-TASK-0023 §21.2 gap.** `MT5Config` still accepts an empty
  `password` and a bare `terminal_path`. Closing it is a new invariant and needs
  an ADR (§6.1).
- **The `server_utc_offset` gap**, inherited from ATLAS-TASK-0022 §21.3.
- **`docs/ROADMAP.md`'s "Known documentation debt" section.** Both of its
  bullets are historical — the unreconstructable three-digit ADR-015/016, and
  the ADR-0012 index debt discharged by ATLAS-TASK-0018 — and neither is open.
  This task does not extend the section.
- **`docs/ROADMAP.md:1430`'s "five configuration sections" item**, which does
  not resolve against `overview.md` and collapses into ADR-0011 (D-4). It is
  historical narrative in a completed entry and is left as written.

---

## 16. Relationship to the ADRs

**Fifteen ADRs are Accepted and immutable. This task implements none and edits
none.**

| ADR | Bearing on this task | Effect |
|---|---|---|
| ADR-0006 | Business logic cannot discover which adapter it holds | Preserved — T-2 keeps the venue out of the overview's prose |
| ADR-0010 | Risk is a verdict on an intent | Untouched; P-4 corrects a comment about a boundary it already enforces |
| ADR-0011 | `AtlasSettings` has no broker surface (`:99-103`) | Inaccurate since `d0f5b709`; corrected nowhere, because no living-document counterpart exists (D-4) |
| ADR-0012 | The revisit condition at `:280`, now satisfied by `composition.py` | **Not reopened.** §6.1 |
| ADR-0013 | The application owns the adapter; corrections belong in the living documents (`:280-283`) | The rule this task operates under |
| ADR-0015 | Startup constructs the adapter | The decision P-1 and P-2 now describe as implemented; the record itself is untouched |

---

## 17. Separation from future architectural decision work

This task is a documentation correction. It is **not** an architectural decision
gate, and nothing in its diff may be justified as groundwork for one.

`docs/tasks/ATLAS-TASK-0021.md` §17 made this argument for the previous cycle,
and it transfers unchanged. Two of the blockers it listed — the broker
configuration surface, and adapter selection and process startup — have since
been decided by ADR-0014 and ADR-0015 and built by ATLAS-TASK-0022 and
ATLAS-TASK-0023. The rest of its list is §6.1 of this document.

Its closing reasoning is why this task comes first: "every one of the decisions
above will be argued against `docs/architecture/overview.md` by whoever makes
it. A document that denies the existence of the repository's only adapter owner
is the wrong baseline for that argument — and one that overstates what the owner
does is a worse one." At this baseline the document denies the existence of a
construction that CI verifies on every push, in two jobs, on every commit to
`main`. That is the wrong baseline for ADR-0016, whichever of §6.1 it turns out
to decide.
