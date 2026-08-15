# ATLAS-TASK-0021 — Living-document correction after application ownership of `BrokerAdapter`

**Status:** Proposed for review. Not authorised, not implemented.
**Date:** 2026-08-15
**Baseline:** `62d7ac4771df40d805a2c3a410f7e1b13755e6c1`
**Decision record:** None. This task creates no ADR and edits none. See §16.

This task is documentation-only. It adds no behaviour, no contract, no
dependency edge, no capability and no test. It touches one file and one passage
inside it. It replaces a statement that is false today with a fact already
provable from the code at the baseline commit above.

It is the fourth instalment of the pattern ATLAS-TASK-0015, ATLAS-TASK-0016 and
ATLAS-TASK-0019 established: when a task changes what the repository is, the
living documents are corrected afterwards, in a separate diff, against a written
list of exactly which passages may move.

**This document is a proposal.** It authorises nothing. ATLAS-TASK-0020 §17.3
and `docs/ROADMAP.md:1168-1172` both record that this correction belongs to a
separate task; neither names a number for it, and no authorisation to implement
one exists. The specification is written first, reviewed, and explicitly
authorised before any edit is made — the sequence ATLAS-TASK-0015 through
ATLAS-TASK-0020 followed without exception.

---

## 1. Status

Proposed, not authorised, not implemented. No branch, commit, pull request or CI
run exists for this task, and none is cited anywhere in this document.

The baseline is `62d7ac4771df40d805a2c3a410f7e1b13755e6c1` on `main`, with a
clean working tree and no divergence from `origin/main`. The implementer must
confirm that state before making any change (§13.1).

At the baseline, `docs/architecture/overview.md` has blob
`ebbd273dd7cb49b9fc3704cec45a46f356f31e0a`.

### 1.1 Why ATLAS-TASK-0021 is the correct identifier

The number is derived from the repository, not chosen.

- **The sequence is dense and unbroken through 0020.** `docs/ROADMAP.md`'s
  status table holds 21 rows running `ATLAS-TASK-0001`, `0001A`, then `0002`
  through `0020` with no gap. `0020` is the highest identifier the repository
  has ever issued.
- **0021 is unissued.** Repository-wide search for `ATLAS-TASK-0021` returns one
  hit, `docs/ROADMAP.md:85`, and it is a *denial*: "this file declares no
  ATLAS-TASK-0021, no ADR-0014 and no work after them." Nothing claims the
  number, and nothing else in the repository mentions it.
- **A denial is not a prohibition.** That sentence records that no such task had
  been declared when it was written. It is the same sentence ATLAS-TASK-0019 was
  numbered against — `docs/tasks/ATLAS-TASK-0019.md:543-546` records that the
  roadmap then said "this file declares no ATLAS-TASK-0019 and no work after
  it", and 0019 was nevertheless correctly numbered 0019. The sentence is
  replaced at closeout, by the same step that writes the row.
- **Identifiers are issued in order, and the suffix form is reserved.**
  `0001A` is the only non-integer identifier, and `docs/ROADMAP.md:15` shows
  what it is for: `ATLAS-TASK-0001A` is "Repository bootstrap review fixes", a
  follow-up folded into an already-numbered task. This task is not a review fix
  to ATLAS-TASK-0020 — 0020 is complete, merged and CI-green — so `0020A` would
  be the wrong form.
- **A missing spec file is not a missing number.** `docs/tasks/` holds
  `0014, 0015, 0016, 0017, 0019, 0020` and no `0018`. ATLAS-TASK-0018 changed
  one row of `docs/adr/README.md` and has a roadmap row without a specification
  file. The gap in `docs/tasks/` therefore does not mean 0018 is available, and
  the numbering authority is the roadmap table, not the directory listing.

**Nothing in this section issues the number.** It identifies the number that
would be correct if this specification is authorised. If the reviewer declines
the task, 0021 remains unissued and the roadmap's denial at `:85` stays true.

---

## 2. Purpose

`docs/architecture/overview.md:118-121` tells a reader that the chain the data
flow draws is not joined end to end, and gives three reasons. One of the three
stopped being true on 2026-08-14.

ATLAS-TASK-0020 delivered `BrokerOwner` in
`apps/atlas-core/src/atlas/apps/core/broker_ownership.py`, implementing ADR-0013
"The application owns the adapter". The document still states that **no layer
owns a `BrokerAdapter`**. That is the defect this task removes.

The defect is narrow and the correction must be narrower still. The passage
contains four clauses; exactly one is false, and the other three — including the
passage's conclusion — remain true for reasons ATLAS-TASK-0020 was careful to
preserve. A correction that fixes the false clause by weakening the true ones
would replace an understatement of what exists with an overstatement of it, and
an overstatement here is the more dangerous error: it would tell a reader that
Atlas can place an order.

---

## 3. Context

### 3.1 What ATLAS-TASK-0020 delivered, and what it deliberately did not

Implementation commit `55fcbd6161d49c986b0033f37493195c3226493e`, CI run
`31850488760` green on that exact `head_sha`, closeout
`62d7ac4771df40d805a2c3a410f7e1b13755e6c1`.

**Delivered**, all verifiable at the baseline:

- `apps/atlas-core/src/atlas/apps/core/broker_ownership.py` defines
  `BrokerOwner`, exported as that module's sole `__all__` entry. It is the first
  module under `apps/` that names the port.
- `BrokerOwner.__init__(adapter: BrokerAdapter)` stores the instance it is
  handed. It performs no I/O, constructs no adapter, and does not branch on
  which implementation it received.
- Access is governed: `BrokerOwner.adapter` raises `BrokerNotConnectedError`
  before `start()` and again after `stop()`. The public surface is exactly three
  names — `adapter`, `start`, `stop`.
- Lifecycle sequencing is `start()` → `adapter.connect()` and `stop()` →
  `adapter.disconnect()`. A second `start()` raises `RuntimeError`; `stop()` is
  a no-op before `start()` and after a previous `stop()`.
- 200 tests were added; the suite is 3589 at the baseline.

**Deliberately not delivered**, each recorded in the task's own text:

- **No adapter is constructed in a process.** §11.2, §11.3.
  `apps/atlas-core/src/atlas/apps/core/__main__.py` is byte-identical to its
  pre-task state.
- **No broker or venue configuration surface.** §11.4: `AtlasSettings` carries
  `environment, app_name, debug, logging, postgres, redis, duckdb, risk` and no
  broker section. ADR-0013 `:101-105` declined to add one.
- **No supervision.** `reconnect()` and `health()` are called by nothing. The
  owner implements two of ADR-0013's five responsibilities in full — holding and
  governing access — plus lifecycle sequencing limited to connect and
  disconnect. Supervision is unimplemented.
- **The owner is unwired.** §16 stop condition 6: "The owner is meant to sit
  unwired at the end of this task." Nothing outside the test suite constructs a
  `BrokerOwner` or hands one an adapter.

### 3.2 The established treatment when a document's claim is falsified

Three precedents, all in this repository, all the same shape:

| Task | What changed | What the correction did |
|---|---|---|
| ATLAS-TASK-0015 | `atlas.execution` gained `build_order_request` | Corrected the passages that denied it, in a separate diff, against a written list |
| ATLAS-TASK-0016 | The same drift, two passages missed | Corrected exactly those two and recorded what it did *not* touch |
| ATLAS-TASK-0019 | `atlas.risk` gained `evaluate_exposure` | Corrected the banner alone; §4.2 listed nine passages checked and left |

Each corrected a false statement without expanding the document's claims, and
each carried a §4.2-style list of statements checked and found still true. That
list is the part of the pattern that matters most here, because this passage's
surviving clauses sit in the same four lines as the false one.

### 3.3 The banner's form is already decided, and this task does not reopen it

`docs/architecture/overview.md:3-25` is a status banner whose form was fixed by
ATLAS-TASK-0015 D-1: it is dated to a task, and it names `docs/ROADMAP.md` as
the authority where the two disagree (`:24-25`). ATLAS-TASK-0019 D-1 re-dated it
from `ATLAS-TASK-0014` to `ATLAS-TASK-0018`, on the reasoning that the banner
exists to be compared against the roadmap's last row.

At the baseline the banner reads `> **Status at ATLAS-TASK-0018.**` and the
roadmap's last row is `ATLAS-TASK-0020`. Whether this task re-dates it is **not
decided by this specification** — see D-2 in §7, which is referred to the
reviewer rather than resolved.

---

## 4. Problem statement

### 4.1 The passage, clause by clause

`docs/architecture/overview.md:118-121` reads, in full:

> The chain the data flow draws is not joined end to end. Nothing outside the
> test suite produces a `TradeIntent` or hands one to `atlas.risk`, and no layer
> owns a `BrokerAdapter` — so the request `atlas.execution` builds is, today,
> received by nothing.

| | Clause | Verdict at the baseline |
|---|---|---|
| **C-1** | "The chain the data flow draws is not joined end to end." | **True.** No engine, run loop, scheduler or composition root exists. Nothing calls `build_order_request`. The owner is unwired. |
| **C-2** | "Nothing outside the test suite produces a `TradeIntent` or hands one to `atlas.risk`" | **True.** Unchanged by ATLAS-TASK-0020, which touched no strategy, risk or execution file. |
| **P-1** | "and no layer owns a `BrokerAdapter`" | **FALSE.** `apps/atlas-core` owns it. ADR-0013 decides ownership; `BrokerOwner` implements holding, lifecycle sequencing and governed access. This is the single defect. |
| **C-3** | "so the request `atlas.execution` builds is, today, received by nothing." | **True.** Ownership is not wiring. No `OrderRequest` reaches an adapter, because nothing produces one and nothing hands one to an owner. |

**P-1 is the whole of the defect.** C-1, C-2 and C-3 are true at the baseline and
must survive the correction (§10 T-6).

The trap this specification exists to close is that P-1 reads as C-3's premise.
An implementer who corrects P-1 by rewriting the sentence around it can easily
make C-3 conditional, hedged or absent — and a reader who loses C-3 concludes
that an owner exists, therefore something places orders. Owning an adapter and
being able to place an order are separated by everything ADR-0013 declined to
decide.

### 4.2 Statements checked and found still true — these must not change

Each was verified against the repository at the baseline. Correcting any of them
would introduce a falsehood.

| Passage | Why it stays |
|---|---|
| `:111-112` — "Nothing here obtains, constructs or invokes a `BrokerAdapter`, and an `OrderRequest` is inert until some layer places it." | True. "Here" is `atlas.execution`. ATLAS-TASK-0020 §9 preserved the execution boundary in full and `tests/unit/execution/test_execution_boundary.py` is unmodified. The second half is still true: no layer places one. |
| `:4-7` — "Three packages hold implementation: `atlas.config` … `atlas.broker` … `atlas.common`" | True. ATLAS-TASK-0020 added a module under `apps/`, not a package. The count of *packages* holding implementation is unchanged. |
| `:13-14` — "Every other package remains an empty, importable unit with a declared responsibility." | True for the same reason. `apps/atlas-core` is an application, not a package, and is not counted by this sentence. |
| `:61-64` — "Six edges between feature packages exist in the graph today" and the enumeration | True. ATLAS-TASK-0020 added `apps/atlas-core → atlas.broker`, an application-to-package edge. ATLAS-TASK-0015 §11.1 and ATLAS-TASK-0016 §11 both classify that as a different kind of edge from the six. See §11. |
| `:130` — the `broker` row, "The `BrokerAdapter` port and its data contracts" | True. ADR-0013 `:63-66`: the port and its implementations do not move from `packages/broker`. |
| `:134-137` — the `strategy`, `risk` and `execution` responsibility rows | **Not false.** ATLAS-TASK-0015 §9 and ATLAS-TASK-0017 §4.3 both ruled that this table states charters, not implementation status. That ruling holds here. |
| `:145-163` — invariant 1 and its three paragraphs | True. "What is still absent is anything that drives a strategy, reaches a verdict and calls the translation in sequence" is *more* pointedly true after ATLAS-TASK-0020, which built an owner and wired it to nothing. |
| `:185` — the `atlas-core` row, "Owns the event loop and runs the trading pipeline" | **Not false.** A charter row, governed by the same ruling as the package table. It must not be read as newly satisfied: `atlas-core` owns no event loop and runs no pipeline. |
| `:189-191` — "At ATLAS-TASK-0001, `atlas-core` has no run loop. Its entrypoint resolves configuration, enforces the environment's invariants, emits a JSON startup record and exits" | **Dated and still true.** ATLAS-TASK-0020 §11.2 and C-5 forbade touching `__main__.py`, and the file is byte-identical. This is the passage most likely to be mistaken for drift, because it names an application and a task number. It must not change. |
| `:24-25` — "Where this banner and the roadmap disagree, the roadmap is correct." | True and load-bearing. It is the sentence that bounds how stale the banner can become, and it is relevant to D-2. |

---

## 5. Scope

**Exactly one correction, in one file: P-1.**

Nothing else in `docs/architecture/overview.md` changes, subject to the
reviewer's ruling on D-2 (§7). No other file changes.

If D-2 is ruled in scope, the diff is two hunks in one file; if ruled out of
scope, one hunk in one file. In neither case does any other passage move.

---

## 6. Non-goals

This task does not:

1. Create an ADR, or edit one. See §16.
2. Decide the broker or venue configuration surface — no section name, field,
   environment variable, secrets mechanism or placeholder. ADR-0013 `:101-105`
   reserved it; ATLAS-TASK-0020 §11.4 declined it; this task must not describe
   its shape even in prose.
3. Decide adapter selection, or state how a process learns which venue it
   trades. ATLAS-TASK-0020 §11.3.
4. Define, describe or imply startup wiring — where an adapter is constructed,
   what `__main__.py` should do, or what a composition root would look like.
5. Define or describe supervision: no run loop, timer, thread, `health()`
   polling or `reconnect()` policy. ADR-0013 `:258-260`.
6. Rule on whether `apps/dashboard` may hold or invoke a `BrokerAdapter`.
   ADR-0013 `:250-252` created that question and placed it outside itself.
7. Introduce an `apps/` import boundary, an allowlist for `atlas.apps`, or any
   statement about what an application may import. ADR-0013 `:242-249` records
   that the rule is not created, implied or prefigured.
8. Change any package boundary, or add, remove or reword any row of the package
   responsibilities table or the processes table.
9. Change any source file, test file, configuration file, CI file or deployment
   file.
10. Change `docs/ROADMAP.md`. See §8.
11. Modify ADR-0011, footnote it, or state that its non-guarantee has been
    corrected, superseded or amended. See §16.
12. Restate, summarise or relocate ADR-0013's decision into the overview. The
    overview may state the fact; the ADR keeps the reasoning.
13. Assert that any pipeline, engine, run loop, scheduler, registry, factory,
    service container or composition root exists. None does.
14. Add a test, including a documentation-currency test. See §12.
15. Rewrite the passage for style, length or tone. One clause moves.

---

## 7. Authoritative decisions

### D-1 — Only P-1 moves; C-1, C-2 and C-3 survive

*Evidence.* §4.1. Three of the passage's four clauses are true at the baseline,
and C-3 is the passage's conclusion. ATLAS-TASK-0019 §4.2 is the precedent for
correcting one clause of a paragraph and listing the rest as checked and kept.

The correction states that a layer owns a `BrokerAdapter` and names it, and it
leaves the reader with the same conclusion the passage reaches today: the
request `atlas.execution` builds is received by nothing.

*Rejected alternative.* Deleting the passage and rewriting it as a description
of what now exists. Rejected because C-1, C-2 and C-3 are the document's only
statement of how far the pipeline is from joined, and the document has no other
home for them.

### D-2 — Whether the banner is re-dated is REFERRED TO THE REVIEWER

**This specification does not decide it.** Both readings are supported by
repository evidence, and they conflict.

*For re-dating to `ATLAS-TASK-0020`.* ATLAS-TASK-0015 §7 D-1 states the banner's
purpose: "a reader compares it to the roadmap's last row and knows immediately
how much to trust." The roadmap's last row is now `ATLAS-TASK-0020`, and the
banner reads `ATLAS-TASK-0018`. ATLAS-TASK-0019 D-1 re-dated the banner as part
of exactly this kind of correction, on exactly this reasoning. On that
precedent, a living-document correction that leaves the banner stale has done
half its job.

*Against re-dating in this task.* The authorisation for this work names one
correction, `docs/architecture/overview.md:118-121`. The banner is a different
passage, at `:3`, and it is not false — `:24-25` says the roadmap governs where
the two disagree, so a banner one task behind is dated, not wrong. ATLAS-TASK-0016
exists because a previous correction swept in more than its list allowed, and
§4.2 of that task is the record of the cost.

*What must not happen.* The implementer must not decide this. If the reviewer
does not rule, §15.10 applies: stop and report.

---

## 8. Files permitted to change

During implementation, exactly this:

| Path | Change |
|---|---|
| `docs/architecture/overview.md` | Correction P-1 at `:118-121`, and the banner at `:3` **only if** D-2 is ruled in scope |

Plus this specification file, `docs/tasks/ATLAS-TASK-0021.md`, which is not
modified by the implementation.

**`docs/ROADMAP.md` is not in this list.** Its row for this task — and the
replacement of the sentence at `:84-88`, which currently reads "this file
declares no ATLAS-TASK-0021, no ADR-0014 and no work after them" — is a
post-merge closeout step performed under separate authorisation, exactly as it
was for ATLAS-TASK-0011 through ATLAS-TASK-0020. It is not part of the
implementation and must not appear in the implementation diff.

The implementation diff is therefore **one file.**

---

## 9. Files explicitly forbidden to change

Any diff touching these fails the task.

**Immutable decision records.** Every file under `docs/adr/`. The thirteen ADRs
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
| `0013-the-application-owns-the-adapter.md` | `5bc9bcf27008f7f96cd50479ec0715e306a5c2b5` |
| `README.md` | `a0ce549bc1fbb1e944cf66dd368a8c3d7f2cf677` |

**ADR-0011 in particular.** Its non-guarantee "the broker-owning layer this
record names does not exist" became inaccurate when ATLAS-TASK-0020 merged.
ADR-0013 `:290-293` pre-recorded the handling: "That is the immutability rule
working as designed: the correction belongs in the roadmap and the living
documents, never in ADR-0011 itself." This task is one of those living
documents. It corrects the overview and leaves ADR-0011 alone.

**Historical task records.** `docs/tasks/ATLAS-TASK-0014.md` through
`ATLAS-TASK-0020.md`. Each is a dated account and none is a live claim about
today. ATLAS-TASK-0019 §4.2 quotes the phrase "no layer owns a `BrokerAdapter`"
verbatim while ruling it still true at *its* baseline, and ATLAS-TASK-0020 §17.3
quotes it again. Both match the search patterns this task works from and are the
likeliest files to be swept up by a repository-wide edit. They must not change.

**`docs/ROADMAP.md`.** Blob `a1fcceba800578f236fbb120ca3022bb6637d19d`. See §8.
Its "Known documentation debt" section is not extended by this task.

**Every source file.** In particular
`apps/atlas-core/src/atlas/apps/core/broker_ownership.py` and
`apps/atlas-core/src/atlas/apps/core/__main__.py`. The first is the evidence
this correction rests on; the second is the evidence for C-3 and for `:189-191`.

**Every test file.** See §12.

**Everything else outside §8**, and in particular every file under `packages/`,
`apps/`, `.github/`, `config/`, `infrastructure/` and `scripts/`.

**Every passage of `docs/architecture/overview.md` outside `:118-121`**, subject
to D-2, and everything named in §4.2.

---

## 10. Exact documentation truths that must hold after implementation

Each truth must be discoverable from the corrected passage. The wording is the
implementer's; the fact is not.

- **T-1.** The document no longer states that no layer owns a `BrokerAdapter`.
- **T-2.** It states that `apps/atlas-core` owns the adapter, and it may name
  ADR-0013 as the decision. It must not name the module or the class as the
  document's subject: the fact is that an application owns the port, and
  `BrokerOwner` is an implementation detail the overview has no other precedent
  for naming.
- **T-3.** It states or preserves that ownership is not wiring: nothing outside
  the test suite hands the owner an adapter, and the `OrderRequest`
  `atlas.execution` builds is still received by nothing (C-3).
- **T-4.** It does not claim that a composition root, engine, run loop,
  scheduler, pipeline, registry, factory or service container exists. None does.
- **T-5.** It does not claim that an adapter is constructed anywhere outside
  `packages/broker` and the test suite. None is.
- **T-6.** Clauses C-1, C-2 and C-3 of §4.1 survive in substance. The reader's
  conclusion — the chain is not joined end to end — is unchanged.
- **T-7.** If lifecycle is described at all, it is described as connect and
  disconnect. The owner implements neither supervision nor reconnection, and the
  document must not imply that `health()` or `reconnect()` is called by
  anything.
- **T-8.** It states nothing about a broker or venue configuration surface,
  adapter selection, credentials, or how a process would choose an
  implementation. All four are undecided (§6.2, §6.3).
- **T-9.** It states nothing about what an application may import, and nothing
  about whether `apps/dashboard` may hold an adapter.
- **T-10.** It does not state or imply that any ADR has been corrected,
  superseded, amended or footnoted. None has.
- **T-11.** Every passage listed in §4.2 survives byte-for-byte, and in
  particular `:111-112`, `:185` and `:189-191`.
- **T-12.** The document names no task number that does not exist in
  `docs/ROADMAP.md`'s status table.

---

## 11. Dependency-graph requirements

**No edge changes.** This task adds no import, removes none, and touches no
Python file.

The six feature-package edges at the baseline — `broker → common`,
`risk → broker`, `risk → config`, `strategy → risk`, `execution → risk`,
`execution → broker` — are the six after implementation, and
`docs/architecture/overview.md:61-64` states six before and after (T-11).

ATLAS-TASK-0020 added `apps/atlas-core → atlas.broker`. It is an
application-to-package edge, not an edge between feature packages, on the
classification `docs/tasks/ATLAS-TASK-0015.md:341` (§11.1) and
`docs/tasks/ATLAS-TASK-0016.md:457` (§11) both give, and which
`docs/tasks/ATLAS-TASK-0019.md:346-350` applied to `apps/core → atlas.config`.
**This task neither changes that classification nor builds anything on it, and
must not add the new edge to the six.** Whether application edges are counted,
ruled on or bounded is part of the undecided `apps/` boundary question (§6.7).

---

## 12. Test requirements

**No test is added, removed or modified.**

The suite passes 3589 tests at the baseline, and must pass 3589 after — the same
count, and the same tests. A changed count is a stop condition (§15.5).

**The suite does not verify this change, and no test is written to make it do
so.** No test opens, parses or asserts on `docs/architecture/overview.md` — this
was checked across `tests/` at the baseline, and the only file-reading tests
(`tests/contract/test_repository_structure.py`,
`tests/unit/broker/mt5/test_mt5_connection.py`,
`tests/unit/broker/test_adapter_concurrency.py`) read `pyproject.toml` and
Python sources. The suite would pass identically if the passage were left false,
corrected wrongly, or deleted. Acceptance therefore rests on the mechanical
checks in §13, not on a green suite; the 3589 passing tests are evidence that
nothing else moved, which is the only thing they can be evidence of here.

**A documentation-currency test is deliberately not written.** ATLAS-TASK-0015
§13, ATLAS-TASK-0016 §12.1 and ATLAS-TASK-0019 §12 all reach the same
conclusion: a test that read prose would make the wording of a document a
contract. That reasoning is unchanged here. Writing such a test is a separate
decision with its own trade-off, and it is not made by a documentation
correction.

### 12.1 Three tests cite the overview in comments, and none is affected

A repository-wide search for `overview.md` returns three hits inside `tests/`,
all of them prose in a `#:` comment above an import allowlist:

| File | Line | What it cites |
|---|---|---|
| `tests/unit/broker/test_adapter_contract.py` | 178 | the overview "assigns the clock to that package and declares it dependency-free and importable anywhere" |
| `tests/unit/risk/test_risk_boundary.py` | 63 | `atlas.common` admitted "on the grounds `docs/architecture/overview.md` already states — dependency-free, importable anywhere, encoding no domain rules" |
| `tests/unit/strategy/test_strategy_boundary.py` | 57 | the same grounds, in the same words |

All three cite the overview's treatment of `atlas.common`, which lives in the
package responsibilities table and is nowhere near `:118-121`. **None is
affected by this correction, and none may be edited by it** (§9). They are
listed here because an implementer who greps for `overview.md` will find them,
and because they are the closest thing in the suite to a documentation
dependency — a comment, not an assertion, which is why §12's "no test verifies
this change" holds despite them.

Note also that `tests/unit/test_core_broker_boundary.py` collects 183 tests
(40 `assert` statements, the rest parametrised) constraining what `apps/` may
import. None reads documentation. It is not modified, and it is not evidence for
or against anything in §10.

---

## 13. Validation requirements

1. **Before any edit**, confirm: branch `main`; `HEAD` and `origin/main` both
   `62d7ac4771df40d805a2c3a410f7e1b13755e6c1`; `git status --porcelain` empty;
   `git rev-parse HEAD:docs/architecture/overview.md` is
   `ebbd273dd7cb49b9fc3704cec45a46f356f31e0a`.
2. **Re-verify P-1 against the code, not against this document.**
   `apps/atlas-core/src/atlas/apps/core/broker_ownership.py` exists, defines
   `BrokerOwner`, stores an adapter on the instance, and exposes `adapter`,
   `start` and `stop`. If it does not, the premise of this task has changed and
   §15.1 applies.
3. **Re-verify C-3 against the code.** `__main__.py` constructs no adapter and
   no owner; no module outside the test suite instantiates `BrokerOwner`. If
   something does, C-3 is false too and the scope of this task is wrong — report
   it rather than widening the correction.
4. **Re-verify the baseline count.** The roadmap's last row is
   `ATLAS-TASK-0020`, cited at `55fcbd6161d49c986b0033f37493195c3226493e`.
5. **After the edit**, `git diff --stat` must report exactly one file changed,
   and `git diff` must show changes confined to `:118-121` — plus `:3` only if
   D-2 was ruled in scope.
6. **Confirm the ADRs are untouched**: each blob in §9 is unchanged.
7. Run the full test suite. Expect 3589 passed.
8. Ruff, Black and MyPy are not required locally: the change touches no Python.
   CI's Quality Gate runs them regardless, and a failure in any of them on a
   documentation-only diff is a stop condition (§15.6).
9. **Read the corrected passage end to end, in the context of `:106-121`**, and
   confirm each of T-1 through T-12. This is the only check that can catch a
   correction that is true in isolation and false in context — specifically, one
   that contradicts `:111-112`.
10. **Confirm no new task number or ADR number appears anywhere in the diff.**

---

## 14. Acceptance criteria

- **AC-1.** `docs/architecture/overview.md` no longer states that no layer owns
  a `BrokerAdapter` (P-1, T-1).
- **AC-2.** The corrected passage names `apps/atlas-core` as the owner (T-2).
- **AC-3.** The corrected passage still tells the reader the chain is not joined
  end to end and that the `OrderRequest` is received by nothing (T-3, T-6).
- **AC-4.** Truths T-1 through T-12 hold.
- **AC-5.** The diff touches exactly one file, and only the passages §8 permits.
- **AC-6.** No ADR changed. No test changed. No source file changed.
  `docs/ROADMAP.md` unchanged.
- **AC-7.** The test suite passes with 3589 tests.
- **AC-8.** The diff contains no statement that decides, prepares for, or
  presumes an answer to anything in §6 or §17.
- **AC-9.** The diff introduces no task identifier and no ADR identifier.
- **AC-10.** If D-2 was not ruled by the reviewer, the banner is unchanged and
  the implementer has reported the ambiguity rather than resolving it.

---

## 15. Stop conditions

Stop and report rather than deciding, if:

1. `apps/atlas-core/src/atlas/apps/core/broker_ownership.py` is absent, or does
   not hold the adapter, or the repository has moved from the baseline. Any of
   these means the premise of this task no longer holds.
2. An ADR-0014 or later exists, or a task after ATLAS-TASK-0020 exists. Either
   may have already corrected the passage or changed what is true.
3. A correction appears to require editing an ADR. It does not; see §16.
4. A correction appears to require a source change. It does not; every truth in
   §10 is already true of the code at the baseline. If a document cannot be made
   true without changing code, the document is describing something
   ATLAS-TASK-0020 did not deliver, and that is a finding to report, not to fix.
5. The test count is anything other than 3589.
6. Ruff, Black or MyPy reports anything on a diff that touches no Python.
7. **A second stale statement is found.** Report it with its evidence; do not
   fold it into this task's diff. §4.2 is the precedent for how such a finding
   is recorded, and §4.2 already rules on the four candidates most likely to be
   mistaken for defects — `:111-112`, `:134-137`, `:185` and `:189-191`.
8. Correcting the passage appears to require naming a configuration surface, an
   adapter implementation, a startup sequence, a supervision mechanism, an
   `apps/` import rule, or anything else in §6 or §17.
9. The correction cannot be written without stating something the repository has
   not decided. This is the architectural-invention stop: if every available
   wording either leaves P-1 false or asserts something undecided, the
   specification is wrong and must be revised before implementation, not worked
   around. Report the wordings tried and what each would have decided.
10. **D-2 has not been ruled by the reviewer.** The implementer must not choose.
11. The scope expands beyond documentation correction for any reason.

In every case: report both pieces of conflicting evidence and explain the
conflict. Do not silently reconcile them.

---

## 16. Relationship to the ADRs

**All thirteen ADRs are Accepted and immutable. No ADR is required by this task,
and this task edits none.**

`docs/adr/README.md:4-6` defines exactly four statuses — `Proposed`, `Accepted`,
`Superseded by ADR-NNNN`, `Deprecated`. There is no amendment status.

| ADR | Relationship |
|---|---|
| ADR-0013 | The decision this correction reports. It is cited, not restated, not summarised and not relocated. |
| ADR-0011 | Holds a non-guarantee that ATLAS-TASK-0020 made inaccurate. ADR-0013 `:290-293` already ruled that the correction belongs in the living documents and "never in ADR-0011 itself". This task is that correction and leaves ADR-0011 untouched. |
| ADR-0012 | Its revisit condition — "when a single wiring point exists and can be pointed at" — is **not** satisfied. ATLAS-TASK-0020 §10 R-1 and §20 both say so. The corrected passage must not imply otherwise. |
| ADR-0007 | Assigns lifecycle sequencing and supervision to "a caller". Sequencing now has an owner; supervision does not. T-7. |
| ADR-0006 | `MockBrokerAdapter` stays exported from `atlas.broker.mock` and never from `atlas.broker`. The corrected passage must not name an implementation as the thing owned; the owner holds a `BrokerAdapter`. |

An ADR is required when a decision changes the architecture. This task changes
no contract, no boundary, no edge and no behaviour.

Accordingly, this task must not: edit any ADR; add a footnote or cross-reference
to one; create ADR-0014; or state, in the corrected passage, that any ADR's
wording has been corrected, superseded or amended. None has been.

---

## 17. Separation from future architectural decision work

This task is a documentation correction. It is **not** an architectural decision
gate, and nothing in its diff may be justified as groundwork for one.

ADR-0013 `:240-264` and ATLAS-TASK-0020 §20 list the decisions the repository
has deliberately declined to make. This task makes and prepares none of them:

- **The broker or venue configuration surface.** ADR-0013 `:101-105`,
  `:253-254`. The hard blocker: no live adapter can be constructed until it is
  decided.
- **Adapter selection and process startup.** ATLAS-TASK-0020 §11.3. No ADR
  decides how a process learns which venue it trades.
- **What kind of rule an `apps/` boundary is.** ADR-0013 `:242-249`.
- **Whether `apps/dashboard` may hold or invoke a `BrokerAdapter`.** ADR-0013
  `:250-252`.
- **Supervision: the run loop, the `health()` timer, the threading model.**
  ADR-0013 `:258-260`.
- **Order identity and idempotency; routing, fills and reconciliation.**
  ADR-0013 `:261-262`.
- **The state contracts the remaining risk controls need.** ADR-0010 `:198`,
  ADR-0011 `:184`, ADR-0012 `:282`, ADR-0013 `:263-264`.

When one of these is taken up, it begins with an owner decision gate and a new
ADR, in the sequence ATLAS-TASK-0014, ATLAS-TASK-0017 and ADR-0013 followed —
not with a documentation pass, and not with this task.

Correcting the passage is worth doing on its own terms, and it is worth doing
before any of them: it requires no architectural decision, and every one of the
decisions above will be argued against `docs/architecture/overview.md` by
whoever makes it. A document that denies the existence of the repository's only
adapter owner is the wrong baseline for that argument — and one that overstates
what the owner does is a worse one.

---

## Roadmap

`docs/ROADMAP.md` is not modified by this task, and is not modified by the
existence of this specification.

The roadmap's status table records completed tasks citing the commit they
reached `main` on (`:3-5`, `:12-13`). A specification is not a completed task
and has no row. The row for ATLAS-TASK-0021 — and the replacement of the
sentence at `:84-88` stating that the file declares no ATLAS-TASK-0021 — is
written after this specification has been reviewed and explicitly authorised,
and after the implementation has merged, following the pattern of
ATLAS-TASK-0011 through ATLAS-TASK-0020.
