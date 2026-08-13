# ATLAS-TASK-0016 — Completing the living-document correction

**Status:** Specified, not implemented
**Date:** 2026-08-12
**Baseline:** `e34d731017d650a59792d0a6ee51d413913631d8`
**Decision record:** None. This task creates no ADR and edits none. See §16.

This task is documentation-only. It adds no behaviour, no contract, no
dependency edge and no capability. Every correction it makes replaces a
statement that is false today with a fact already provable from the code at the
baseline commit above. Two of the three files it touches are test modules; only
their module docstrings change, and §12 states the mechanical check that proves
no test behaviour changed with them.

`docs/ROADMAP.md` does not list this task, by that file's own rule — every row
in its status table is a completed task citing a commit. The roadmap row is
written when this task merges, the way ATLAS-TASK-0011 through ATLAS-TASK-0015
were, and is not part of the implementation. See §8.

---

## 1. Status

Specified, not implemented. No branch, commit, pull request or CI run exists for
this task, and none is cited anywhere in this document.

The baseline is `e34d731017d650a59792d0a6ee51d413913631d8` on `main`, with a
clean working tree, no divergence from `origin/main`, and an empty stash. The
implementer must confirm that state before making any change (§13.1).

---

## 2. Purpose

ATLAS-TASK-0013 enumerated, by name, every location in the repository that
carried the claim that `atlas.execution` was an empty stub consuming no
`RiskVerdict`. ATLAS-TASK-0014 made every one of them false. ATLAS-TASK-0015
corrected two of the four.

This task corrects the remaining two, and nothing else.

---

## 3. Context

### 3.1 The enumeration exists, and it is the repository's own

`docs/ROADMAP.md:562-565`, written by ATLAS-TASK-0013, states:

> Every other occurrence of that wording was checked and left alone.
> `README.md`, `docs/architecture/overview.md`,
> `packages/strategy/src/atlas/strategy/README.md` and both boundary tests name
> `atlas.execution` alone and are still true.

Four entries. Their status at this baseline:

| Enumerated at ATLAS-TASK-0013 | Status now | Closed by |
|---|---|---|
| `docs/architecture/overview.md` | Corrected | ATLAS-TASK-0015 (P-1…P-5) |
| `packages/strategy/src/atlas/strategy/README.md` | Corrected | ATLAS-TASK-0015 (P-6) |
| `README.md` | **Still false** | — |
| both boundary tests | **Still false** | — |

### 3.2 Why the remaining two survived

Neither survived because it was judged true.

**`README.md` was never surveyed by ATLAS-TASK-0015.** That task's problem
statement lists six defects across three files; the repository root `README.md`
appears in none of them, in none of its §5 scope, and in none of its fourteen
§6 non-goals. The only mention of it anywhere in that specification is
`docs/tasks/ATLAS-TASK-0015.md:389-391`, an aside explaining that the
`"README.md"` entry in `REQUIRED_ROOT_FILES` refers to the root README rather
than a package one — in the course of deciding a different question. The
implementation of ATLAS-TASK-0015 did exactly what it was specified to do. The
gap is in the survey, not in the work.

**Both boundary tests were excluded by decision.** ATLAS-TASK-0015 non-goal 2
forbids modifying, adding or deleting any test. That is a recorded scope
boundary, which is why these two docstrings are deferred work rather than an
escaped defect.

### 3.3 This is the third occurrence of this drift

ATLAS-TASK-0013 corrected this class of stale statement. ATLAS-TASK-0015
corrected it again, and its own §3 recorded the recurrence: "This is the second
occurrence of this drift." This task is the third pass, and it is the one that
empties the ATLAS-TASK-0013 list.

The repository has already ruled on the mechanical remedy and rejected it.
`docs/ROADMAP.md:554-555`: "That banner is the one copy no test binds, and it
stays that way deliberately — a test that read prose would make the banner's
wording a contract." Adding a freshness test is therefore not available to this
task, and §6.15 forbids it. What is available is decision **D-1** in §7, which
removes one drifting duplicate rather than re-dating it.

### 3.4 What is true at the baseline, verified from source

- `packages/execution/src/atlas/execution/contracts.py` defines
  `ExecutionPolicy` (frozen, `extra="forbid"`, fields `order_type` and an
  optional `price`) and `build_order_request(verdict, policy)`.
- `packages/execution/src/atlas/execution/__init__.py` exports both:
  `__all__ = ["ExecutionPolicy", "build_order_request"]`.
- An approved `RiskVerdict` and a caller-supplied `ExecutionPolicy` become an
  `atlas.broker.OrderRequest` carrying the verdict's `approved_volume`; a
  rejected verdict becomes `None`.
- The edge `atlas.execution → atlas.risk` is live, written under a
  `TYPE_CHECKING` guard.

Equally verified, and equally load-bearing for the wording this task produces:

- Nothing anywhere maps a `TradeIntent` to a `RiskVerdict`. `atlas.risk` exports
  five names — `RISK_MODEL_CONFIG`, `RejectionReason`, `RiskVerdict`,
  `TradeIntent`, `VerdictStatus` — and no decision function.
- No layer owns or constructs a `BrokerAdapter` outside `packages/broker/`.
- Nothing outside the test suite calls `build_order_request` or
  `Strategy.propose`. No module under `apps/` or `scripts/` imports
  `atlas.execution`, `atlas.risk` or `atlas.strategy`.

The corrections in this task must leave that second list legible. See §10,
truth **T-15**, and §15.4.

---

## 4. Problem statement

Four statements across three files are false at the baseline. Line numbers are
relative to `e34d731017d650a59792d0a6ee51d413913631d8` and are given for
location only; the implementer must match on text, because the numbers shift as
edits are applied.

| # | Location | Current text | Why it is false |
|---|---|---|---|
| P-1 | `README.md:27` | "Last completed: **ATLAS-TASK-0012 — the strategy boundary**." | Three tasks behind. `docs/ROADMAP.md:27-29` records ATLAS-TASK-0013, 0014 and 0015 as ✅ Complete with cited commits. |
| P-2 | `README.md:101-102` | "`atlas.execution` is still an empty stub, so nothing consumes a verdict." | Both clauses false since ATLAS-TASK-0014 (§3.4). The package holds two public names and consumes a `RiskVerdict`. |
| P-3 | `tests/unit/risk/test_risk_boundary.py:11-12, 16` | ":mod:`atlas.execution` is still an empty stub, so there is no consumer to observe…"; "The rest arrives with the task that implements execution." | The stub claim is false; the consumer exists; the task that implements execution has arrived (ATLAS-TASK-0014). |
| P-4 | `tests/unit/strategy/test_strategy_boundary.py:18` | "…reach :mod:`atlas.execution`, which is still an empty stub." | The appositive is false. The surrounding claim — that nothing in `atlas.strategy` can reach execution — is true and is not a defect. |

### 4.1 The blast radius of P-2

P-2 is not a self-contained clause. Two neighbouring sentences depend on it and
become false, or stay false, if only the clause itself is edited.

`README.md:102-104` reads "Every package below other than those named above is
an importable unit with a documented responsibility and no implementation, by
design." The packages "named above" are `common`, `config`, `broker`, `risk` and
`strategy`. `atlas.execution` is not among them, so this sentence asserts by
omission that `atlas.execution` has no implementation. It has one. Truth
**T-3** requires that the corrected Status section name `atlas.execution` among
the packages holding contents, which is what makes this sentence true again.

`README.md:99` reads "**No trading logic exists yet.** The two boundaries above
are contracts, not controls". The count refers to the risk and strategy
paragraphs. Correcting P-2 by adding an execution paragraph, without touching
this sentence, leaves a stale integer of exactly the kind ATLAS-TASK-0015
corrected at `docs/architecture/overview.md:52` ("Three edges"). Truth **T-4**
forbids that outcome.

### 4.2 What P-3 and P-4 do *not* make false

In both test docstrings the **conclusion** is still correct and must survive.

The risk docstring concludes that the behavioural half of the invariant "is not
provable today" and that what is asserted below is the structural half alone.
That remains true — nothing outside the test suite produces a `TradeIntent` and
nothing anywhere turns one into a `RiskVerdict`. What is stale is the *reason
given* for it, not the conclusion. The same holds for the strategy docstring's
"what is asserted below is the structural half and nothing more."

This distinction is the whole shape of the task. The correction replaces a stale
reason with the true one and leaves every claim about test coverage exactly as
strong as it was. A correction that made either docstring claim wider coverage
would be a defect, not a fix; see §15.4.

### 4.3 Observed and deliberately excluded

`README.md:218` lists `docs/` as "adr, architecture, api, runbooks, operations"
and does not mention `docs/tasks/`, which has existed since ATLAS-TASK-0014.
This is an incomplete enumeration rather than a false statement, it is not on
the ATLAS-TASK-0013 list this task exists to empty, and `docs/tasks` is not in
`REQUIRED_DIRECTORIES` in `tests/contract/test_repository_structure.py`. It is
recorded here so that it is neither lost nor silently swept into this task's
diff. **It is out of scope** (§6.16).

---

## 5. Scope

Exactly three files are corrected:

1. `README.md`
2. `tests/unit/risk/test_risk_boundary.py` — module docstring only
3. `tests/unit/strategy/test_strategy_boundary.py` — module docstring only

The work is: make the four defects in §4 read true, satisfying every truth in
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
2. Modify test **behaviour**. The only permitted change to a test file is its
   module docstring; see §12 and truth **T-16**.
3. Add or delete any test, fixture, helper or assertion.
4. Modify `docs/ROADMAP.md`, including its historical task narratives and the
   sentence at `docs/ROADMAP.md:60-62`.
5. Modify any file under `docs/adr/`, or create a new ADR. See §16.
6. Modify `docs/tasks/ATLAS-TASK-0014.md` or `docs/tasks/ATLAS-TASK-0015.md`.
   Those are historical records, and later tasks do not edit them.
7. Modify `docs/architecture/overview.md` or
   `packages/strategy/src/atlas/strategy/README.md`. ATLAS-TASK-0015 corrected
   both; they are true at this baseline and re-opening them is not a correction.
8. Modify `packages/risk/src/atlas/risk/README.md`. It is true at this baseline.
9. Modify `pyproject.toml`, `poetry.lock`, `mypy.ini`, `ruff.toml`, `pytest.ini`,
   `.pre-commit-config.yaml`, `Dockerfile`, `docker-compose.yml`, or anything
   under `.github/`, `config/`, `infrastructure/` or `scripts/`.
10. Implement `TradeIntent → RiskVerdict`, any risk control, a `RiskEngine` or a
    `RiskControl` protocol.
11. Introduce account or portfolio state.
12. Introduce a broker-owning layer, routing, fills, reconciliation, idempotent
    retry, venue integration, or MT5 trading methods.
13. Introduce events or message-bus infrastructure, market ingestion,
    persistence, transport, a run loop, or `atlas-core` orchestration.
14. Widen `ExecutionPolicy`, add `STOP_LIMIT`, add configuration, or change any
    of the five existing package dependency edges or create a new one. See §11.
15. Add any test whose purpose is to bind documentation prose to exact wording.
    `docs/ROADMAP.md:554-555` already ruled against it, and D-1 changes the
    form of the passage such a test would have frozen.
16. Correct `README.md:218`, or any other statement that is incomplete rather
    than false. Only the four defects in §4 are in scope.
17. Tidy, reflow or reword prose that is not false.

---

## 7. Authoritative decisions

Two questions the implementer would otherwise have to answer are answered here.
Both are resolved from repository evidence; neither invents policy.

### D-1 — The `README.md` status line stops naming a task and defers to the roadmap

`README.md:27-28` must no longer carry a task number. It names
`docs/ROADMAP.md` as the authoritative record of which tasks are complete, and
stops duplicating its last row.

*Evidence that the fact is a duplicate.* `docs/ROADMAP.md:3-5` claims the
authority in its own words: "The authoritative record of which ATLAS tasks are
complete and what comes next. A task is **Complete** only when it is merged on
`main` and every gate in the repository's definition of done passed on that
commit." Its status table at `docs/ROADMAP.md:12-29` holds every task and its
commit. `README.md:27-28` restates the last row of that table and then links to
the table. It carries no fact the roadmap does not.

*Evidence that the duplicate is what drifts.* The Status section names tasks in
two ways. Inline, in the narrative — "`atlas.risk` has its first contents
(TASK-0011)" at `README.md:73`, "(TASK-0012)" at `README.md:85`, and eight
similar at `README.md:34-71`. Those pin a fact that has not moved and are still
correct after five subsequent tasks. The summary line at `README.md:27` pins a
fact that moves on every merge, and it is the only line in the file that has
gone stale. Removing the drifting duplicate while keeping the non-drifting
narrative removes the defect rather than re-arming it.

*Why this does not contradict ATLAS-TASK-0015's D-1.* That decision kept
`docs/architecture/overview.md`'s banner dated rather than undating it, choosing
a marker that announces its own staleness over one that is silently wrong. It
was choosing between two forms of a summary that had to exist: the overview's
banner enumerates which packages hold implementation, and the roadmap does not
record that. `README.md:27` has no such content. The third option — do not
duplicate the fact at all — was not available there and is available here, and
it is strictly better than either form of duplicate. The rejected alternative,
re-dating the line to name ATLAS-TASK-0015, is recorded here as considered:
it cures P-1 for exactly one task and reproduces it on the next.

*What must not happen.* No dated status banner is added to `README.md` in place
of the removed line. The Status section's own narrative, corrected under P-2, is
what tells a reader where the project is.

### D-2 — The docstring corrections are documentation, not test changes

Correcting `P-3` and `P-4` changes prose inside two `.py` files and changes no
test. §12 states the evidence and the mechanical check. This is why §6.2 forbids
modifying test behaviour rather than forbidding modifying test files, and the
distinction is enforced by truth **T-16**, not by assertion.

---

## 8. Files permitted to change

During implementation, exactly these:

| Path | Change |
|---|---|
| `README.md` | Corrections P-1 and P-2 |
| `tests/unit/risk/test_risk_boundary.py` | Correction P-3 — module docstring only |
| `tests/unit/strategy/test_strategy_boundary.py` | Correction P-4 — module docstring only |

Plus this specification file, `docs/tasks/ATLAS-TASK-0016.md`, which already
exists and is not modified by the implementation.

**`docs/ROADMAP.md` is not in this list.** Its row for this task — including the
replacement of the sentence at `docs/ROADMAP.md:60-62`, which currently reads
"Nothing beyond ATLAS-TASK-0015 is defined, and nothing here declares what
ATLAS-TASK-0016 will be" — is a post-merge closeout step performed under
separate authorisation, exactly as it was for ATLAS-TASK-0011 through 0015. It
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

**Historical task records.** `docs/tasks/ATLAS-TASK-0014.md` and
`docs/tasks/ATLAS-TASK-0015.md`. Both contain the string "empty stub" in
statements that were true when written; both are dated accounts and neither is a
live claim about today.

**`tests/unit/execution/test_execution_boundary.py`.** Its docstring at
`:22-24` reads "That a running pipeline routes every intent through risk needs a
pipeline, and there is still no engine, no registry and no consumer." That
sentence is about a consumer of the *`OrderRequest`* `atlas.execution` produces,
and it is **true** — no layer owns a `BrokerAdapter`. It matches the search
patterns this task works from and is the likeliest file to be swept up by a
repository-wide edit. It must not change.

**Everything else outside §8**, and in particular every file under
`packages/*/src/`, `apps/`, `.github/`, `config/`, `infrastructure/`, and
`scripts/`, and every file under `tests/` other than the two named in §8.

**Passages inside the three permitted files that must not change**, because they
are true and correcting them would introduce a new falsehood:

| Passage | Why it stays |
|---|---|
| `README.md:5` — the `v0.2.0-alpha` banner | Matches `pyproject.toml`'s `version = "0.2.0a0"`. ATLAS-TASK-0013 established this parity. |
| `README.md:34-41` — "the vendor-neutral `BrokerAdapter` port of 31 methods", "implements 24 of the 31", "The remaining seven methods raise `NotImplementedError`" | All three verified at the baseline: `BrokerAdapter` declares exactly 31 public methods and the MT5 adapter raises `NotImplementedError` exactly seven times. |
| `README.md:43-48` — the `atlas.broker.mock` paragraph, "satisfying all 31 methods" | True. `MockBrokerAdapter` implements the whole port. |
| `README.md:99-101` up to "no real strategy" — "**No trading logic exists yet.** The two boundaries above are contracts, not controls: there is no sizing rule, no exposure limit, no drawdown control, no kill switch and no real strategy." | Entirely true. ATLAS-TASK-0014 added a *consumer* of verdicts and nothing that *reaches* one. This is the sentence most likely to be swept up by an over-eager edit, and only its word "two" is at risk (T-4). |
| `README.md:104-105` — "`atlas.config` is the exception — configuration *is* foundation, so it is fully implemented and tested." | True. |
| `README.md:117-154` — the flow diagram | It draws the intended architecture, not the implemented one, exactly as `docs/architecture/overview.md:36-42` does. Unchanged by ATLAS-TASK-0014. |
| `README.md:319-322` — "`tests/integration/` and `tests/e2e/` are established but empty" | True. Both directories contain only a README. |
| `README.md:347-350` — the `restart: "no"` paragraph | True, and tied to the absence of a run loop, which this task does not change. |
| `tests/unit/risk/test_risk_boundary.py:1-7` — the summary of what the module asserts | True and unchanged by ATLAS-TASK-0014. |
| `tests/unit/risk/test_risk_boundary.py:10` — "The invariant is that execution acts only on approved risk output." | True. It states the invariant, not its implementation status. |
| `tests/unit/risk/test_risk_boundary.py:13-15` — "What is provable now is the structural half — risk exposes no path to an order, and the only place an approved volume exists is on a verdict whose status is ``APPROVED`` — and that is all that is asserted below." | True, and it is the sentence that keeps the docstring's coverage claim honest. See §4.2. |
| `tests/unit/strategy/test_strategy_boundary.py:1-13` — the summary of what the module asserts | True. |
| `tests/unit/strategy/test_strategy_boundary.py:16-18` — "The invariant is that a strategy proposes and cannot bypass risk. Half of that is provable today — nothing here can obtain an adapter, name an order or reach :mod:`atlas.execution`" | True. Only the trailing appositive "which is still an empty stub" is false; the claim about what `atlas.strategy` can reach is correct and must survive. |
| `tests/unit/strategy/test_strategy_boundary.py:21` — "what is asserted below is the structural half and nothing more" | True. See §4.2. |
| Every line of both test files outside the module docstring | Enforced mechanically by T-16 and §13.4, not by inspection. In particular the import allowlists at `test_risk_boundary.py:57-67` and `test_strategy_boundary.py:70-81`, and the synthetic source strings `"from atlas.execution import Executor"` at `test_risk_boundary.py:163` and `test_strategy_boundary.py:242`, which are test *inputs* proving the scanner can fail and are not claims about the repository. |

---

## 10. Exact documentation truths that must hold after implementation

Each truth below must be discoverable from the corrected files. The wording is
the implementer's; the fact is not.

**About `README.md`:**

- **T-1.** `README.md` does not state that `atlas.execution` is an empty stub,
  and does not state that nothing consumes a verdict.
- **T-2.** `README.md` states that `atlas.execution` consumes a `RiskVerdict`:
  an approved verdict, with a caller-supplied `ExecutionPolicy`, becomes an
  `OrderRequest` carrying the approved volume; a rejected verdict becomes
  `None`. It attributes this to ATLAS-TASK-0014, in the register the section's
  other paragraphs use.
- **T-3.** `atlas.execution` is among the packages the Status section names as
  holding contents, so that "Every package below other than those named above is
  an importable unit with a documented responsibility and no implementation" is
  true of the packages it still covers (§4.1).
- **T-4.** No numeric claim in the Status section is falsified by the
  correction. In particular, "The two boundaries above are contracts, not
  controls" must still count correctly after P-2 is applied.
- **T-5.** The Status section still states that no trading logic exists: no
  sizing rule, no exposure limit, no drawdown control, no kill switch, no real
  strategy.
- **T-6.** `README.md` no longer names a "last completed" task, and names
  `docs/ROADMAP.md` as the authoritative record of task status (D-1).

**About `tests/unit/risk/test_risk_boundary.py`:**

- **T-7.** The docstring does not state that `atlas.execution` is an empty stub,
  and does not state that there is no consumer to observe.
- **T-8.** The docstring still states that the behavioural half of the invariant
  is not provable today, and gives the true reason: nothing outside the test
  suite produces a `TradeIntent`, and nothing anywhere turns one into a
  `RiskVerdict`.
- **T-9.** The docstring's account of what *is* asserted below is unchanged in
  substance: the structural half, and nothing more.

**About `tests/unit/strategy/test_strategy_boundary.py`:**

- **T-10.** The docstring does not state that `atlas.execution` is an empty stub.
- **T-11.** The docstring still states that nothing in `atlas.strategy` can
  obtain an adapter, name an order or reach `atlas.execution`.
- **T-12.** If the docstring retains a clause about a missing consumer, that
  clause names what is missing — a consumer of a `TradeIntent`, because nothing
  maps an intent to a verdict — and cannot be read as "nothing consumes a
  verdict", which is false.
- **T-13.** The docstring's account of what *is* asserted below is unchanged in
  substance: the structural half, and nothing more.

**About the system as a whole — the truths that stop this correction becoming a
false capability claim:**

- **T-14.** `atlas.execution` does not route orders, does not own or construct a
  `BrokerAdapter`, does not place orders and does not reach a venue. The
  `OrderRequest` it produces is inert.
- **T-15.** There is still no running trading pipeline. Nothing produces a
  `TradeIntent` outside the test suite; nothing maps a `TradeIntent` to a
  `RiskVerdict`; no layer owns a `BrokerAdapter`. The request `atlas.execution`
  builds is received by nothing. No corrected sentence may state or imply
  otherwise.
- **T-16.** No source behaviour changes. For each of the two test files, the
  abstract syntax tree with the module docstring removed is identical to the
  baseline's. See §12 and §13.4.
- **T-17.** `atlas.risk` still holds its contracts and none of the controls that
  reach a decision. `atlas.market`, `atlas.features` and `atlas.regime` are
  still empty stubs.

---

## 11. Dependency graph requirements

**No dependency graph change is permitted.** This task creates no edge, removes
none, and changes none.

At the baseline there are **five** dependency edges between feature packages,
and every one of them runs downward:

| Edge | Names taken | Introduced by |
|---|---|---|
| `atlas.broker → atlas.common` | `Clock`, `ManualClock`, `RetryPolicy`, `SystemClock`, `retry_call` | ATLAS-TASK-0008 / 0009 |
| `atlas.risk → atlas.broker` | `OrderSide`, `Price`, `SymbolName`, `Volume` | ATLAS-TASK-0011 |
| `atlas.strategy → atlas.risk` | `TradeIntent` | ATLAS-TASK-0012 |
| `atlas.execution → atlas.risk` | `RiskVerdict` | ATLAS-TASK-0014 |
| `atlas.execution → atlas.broker` | `OrderRequest`, `OrderType`, `Price` | ATLAS-TASK-0014 |

`app:atlas-core → atlas.config` is an application-to-package edge, not an edge
between feature packages, and is not counted among the five.

The census after implementation must be identical to this table. It must be
derived from the repository's AST/import graph rather than counted by hand,
under the three conditions ATLAS-TASK-0015 §11.2 established, each of which has
already caused a wrong answer once:

1. **Parse the AST; do not grep for `^from atlas`.** The
   `atlas.execution → atlas.risk` import is written under a `TYPE_CHECKING`
   guard and is indented. A line-anchored grep misses it.
2. **Count `TYPE_CHECKING`-guarded imports as real edges.** `ast.walk` descends
   into `if TYPE_CHECKING:` blocks, and
   `tests/unit/execution/test_execution_boundary.py::test_the_import_scanner_sees_through_a_type_checking_guard`
   asserts that the repository's own scanners do so.
3. **Derive the owning package from the source-root directory** —
   `packages/<name>/` or `apps/<name>/` — and **not** by searching the path for
   the segment `atlas`. Under `packages/<pkg>/src/atlas/<pkg>/…` the first
   `atlas` segment is the PEP 420 namespace directory, and keying on it
   collapses every package into a single owner.

The derivation is run from a scratch script outside the repository. **No script,
tool or test is added to the repository by this task** (§6.1, §6.3).

For a change that edits Markdown and two module docstrings this is trivially
satisfied. It is checked anyway, because "no dependency change" is a claim this
task makes and an unchecked claim is the class of thing this task exists to
correct.

---

## 12. Test requirements

**No new test is required, and no test behaviour may change.**

### 12.1 Why a docstring correction is not a test change

*No test reads a test module's docstring.* The only docstring assertion in the
repository is
`tests/contract/test_repository_structure.py:209-213`, which reads
`importlib.import_module(module).__doc__` for each entry in `LEAF_MODULES` —
the declared `atlas.*` packages. No test module is a member. No test anywhere
imports `tests.unit.risk.test_risk_boundary` or
`tests.unit.strategy.test_strategy_boundary` and inspects `__doc__`.

*The `read_text` calls in both files read package source, not their own file.*
`tests/unit/risk/test_risk_boundary.py:147` and
`tests/unit/strategy/test_strategy_boundary.py:219` are helpers that read the
source of the package under test in order to walk its AST. Neither reads a file
under `tests/`.

*No test asserts on prose.* `docs/ROADMAP.md:554-555` records that the one
banner a test might have bound is deliberately unbound, for the reason §6.15
restates.

### 12.2 The check that proves it

Assertion is not evidence. For each of the two test files, the implementer must
mechanically compare the baseline and the corrected file:

1. Parse both with `ast.parse`.
2. Remove the module docstring from each tree — the leading
   `ast.Expr` whose value is an `ast.Constant` holding a `str`.
3. Compare `ast.dump(tree, include_attributes=False)` of the remainder.

The two dumps must be **identical strings**. This proves that every import,
constant, class, function, decorator, assertion and parametrisation is
byte-equivalent after parsing, and that the only thing that changed is the text
no interpreter acts on. Recording the two comparisons is what satisfies **T-16**
and **AC-9**.

### 12.3 Suite parity

The test count after implementation must be identical to `main` at the
baseline: **3296 tests collected**, all passing. A change is evidence that
something outside scope was touched. Coverage is not compared during local
verification, because the local quality gate does not measure it; CI does, and
this task does not introduce or alter coverage measurement — see AC-12.

*Structural tests affected:* none. `TestRepositoryLayout` requires `README.md`
to exist and does not read it. `TestPackageDeclarations`,
`TestNamespaceIntegrity`, `TestPackageContracts`, `TestToolchainParity` and
`TestConfigurationTree` are all unaffected, because no package source, no
configuration file and no declared module changes.

### 12.4 Formatting

Both test files are formatted by Black and linted by Ruff at
`line-length = 100`. A corrected docstring must satisfy both without any other
line in the file being reformatted. `.gitattributes` sets `* text=auto eol=lf`,
so no changed file may contain a CR byte.

---

## 13. Validation requirements

Every item below is a command whose output must be recorded. A criterion is met
only when its command has been run and its output shown — not when the change
looks right.

1. **Before any edit**, confirm the baseline: `git rev-parse HEAD` is
   `e34d731017d650a59792d0a6ee51d413913631d8`; `git status --short` is empty;
   `git diff --exit-code` and `git diff --cached --exit-code` both exit 0; the
   stash is empty; `git rev-list --left-right --count origin/main...HEAD` is
   `0 0`. Record the pre-existing local `task-00xx-*` branches so they are not
   confused with this task's.
2. **Record the baseline blobs** of the three permitted files, so §13.4 has
   something to compare against:
   `README.md` → `8f2f3b5bee3433f9b0817bd2946fb5d6121f6229`;
   `tests/unit/risk/test_risk_boundary.py` →
   `ecfae91ff5a9f7852c42f24c90dd17b0b9e8e615`;
   `tests/unit/strategy/test_strategy_boundary.py` →
   `4fec42f1e72f591a7e990b3d57fdf2f849c9fdf0`.
3. **Diff scope.** `git diff --name-only` lists exactly the three files in §8
   and nothing else. In particular `git diff --name-only -- packages/ apps/
   scripts/ .github/ config/ infrastructure/ docs/ pyproject.toml poetry.lock`
   is empty, and `git diff --name-only -- tests/` lists exactly the two
   boundary test files.
4. **AST equivalence.** Run the §12.2 comparison for both test files, using the
   baseline blob (`git show HEAD:<path>`) as the "before" side. Both must report
   identical dumps.
5. **ADRs byte-identical.** `git rev-parse HEAD:docs/adr/0010-…md` still returns
   `6f20807a73496c087a252145696dea4a3330d55b` and
   `git rev-parse HEAD:docs/adr/0011-…md` still returns
   `45600504bd9212db0a5efcf1eb4d85ebfc1595ed`.
6. **Historical records untouched.** `git diff --name-only -- docs/tasks/` is
   empty, and `git diff --name-only -- docs/ROADMAP.md` is empty.
7. **Edge census unchanged.** Run the §11 derivation before and after the edits.
   Both must return the same five edges.
8. **Protected passages unchanged.** For each passage in §9's table, compare
   against the baseline blob. `git diff` on the three files must show no hunk
   overlapping them.
9. **No CRLF.** For each changed file, `tr -d -c '\r' < <file> | wc -c` returns
   `0`.
10. **Quality gate green.** Run the repository's gate — `scripts/quality.ps1` on
    Windows, `scripts/quality.sh` otherwise — with full output captured. Ruff,
    Black and MyPy must be clean; pytest must report exactly **3296** tests, all
    passing. Coverage is not compared, because the local gate does not measure
    it; CI does, and this task does not alter that — see AC-12. **Container &
    Compose runs only in CI and cannot be run locally; say so rather than
    implying it passed.**
11. **Read all three corrected files end to end.** Truths T-14, T-15 and T-17
    cannot be checked by command. The specific failure to hunt for is a set of
    sentences that are each individually true but together imply the chain runs.
12. **CI**, when the change reaches `main` or a pull request, verified by
    `head_sha` rather than by recency — a run against a pull-request head is not
    a run against the merge commit. If CI has not been run, state **CI NOT RUN**.

Nothing further is required. No validation is added for ceremony.

---

## 14. Acceptance criteria

- **AC-1.** `git diff --name-only` against the baseline lists exactly
  `README.md`, `tests/unit/risk/test_risk_boundary.py` and
  `tests/unit/strategy/test_strategy_boundary.py`.
- **AC-2.** `git grep -n "empty stub" -- README.md tests/` returns nothing.
  Matches under `docs/` are expected — `docs/ROADMAP.md`, `docs/adr/0010-…md`,
  `docs/tasks/` and this specification — and are not violations, because those
  are historical records or statements about packages other than
  `atlas.execution`.
- **AC-3.** `git grep -n "still a stub" -- README.md tests/` returns nothing.
- **AC-4.** `git grep -n "ATLAS-TASK-0012" -- README.md` returns nothing, and
  `git grep -n "Last completed" -- README.md` returns nothing (D-1, T-6). The
  inline narrative references `(TASK-0011)` and `(TASK-0012)` at
  `README.md:73` and `README.md:85` are expected to remain: they pin facts that
  have not moved.
- **AC-5.** Truths T-1 through T-6 hold in `README.md`.
- **AC-6.** Truths T-7 through T-9 hold in
  `tests/unit/risk/test_risk_boundary.py`.
- **AC-7.** Truths T-10 through T-13 hold in
  `tests/unit/strategy/test_strategy_boundary.py`.
- **AC-8.** Truths T-14, T-15 and T-17 hold. No corrected sentence asserts a
  running pipeline, a producer of `TradeIntent` outside tests, a mapping from
  `TradeIntent` to `RiskVerdict`, or any layer owning a `BrokerAdapter`.
- **AC-9.** T-16 holds, demonstrated by the §12.2 AST comparison for both test
  files, with both outputs recorded.
- **AC-10.** `git diff -- docs/ packages/ apps/ scripts/ .github/ config/
  infrastructure/ pyproject.toml poetry.lock` is empty, and both ADR blob hashes
  are unchanged.
- **AC-11.** `git diff -- tests/unit/execution/` is empty.
- **AC-12.** The quality gate passes, reporting exactly **3296** tests — the
  baseline count. Coverage is not compared during local verification, because
  the local gate does not measure it: `pytest.ini` enables no `--cov` and
  `scripts/quality.ps1` runs plain `pytest`, so a local run produces no figure
  to compare and reporting one would mean inventing it. CI does measure
  coverage — `.github/workflows/ci.yml` runs `pytest --cov --cov-report=xml
  --cov-report=term-missing` — but this task neither introduces nor alters
  coverage measurement.
- **AC-13.** Every passage listed in §9's protected table is byte-for-byte
  unchanged.
- **AC-14.** No changed file contains a CR byte.
- **AC-15.** The derived edge census after implementation is the same five edges
  as before it.
- **AC-16.** No file was created by the implementation. In particular
  `packages/execution/src/atlas/execution/README.md` does not exist —
  ATLAS-TASK-0015 §12 ruled it not required, and that is a closed question, not
  a deferral.

---

## 15. Stop conditions

Stop and report rather than deciding, if:

1. An architectural decision arises that §7 does not answer.
2. A correction appears to require editing an ADR. It does not; see §16.
3. A documentation correction appears to require a source change. It does not;
   every truth in §10 is already true of the code at the baseline. If a document
   cannot be made true without changing code, the document is describing
   something ATLAS-TASK-0014 did not deliver, and that is a finding to report,
   not to fix.
4. Making a statement true appears to require asserting that the system works
   end to end, or appears to require either test docstring to claim wider
   coverage than it claims today. Truths T-14, T-15 and T-9/T-13 are not
   negotiable; a wording that cannot satisfy them is the wrong wording.
5. The §12.2 AST comparison reports any difference.
6. The edge census returns anything other than the five edges in §11.
7. A fifth stale statement is found. Report it with its evidence; do not fold it
   into this task's diff. §4.3 is the precedent for how such a finding is
   recorded.
8. The scope expands beyond documentation correction for any reason.

In every case: report both pieces of conflicting evidence and explain the
conflict. Do not silently reconcile them.

---

## 16. Relationship to ADR-0010 and ADR-0011

**Both ADRs are Accepted and immutable. No ADR is required by this task, and
this task edits none.**

`docs/adr/README.md` defines exactly four statuses — `Proposed`, `Accepted`,
`Superseded by ADR-NNNN`, `Deprecated`. There is no amendment status, and
ATLAS-TASK-0013 removed the phrase "amending or superseding" from the roadmap
for that reason.

Both ADRs contain statements about `atlas.execution` that no longer describe the
repository — `docs/adr/0010-…md:191-192` ("Nothing consumes a verdict.
`atlas.execution` is still a stub") and `docs/adr/0011-…md:10`. **These are
historical decision-record content and are intentionally preserved.** ADR-0011
states the governing rule itself: the correction "belongs in the roadmap's
completed record and in the living documents, never in ADR-0010 itself." This
task is the last instalment of the living-document half of that rule.

An ADR is required when a decision changes the architecture. This task changes
no contract, no boundary, no edge and no behaviour; **T-16** proves the last of
those mechanically. Decision D-1 governs where a fact is recorded in one
document and is not an architectural decision.

Accordingly, this task must not:

- edit either ADR;
- add a footnote, marginal note or cross-reference to either ADR;
- create an ADR-0012 to record the correction;
- state, in any corrected document, that either ADR's wording has been
  corrected, superseded or amended. It has not been.

ADR-0011 refers to `execution → broker` as "the fourth edge in the graph" while
the AST census finds five. ATLAS-TASK-0015 §17 recorded that discrepancy and
declined to reconcile it. This task does not revisit it, offers no explanation
for it, and writes none into any document.

---

## 17. Separation from future architectural decision work

This task is a documentation correction. It is **not** an architectural decision
gate, and it must not be treated as a step toward one.

Two directions are the repository's substantive next work, and each is blocked
behind a decision the repository has deliberately declined to make:

- **A producer for `RiskVerdict`** — the controls that map a `TradeIntent` to a
  verdict. Every one of them reads account or portfolio state, and
  `docs/adr/0010-…md:198-200` declined to define that contract "before the
  controls that read it exist". `docs/adr/0011-…md:142-147` restates the
  deferral as still in force. A concrete control cannot be written until a new
  ADR settles it.
- **The layer that owns broker interaction** — named in ADR-0011's Decision.
  ADR-0011 rejects `atlas.execution` as its home and names no replacement;
  `AtlasSettings` carries no broker or venue surface; and no `BrokerAdapter` is
  constructed anywhere outside `packages/broker/`. Three unmade decisions, not
  one.

Neither is in this task's scope (§6.10, §6.12), neither is prepared for by it,
and nothing in this task's diff may be justified as groundwork for either. When
one of them is taken up, it begins with an owner decision gate and a new ADR,
in the sequence ATLAS-TASK-0014 followed — not with a documentation pass.

Completing the ATLAS-TASK-0013 enumeration is worth doing on its own terms: it
is the only outstanding work in the repository that requires no architectural
decision, and leaving a known-false statement in the front page of the
repository is the defect the previous two correction tasks existed to remove.

---

## Roadmap

`docs/ROADMAP.md` is not modified by this task. Its row for ATLAS-TASK-0016 —
and the replacement of its current sentence stating that nothing declares what
ATLAS-TASK-0016 will be — is written after this specification has been reviewed
and explicitly authorised, and after the implementation has merged, following
the pattern of ATLAS-TASK-0011 through 0015.
