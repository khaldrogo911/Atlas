# ATLAS-TASK-0015 — Living-document correction after the execution contract

**Status:** Specified, not implemented
**Date:** 2026-08-12
**Baseline:** `5b1429b53d255d2322917eb6dae44f5179950398`
**Decision record:** None. This task creates no ADR and edits none. See §17.

This task is documentation-only. It adds no behaviour, no contract, no
dependency edge and no capability. Every correction it makes replaces a
statement that is false today with a fact already provable from the code at the
baseline commit above.

`docs/ROADMAP.md` does not list this task, by that file's own rule — every row
in its status table is a completed task citing a commit. The roadmap row is
written when this task merges, the way ATLAS-TASK-0011, 0012, 0013 and 0014
were, and is not part of the implementation. See §8.

---

## 1. Status

Specified, not implemented. No branch, commit, pull request or CI run exists for
this task, and none is cited anywhere in this document.

The baseline is `5b1429b53d255d2322917eb6dae44f5179950398` on `main`, with a
clean working tree, no divergence from `origin/main`, and an empty stash. The
implementer must confirm that state before making any change (§14.1).

---

## 2. Purpose

ATLAS-TASK-0014 gave `atlas.execution` its first implementation. Three living
documents still describe the repository as it was before that merge, and each
states in the present tense that `atlas.execution` is an empty stub which
consumes no `RiskVerdict`. A fourth statement — the count of dependency edges
between feature packages — was measurably correct when written and is
measurably wrong now.

This task corrects those statements, and nothing else.

---

## 3. Context

ATLAS-TASK-0014 merged through pull request #4 as merge commit
`00364ac24f0479de2cb5278b519dbe97cf2e0d2b`. Its post-merge CI run, `31449617099`,
completed with **Quality Gate: success** and **Container & Compose: success**.
The roadmap follow-up commit is `5b1429b53`, which is this task's baseline.

What ATLAS-TASK-0014 delivered, verified from the source at the baseline:

- `packages/execution/src/atlas/execution/contracts.py` defines
  `ExecutionPolicy` (frozen, `extra="forbid"`, fields `order_type` and an
  optional `price`) and `build_order_request(verdict, policy)`.
- `packages/execution/src/atlas/execution/__init__.py` exports both:
  `__all__ = ["ExecutionPolicy", "build_order_request"]`.
- The package gained two dependency edges: `atlas.execution → atlas.risk` (for
  `RiskVerdict`, under a `TYPE_CHECKING` guard) and `atlas.execution →
  atlas.broker` (for `OrderRequest`, `OrderType`, `Price`).

What ATLAS-TASK-0014 did **not** deliver, equally verified:

- Nothing anywhere maps a `TradeIntent` to a `RiskVerdict`. `atlas.risk`
  exports five names — `RISK_MODEL_CONFIG`, `RejectionReason`, `RiskVerdict`,
  `TradeIntent`, `VerdictStatus` — and no decision function.
- No layer owns or constructs a `BrokerAdapter` outside `packages/broker/`.
- Nothing outside the test suite calls `build_order_request` or
  `Strategy.propose`. No module under `apps/` or `scripts/` imports
  `atlas.execution`, `atlas.risk` or `atlas.strategy`.

ATLAS-TASK-0014 therefore joined two contracts that are each still unreachable
from a running program. The corrections in this task must leave that legible;
see §10, truth **T-9**, and §16.4.

**This is the second occurrence of this drift.** ATLAS-TASK-0013 existed to
correct the same class of stale statement, and one of the exact lines it
corrected — `packages/risk/src/atlas/risk/README.md:175` — is stale again one
task later. That recurrence is the reason decision **D-1** in §7 does more than
change a task number.

---

## 4. Problem statement

Six statements across three living documents are false or incomplete at the
baseline. Line numbers are relative to
`5b1429b53d255d2322917eb6dae44f5179950398` and are given for location only; the
implementer must match on text, because the numbers shift as edits are applied.

| # | Location | Defect |
|---|---|---|
| P-1 | `docs/architecture/overview.md:3` | Banner reads `> **Status at ATLAS-TASK-0012.**` The document is two completed tasks behind. |
| P-2 | `docs/architecture/overview.md:3-13` | The banner's package enumeration omits `atlas.execution`, so the closing clause "Every other package remains an empty, importable unit" asserts, by omission, that `atlas.execution` is empty. It is not. |
| P-3 | `docs/architecture/overview.md:52` | "Three edges between feature packages exist in the graph today, and every one of them runs downward." The count is now five. |
| P-4 | `docs/architecture/overview.md:81-83` | "`atlas.execution` remains an empty stub, so nothing consumes a `RiskVerdict` yet. The consuming half of the flow is still the contract a later task must satisfy." Both sentences are false. |
| P-5 | `docs/architecture/overview.md:120-123` | "the behavioural half, that a running pipeline routes every intent through risk, waits on `execution` and an engine existing." Half false: `execution` now exists; an engine does not. |
| P-6 | `packages/risk/src/atlas/risk/README.md:175` and `packages/strategy/src/atlas/strategy/README.md:189` | Both state `atlas.execution` "is still an empty stub" / "is still a stub, so nothing consumes a verdict." Both are false. |

A reader who trusts `docs/architecture/overview.md` today concludes that the
`strategy → risk → execution → broker` chain has one hole. It has two (§3). That
is a worse error than the literal falsehood, because the document reads as
authoritative.

---

## 5. Scope

Exactly three files are corrected:

1. `docs/architecture/overview.md`
2. `packages/risk/src/atlas/risk/README.md`
3. `packages/strategy/src/atlas/strategy/README.md`

The work is: make the six defects in §4 read true, satisfying every truth in
§10, without changing anything else in those files and without touching any
other file.

Where this document states a truth that must hold, it states the truth and not
the sentence. The implementer chooses wording that fits each document's existing
register. Where this document says a passage must not change, it means
byte-for-byte.

---

## 6. Non-goals

This task does not, and any change that does so is out of scope:

1. Modify source code under `packages/*/src/` or `apps/`.
2. Modify, add or delete any test.
3. Modify `pyproject.toml`, `poetry.lock`, `mypy.ini`, `ruff.toml`,
   `pytest.ini`, `.pre-commit-config.yaml`, `Dockerfile`, `docker-compose.yml`,
   or anything under `.github/`, `config/` or `infrastructure/`.
4. Modify ADR-0010 or ADR-0011, or create ADR-0012. See §17.
5. Modify `docs/ROADMAP.md`, including its historical task narratives.
6. Implement `TradeIntent → RiskVerdict`, any risk control, a `RiskEngine`, or a
   `RiskControl` protocol.
7. Introduce account or portfolio state.
8. Introduce a broker-owning layer, routing, venue integration, or MT5 trading
   methods.
9. Introduce events or message-bus infrastructure.
10. Widen `ExecutionPolicy` or add `STOP_LIMIT` support. `STOP_LIMIT` remains
    deferred until a real caller requires it; ATLAS-TASK-0014 recorded that
    deferral and this task does not revisit it.
11. Introduce persistence, transport, a run loop, or `atlas-core` orchestration.
12. Change any of the five existing package dependency edges, or create a new
    one. See §11.
13. Create a README for any package other than as decided in §12.
14. Tidy, reflow or reword prose that is not false. Only the six defects in §4
    are in scope.

---

## 7. Authoritative decisions

Two questions the implementer would otherwise have to answer are answered here.
Both are resolved from repository evidence; neither invents policy.

### D-1 — The `overview.md` status banner is re-dated to ATLAS-TASK-0014 and names the roadmap as the authority

The banner must carry a task date, and that date must be ATLAS-TASK-0014.

*Evidence.* Dated status markers are the repository's established convention:
`docs/api/README.md:7` ("**Empty at ATLAS-TASK-0001.**"),
`tests/integration/README.md` and `tests/e2e/README.md` ("**This directory is
intentionally empty at ATLAS-TASK-0001.**"), `docs/runbooks/README.md`
("## Scope at ATLAS-TASK-0001") and `docs/architecture/overview.md:149` ("At
ATLAS-TASK-0001, `atlas-core` has no run loop."). Every one of them is still
correct, because each pins a fact that has not moved.

*Why the date stays rather than being removed.* `overview.md`'s banner
summarises implementation state, which moves with every task. Removing the date
would not stop the summary drifting; it would only stop a reader being able to
tell that it had. A dated banner that falls behind announces itself — a reader
compares it to the roadmap's last row and knows immediately how much to trust.
An undated summary that has drifted is silently wrong, which is the worse
failure.

*What is added, and why.* The banner must additionally name `docs/ROADMAP.md`
as the authoritative record of which tasks are complete, and state that where
the two disagree the roadmap is correct. `docs/ROADMAP.md:3-5` already claims
that authority in its own words: "The authoritative record of which ATLAS tasks
are complete and what comes next. A task is **Complete** only when it is merged
on `main` and every gate in the repository's definition of done passed on that
commit." Naming it converts a silent duplication of authority into an explicit
subordination, so the next reader of a stale banner knows where to look instead
of guessing. This is the only durability change the task makes, and it changes
no other document.

### D-2 — No `atlas.execution` README is created

See §12 for the full evidence and reasoning. `packages/execution/src/atlas/execution/README.md`
is **not** created by this task.

---

## 8. Files permitted to change

During implementation, exactly these:

| Path | Change |
|---|---|
| `docs/architecture/overview.md` | Corrections P-1 through P-5 |
| `packages/risk/src/atlas/risk/README.md` | Correction P-6 (risk half) |
| `packages/strategy/src/atlas/strategy/README.md` | Correction P-6 (strategy half) |

Plus this specification file, `docs/tasks/ATLAS-TASK-0015.md`, which already
exists and is not modified by the implementation.

**`docs/ROADMAP.md` is not in this list.** Its row for this task — including the
replacement of the sentence at `docs/ROADMAP.md:60-62`, which currently reads
"Nothing beyond ATLAS-TASK-0014 is defined, and nothing here declares what
ATLAS-TASK-0015 will be" — is a post-merge closeout step performed under
separate authorisation, exactly as it was for ATLAS-TASK-0011 through 0014. It
is not part of the implementation and must not appear in the implementation
diff.

---

## 9. Files explicitly forbidden to change

Any diff touching these fails the task.

**Immutable decision records.**

- `docs/adr/0010-the-risk-boundary-is-a-verdict-on-an-intent.md` — blob
  `6f20807a73496c087a252145696dea4a3330d55b`
- `docs/adr/0011-execution-builds-the-request-another-layer-owns-the-port.md` —
  blob `45600504bd9212db0a5efcf1eb4d85ebfc1595ed`
- Every other file under `docs/adr/`

**Everything else outside §8**, and in particular every file under
`packages/*/src/`, `apps/`, `tests/`, `.github/`, `config/`, `infrastructure/`,
and `scripts/`.

**Passages inside the three permitted files that must not change**, because they
are true and correcting them would introduce a new falsehood:

| Passage | Why it stays |
|---|---|
| `packages/risk/src/atlas/risk/README.md:165-170` — "**Constructing an `APPROVED` verdict does not make it true.** There is no sizing algorithm, no exposure limit, no drawdown control, no correlation cap and no kill switch…" | Entirely true. ATLAS-TASK-0014 added a *consumer* of verdicts and nothing that *produces* one. This is the paragraph most likely to be swept up by an over-eager edit. |
| `packages/risk/src/atlas/risk/README.md:171-173` — "`atlas.strategy` holds the `Strategy` contract and `ConstantStrategy`… nothing drives a strategy and no intent is produced in practice." | True. |
| `packages/strategy/src/atlas/strategy/README.md:63-66` — the `atlas.market` / `atlas.features` / `atlas.regime` "all still empty stubs" passage | True. All three are still empty. This mentions stubs but never mentions `atlas.execution`, and it is the likeliest accidental edit in the task. |
| `packages/strategy/src/atlas/strategy/README.md:188-189`, the clause "`atlas.market`, `atlas.features` and `atlas.regime` are still empty stubs, so `InputT` has nothing concrete to be" | True. Only the trailing `atlas.execution` clause of this sentence is false. |
| `packages/strategy/src/atlas/strategy/README.md:183-185` — "no lifecycle, no registry, no engine, no scheduling and no event subscription" | True. |
| `docs/architecture/overview.md:149` — "At ATLAS-TASK-0001, `atlas-core` has no run loop." | Dated and still true. |
| `docs/architecture/overview.md:87-101`, the Package responsibilities table, including the `execution` row | The table states each package's charter — what it owns and what it must not do — not what is implemented. `execution`'s charter did not change; ATLAS-TASK-0014 delivered translation only, and routing, fills and reconciliation remain its unbuilt responsibilities. The `— *(implemented)*` note on the `config` row occupies the "Must not" column, which is empty for that package; it is not an implementation-state marker and no such marker is added. |
| `docs/architecture/overview.md:104-141`, the five invariants, except for the single clause identified as P-5 | The invariants themselves are unchanged by ATLAS-TASK-0014. |

---

## 10. Exact documentation truths that must hold after implementation

Each truth below must be discoverable from the corrected documents. The wording
is the implementer's; the fact is not.

**About `atlas.execution`:**

- **T-1.** `atlas.execution` is not an empty stub. It contains `ExecutionPolicy`
  and `build_order_request`, delivered by ATLAS-TASK-0014.
- **T-2.** `atlas.execution` consumes a `RiskVerdict`.
- **T-3.** An approved `RiskVerdict`, together with a caller-supplied
  `ExecutionPolicy`, becomes an `atlas.broker.OrderRequest`.
- **T-4.** A rejected `RiskVerdict` produces `None`. `None` is an ordinary
  answer and not an error: a rejection is risk working, and is not a broker
  failure.
- **T-5.** The volume carried into the request is the verdict's approved volume,
  never the intent's requested volume.
- **T-6.** The `ExecutionPolicy` is supplied per call. Nothing stores one,
  nothing reads one from configuration, and there is no default.
- **T-7.** `atlas.execution` does not route orders, does not own or construct a
  `BrokerAdapter`, does not place orders, and does not reach a venue. The
  `OrderRequest` it produces is inert.
- **T-8.** `atlas.execution` names the broker's order vocabulary as types. That
  dependency is a type dependency and is not a call path.

**About the system as a whole — the truths that stop this correction becoming a
false capability claim:**

- **T-9.** There is still no running trading pipeline. Nothing produces a
  `TradeIntent` outside the test suite; nothing maps a `TradeIntent` to a
  `RiskVerdict`; no layer owns a `BrokerAdapter`. The request `atlas.execution`
  builds is received by nothing. No corrected sentence may state or imply
  otherwise.
- **T-10.** The structural half of the risk invariant — that no package exposes
  a path around risk — remains the half that is proven by test. The behavioural
  half remains unproven, and now waits on an engine alone rather than on
  `execution`.
- **T-11.** `atlas.risk` still holds its contracts and none of the controls that
  reach a decision.
- **T-12.** `atlas.market`, `atlas.features` and `atlas.regime` are still empty
  stubs.

**About the banner (D-1):**

- **T-13.** `docs/architecture/overview.md`'s status banner is dated to
  ATLAS-TASK-0014.
- **T-14.** The banner's package enumeration accounts for `atlas.execution`,
  describing it as narrowly as it is implemented — the verdict-to-request
  translation and nothing further — so that the enumeration's closing
  "every other package remains an empty, importable unit" clause is true of the
  packages it still covers.
- **T-15.** The banner names `docs/ROADMAP.md` as the authoritative record of
  which tasks are complete, and states that the roadmap governs where the two
  disagree.

**About the edge census:**

- **T-16.** See §11.

---

## 11. Package/architecture edge requirements

### 11.1 The count

At the baseline there are **five** dependency edges between feature packages,
and every one of them runs downward:

| Edge | Names taken | Introduced by |
|---|---|---|
| `atlas.broker → atlas.common` | `Clock`, `ManualClock`, `RetryPolicy`, `SystemClock`, `retry_call` | ATLAS-TASK-0008 / 0009 |
| `atlas.risk → atlas.broker` | `OrderSide`, `Price`, `SymbolName`, `Volume` | ATLAS-TASK-0011 |
| `atlas.strategy → atlas.risk` | `TradeIntent` | ATLAS-TASK-0012 |
| `atlas.execution → atlas.risk` | `RiskVerdict` | ATLAS-TASK-0014 |
| `atlas.execution → atlas.broker` | `OrderRequest`, `OrderType`, `Price` | ATLAS-TASK-0014 |

**T-16.** `docs/architecture/overview.md` must state five, must state that all
five run downward, and must **name them individually**. Naming them is required,
not stylistic: a wrong list is falsifiable by inspection, whereas a wrong
integer is not, and the integer is exactly what went stale here.

The two edges ATLAS-TASK-0014 introduced must each be described in the same
place and manner as the three that precede them at
`docs/architecture/overview.md:52-83`, replacing the false paragraph P-4 that
currently closes that sequence. `atlas.execution → atlas.broker` must be
described as a type dependency on the port's order vocabulary — not venue
access — consistent with T-7 and T-8.

`app:atlas-core → atlas.config` is an application-to-package edge, not an edge
between feature packages, and is not counted among the five. The document's
sentence is about feature packages and remains so.

### 11.2 How the count must be derived

The count must be derived from the repository's AST/import graph. It must not
be counted by hand or copied from this document.

The derivation must satisfy three conditions, each of which has already caused a
wrong answer once:

1. **It must parse the AST, not grep for `^from atlas`.** The
   `atlas.execution → atlas.risk` edge is written under a `TYPE_CHECKING`
   guard and is therefore indented. A line-anchored grep misses it.
2. **It must count `TYPE_CHECKING`-guarded imports as real edges.**
   `ast.walk` descends into `if TYPE_CHECKING:` blocks, and
   `tests/unit/execution/test_execution_boundary.py::test_the_import_scanner_sees_through_a_type_checking_guard`
   asserts that the repository's own boundary scanners do so.
3. **It must derive the owning package from the source-root directory** —
   `packages/<name>/` or `apps/<name>/` — and **not** by searching the path for
   the segment `atlas`. Under `packages/<pkg>/src/atlas/<pkg>/…` the first
   `atlas` segment is the PEP 420 namespace directory, and keying on it
   collapses every package into a single owner.

The derivation is run from a scratch script outside the repository. **No script,
tool or test is added to the repository by this task** (§6.1, §6.2).

### 11.3 The edge set must not change

This task creates no edge, removes none, and changes none. The census after
implementation must be identical to the table in §11.1. See §14.5.

---

## 12. README decision

**`packages/execution/src/atlas/execution/README.md` is NOT created by this
task.**

The question was whether an existing repository convention, acceptance criterion
or architectural obligation requires one. Three checks say no.

**No contract test requires a package README.** The repository contains exactly
two assertions that a README exists, and both are local to the broker package
tree: `tests/unit/broker/test_adapter_contract.py::test_the_package_ships_a_readme`
(against the directory holding the MT5 adapter) and
`tests/unit/broker/test_model_invariants.py::test_the_package_ships_a_readme`
(against `atlas.broker.models`). The `"README.md"` entry in
`tests/contract/test_repository_structure.py:44` is a member of
`REQUIRED_ROOT_FILES` and refers to the repository root README, not a package
one. `tests/contract/test_repository_structure.py::TestPackageContracts` asserts
four things of every declared package — importable, documented, declares
`__all__`, ships `py.typed` — and README is not among them. No test anywhere
references the risk, strategy, common or top-level broker READMEs.

**No convention requires one.** Four of the fifteen packages carry a README:
`broker`, `common`, `risk`, `strategy`. The decisive counterexample is
`atlas.config`, which is the most completely implemented package in the
repository — six source modules, described in the overview banner as implemented
"in full" — and has no README. A pattern that four packages follow and the
most-implemented package does not is not an obligation.

**The prior task ruled on it.** ATLAS-TASK-0014 excluded an execution README
from its own scope explicitly. That was a scope decision, not a debt with a due
date.

Positively: `packages/execution/src/atlas/execution/__init__.py:11-22` and the
module docstring of `contracts.py` already carry what such a README would carry
— what ATLAS-TASK-0014 delivered, that routing, fills, reconciliation and
idempotent retry remain untouched, that nothing here reaches a venue, and a
pointer to ADR-0011. A README today would restate them, and restating a rule in
a second place is the divergence hazard `contracts.py` itself refuses when it
declines to copy `OrderRequest`'s price rule.

**When one would become justified:** when `atlas.execution` acquires a second
concern that the module docstrings cannot hold together — one of the four
responsibilities its `__init__` lists as untouched. That is a decision for the
task that adds one.

No README is created for any other package either.

---

## 13. Test requirements

**No new test is required, and no existing test may be modified.**

*Evidence.* No test in the repository reads documentation prose. The only
README-related assertions are the two broker-local existence checks described in
§12, and neither is affected: this task creates no README, deletes none, and
touches no file under `packages/broker/`.

*Precedent.* ATLAS-TASK-0013 corrected this same class of stale statement and
added no test, on the reasoning that a test which read prose would make the
wording of a banner a contract. That reasoning applies unchanged here, and more
strongly: this task changes the banner's *form* (D-1), which such a test would
have frozen.

*Structural tests affected:* none. The three corrected files are Markdown.
`TestRepositoryLayout` requires `docs/architecture` to exist and does not read
its contents. `TestPackageDeclarations`, `TestNamespaceIntegrity`,
`TestPackageContracts`, `TestToolchainParity` and `TestConfigurationTree` are
all unaffected, as are the three boundary test modules, because no `.py` file
changes.

The test count and coverage figures after implementation must be identical to
`main` at the baseline. A change in either is evidence that something outside
scope was touched (§15, AC-12).

---

## 14. Validation requirements

Every item below is a command whose output must be recorded. A criterion is met
only when its command has been run and its output shown — not when the change
looks right.

1. **Before any edit**, confirm the baseline: `git rev-parse HEAD` is
   `5b1429b53d255d2322917eb6dae44f5179950398`; `git status --short` is empty;
   `git diff --exit-code` and `git diff --cached --exit-code` both exit 0; the
   stash is empty; `git rev-list --left-right --count origin/main...HEAD` is
   `0 0`. Record the pre-existing local `task-00xx-*` branches so they are not
   confused with this task's.
2. **Re-derive the edge census immediately before writing the corrected
   sentence**, by the method in §11.2, rather than copying §11.1. If the result
   is not the five edges in §11.1, stop and report (§16.5).
3. **Diff scope.** `git diff --name-only` lists exactly the three files in §8
   and nothing else. In particular `git diff --name-only -- '*.py'` is empty,
   `git diff --name-only -- tests/` is empty, `git diff --name-only -- docs/adr/`
   is empty, and `git diff --name-only -- docs/ROADMAP.md` is empty.
4. **ADRs byte-identical.** `git rev-parse HEAD:docs/adr/0010-…md` still returns
   `6f20807a73496c087a252145696dea4a3330d55b` and
   `git rev-parse HEAD:docs/adr/0011-…md` still returns
   `45600504bd9212db0a5efcf1eb4d85ebfc1595ed`.
5. **Edge census unchanged.** Re-run the §11.2 derivation after the edits; it
   returns the same five edges. This is trivially true for a documentation-only
   change and is checked precisely because it is the claim the corrected
   document now makes.
6. **Protected passages unchanged.** For each passage in §9's table, compare
   against the baseline blob. `git diff` on the three files must show no hunk
   overlapping them.
7. **No dependency change.** `git diff --name-only -- pyproject.toml poetry.lock`
   is empty.
8. **No CRLF.** For each changed file, `tr -d -c '\r' < <file> | wc -c` returns
   `0`, per `.gitattributes`' `* text=auto eol=lf`.
9. **Quality gate green.** Run the repository's gate — `scripts/quality.ps1` on
   Windows, `scripts/quality.sh` otherwise — with full output captured. ruff,
   black and mypy are expected to be no-ops for Markdown; pytest must report the
   same test count and coverage as the baseline. **Container & Compose runs only
   in CI and cannot be run locally; say so rather than implying it passed.**
10. **Read all three corrected files end to end.** Truths T-9 and T-10 cannot be
    checked by command. The specific failure to hunt for is a set of sentences
    that are each individually true but together imply the chain runs.
11. **CI**, when the change reaches a pull request, verified by `head_sha`
    rather than by recency — a run against the PR head is not a run against the
    merge commit. If CI has not been run, state **CI NOT RUN**.

Nothing further is required. No validation is added for ceremony.

---

## 15. Acceptance criteria

- **AC-1.** `git diff --name-only` against the baseline lists exactly
  `docs/architecture/overview.md`,
  `packages/risk/src/atlas/risk/README.md` and
  `packages/strategy/src/atlas/strategy/README.md`.
- **AC-2.** `git grep -n "empty stub" -- docs/architecture/ packages/` returns no
  line naming `atlas.execution`. Lines naming `market`, `features` or `regime`
  are expected to remain and are not violations.
- **AC-3.** `git grep -n "still a stub" -- docs/ packages/` returns matches only
  under `docs/adr/` and in `docs/ROADMAP.md`.
- **AC-4.** `git grep -n "Three edges" -- docs/` returns nothing.
- **AC-5.** `docs/architecture/overview.md` states five feature-package edges,
  states that all five run downward, and names all five. The named set matches
  the §11.2 derivation exactly, with no addition or omission.
- **AC-6.** `git grep -n "Status at ATLAS-TASK-0012" -- docs/architecture/ packages/`
  returns nothing, and `docs/architecture/overview.md`'s banner is dated to
  ATLAS-TASK-0014 and cites `docs/ROADMAP.md` as authoritative (T-13, T-15).
  The string may remain in historical task specifications under `docs/tasks/`;
  those records are not modified by later tasks.
- **AC-7.** The banner's enumeration accounts for `atlas.execution` (T-14).
- **AC-8.** Truths T-1 through T-8 hold in `docs/architecture/overview.md`, and
  T-1, T-2, T-3, T-4 and T-7 hold in both corrected READMEs.
- **AC-9.** Truths T-9 through T-12 hold. No corrected sentence asserts a
  running pipeline, a producer of `TradeIntent` outside tests, a mapping from
  `TradeIntent` to `RiskVerdict`, or any layer owning a `BrokerAdapter`.
- **AC-10.** `git diff -- docs/adr/` is empty and both ADR blob hashes are
  unchanged (§14.4).
- **AC-11.** `git diff -- '*.py' tests/ pyproject.toml poetry.lock docs/ROADMAP.md`
  is empty.
- **AC-12.** The quality gate passes with the same test count and coverage as
  the baseline.
- **AC-13.** `packages/execution/src/atlas/execution/README.md` does not exist.
- **AC-14.** Every passage listed in §9's protected table is byte-for-byte
  unchanged.
- **AC-15.** No changed file contains a CR byte.
- **AC-16.** The derived edge census after implementation is the same five edges
  as before it.

---

## 16. Stop conditions

Stop and report rather than deciding, if:

1. An architectural decision arises that §7 does not answer.
2. A correction appears to require editing ADR-0010 or ADR-0011. It does not;
   see §17. If it seems to, the correction has been misread.
3. A documentation correction appears to require a source change. It does not;
   every truth in §10 is already true of the code at the baseline. If a document
   cannot be made true without changing code, the document is describing
   something ATLAS-TASK-0014 did not deliver, and that is a finding to report,
   not to fix.
4. Making a statement true appears to require asserting that the system works
   end to end. Truths T-9 and T-10 are not negotiable; a wording that cannot
   satisfy them is the wrong wording.
5. The edge count cannot be established unambiguously from AST evidence, or the
   derivation returns anything other than the five edges in §11.1.
6. A test or contract turns out to require a change outside §8.
7. Any new package dependency would be required. None is.
8. The scope expands beyond documentation correction for any reason.

In every case: report both pieces of conflicting evidence and explain the
conflict. Do not silently reconcile them.

---

## 17. Relationship to ADR-0010 and ADR-0011

**Both ADRs are Accepted and immutable. This task edits neither.**

`docs/adr/README.md` defines exactly four statuses — `Proposed`, `Accepted`,
`Superseded by ADR-NNNN`, `Deprecated`. There is no amendment status, and
ATLAS-TASK-0013 removed the phrase "amending or superseding" from the roadmap
for that reason.

Both ADRs contain statements about `atlas.execution` that no longer describe the
repository:

- ADR-0010, under *Not guaranteed*: "**Nothing consumes a verdict.**
  `atlas.execution` is still a stub."
- ADR-0011, in its opening context, contains its own reference to
  `atlas.execution` as a stub.

**These are historical decision-record content and are intentionally preserved.**
ADR-0011 states the governing rule itself: the correction "belongs in the
roadmap's completed record and in the living documents, never in ADR-0010
itself." This task is the living-document half of that rule.

Accordingly, this task must not:

- edit either ADR;
- add a footnote, marginal note or cross-reference to either ADR;
- create an ADR-0012 to record the correction;
- state, in any corrected document, that either ADR's wording has been
  corrected, superseded or amended. It has not been.

### The edge count and ADR-0011

ADR-0011 refers to `execution → broker` as "the fourth edge in the graph". The
AST-derived census at the baseline finds five edges between feature packages
(§11.1).

For this task:

1. The current repository fact is **five**, derived from the AST, and that is
   the number `docs/architecture/overview.md` must state.
2. ADR-0011 is immutable and is not edited.
3. No corrected document may claim that ADR-0011's wording has been corrected.
4. No explanation of the difference is offered here, and none is to be written
   into any document. The discrepancy is recorded, not reconciled.

A reader comparing the two will find a five-edge census in the living document
and a "fourth edge" in an immutable decision record. That is the intended
outcome of the rule above, and it is not a defect to be resolved by this task.

---

## Roadmap

`docs/ROADMAP.md` is not modified by this task. Its row for ATLAS-TASK-0015 —
and the replacement of its current sentence stating that nothing declares what
ATLAS-TASK-0015 will be — is written after this specification has been reviewed
and explicitly authorised, and after the implementation has merged, following
the pattern of ATLAS-TASK-0011 through 0014.
