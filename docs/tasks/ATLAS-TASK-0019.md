# ATLAS-TASK-0019 — Living-document correction after the first risk control

**Status:** Specified, not implemented
**Date:** 2026-08-14
**Baseline:** `b1f7671ad326e9d32cbcbfcccf92c742dc7526b1`
**Decision record:** None. This task creates no ADR and edits none. See §16.

This task is documentation-only. It adds no behaviour, no contract, no
dependency edge, no capability and no test. It touches one file and two
passages inside it. Both replace a statement that is false today with a fact
already provable from the code at the baseline commit above.

It is the third instalment of the pattern ATLAS-TASK-0015 and ATLAS-TASK-0016
established: when a task changes what the repository is, the living documents
are corrected afterwards, in a separate diff, against a written list of exactly
which passages may move.

`docs/ROADMAP.md` does not list this task, by that file's own rule — every row
in its status table is a completed task citing a commit. The roadmap row is
written when this task merges, the way ATLAS-TASK-0011 through ATLAS-TASK-0018
were, and is not part of the implementation. See §8.

---

## 1. Status

Specified, not implemented. No branch, commit, pull request or CI run exists for
this task, and none is cited anywhere in this document.

The baseline is `b1f7671ad326e9d32cbcbfcccf92c742dc7526b1` on `main`, with a
clean working tree and no divergence from `origin/main`. The implementer must
confirm that state before making any change (§13.1).

At the baseline, `docs/architecture/overview.md` has blob
`accdc88aafd840aecda7658f26f7f73db0d2b33e`.

---

## 2. Purpose

`docs/architecture/overview.md` opens with a status banner that tells a reader
how much of the document is implemented and how much is a contract a later task
must satisfy. That banner currently states that `atlas.risk` holds **"none of
the controls that reach a decision."**

ATLAS-TASK-0017 delivered one. `packages/risk/src/atlas/risk/exposure.py` holds
`evaluate_exposure`, and `docs/ROADMAP.md:782` describes it in those exact terms:
"this is the first thing in `atlas.risk` that reaches a decision."

The front matter of the architecture document therefore denies the existence of
the repository's only risk control. That is the defect this task removes.

---

## 3. Context

### 3.1 What ATLAS-TASK-0017 corrected, and what it deliberately did not

ATLAS-TASK-0017 corrected three passages in `docs/architecture/overview.md` and
was explicit that it corrected no others. Its §8 F-13 reads: "Correct P-2, P-3,
P-14. **Exactly three passages, and nothing else**." Those three were the
feature-package edge count at `:59-62`, the pipeline sentence at `:114-117`, and
the boundary-test sentence at `:74-76`. All three are correct at the baseline;
this task re-verifies them (§4.2) and does not touch them.

**The banner was not among them, and ATLAS-TASK-0017 does not mention it.** The
string `banner` does not appear anywhere in `docs/tasks/ATLAS-TASK-0017.md`. The
omission is not recorded as a deferral, an exclusion or a known debt: it is
absent. `docs/ROADMAP.md`'s "Known documentation debt" section (`:955-976`)
lists two entries, neither of which is this one.

This task therefore records a stale statement that was left behind rather than
one that was scheduled.

### 3.2 The banner's form is already decided, and this task does not reopen it

ATLAS-TASK-0015 §7 D-1 decided three things about this banner, and each remains
in force:

- It carries a task date rather than being undated. "A dated banner that falls
  behind announces itself — a reader compares it to the roadmap's last row and
  knows immediately how much to trust. An undated summary that has drifted is
  silently wrong, which is the worse failure."
- It names `docs/ROADMAP.md` as the authoritative record of which tasks are
  complete.
- No test binds it. ATLAS-TASK-0015 §13 states the reason and applies it to this
  banner directly: a test "which read prose would make the wording of a banner a
  contract," and this is a banner whose *form* such a test would have frozen.
  The general precedent is `docs/ROADMAP.md:557-559`, recorded there for
  `README.md`'s version banner rather than for this one; ATLAS-TASK-0016 §12.1
  restates it as the rule that no test asserts on prose.

This task changes the banner's **content** and none of its form. It adds no
test, and it does not revisit D-1.

### 3.3 The established treatment when a package gains its first working piece

The precedent is in the history and is decisive for §5.

ATLAS-TASK-0014 gave `atlas.execution` `build_order_request` — a real function
that does real work. ATLAS-TASK-0015 corrected the banner for it and **did not**
move `atlas.execution` into the opening sentence's list of packages that "hold
implementation." That sentence read "Three packages hold implementation" at
`00364ac2` and reads "Three packages hold implementation" at `5e730b47`,
unchanged. What ATLAS-TASK-0015 added instead was a sentence in the second
group: "`atlas.execution` holds one thing — the translation of an approved
`RiskVerdict` into an `OrderRequest` — and none of the routing, fills,
reconciliation or idempotent retry its responsibility also names."

`atlas.risk` already has a sentence of that shape. It needs its content
corrected, not its position changed. The count "Three" does not move (§7 D-2).

---

## 4. Problem statement

### 4.1 The two false or stale passages

| | Location | Current text | Why it is wrong |
|---|---|---|---|
| **P-1** | `docs/architecture/overview.md:3` | `> **Status at ATLAS-TASK-0014.**` | Four tasks have completed since. `docs/ROADMAP.md`'s status table lists ATLAS-TASK-0015 (`5e730b47`), 0016 (`c37b0ebb`), 0017 (`4147f12c`) and 0018 (`dfc12899`) as Complete, and `:63-64` states ATLAS-TASK-0018 is the last. |
| **P-2** | `docs/architecture/overview.md:7-8` | "`atlas.risk` holds its two boundary contracts **and none of the controls that reach a decision**." | False. `packages/risk/src/atlas/risk/exposure.py` holds `evaluate_exposure(intent, account) -> RiskVerdict`, which returns `APPROVED` or `REJECTED`. It is exported from `atlas.risk.__all__`. `docs/ROADMAP.md:782` calls it "the first thing in `atlas.risk` that reaches a decision." |

P-1 and P-2 are one banner and are corrected together. A reader who trusts the
banner today concludes that Atlas has no risk control at all, which is the
single most consequential thing the document could get wrong about itself: risk
is the invariant `docs/architecture/overview.md:143-146` says every other safety
property depends on.

### 4.2 Statements checked and found still true — these must not change

Each was verified against the repository at the baseline. Correcting any of them
would introduce a falsehood.

| Passage | Why it stays |
|---|---|
| `:4-7` — "Three packages hold implementation: `atlas.config` in full, `atlas.broker` (domain models, the `BrokerAdapter` port, two adapters, the exception hierarchy) and `atlas.common` (clock, retry)." | True, and unchanged by ATLAS-TASK-0015 through 0018. The count is governed by D-2 (§7). |
| `:8-10` — the `atlas.strategy` sentence | True. The package holds `contracts.py` and `reference.py` and no other module: no lifecycle, no registry, no engine. |
| `:10-13` — the `atlas.execution` sentence | True. The package holds `contracts.py` and no other module: no routing, no fills, no reconciliation, no idempotent retry. |
| `:13-14` — "Every other package remains an empty, importable unit with a declared responsibility." | True. Nine packages — `ai`, `analytics`, `audit`, `events`, `features`, `learning`, `market`, `notification`, `regime` — hold zero modules other than `__init__.py`. |
| `:14-16` — "Where this document describes behaviour, read it as the contract a later task must satisfy, not as a description of code that exists." | True and load-bearing. It is the sentence that keeps the rest of the document honest, and P-2's correction narrows what it covers without falsifying it. |
| `:18-20` — the paragraph naming the roadmap authoritative | True. Added by ATLAS-TASK-0015 D-1 and unchanged. |
| `:60-62` — "Six edges between feature packages exist in the graph today" and the enumeration | True; corrected by ATLAS-TASK-0017 (its P-2). The six are `broker → common`, `risk → broker`, `risk → config`, `strategy → risk`, `execution → risk`, `execution → broker`. |
| `:70-79` — the risk boundary paragraph, including what `test_risk_boundary.py` asserts | True; corrected by ATLAS-TASK-0017 (its P-14). |
| `:116-119` — "The chain the data flow draws is not joined end to end … no layer owns a `BrokerAdapter`" | True; corrected by ATLAS-TASK-0017 (its P-3). Still true at the baseline: nothing outside `packages/broker/src` and the test suite constructs an adapter. |
| `:132` — the `strategy` row, "Strategy contracts, lifecycle, engine" | **Not false.** ATLAS-TASK-0015 §9 ruled on this table: "The table states each package's charter — what it owns and what it must not do — not what is implemented." A charter naming an unbuilt responsibility is the table working as designed. See §6.3. |
| `:134` — the `risk` row, "Sizing, exposure limits, drawdown control, kill switches — *(authoritative and non-bypassable)*" | **Not false.** ATLAS-TASK-0017 §4.3 ruled on this exact row: "A statement of responsibility, not of implementation status. Unchanged by this task." That ruling holds here for the same reason. |
| `:143-161` — invariant 1 and its three paragraphs | True. ATLAS-TASK-0017 §4.3 ruled on the closing sentence — "the behavioural half … now waits on an engine alone … what is still absent is anything that drives a strategy, reaches a verdict and calls the translation in sequence" — as "Still true, and more pointedly true after this task." That the paragraph traces 0011, 0012 and 0014 without mentioning 0017 makes its history incomplete, not its claims false. |
| `:187-189` — "At ATLAS-TASK-0001, `atlas-core` has no run loop." | Dated and still true. `apps/atlas-core/src/atlas/apps/core/__main__.py` resolves configuration, emits a startup record and exits. ATLAS-TASK-0015 §9 reached the same verdict. |

---

## 5. Scope

Exactly two corrections, in one file: **P-1** and **P-2**.

Nothing else in `docs/architecture/overview.md` changes. No other file changes.

---

## 6. Non-goals

This task does not:

1. Create an ADR, or edit one. See §16.
2. Introduce an `apps/` import boundary, an allowlist for `atlas.apps`, or any
   statement about what an application may import.
3. Decide, name or prepare a home for the layer that owns a `BrokerAdapter`.
4. Decide where a composition root lives, or state that one should exist.
5. Add, remove or reword any row of the package responsibilities table,
   including the `strategy` and `risk` rows (§4.2).
6. Add a test, including a documentation-currency test. See §12.
7. Change any source file, configuration file, CI file or deployment file.
8. Change `docs/ROADMAP.md`. See §8.
9. Restate, summarise or relocate ADR-0012's decision into the overview.
10. Describe sizing, drawdown control, correlation caps or kill switches as
    anything other than absent.
11. Assert that any pipeline, engine, run loop or scheduler exists.
12. Add monitoring, metrics, alerting or notification requirements. The
    repository has never designed any; `atlas.notification` is a declared
    responsibility with no implementation and no named transport, and this task
    does not change that or characterise it as an omission.
13. Rewrite the banner for style, length or tone. Two passages move.

---

## 7. Authoritative decisions

Both are resolved from repository evidence; neither invents policy.

### D-1 — The banner is re-dated to ATLAS-TASK-0018

*Not to ATLAS-TASK-0017, and not to this task.*

*Evidence.* ATLAS-TASK-0015 §7 D-1 states the banner's purpose: "a reader
compares it to the roadmap's last row and knows immediately how much to trust."
The comparison the banner is designed to support is against **the roadmap's last
row**, which is ATLAS-TASK-0018 (`docs/ROADMAP.md:32`, and `:63-64`: "ATLAS-TASK-0018
is complete and pushed to `main`. Nothing beyond it is defined").

Dating to ATLAS-TASK-0017 — the last task that changed anything this document
describes — would leave the banner reading as one task behind on the only
comparison it exists to serve, and a reader could not tell whether ATLAS-TASK-0018
had changed something the document had missed. Dating to ATLAS-TASK-0018 is a
true statement, because ATLAS-TASK-0018 changed one row of `docs/adr/README.md`
and nothing this document describes.

Dating to ATLAS-TASK-0019 is wrong on the precedent: ATLAS-TASK-0015 was itself
the correcting task and dated the banner to ATLAS-TASK-0014, the state it had
brought the document up to.

### D-2 — "Three packages hold implementation" does not change

*Evidence.* §3.3. ATLAS-TASK-0015 faced the identical question for
`atlas.execution` — a package that had just gained its first working function —
and left the count at three, adding a second-group sentence instead. The banner's
first group names packages built out to their responsibility; its second group
names packages holding a contract and a first piece. `atlas.risk` belongs to the
second group and already has a sentence there.

Moving `atlas.risk` to the first group would assert that the package is built out
to a responsibility that names four controls and delivers one, which is the
falsehood in the opposite direction.

---

## 8. Files permitted to change

During implementation, exactly this:

| Path | Change |
|---|---|
| `docs/architecture/overview.md` | Corrections P-1 and P-2 — the banner only |

Plus this specification file, `docs/tasks/ATLAS-TASK-0019.md`, which already
exists and is not modified by the implementation.

**`docs/ROADMAP.md` is not in this list.** Its row for this task — including the
replacement of the sentence at `docs/ROADMAP.md:63-66`, which currently reads
"this file declares no ATLAS-TASK-0019 and no work after it" — is a post-merge
closeout step performed under separate authorisation, exactly as it was for
ATLAS-TASK-0011 through 0018. It is not part of the implementation and must not
appear in the implementation diff.

The implementation diff is therefore **one file, and both hunks are inside the
banner at `:3-16`.**

---

## 9. Files explicitly forbidden to change

Any diff touching these fails the task.

**Immutable decision records.** Every file under `docs/adr/`. The twelve ADRs
and the index carry these blobs at the baseline, and each must be unchanged
afterwards:

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
| `README.md` | `a81fcf3640f924e9a17167ac6ff2df9fddb9f41c` |

**Historical task records.** `docs/tasks/ATLAS-TASK-0014.md` through
`ATLAS-TASK-0017.md`. All four contain statements that were true when written;
each is a dated account and none is a live claim about today. In particular,
ATLAS-TASK-0015 and ATLAS-TASK-0016 both quote the phrase "none of the controls
that reach a decision" in passages describing the banner as it then stood, and
`docs/tasks/ATLAS-TASK-0015.md:94` quotes the older `> **Status at
ATLAS-TASK-0012.**`. These match the search patterns this task works from and
are the likeliest files to be swept up by a repository-wide edit. They must not
change.

**`docs/ROADMAP.md`.** Blob `e669a4b720c56544af79af6307d55443799873ed`. See §8.
Its "Known documentation debt" section is not extended by this task: the debt is
discharged in the same diff that would have recorded it, and the roadmap's
account of that is written at closeout.

**Every source file.** In particular `packages/risk/src/atlas/risk/exposure.py`,
`contracts.py` and `__init__.py`, which are correct and are the evidence this
task's corrections rest on. `packages/risk/src/atlas/risk/README.md` and the
risk package docstring were both corrected by ATLAS-TASK-0017 and already state
the control exists.

**Every test file.** See §12.

**Everything else outside §8**, and in particular every file under `apps/`,
`.github/`, `config/`, `infrastructure/` and `scripts/`.

**Every passage of `docs/architecture/overview.md` outside the banner**, and
within the banner, everything named in §4.2.

---

## 10. Exact documentation truths that must hold after implementation

Each truth must be discoverable from the corrected banner. The wording is the
implementer's; the fact is not.

- **T-1.** The banner is dated `ATLAS-TASK-0018` (D-1).
- **T-2.** The banner states that `atlas.risk` holds a control that reaches a
  decision, and identifies it as a portfolio margin-utilisation limit.
- **T-3.** The banner states that the controls `atlas.risk`'s responsibility
  names beside it — sizing, drawdown control and kill switches — do not exist.
  A reader must not be able to conclude from the corrected banner that
  `atlas.risk` is complete.
- **T-4.** The banner does not claim that anything drives the control. Nothing
  outside the test suite produces a `TradeIntent` or calls `evaluate_exposure`,
  and the banner must not imply a pipeline, an engine or a run loop.
- **T-5.** The banner does not name the configuration edge, the limit's default,
  the start-up invariant or ADR-0012. All four are stated accurately elsewhere —
  at `:70-79`, in `packages/risk/src/atlas/risk/README.md`, in
  `config/production/atlas.toml` and in the ADR itself — and restating them in a
  status banner duplicates authority the banner does not hold.
- **T-6.** The sentence "Three packages hold implementation" survives verbatim
  (D-2).
- **T-7.** Every passage listed in §4.2 survives, and the three ATLAS-TASK-0017
  corrections at `:60-62`, `:70-79` and `:116-119` are byte-for-byte unchanged.
- **T-8.** The corrected banner names no package as implemented that is not, and
  names no package as empty that is not. Six packages hold modules beyond
  `__init__.py`: `broker`, `common`, `config`, `execution`, `risk`, `strategy`.
  Nine hold none.

---

## 11. Dependency-graph requirements

**No edge changes.** This task adds no import, removes none, and touches no
Python file.

The six feature-package edges at the baseline — `broker → common`,
`risk → broker`, `risk → config`, `strategy → risk`, `execution → risk`,
`execution → broker` — are the six after implementation, and
`docs/architecture/overview.md:60-62` states six before and after (T-7).

The application-to-package edge `app:atlas-core → atlas.config` is not counted
among the six, for the reason `docs/tasks/ATLAS-TASK-0015.md:341` (§11.1) and
`docs/tasks/ATLAS-TASK-0016.md:457` (§11) both give: it is an
application-to-package edge, not an edge between feature packages. This task neither changes that
classification nor builds anything on it. See §17.

---

## 12. Test requirements

**No test is added, removed or modified.**

The suite passes 3389 tests at the baseline, and must pass 3389 after — the same
count, and the same tests. A changed count is a stop condition (§15.5).

**The suite does not verify this change, and no test is written to make it do
so.** No test reads `docs/architecture/overview.md`. The suite would pass
identically if the banner were left stale, corrected wrongly, or deleted.
Acceptance therefore rests on the mechanical checks in §13, not on a green
suite; the 3389 passing tests are evidence that nothing else moved, which is the
only thing they can be evidence of here.

**A documentation-currency test is deliberately not written.** ATLAS-TASK-0015
§13 is the authority for this banner: "ATLAS-TASK-0013 corrected this same class
of stale statement and added no test, on the reasoning that a test which read
prose would make the wording of a banner a contract. That reasoning applies
unchanged here, and more strongly: this task changes the banner's *form* (D-1),
which such a test would have frozen." The reasoning it inherits is recorded at
`docs/ROADMAP.md:557-559`, where ATLAS-TASK-0013 applied it to `README.md`'s
version banner — a different banner, and the generalisation is
ATLAS-TASK-0015's rather than that passage's. ATLAS-TASK-0016 §12.1 restates it
as the rule that no test asserts on prose. Writing such a test is a separate
decision with its own trade-off, and it is not made here.

---

## 13. Validation requirements

1. **Before any edit**, confirm: branch `main`; `HEAD` and `origin/main` both
   `b1f7671ad326e9d32cbcbfcccf92c742dc7526b1`; `git status --porcelain` empty;
   `git rev-parse HEAD:docs/architecture/overview.md` is
   `accdc88aafd840aecda7658f26f7f73db0d2b33e`.
2. **Re-verify P-2 against the code, not against this document.**
   `packages/risk/src/atlas/risk/exposure.py` defines `evaluate_exposure` and
   returns a `RiskVerdict` carrying `VerdictStatus.APPROVED` on one path and
   `VerdictStatus.REJECTED` on the others, and `evaluate_exposure` appears in
   `atlas.risk.__all__`. If it does not, the premise of this task has changed and
   §15.1 applies.
3. **Re-verify P-1 against the roadmap.** `docs/ROADMAP.md`'s status table lists
   ATLAS-TASK-0018 as its last row and as Complete.
4. **After the edit**, `git diff --stat` must report exactly one file changed.
   `git diff` must show changes confined to lines 3-16 of
   `docs/architecture/overview.md`.
5. **Confirm the ADRs are untouched**: each blob in §9 is unchanged.
6. Run the full test suite. Expect 3389 passed.
7. Ruff, Black and MyPy are not required locally: the change touches no Python.
   CI's Quality Gate runs them regardless, and a failure in any of them on a
   documentation-only diff is a stop condition (§15.6).
8. **Read the corrected banner end to end** and confirm each of T-1 through T-8.
   This is the only check that can catch a correction that is true in isolation
   and false in context.

---

## 14. Acceptance criteria

- **AC-1.** `docs/architecture/overview.md` no longer states that `atlas.risk`
  holds none of the controls that reach a decision (P-2, T-2).
- **AC-2.** The banner is dated `ATLAS-TASK-0018` (P-1, T-1).
- **AC-3.** The corrected banner does not imply that `atlas.risk` is complete,
  that a pipeline exists, or that anything calls the control (T-3, T-4).
- **AC-4.** Truths T-1 through T-8 hold.
- **AC-5.** The diff touches exactly one file, and only its banner.
- **AC-6.** No ADR changed. No test changed. No source file changed.
  `docs/ROADMAP.md` unchanged.
- **AC-7.** The test suite passes with 3389 tests.
- **AC-8.** The diff contains no statement that decides, prepares for, or
  presumes an answer to anything in §17.

---

## 15. Stop conditions

Stop and report rather than deciding, if:

1. `packages/risk/src/atlas/risk/exposure.py` does not hold a control that
   reaches a decision, or the repository has moved from the baseline. Either
   means the premise of this task no longer holds.
2. An ADR-0013 or later exists, or a task after ATLAS-TASK-0018 exists. Either
   may have already corrected the banner or changed what is true.
3. A correction appears to require editing an ADR. It does not; see §16.
4. A correction appears to require a source change. It does not; every truth in
   §10 is already true of the code at the baseline. If a document cannot be made
   true without changing code, the document is describing something
   ATLAS-TASK-0017 did not deliver, and that is a finding to report, not to fix.
5. The test count is anything other than 3389.
6. Ruff, Black or MyPy reports anything on a diff that touches no Python.
7. **A third stale statement is found.** Report it with its evidence; do not fold
   it into this task's diff. §4.2 is the precedent for how such a finding is
   recorded, and §4.2 is also where the two candidates most likely to be mistaken
   for defects — the `strategy` and `risk` rows of the responsibilities table —
   are already ruled on as charter statements.
8. Correcting the banner appears to require naming where the broker-owning layer
   lives, what an `apps/` boundary is, or any other item in §17.
9. The scope expands beyond documentation correction for any reason.

In every case: report both pieces of conflicting evidence and explain the
conflict. Do not silently reconcile them.

---

## 16. Relationship to the ADRs

**All twelve ADRs are Accepted and immutable. No ADR is required by this task,
and this task edits none.**

`docs/adr/README.md` defines exactly four statuses — `Proposed`, `Accepted`,
`Superseded by ADR-NNNN`, `Deprecated`. There is no amendment status.

Five ADRs cite `docs/architecture/overview.md`. Each was checked, and none
depends on the banner:

| ADR | What it cites | Affected? |
|---|---|---|
| ADR-0008 `:76` | that the overview assigns the clock to `common` | No |
| ADR-0010 `:8` | invariant 1 | No — invariant 1 is not touched (§4.2) |
| ADR-0011 `:11` | invariant 1's behavioural half, and the flow's missing half | No |
| ADR-0011 `:225` | "only `atlas.execution` turns an approved verdict into an `OrderRequest`", at `:150` | No |
| ADR-0012 `:49` | the `risk` row of the responsibilities table, "authoritative and non-bypassable" | No — the row is not touched (§4.2, §6.5) |

ADR-0012 is the decision `evaluate_exposure` implements, and it is the reason
P-2 is now false. It is not amended, footnoted, restated or cross-referenced by
this task. ADR-0011 governs where such a correction belongs: "in the roadmap's
completed record and in the living documents, never in ADR-0010 itself."

An ADR is required when a decision changes the architecture. This task changes
no contract, no boundary, no edge and no behaviour.

Accordingly, this task must not: edit any ADR; add a footnote or cross-reference
to one; create ADR-0013; or state, in the corrected banner, that any ADR's
wording has been corrected, superseded or amended. None has been.

---

## 17. Separation from future architectural decision work

This task is a documentation correction. It is **not** an architectural decision
gate, and nothing in its diff may be justified as groundwork for one.

The repository's substantive next work is blocked behind decisions it has
deliberately declined to make, and this task neither makes nor prepares any of
them:

- **The layer that owns a `BrokerAdapter`.** Named in ADR-0011's Decision;
  ADR-0011 rejects `atlas.execution` as its home and names no replacement.
  ADR-0007 `:147-148` assigns lifecycle sequencing to "a caller that must not
  lose a request" — an obligation held today by no layer that exists. Nothing
  outside `packages/broker/src` and the test suite constructs an adapter, and
  `AtlasSettings` carries no broker or venue section.
- **What kind of rule an `apps/` boundary is.** No ADR decides one. ADR-0012
  `:105-107` records `apps/core → atlas.config` as the accepted baseline without
  ruling on it. `README.md:129-130` states that apps "compose" the packages, and
  ATLAS-TASK-0015 §11.1 and ATLAS-TASK-0016 §11 both classify an
  application-to-package edge as a different kind of edge from the ones the four
  boundary tests enforce. Whether an apps rule is a forward allowlist, a reverse
  prohibition, a construction-site rule or a content rule is undecided, and this
  task does not decide it, hint at it, or write anything into the overview that
  presumes an answer.
- **Where a composition root lives, and whether one should exist.** ADR-0012
  `:274-280` rejected a composition root that hands risk its limits and set the
  revisit condition: "when a single wiring point exists and can be pointed at."
  None exists.
- **The state contracts the remaining risk controls need.** ADR-0010 `:198`,
  ADR-0011 `:184` and ADR-0012 `:282` each declined to define account or
  portfolio state. ADR-0012 `:230-236` records that drawdown "needs a reference
  point over time that no contract here carries" and that correlation needs
  `atlas.market`, which does not exist. Two of the three controls T-3 requires
  the banner to describe as absent are blocked by those refusals rather than
  merely unbuilt, and the banner must not characterise either as scheduled.
- **Order identity and idempotency.** No ADR, task specification or module
  analyses either. ADR-0011 `:177` lists idempotent retry among what it does not
  decide. This task adds nothing to that record.

When one of these is taken up, it begins with an owner decision gate and a new
ADR, in the sequence ATLAS-TASK-0014 and ATLAS-TASK-0017 followed — not with a
documentation pass.

Correcting the banner is worth doing on its own terms, and it is worth doing
first: it requires no architectural decision, and every one of the decisions
above will be argued against `docs/architecture/overview.md` by whoever makes
it. A document that denies the existence of the repository's only risk control
is the wrong baseline for that argument.

---

## Roadmap

`docs/ROADMAP.md` is not modified by this task. Its row for ATLAS-TASK-0019 —
and the replacement of its current sentence at `:63-66` stating that the file
declares no ATLAS-TASK-0019 and no work after it — is written after this
specification has been reviewed and explicitly authorised, and after the
implementation has merged, following the pattern of ATLAS-TASK-0011 through
ATLAS-TASK-0018.
