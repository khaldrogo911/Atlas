# Roadmap and Task Tracker

The authoritative record of which ATLAS tasks are complete and what comes next.
A task is **Complete** only when it is merged on `main` and every gate in the
repository's definition of done passed on that commit.

Task identifiers appear in commit subjects, in `TODO(ATLAS-TASK-nnnn)` markers,
and in package documentation. This file is where they resolve to a status.

## Status

| Task | Title | Status | Commit |
|---|---|---|---|
| ATLAS-TASK-0001 | Repository bootstrap and engineering foundation | ✅ Complete | `5427475` |
| ATLAS-TASK-0001A | Repository bootstrap review fixes | ✅ Complete | `b994b18` |
| ATLAS-TASK-0002 | Broker domain models | ✅ Complete | `0498866` |
| ATLAS-TASK-0003 | The `BrokerAdapter` port | ✅ Complete | `4c7a9d7` |
| ATLAS-TASK-0004 | MetaTrader 5 broker adapter (demo foundation) | ✅ Complete | `36fa3e3` |
| ATLAS-TASK-0005 | Broker exception hierarchy | ✅ Complete | `a07dcea` |
| ATLAS-TASK-0006 | `MockBrokerAdapter` | ✅ Complete | `b11b154` |
| ATLAS-TASK-0007 | `BaseBrokerAdapter` | ✅ Complete | `1673f79` |
| ATLAS-TASK-0008 | Adapter concurrency | ✅ Complete | `e451608` |
| ATLAS-TASK-0009 | The `Clock` abstraction | ✅ Complete | `a400530` |
| ATLAS-TASK-0010 | Retry and reconnection policy | ✅ Complete | `de7e905` ‡ |
| ATLAS-TASK-0011 † | The risk boundary: `TradeIntent` and `RiskVerdict` | ✅ Complete | `f54ad613` |
| ATLAS-TASK-0012 † | The strategy boundary: producing a `TradeIntent` | ✅ Complete | `2e567aa5` |
| ATLAS-TASK-0013 † | Documentation and release-metadata debt | ✅ Complete | `19afcf40` § |
| ATLAS-TASK-0014 † | The execution contract: an approved verdict becomes an `OrderRequest` | ✅ Complete | `00364ac24f0479de2cb5278b519dbe97cf2e0d2b` |
| ATLAS-TASK-0015 † | Living-document correction after the execution contract | ✅ Complete | `5e730b4766165a16d994f55251d9eca50df0b842` |
| ATLAS-TASK-0016 † | Completing the living-document correction | ✅ Complete | `c37b0ebba3b4206705dfd8c06ba6e96c9ebfcf48` |
| ATLAS-TASK-0017 † | The first risk control: a portfolio margin-utilisation limit | ✅ Complete | `4147f12c8a52b6095b4380ebbc57c92cd058d633` |
| ATLAS-TASK-0018 † | Index ADR-0012 in `docs/adr/README.md` | ✅ Complete | `dfc1289949dca9f3b8506e6e2b99730495318669` |
| ATLAS-TASK-0019 † | Living-document correction after the first risk control | ✅ Complete | `394df7debe6c77cbcf4e79cfe2cfc0ef798c1d8a` |
| ATLAS-TASK-0020 † | Implement application ownership of `BrokerAdapter` | ✅ Complete | `55fcbd6161d49c986b0033f37493195c3226493e` |
| ATLAS-TASK-0021 † | Living-document correction after application ownership of `BrokerAdapter` | ✅ Complete | `d7a68cb4aa6aa1a3465e1305e2b04b432adf00da` |
| ATLAS-TASK-0022 † | The broker configuration surface: `BrokerSettings` | ✅ Complete | `d0f5b709979a3b634c859b31c77fd5dc41c6ab7b` |
| ATLAS-TASK-0023 † | Construct the broker adapter at startup | ✅ Complete | `6f5eff81361e904b746a37a8c975683b138972e7` ¶ |
| ATLAS-TASK-0024 † | CI Container Self-Check After Broker Startup Construction | ✅ Complete | `2c4e7e8bdbf2839b11fe25e38b7b0d9bbd8c4732` |
| ATLAS-TASK-0025 † | Living-document correction after broker adapter construction | ✅ Complete | `db92e7795055bc88f022c1a4b9932ef9fe586fe1` |
| ATLAS-TASK-0026 † | Enforce the ADR-0016 broker startup validation boundary | ✅ Complete | `06418acf326a2c4f7964a8963ccfeae433c25db6` ‖ |
| ATLAS-TASK-0027 † | Execute broker lifecycle during startup | ✅ Complete | `c5500dc58186dded011b52d62b227bd8d9e96872` |
| ATLAS-TASK-0028 † | Strengthen CI container startup/refusal contracts | ✅ Complete | `c5500dc58186dded011b52d62b227bd8d9e96872` |

† **Newly specified, not recovered.** The unmarked rows are evidenced by the
repository record: the task existed, and the commit it cites is the work.
ATLAS-TASK-0011 through ATLAS-TASK-0028 were each specified and authorised as
new work during the task itself. Their presence in this table is not evidence
that any was previously planned, and none may be described as recovered project
history or as previously completed.

ATLAS-TASK-0012 cites the branch tip rather than the branch's first commit.
`270f57a8` added the package and `2e567aa5` removed the dependency on
`atlas.broker` that it had taken, so `2e567aa5` is the state that reached
`main`. The gates passed on that tree twice — once on the pull request and
again on the merge commit `e909b4b`, whose tree is identical — so unlike
`de7e905` below there is no gap here against the definition above.

‡ **The gates passed one commit later.** `de7e905` is where ATLAS-TASK-0010's
work lives and it is on `main`, which is why it is the commit cited. The tree at
that commit did not itself pass CI: the run covering it failed at Pytest, and CI
was first green at `6cca03d`, which corrected a flaky clock test. The citation
is left as the feature commit — the history is not rewritten — and the gap
against the definition of **Complete** above is recorded here instead.

§ **The commit is cited after the fact.** This file is part of what
ATLAS-TASK-0013 delivered, so the row above could not cite its own commit: the
SHA did not exist until the commit was written. The citation is completed here
after the merge, which is how ATLAS-TASK-0012's row was filled in too, by
`b023f8b`. `19afcf40` is the implementation commit and holds the work; the
merge commit is `1d964186`, and as with `2e567aa5` above it is not what the
row cites.

¶ **One gate failed here, and a later task closed it.**
`6f5eff81361e904b746a37a8c975683b138972e7` is where ATLAS-TASK-0023's work lives
and it is on `main`, which is why it is the commit cited. CI run 43 — id
`31886471062`, head `6f5eff81361e904b746a37a8c975683b138972e7` — passed the
Quality Gate in full, every step of it, and failed Container & Compose at
exactly one step, "Run the image configuration self-check". `docker compose
config` and the image build had both already succeeded; the self-check ran the
image with no broker configuration, and start-up had become the place that
refuses without one. This is not the same kind of gap as ‡ above: the
application code was correct, and what had not caught up with it was the
repository's deployment surface — the workflow, the compose file and the example
environment. ATLAS-TASK-0024 brought those level in
`2c4e7e8bdbf2839b11fe25e38b7b0d9bbd8c4732`, and CI run 44 against that commit is
green in both jobs. The citation is left as the feature commit — the
history is not rewritten — and the gap against the definition of **Complete**
above is recorded here instead.

‖ **A test control failed here, and the next commit closed it.**
`06418acf326a2c4f7964a8963ccfeae433c25db6` is where ATLAS-TASK-0026's work lives
and it is on `main`, which is why it is the commit cited. CI run 49 failed at
one step, Pytest, on one test:
`test_the_filesystem_patch_can_actually_intercept[absolute]`. That test is not a
test of the validator. It is the control that proves the filesystem instrument
of the no-I/O proof can fire at all, and it probed a path beginning with a
slash — absolute under POSIX, relative under Windows, which is the mirror image
of the portability example ADR-0016 `:93-97` gives for declining an absoluteness
invariant. `Path.absolute()` returns `self` without consulting the working
directory when the path is already absolute, so on Linux the control touched
nothing and did not fire, while on the Windows host it had been written on it
did. **No production code was implicated and none was changed.** The validator
behaved identically on both platforms, every test of the invariants themselves
passed on run 49, and the defect was confined to the probe path chosen for the
control. `05421d5c0934413d314ce851c8ec451d3d79027c` dropped the leading slash and
changed nothing else — one file, one line of test data and a comment saying why
— and CI run 50 against it passed both jobs on Linux under Python 3.12.13 with
coverage active: 3623 passed, 105 skipped, none of the skips in this task's
tests. This is neither ‡'s flaky gate nor ¶'s deployment surface lagging behind
correct application code; it is a defect in the task's own instrument, which
failed in exactly the environment it was written to describe. The citation is
left as the feature commit — the history is not rewritten — and the gap against
the definition of **Complete** above is recorded here instead.

ATLAS-TASK-0019 is complete, committed and pushed. `main` and `origin/main` are
both `a634fa48`, the closeout commit for that task, so the push its entry below
describes as the thing that closes its gap against **Complete** has happened;
that entry is left as written, as it says it should be.

**ADR-0013 is accepted, and ATLAS-TASK-0020 is implemented.** ADR-0013 —
`docs/adr/0013-the-application-owns-the-adapter.md`, indexed in
`docs/adr/README.md` — decides that `apps/atlas-core` owns the `BrokerAdapter`,
and that the port and its implementations do not move from `packages/broker`.
`docs/tasks/ATLAS-TASK-0020.md` is the implementation specification for that
decision, and `55fcbd61` is the commit that implements it: the first source
change either has produced, and the first module under `apps/` that names the
port. ATLAS-TASK-0020's row was written once that commit reached `main`, the way
every row above it was. ADR-0013 has no row there and will not acquire one —
that table records tasks, and a decision is not a task.

**ADR-0014 is accepted, and ATLAS-TASK-0022 is implemented.** ADR-0014 —
`docs/adr/0014-broker-settings-are-restated-not-imported.md`, indexed in
`docs/adr/README.md` — decides that the values a trading session needs are
restated in `atlas.config`'s own primitives rather than imported from
`atlas.broker`, so that the configuration package does not import a feature
package in order to learn its own shape. `docs/tasks/ATLAS-TASK-0022.md` is the
implementation specification for that decision, and `d0f5b709` is the commit
that implements it. As with ADR-0013, ADR-0014 has no row in that table and will
not acquire one — a decision is not a task.

**ADR-0015 is accepted, and ATLAS-TASK-0023 is implemented.** ADR-0015 —
`docs/adr/0015-broker-adapter-selection.md`, indexed in `docs/adr/README.md` —
decides that `apps/atlas-core` selects `MT5BrokerAdapter`, translates the broker
section of `AtlasSettings` into an `MT5Config` at its own composition boundary,
constructs the adapter during start-up and hands it to a `BrokerOwner`, and that
a broker section no session could be opened from fails start-up at that
translation. `docs/tasks/ATLAS-TASK-0023.md` is the implementation specification
for that decision, and `6f5eff81361e904b746a37a8c975683b138972e7` is the commit
that implements it. As with ADR-0013 and ADR-0014, ADR-0015 has no row in that
table and will not acquire one — a decision is not a task.

**ADR-0016 is proposed, and ATLAS-TASK-0026 is implemented.** ADR-0016 —
`docs/adr/0016-unusable-broker-configuration-refuses-startup.md`, indexed in
`docs/adr/README.md` — decides that broker configuration which cannot open a
session is refused where the session is assembled, and that the refusal is
confined to properties holding independently of the machine validating them: an
empty password and the not-configured terminal path are refused, and no other
property of that path is checked. `docs/tasks/ATLAS-TASK-0026.md` is the
implementation specification for that decision, and
`06418acf326a2c4f7964a8963ccfeae433c25db6` is the commit that implements it. As
with ADR-0013, ADR-0014 and ADR-0015, ADR-0016 has no row in that table and will
not acquire one — a decision is not a task.

**ADR-0017 is proposed, and ATLAS-TASK-0027 is implemented.** ADR-0017 —
`docs/adr/0017-startup-opens-a-session-and-closes-it.md`, indexed in
`docs/adr/README.md` — decides that start-up opens the session the constructed
adapter describes, verifies it by opening it, and closes it again before the
process ends, and that `atlas-core` is therefore not a long-running process.
It has no specification file: the work was authorised in session and implemented
directly, so there is no `docs/tasks/ATLAS-TASK-0027.md`, and
`c5500dc58186dded011b52d62b227bd8d9e96872` is the commit that implements it. The
record itself was committed first, in
`f98b41ea2cb59d54980a1867a755c01ef8980937`, before any code was written against
it. As with ADR-0013, ADR-0014, ADR-0015 and ADR-0016, ADR-0017 has no row in
that table and will not acquire one — a decision is not a task.

**The word in the two paragraphs above is `Proposed`, not `Accepted`, and the
difference is recorded rather than smoothed over.** ADR-0013, ADR-0014 and
ADR-0015 were each accepted before the task implementing it was specified, and
each paragraph above says so. ADR-0016 is the first that was implemented while
still proposed. The authority for the work was the owner's decision to implement
the record as written, which ATLAS-TASK-0026 §2.1 states in those terms rather
than inferring it from a status the record does not carry; the task did not edit
the record and did not advance it, and `docs/adr/README.md` lists it as
`Proposed` today. Whether it is accepted is a step for the owner and not for
this file, and nothing above is evidence that it has been taken.

**ADR-0017 is the second instance of exactly that situation, and it is recorded
the same way rather than allowed to pass as the ordinary case.**
ATLAS-TASK-0027 implemented a record carrying `Proposed`, under the same
authority and for the same reason: the status the record carries was not read as
permission, and the owner gave permission explicitly instead. That task did not
edit ADR-0017 and did not advance it, and `docs/adr/README.md` lists both
ADR-0016 and ADR-0017 as `Proposed` today. Two records now govern shipped
behaviour without having been accepted — ADR-0016 the configuration values
start-up refuses, ADR-0017 the session it opens and the exit codes it reports.
Accepting either is a step for the owner and not for this file, and nothing
above is evidence that either step has been taken.

ATLAS-TASK-0020 does not decide the broker or venue configuration surface.
ADR-0013 declined to, and the specification names the absence of that surface in
`AtlasSettings` as the exact dependency blocking construction of a live adapter,
rather than inventing one to work around it. ATLAS-TASK-0021 does not decide it
either: that task is a documentation correction, and the blocker is exactly
where ADR-0013 left it. ADR-0014 decided it and ATLAS-TASK-0022 built it, which
is the ADR-0014 paragraph above. ADR-0015 then decided what to build from that
surface and ATLAS-TASK-0023 built it, which is the paragraph directly above this
one.
ATLAS-TASK-0024 carried that work into the deployment surface, and
`2c4e7e8bdbf2839b11fe25e38b7b0d9bbd8c4732` is its implementation. It has no
specification file; its row above was written all the same, as
ATLAS-TASK-0018's was. ATLAS-TASK-0025 then corrected the living documents
that construction left stale. ADR-0016 exists, is indexed in
`docs/adr/README.md`, and is implemented by ATLAS-TASK-0026, whose row is the
last one above; it remains `Proposed`, which the ADR-0016 paragraph above
records.

ATLAS-TASK-0027 and ATLAS-TASK-0028 were authorised and implemented after
ATLAS-TASK-0026, so the clause immediately above naming that task's row as the
last one is answered here rather than corrected there: ATLAS-TASK-0028 is the
final task this file represents. Both of their rows cite
`c5500dc58186dded011b52d62b227bd8d9e96872`, which is the first time two rows in
that table cite one commit; that is a fact about how the work was committed and
not about how it was scoped, and the two remain separate tasks. ADR-0017 is the
governing decision record for ATLAS-TASK-0027, and the ADR-0017 paragraph above
records that it too remains `Proposed`. ATLAS-TASK-0028 has no record of its
own: it carried that same implementation into CI. This file declares no work
after ATLAS-TASK-0028. The tasks above are the ones the repository itself
declares; this file does not speculate past them.

**ADR-0016 and ADR-0017 are now accepted, and the paragraphs above calling them
proposed are answered here rather than corrected there.** The owner accepted
both as written, in the same decision that created ADR-0018. Acceptance changed
one word in each record — the `**Status:**` line — and the matching cell in
`docs/adr/README.md`; no other line of either record was touched, and neither
record's decision moved. This is the first time the `Proposed` → `Accepted`
transition has been exercised here: ADR-0001 through ADR-0015 each entered the
index already accepted, so until now the status vocabulary in
`docs/adr/README.md` described a step the repository had never taken. The two
paragraphs above are left as written, as ATLAS-TASK-0019's, ATLAS-TASK-0020's,
ATLAS-TASK-0021's, ATLAS-TASK-0022's and ATLAS-TASK-0023's entries were. So is
the sentence in the ATLAS-TASK-0026 entry below recording that ADR-0016 was
proposed when that task shipped, which is a statement about the moment the task
shipped and stays true. The claim above that two records govern shipped
behaviour without having been accepted was true when written and is answered
here; what the owner accepted is what those records already said, so no shipped
behaviour changed and neither implementing task is reopened.

One consequence of accepting ADR-0017 is left standing rather than repaired.
Its `## Relationship to ADR-0016` section says ADR-0016 "remains `Proposed`",
which was true when that record was written and is false now. It is left exactly
where the immutability rule in `docs/adr/README.md` puts it, as ADR-0011
`:99-103` and ADR-0015's closing sentence were — false of the repository now,
and not this file's to correct or an ADR's to amend. The contingency the same
section attaches to ADR-0016's status turns on that record being *rejected*, not
accepted, so acceptance settles it rather than triggering it.

**ADR-0018 is accepted, and it specifies no task.** ADR-0018 —
`docs/adr/0018-the-runtime-process-shape-is-deferred.md`, indexed in
`docs/adr/README.md` — decides that the long-lived runtime and process shape is
intentionally deferred pending an explicit architectural decision, and that no
persistent broker session, run loop, supervision, reconnect, failover, strategy
lifecycle, risk integration or execution pipeline is implemented until a
dedicated record defines that shape and is accepted. It is the first record here
that decides a prohibition rather than a construction. It names the questions
that record must answer and the process shapes it declines to choose between,
and it chooses none of them: the deferral is the decision. It has no
specification file, no implementing commit and no task, because there is nothing
to implement — the whole of its effect is a constraint on what may be built
next. As with ADR-0013, ADR-0014, ADR-0015, ADR-0016 and ADR-0017, ADR-0018 has
no row in that table and will not acquire one — a decision is not a task. Unlike
them, it will acquire no implementing task either, and this file still declares
no work after ATLAS-TASK-0028.

ADR-0018 carries `Accepted` from its first commit, and that is not a formality
here. A prohibition that has not been accepted binds nothing, and the record
says as much of itself: the gate it describes closes when the owner accepts it.
The owner accepted it in the same decision that accepted ADR-0016 and ADR-0017,
so the gate is in force rather than pending, and the deferral it records is not
a note about future intentions but a constraint on what may be built next. The
two records that governed shipped behaviour while proposed, recorded above, are
why that distinction is written down rather than assumed — the difference
between what a record carries and what the owner has authorised has been
load-bearing twice in this file already, and it is not left ambiguous a third
time.

ADR-0018 therefore enters the index already accepted, as ADR-0001 through
ADR-0015 did, and unlike ADR-0016 and ADR-0017 it was never implemented against
while proposed, because there is nothing to implement against it.

ATLAS-TASK-0021 is the correction the ATLAS-TASK-0020 entry below calls for and
declines to number. That entry closes "this file names no number for it", which
was true when written and is answered by the row above; the entry is left as
written, as ATLAS-TASK-0019's was.

ATLAS-TASK-0022 supplies the surface that same entry names as the dependency
blocking a live adapter. That entry says `MT5BrokerAdapter` "cannot be
constructed at all, because `AtlasSettings` carries no broker or venue section
from which an `MT5Config` could be built"; the section now exists, and what the
entry goes on to describe as the remaining work — "when the configuration
decision is taken, the work it leaves is one call site" — is where this task
leaves it. That entry is left as written, as ATLAS-TASK-0019's and
ATLAS-TASK-0020's were.

ATLAS-TASK-0025 is the correction the ATLAS-TASK-0022 and ATLAS-TASK-0023
entries below call for and decline to number. Both close with "this file names
no number for it", which was true when each was written and is answered by the
row above; both entries are left as written, as ATLAS-TASK-0019's,
ATLAS-TASK-0020's and ATLAS-TASK-0021's were. It answers them in part and not
in full, which is the deliberate half: the two `docs/architecture/overview.md`
passages and the stale `#:` comment in `tests/unit/risk/test_risk_boundary.py`
are corrected, while ADR-0011 `:99-103` and ADR-0015's closing sentence are
left exactly where the immutability rule in `docs/adr/README.md` puts them —
false of the repository now, and not this file's to correct or an ADR's to
amend.

## Completed

### ATLAS-TASK-0001 / 0001A — engineering foundation

Poetry monorepo, PEP 420 namespace packages across 18 source roots, strict
typing, linting, formatting, containerisation, layered configuration and CI.
`atlas.config` is fully implemented because configuration *is* foundation;
every other package was an importable unit with a declared responsibility and
no implementation.

0001A was a cross-file consistency audit of the generated configuration plus
the Git topology fix. No features added.

### ATLAS-TASK-0002 — broker domain models

`Account`, `Symbol`, `Tick`, `Candle`, `Order`, `Position`, `Execution`,
`Connection` and their enumerations. Pydantic v2, frozen, `extra="forbid"`.
`Decimal` for every price, volume and money amount. Timezone-aware timestamps
normalised to UTC on the way in. Depends on no venue SDK, enforced by an AST
import scan rather than by convention.

### ATLAS-TASK-0003 — the `BrokerAdapter` port

One abstract class of 31 methods, five capability protocols, and the request
types the port speaks. Synchronous by policy. Returns domain models only —
never vendor objects, never dictionaries, never `Any`. No implementation.

### ATLAS-TASK-0004 — MetaTrader 5 broker adapter

The first real implementation of the port, for a dedicated demo account. The
port was not changed: the task exists to validate the contract against a live
venue, not to reshape it around one.

24 of 31 methods are implemented. Seven raise `NotImplementedError` with the
missing MT5 capability named at the call site — the four trading methods, plus
`subscribe_ticks` and `subscribe_candles` (the MT5 Python API polls and opens
no push channel) and `server_time` (the terminal exposes no clock).

`MetaTrader5` is imported inside exactly one function, behind a typed protocol,
never at module scope, and is an optional Windows-marked extra — so the
distribution installs and the whole suite runs on a Linux runner with no wheel
and no terminal.

### ATLAS-TASK-0005 — broker exception hierarchy

`atlas/broker/exceptions.py`: the thirteen-class `BrokerError` tree that every
`Raises:` clause in the port already named. Plain `Exception` subclasses, no
pydantic, no third-party dependency, detail carried as attributes rather than
inside the message, and constructors that only assign — these are built while a
venue is unreachable, so one that can itself fail is a liability.

Two placements are load-bearing and are asserted rather than only written down.
`BrokerAuthenticationError` sits outside `BrokerConnectionError`, so a
supervision loop retrying connection faults cannot swallow a credential that
will never work. `BrokerTimeoutError` sits inside it but means the request may
have been *executed*, which is why every state-changing method documents
reconciliation rather than retry.

On the MetaTrader 5 side the eight temporary `MT5*Error` classes are gone,
`constants.py` gained the 40 deferred `TRADE_RETCODE_*` values, and
`error_from_retcode` maps a trade server's verdict to the hierarchy. The two
integer spaces stay separate: `RES_E_*` says whether the terminal could be
spoken to at all, a retcode says what a server did with a request it received,
and each has its own total classifier with its own fallback.

No trading behaviour was added. The four trading methods still refuse, now
naming what is actually missing — filling mode per instrument, a deviation
policy, and a read-back of the resulting deals — rather than the hierarchy.

### ATLAS-TASK-0006 — `MockBrokerAdapter`

The port's second implementation: `atlas/broker/mock/`, a `MockVenue` holding
state in memory and a `MockBrokerAdapter` implementing all 31 methods against
it. Every method that MetaTrader 5 cannot honour is honoured here — the four
trading methods, both subscribe methods, and `server_time` — which is the
evidence the contract was designed against a specification rather than around a
vendor.

The venue owns the state and the adapter owns the session, so a test asserting
through `adapter.venue` and a test asserting through the port's read methods are
two independent readings that can disagree. The venue signals misuse with
`ValueError` and never with a `BrokerError`, so a test's own bug cannot be
swallowed by the error handling it is exercising.

Deterministic by construction: its own clock from 2020-01-01 UTC, sequential
identifiers from 1, no randomness, no read of the host clock.

The simulation boundary is the decision, and it is recorded in
[ADR-0006](adr/0006-mock-adapter-simulates-bookkeeping-not-price.md). A market
order fills at the published quote; nothing else happens on its own. No resting
order triggers on price, no position is revalued, the account does not respond
to trading. An attached `stop_loss` or `take_profit` is *refused* rather than
ignored, because `Position` has nowhere to report one and a silent no-op would
hide the gap for exactly as long as the position is open.

`tests/unit/broker/test_adapter_conformance.py` arrived with it: it discovers
every concrete `BrokerAdapter` in the package by walking it, and holds all of
them — not just this one — to identical signatures and the five capability
protocols.

### ATLAS-TASK-0007 — `BaseBrokerAdapter`

`atlas/broker/base.py`: a class between the port and its implementations, which
both adapters now inherit from. It is not in the port itself because a replay
engine has nothing to reconnect to and should not inherit the concept.

What moved into it is what the two adapters were genuinely duplicating: the two
cached session readings, the `Connection` snapshot assembled from them, and
`is_connected` and `health`, which need nothing but that snapshot. A subclass
answers three properties — where its state lives, and who is at the far end —
and gets both reads for free. The public `BrokerAdapter` interface did not
change, and neither adapter's observable behaviour did.

What did *not* move is the more interesting half, because each case is a real
difference rather than an accident, and lifting it would have been a regression:

- **Connecting.** MT5 re-reads the brokerage name on a redundant connect; the
  mock keys scheduled faults by operation so a test can fail `connect` and
  `reconnect` independently.
- **The clock.** MT5 stamps a heartbeat from the host; the mock stamps it from
  the venue's own clock, which is what makes it deterministic.
- **The not-connected guard.** The mock checks on entry to each method; MT5
  checks once, inside `MT5Session.terminal()`. The refusal a caller sees is
  identical, and a test asserts that across every guarded method on both.
- **Locking.** Left out here, and written next. Serialising access was behaviour
  *neither* adapter had, which made it an addition rather than part of this move
  — the reason it was excluded from a refactor whose brief was not to change
  behaviour. `base.py` was named as where it belonged, and ATLAS-TASK-0008 is
  where it went.

The class is deliberately not exported from `atlas.broker`. That namespace is
what a caller depends on, and a caller has no use for a base class; an adapter
author imports from `atlas.broker.base`. `base.py` is also in the port's AST
import scan, so the same rule that keeps a venue SDK out of the port keeps one
out of the base.

No ADR was added or changed. Nothing recorded in an existing one was reversed —
the boundary above is reasoning about *this* class, and it lives in its module
docstring where an implementer reading the class will find it.

### ATLAS-TASK-0008 — adapter concurrency

`BaseBrokerAdapter` gained two locks and, with them, the lifecycle itself.
`connect`, `disconnect` and `reconnect` are the base's own methods now: each
takes the session lock and delegates to a `_connect`, `_disconnect` or
`_reconnect` hook that the subclass supplies and that runs with the lock already
held. Neither adapter names a lock anywhere, and exactly one module in
`atlas.broker` imports `threading` — asserted by a test rather than left to
review, because duplicated locking is the failure this placement exists to avoid.

The public `BrokerAdapter` interface did not change, and neither adapter's
observable behaviour did. [ADR-0007](adr/0007-two-locks-in-the-base-adapter.md)
records the contract in full: what is guaranteed, what is deliberately not, and
why each rejected alternative was rejected. Two decisions carry it.

- **The session lock is re-entrant; the readings lock is not.** Both adapters
  compose a reconnect out of the public `disconnect` and `connect`, so the
  session lock is re-acquired on every reconnect and a plain lock would make the
  obvious way of writing `_reconnect` a self-deadlock — found in production, by
  whoever writes the third adapter, at the moment a session needed replacing. The
  readings lock is a leaf, and a plain lock there fails loudly if it ever stops
  being one.
- **Supervision is never blocked.** `health()` and `is_connected()` take no
  session lock, so a supervisor still answers while a connect is parked inside an
  unresponsive terminal — the one moment it exists for. That is asserted against
  the real connect path, by parking a real adapter inside it, rather than against
  a lock held by hand. The other twenty-six port methods take no lock at all.

One behavioural adjustment was needed, and it is a write ordering rather than a
third lock: both adapters now clear the cached readings *before* taking the
session down, which closes the window in which a racing `health()` reports no
session and a live latency in the same snapshot.

65 concurrency tests were added in `tests/unit/broker/test_adapter_concurrency.py`.
Every test asserting that something *cannot* happen is paired with one asserting
that the opposite case does, because a suite in which nothing is ever blocked is
satisfied just as well by an adapter holding no locks — which is the state this
task started from.

An 18-mutant campaign over the new synchronisation — each lock removed, weakened,
widened, aliased, shared between instances, and the teardown write order reversed
— killed 16 on the first run. Both survivors were gaps in the tests rather than
equivalent mutants: removing the lock from `reconnect` alone, and building the
`Connection` model under the readings lock. Both are killed now. The first is the
more instructive: because each half of a reconnect takes the lock on its own
account, the halves never overlap even when the outer call holds nothing, so the
tests had to be rewritten to assert the lock's *hold depth* instead.

### ATLAS-TASK-0009 — the `Clock` abstraction

`atlas/common/clock.py`: a `Clock` protocol with two methods, a `SystemClock`
that reads the host, and a `ManualClock` that moves only when told to. The first
thing `atlas.common` has ever contained, and the first time any package has taken
the dependency the architecture has permitted since ATLAS-TASK-0001.

The port has **two hands because there are two questions**, and conflating them
is the bug it exists to prevent. `now()` answers *when* — an aware UTC instant
that goes into a `Connection` and that a person reads. `monotonic()` answers *how
long ago*, and its differences are the only durations in the system that survive
a clock correction. A wall-clock step forwards reports a healthy session as an
hour silent; a step backwards makes the age negative, which compares as fresh
against every threshold and silences a supervisor at the moment it exists for.

That is what the two ways of moving a `ManualClock` encode. `advance` is time
passing and moves both hands; `set_time` is the wall clock being *corrected* — an
NTP step, an operator, a zone change — and credits no elapsed time at all. Tests
for immunity to a clock step are only worth anything against a clock that can
actually be stepped.

`BaseBrokerAdapter` gained the measurement the port had been declining to provide:
`heartbeat_age()` and `is_heartbeat_fresh(within)`. Neither stores a threshold,
schedules anything or reconnects — `adapter.py` records that the port imposes no
freshness policy, and that is still true. The policy is the supervisor's; only the
measurement moved down. Both are on the base and **not** on the 31-method port,
because widening a contract every adapter implements, for something the base gives
all of them for free, is a breaking change that buys no capability.

Injection is keyword-only and optional, so every existing `super().__init__()`
kept working. `MT5BrokerAdapter` passes a clock through and defaults to the host,
which is what production runs on. `MockBrokerAdapter` deliberately accepts **no**
clock: it takes its venue's, because a mock holding a clock its venue does not is
how a deterministic test stops being deterministic.

[ADR-0008](adr/0008-time-is-injected.md) records the decision, including why
`set_time` crediting elapsed time would have made every clock-step test pass
against a clock with no such immunity.

The lock rules from ADR-0007 constrained the implementation rather than being
revisited by it: the clock is read *before* the readings lock in all three places
that take it, because a clock arrives from outside the package and calling one
under a leaf lock is how a leaf stops being one. Neither new method touches the
session lock, so supervision is still never blocked.

130 tests were added — 36 for the clock itself, 91 for heartbeat freshness across
every discovered adapter, and 3 for the widened import rule. Nothing sleeps: a
365-day silence is asserted as an exact `timedelta`. Two are structural. No module
in `atlas.broker` may call the host clock directly, the same shape of assertion
that keeps `threading` in one file; and `test_adapter_contract.py`'s "imports
nothing but `atlas.broker`" was widened to name `atlas.common`, with the three
new tests proving the widened rule still refuses `atlas.risk`,
`atlas.execution`, `atlas.strategy` and `atlas.config`.

A 17-mutant campaign killed 16 on the first run. The survivor was a gap rather
than an equivalent mutant: `SystemClock.monotonic` returning a wall-clock
timestamp satisfied every property the tests asserted, because a wall clock is
also a float that does not go backwards within a run. It is killed now, by
asserting where the reading comes from and that the two hands have unrelated
origins. One equivalent mutant remains and is left alone — reading the venue
clock's private instant instead of calling `now()` differs only by a lock
acquisition on a value whose read is already atomic.

### ATLAS-TASK-0010 — retry and reconnection policy

`atlas/common/retry.py`: a frozen `RetryPolicy` and a `retry_call` that executes
one. A retry loop written inline is three decisions welded to a call site — how
many attempts, how long between them, and which failures are worth repeating —
and welded they cannot be configured, cannot be tested without provoking the
failure they exist for, and get rewritten slightly differently at the next call
site. This takes them apart.

**The policy is a value.** It holds no clock, no exception types and no reference
to whatever is being retried, so it can be built in a config module, compared,
logged and asserted on. `delays()` returns the whole schedule as a tuple, which
is what makes "exponential backoff progresses 1, 2, 4" a statement about a value
rather than about a run. Four named constructors — `none`, `immediate`, `fixed`,
`exponential` — and a constructor that refuses a policy that could not mean what
it says: fewer than one attempt, a negative delay, a multiplier below one that
would *shrink* each wait, or a ceiling below the first delay that would make
`initial_delay` a silently ignored field.

**The default is one attempt.** Retrying is opted into. A policy that retried by
default would change the behaviour of code that never asked for it, and the only
symptom of a wrongly retried call is that it took longer to fail — which is also
what makes the regression evidence possible: every adapter constructed the way it
was before this task behaves exactly as it did.

**The waiting belongs to the clock.** `Clock` gained a third member, `sleep`, and
it is the port's only *verb*. It is there rather than on a separate `Sleeper`
because waiting and elapsed time are one fact, and two collaborators that must
agree about elapsed time are a bug surface. `ManualClock.sleep` is `advance`, so
a hundred-second backoff runs in no time and the resulting instant is asserted
exactly. Nothing in `retry.py` reads the host clock, and a static scan in
`tests/unit/common/test_retry.py` asserts it — a real sleep would leave a manual
clock exactly where the assertions expect it, and pass.

**Which failures is a domain fact, so it is a parameter.** `retry_call` takes
`retry_on` and a `give_up_on` that carves types back out of it, and `base.py`
states the broker's answer by reading the exception tree that already existed:
`RETRYABLE_ERRORS = (BrokerConnectionError,)`, `PERMANENT_ERRORS =
(BrokerNotConnectedError,)`. `BrokerAuthenticationError` needs no entry because
ATLAS-TASK-0005 deliberately did not make it a `BrokerConnectionError` — a
credential the venue refused is not going to be accepted on the third ask. The
tree had encoded that distinction for five tasks and nothing had ever read it.

Integration is in `BaseBrokerAdapter` and nowhere else. `connect` and `reconnect`
are wrapped; `disconnect` is not, because the port requires it to succeed and
retrying a teardown is repeating an operation the venue may already have honoured.
Both adapters inherit it and neither implements any of it.

Two consequences the lock rules forced. **Attempts do not multiply**: MT5's
`_reconnect` is composed from the public `disconnect` and `connect`, so a naive
wrapper would make a three-attempt policy mean nine attempts there and three on
the mock. A `_retrying` flag, read and written only under the re-entrant session
lock and cleared in a `finally`, makes only the outermost call retry. And **the
backoff waits inside the session lock**, because ADR-0007 fixed that a reconnect
is one critical section and not two; `health()`, `is_connected()` and
`heartbeat_age()` take no session lock, so supervision still answers throughout a
sixty-second backoff, and both halves of that are asserted from a second thread.

[ADR-0009](adr/0009-retry-is-a-value-and-the-waiting-is-the-clocks.md) records
the decision and nine rejected alternatives. `packages/common/src/atlas/common/README.md`
was written, closing the gap ATLAS-TASK-0009 observed.

183 tests were added — 61 for the policy and `retry_call`, 110 across every
discovered adapter, and 13 for `Clock.sleep`. A 34-mutant campaign killed 33 on
the first run. The survivor was a gap rather than an equivalent mutant: the first
attempt's delay being zero was asserted only against `RetryPolicy.none()`, whose
`initial_delay` is zero anyway, so returning `initial_delay` there was the same
answer by accident. It is killed now by asking the same question of a policy that
actually waits.

### ATLAS-TASK-0011 — the risk boundary

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

`atlas/risk/contracts.py`: `TradeIntent`, `RiskVerdict`, `VerdictStatus` and
`RejectionReason`. The architecture's first invariant — a trade intent becomes
an order only by passing through `atlas.risk`, and every other safety property
depends on it — had been prose for ten tasks. Nothing said what an intent *was*,
or what passing through risk *returned*. This gives the invariant its
vocabulary.

**The shape that was avoided.** Left undefined, the boundary gets decided by
whichever task needs it first, and the likely accident is a strategy that builds
the thing execution already accepts — an `OrderRequest` — with risk invoked to
validate it afterwards. At that point risk is advisory: the object exists, its
size is chosen, and the only power left is to veto a decision someone else has
made. `OrderRequest` had already said where the line is, in its own words: whether
a request is *wise* "is a risk decision, made against state neither this model nor
the port can see". These are the types that decision is expressed in.

**A verdict is two-valued, and the number carries the nuance.** A reduced-size
approval is `APPROVED` with a smaller `approved_volume`, not a third status. A
`REDUCED` member would force every consumer to handle two spellings of "yes",
and the first one to handle only `APPROVED` sizes the position off the requested
volume — silent, correct-looking in every test that does not reduce, and wrong
only in the case the status was added for. `approved_volume` is `None` on a
rejection, which makes ignoring the status uninteresting rather than merely
forbidden: there is no number to bypass with.

**Risk may reduce; it may never enlarge.** A validator refuses an
`approved_volume` above the requested one. A boundary that can return a larger
number than it was given is a second, unreviewed sizing authority.

**The primitives are the broker's.** `SymbolName`, `OrderSide`, `Price` and
`Volume` are imported rather than redefined, for the reason `broker/types.py`
gives for its own aliases — two definitions of one concept diverge, and these
would diverge exactly at the translation boundary, where nobody is looking. That
adds `atlas.risk → atlas.broker`, the second edge between feature packages in
the graph and the first since `broker → common`. It runs downward, and
`tests/unit/risk/test_risk_boundary.py` asserts it did not become several, that
no risk module names `OrderRequest`, `OrderType`, `BrokerAdapter` or any order
verb, and that `atlas.broker` still contains no import of `atlas.risk`.

**What this task does not claim.** `atlas.strategy` and `atlas.execution` remain
empty stubs, so nothing produces an intent and nothing consumes a verdict. The
invariant has two halves — risk cannot be bypassed, and execution acts only on
approved output — and only the structural half is provable today. The boundary
test records that limitation in its own docstring rather than leaving a reader
to infer the coverage is wider than it is. No sizing algorithm, exposure limit,
drawdown control, correlation cap or kill switch exists; constructing an
`APPROVED` verdict does not make it true.

[ADR-0010](adr/0010-the-risk-boundary-is-a-verdict-on-an-intent.md) records the
decision and eleven rejected alternatives.
`packages/risk/src/atlas/risk/README.md` was written.

117 tests were added — 29 for the intent, 37 for the verdict and 51 for the
boundary, including six that assert the AST scanners can actually fail, because
a scan that inspects nothing passes everything. A 30-mutant campaign killed 29.
The survivor is equivalent and is left alone: removing `@unique` from
`VerdictStatus` changes no behaviour while the members' values stay distinct,
and `enum.unique` leaves no runtime marker to assert against — it guards a
future edit rather than a current one.

### ATLAS-TASK-0012 — the strategy boundary

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

`atlas/strategy/contracts.py`: `Strategy`, a runtime-checkable protocol with one
method, `propose(observation, /) -> TradeIntent | None`. ATLAS-TASK-0011 gave the
first invariant its vocabulary; this gives it a producer. A strategy is the only
thing in Atlas that originates a `TradeIntent`, and returning one or returning
`None` is the whole of its authority.

**A protocol, not a base class.** Structural typing, for the reason
`atlas/broker/protocols.py` gives for the capability protocols: nothing has to
inherit from these. A strategy is a behaviour, and a required base class would
mean a research notebook, a replay harness and a live component could not be the
same thing unless all three imported it. It would also hand this package a
concrete class to put shared behaviour in, and the first thing that lands in one
is a lifecycle — which this task does not own.

**The input is a type parameter this package does not name.** `Strategy[InputT]`
is generic because what a strategy looks at belongs to `atlas.market`,
`atlas.features` and `atlas.regime`, which are all still stubs. Naming a
concrete input here would fix their shape before they exist, from the package
with the least standing to do it. No market-data contract is defined by this
task. `observation` is positional-only, so an implementation may name it
whatever reads best.

**`None` is the answer to "no opinion".** The alternative — an empty intent, or
a sentinel meaning "ignore me" — puts a value into the pipeline that looks
tradeable, and the first consumer that forgets to check it sends it to risk.
There is no such object to forget about.

**No dependency on `atlas.broker` at all.** `atlas.risk` is the only `atlas`
package a strategy module imports. A `TradeIntent` is stated in `SymbolName`,
`OrderSide`, `Price` and `Volume`, and under `mypy --strict` with `init_typed`
anything that *builds* one must name them — `TradeIntent(side="BUY")` is a type
error even though the string works at runtime. The conclusion drawn is that
nothing in the package builds one: the contract names `TradeIntent` in an
annotation, and a concrete intent is constructed by whoever hands one over,
which today is test code. `BrokerAdapter`, `OrderRequest`, `OrderType`,
`OrderStatus` and the four order verbs appear nowhere in the package, and
nothing was re-exported through `atlas.risk` to get around the rule.

**An inert reference implementation.** `atlas/strategy/reference.py` holds
`ConstantStrategy`, which answers with the intent it was constructed with,
whatever it is shown — `ConstantStrategy()` abstains and
`ConstantStrategy(intent)` recommends that intent. It reads no market data,
performs no I/O, holds no clock, draws no randomness, calls no venue and raises
nothing of its own, and the tests assert each of those against its source rather
than trusting the sentence. That inertness is the design: a reference
implementation that could see a price is one edit away from being a trading
strategy, and it is the kind of edit nobody reviews closely because the file
already existed. It takes a finished intent rather than building one from
`symbol`, `side` and `volume`, which reads less nicely and is what keeps the
port out of the package. It is not exported from `atlas.strategy`, for the
reason `MockBrokerAdapter` is absent from `atlas.broker`. It makes no claim
about profitability and must not be deployed or extended into something that
trades.

**What this task does not claim.** There is no lifecycle, no registry, no engine,
no scheduling and no event subscription — the rest of what the responsibilities
table gives `strategy`. `atlas.execution` remains an empty stub, so nothing
consumes a `RiskVerdict`, and the behavioural half of the first invariant still
waits on a pipeline to observe. No risk control, sizing rule or real strategy was
written.

**No ADR was added, and none was reversed.**
[ADR-0010](adr/0010-the-risk-boundary-is-a-verdict-on-an-intent.md) records that
`atlas.strategy` would depend on the port's types *transitively*, quotes the
strategy stub's "nothing here may reach a broker directly", and rules that the
wording survives that. This task takes no such dependency, so the ADR's ruling
stands untouched and the sentence it quotes is still in the stub verbatim. The
decisions above are recorded in the module docstrings, in
`packages/strategy/src/atlas/strategy/README.md` and in the boundary test.

A later task that gives a real strategy the job of constructing its own intent
will meet the question this one sidestepped — that strategy will have to name
the four primitives — and it should answer it by superseding ADR-0010, not
in prose.

155 tests were added — 90 for the boundary and 65 for the reference
implementation, 45 of which exist only to assert that the AST scanners can
actually fail, because a scan that inspects nothing passes everything. CI was
green on the merge commit: Ruff, Black and MyPy clean across 94 source files,
3072 passed and 105 skipped of 3177 collected, and total coverage at 99%. The
105 skips are the MetaTrader5 vendor-comparison tests, whose wheel installs on
Windows only; they skip on every Linux run and none of them belong to this
task.

### ATLAS-TASK-0013 — documentation and release-metadata debt

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

No source file changed. This task closes what the debt section below had
recorded, corrects the one live document ATLAS-TASK-0012 left stale, and settles
a contradiction between two process documents. It implements nothing, decides no
architecture, and adds, edits and supersedes no ADR.

**The version says one thing in three places.** ATLAS-TASK-0004 was specified as
`v0.2.0-alpha` and the repository had stayed on `0.1.0a0`. `pyproject.toml` is
the source of truth and now declares `0.2.0a0`; `docker-compose.yml` tags the
`atlas-core` image to match, which `tests/contract/test_repository_structure.py`
already asserted and still does; and `README.md`'s banner reads `v0.2.0-alpha`.
That banner is the one copy no test binds, and it stays that way deliberately —
a test that read prose would make the banner's wording a contract.

**The stale sentence was in one place, not several.**
`packages/risk/src/atlas/risk/README.md` said `atlas.strategy` and
`atlas.execution` were both still empty stubs, which ATLAS-TASK-0012 made half
untrue. It is corrected in place, and says what is now the case: `strategy` has
a contract and an inert reference implementation, no engine drives one, and
`execution` is still a stub. Every other occurrence of that wording was checked
and left alone. `README.md`, `docs/architecture/overview.md`,
`packages/strategy/src/atlas/strategy/README.md` and both boundary tests name
`atlas.execution` alone and are still true. ADR-0010 says the same thing and is
an accepted record, immutable by the rule in `docs/adr/README.md`. The
ATLAS-TASK-0011 section above is a dated account of what that task did not
claim, not a live statement about today.

**Supersession, not amendment.** The ATLAS-TASK-0012 section above told a later
task to answer a question by "amending or superseding" ADR-0010. `docs/adr/`
allows no such thing: an ADR is immutable once accepted, and the statuses
defined there are `Proposed`, `Accepted`, `Superseded by ADR-NNNN` and
`Deprecated`, with no amendment among them. This file was the one in the wrong
and the phrase is gone. Nothing was added to the ADR process to meet it halfway
— removing a mechanism that never existed decides nothing, and inventing an
`Amended` status would have decided a great deal.

No test was added, and none was changed. The changes are documentation and
release metadata; the single claim among them that a test can hold — that the
`atlas-core` image tag and `[project].version` are the same string — was already
covered by a contract test that fails when the two drift, which is why the bump
touched `docker-compose.yml` in the same breath as `pyproject.toml`.

### ATLAS-TASK-0014 — the execution contract

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

`atlas/execution/contracts.py`: `ExecutionPolicy`, and
`build_order_request(verdict, policy) -> OrderRequest | None`. ATLAS-TASK-0011
gave the first invariant its vocabulary and ATLAS-TASK-0012 gave it a producer;
this gives it a consumer. An approved `RiskVerdict` becomes the `OrderRequest` a
venue would be asked to fill, and a rejected one becomes nothing. The decision
is ADR-0011, accepted with this task.

**The volume is the approved volume.** Never `TradeIntent.requested_volume`.
A reduced approval is an approval carrying a smaller number, and reading the
requested figure instead is the specific accident ADR-0010 rejected a third
`REDUCED` status to prevent. Three tests hold it, all of them at sizes strictly
below the request, because `RiskVerdict` refuses to be constructed the other way
round — risk may reduce an intent but never enlarge one.

**Naming the port is not calling it.** `OrderRequest`, `OrderType` and `Price`
are imported from `atlas.broker` rather than restated, which is the rule
`atlas.broker.types` applies to its own aliases: two definitions of one concept
"would create two rules for one concept and guarantee they diverge". The edge
that import creates is a type dependency and nothing else. The whole identifier
surface of the package is twenty-four names, and `BrokerAdapter`, the port's four
trading verbs and `OrderStatus` are absent from all of them; the only calls
anywhere in the package are `ConfigDict`, `Field` twice, and `OrderRequest`.
A layer that owns broker interaction still does not exist, and this task did not
invent one.

**Presentation is supplied, not chosen.** The order type and working price
arrive as a caller-supplied `ExecutionPolicy` — frozen, two fields, no default.
A default written here would settle filling-mode selection and a deviation
policy, the two questions `atlas.broker.mt5.adapter` names as having no
"obviously right answer", inside the package least likely to be read as policy.
Nothing stores a policy, nothing reads one from configuration, and
`AtlasSettings` is unchanged: the package's only module-level assignments are
its two `__all__` lists.

**`STOP_LIMIT` is out of reach, deliberately.** It is the one `OrderType` that
needs both a working price and a separate trigger, and a policy with exactly two
answers cannot supply both, so `OrderRequest`'s own validator refuses it. The
specification fixed the policy at two answers; the implementation supplies no
third value rather than inventing one, and a passing test characterises the
refusal so the limit is recorded rather than latent. Widening the policy is a
decision for the task that needs `STOP_LIMIT`, and this was not it.

`tests/unit/execution/test_execution_boundary.py` is the enforcement, since
there are no per-package manifests and the distinction the task rests on is
invisible to both the type checker and the packaging. It follows the scanners in
the risk and strategy boundary tests, and adds the mechanic this package needs:
an allowlist, so that the three vocabulary names pass and every other name taken
from the port is an offence — including `import atlas.broker`, which binds the
module and so reaches `BrokerAdapter` by attribute. Six of its tests splice a
forbidden import into the real source of each shipped module and assert the
scanner reports it, on the ATLAS-TASK-0012 standard that a scan which inspects
nothing passes everything.

CI passed on the merge commit the row above cites. Locally: Ruff, Black and MyPy
clean across 97 source files, 3296 passed, and `atlas.execution` at 100% of both
statements and branches.

### ATLAS-TASK-0015 — living-document correction

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

No source file changed. ATLAS-TASK-0014 gave the risk verdict its consumer, and
the documents describing that boundary went on saying otherwise:
`atlas.execution` was an empty stub, the graph held three edges, and
`docs/architecture/overview.md` was current as of ATLAS-TASK-0012. Each
statement was true when written and false on merge. This task corrects the three
documents that carried them and does nothing else — no test, script or tool is
added, no ADR is created or edited, and no edge is created, removed or changed.

**The banner is dated forward, not undated.** `docs/architecture/overview.md`
now reads "Status at ATLAS-TASK-0014", enumerates `atlas.execution` as narrowly
as it is implemented, and names this file as the authoritative record of which
tasks are complete, with the roadmap governing where the two disagree. The
alternative was to remove the date entirely. A dated banner that falls behind
announces itself against the last row of the table above; an undated one that
has drifted is silently wrong, which is the failure being corrected here.

**Five edges, named individually.** The overview said three. Naming them is not
stylistic: a wrong list is falsifiable by inspection and a wrong integer is not,
and the integer is what went stale. The count is derived from the AST import
graph rather than counted by hand, because the `atlas.execution → atlas.risk`
import sits under a `TYPE_CHECKING` guard — it is indented, and a line-anchored
grep reports four.

**What is not claimed matters as much as what is.** The chain the data flow
draws is still not joined end to end, and the corrected documents say so:
nothing outside the test suite produces a `TradeIntent`, no function anywhere
turns one into a `RiskVerdict`, and no layer owns a `BrokerAdapter`, so the
request `atlas.execution` builds is received by nothing. `atlas.risk` still
holds its two contracts and none of the controls that reach a decision.

One acceptance criterion had to be corrected before the work could be accepted.
As written it required a `git grep` over `docs/` to return nothing, which no
implementation could satisfy: the string survives in ATLAS-TASK-0014's
out-of-scope section, which is a historical record that later tasks do not edit,
and in the specification's own problem statement, and in the criterion itself.
It is now scoped to `docs/architecture/` and `packages/`, where it returns
nothing.

This task reached `main` by direct push rather than through a pull request,
unlike ATLAS-TASK-0011 through ATLAS-TASK-0014, so there is no merge commit for
the row above to cite and it cites the implementation commit, as the rows for
ATLAS-TASK-0011, ATLAS-TASK-0012 and ATLAS-TASK-0013 do. CI passed on that
commit itself, both jobs green, so there is no gap of the kind recorded at ‡.
Locally: Ruff, Black and MyPy clean across 97 source files, 3296 passed.

### ATLAS-TASK-0016 — completing the living-document correction

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

No source file changed. ATLAS-TASK-0013 enumerated by name every location
carrying the claim that `atlas.execution` was an empty stub consuming no
verdict; ATLAS-TASK-0014 made all four false, and ATLAS-TASK-0015 corrected two
of them. This task corrects the remaining two — `README.md` and the module
docstrings of the risk and strategy boundary tests — and empties that list. It
is the third pass at the same drift.

**The duplicated status line is removed rather than re-dated.** `README.md` read
"Last completed: **ATLAS-TASK-0012 — the strategy boundary**", three tasks
behind. That line restated the last row of the table above and then linked to
the table, so it carried no fact this file does not, and it was the only line in
the file that had gone stale — the Status section's inline references,
`(TASK-0011)` and `(TASK-0012)`, pin facts that have not moved and are still
correct. It now names this file as the authoritative record of which tasks are
complete and names no task itself. Re-dating it to ATLAS-TASK-0015 was
considered and rejected: it cures the defect for exactly one task and re-arms
it on the next. That is the opposite of the answer ATLAS-TASK-0015 reached for
the overview banner, and the difference is the content: that banner enumerates
which packages hold implementation, which this file does not record, so not
duplicating it was never an option there. Here it was, and no dated banner
replaces the removed line.

**The reason was stale; the conclusion was not.** Both test docstrings concluded
that only the structural half of the first invariant is provable today, and gave
"`atlas.execution` is still an empty stub" as the reason. The conclusion is
still true and survives verbatim; the reason is replaced with the true one —
nothing outside the test suite produces a `TradeIntent`, and nothing anywhere
turns one into a `RiskVerdict`, so there is no pipeline to observe. Neither
docstring claims wider coverage than it claimed before, which is the specific
way this correction could have gone wrong. `README.md` gained a paragraph naming
what `atlas.execution` actually holds, and the two neighbouring sentences that
addition would otherwise have falsified were dealt with rather than left: the
count of boundaries, corrected from two to three, and the sentence asserting by
omission that every package not named above has no implementation, which stands
verbatim and is true again because `atlas.execution` is now named above it.

**No test behaviour changed, and that is proved rather than asserted.** For each
of the two test files, the abstract syntax tree with the module docstring
removed is identical to the baseline's, compared as `ast.dump` output with
attributes excluded. No test, fixture, helper or assertion was added, deleted or
altered, and the suite still collects 3296 tests. The five dependency edges are
unchanged, derived from the AST import graph rather than counted by hand.
`tests/unit/execution/test_execution_boundary.py` was not touched: its docstring
matches the same search patterns this task worked from and is about a consumer
of the `OrderRequest`, which is still true.

**What was not built.** No risk control and no producer of a `RiskVerdict`, no
layer owning a `BrokerAdapter`, no run loop, no message bus, no market
ingestion, no MT5 trading method, no configuration surface, and no ADR — none of
the architecture the repository has deliberately deferred. The two substantive
directions remain blocked behind decisions this file does not make, and nothing
in this task's diff is groundwork for either. The corrected documents say the
chain is still not joined end to end, because it is not.

This task reached `main` by direct push rather than through a pull request, as
ATLAS-TASK-0015 did, so there is no merge commit for the row above to cite. It
has two commits. The first, `d0364dd9ef28de52ef8245a2f90263d16c9d9f78`, applied
the three corrections and added the specification; the second,
`c37b0ebba3b4206705dfd8c06ba6e96c9ebfcf48`, corrected the specification's own
account of coverage, which had said no baseline figure existed to compare
against when what is true is narrower — the local quality gate does not measure
coverage and CI does, and this task altered neither. The row above cites the
second, which holds the final state. CI passed on both, verified by `head_sha`
rather than by recency: run `31655632275` against `c37b0ebb`, Quality Gate and
Container & Compose both green, so there is no gap of the kind recorded at ‡.
Locally: Ruff, Black and MyPy clean, 3296 passed — the baseline count,
unchanged, which is the evidence that nothing outside the scope was touched.

### ATLAS-TASK-0017 — the first risk control

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

`packages/risk/src/atlas/risk/exposure.py` holds `evaluate_exposure(intent,
account) -> RiskVerdict`, a portfolio margin-utilisation limit. ATLAS-TASK-0011
gave the first invariant its vocabulary, ATLAS-TASK-0012 gave it a producer and
ATLAS-TASK-0014 gave it a consumer; this is the first thing in `atlas.risk` that
reaches a decision. An intent is approved unchanged while `Account.margin` over
`Account.equity` is strictly below the maximum the process is configured to
permit, and rejected with `EXPOSURE_LIMIT` otherwise. There is no reduction path
and no third answer. The decision it implements is
[ADR 0012](adr/0012-risk-is-handed-its-state-and-reads-its-own-limits.md).

**The verdict does not depend on the size of the intent, and that is written
down.** ADR-0012 forbids risk from calling the port, so this control cannot ask
what an intent would cost in margin — the port's `margin_required` is exactly
the operation the boundary test asserts no risk module can reach. It judges the
exposure the account already carries, which means a 0.01-lot intent and a
100-lot intent against the same `Account` get the same answer. That is a real
limitation of a portfolio-level control that may not consult the venue, and it
is stated in the module's own docstring and asserted by a test rather than left
for a reader to infer from the code.

**The comparison is exact integer arithmetic, not decimal arithmetic.**
`margin / equity < limit` rounds the quotient to the ambient decimal context and
at the interpreter's default precision approves cases that should reject;
`margin < limit * equity` rounds the product instead and raises
`decimal.Overflow` on a large finite limit. Both borrow a precision from a
context nothing in this repository sets. Instead each operand is taken apart
with `Decimal.as_integer_ratio()` and the inequality is cross-multiplied in
unbounded integers, so there is no rounding step, no precision, no context and
no trap, and the comparison is total on every finite `Decimal` — including
`1E+999999`, which is where the two rejected formulations fail.

**An unusable account state is not a reason to permit new exposure.** A
non-finite margin, equity or limit fails closed, and so does non-positive
equity, checked in that order: a non-finite `Decimal` has no integer ratio, and
cross-multiplying an inequality is valid only where equity is positive. Nothing
raises. A control that threw where it was asked to judge would be bypassable by
an exception handler one layer up, so a blown account and a venue reporting a
non-finite amount are refusals rather than errors. `status` and `reason` are
identical for every refusal this control makes, which leaves `detail` as the
only field that tells an operator which refusal it was.

**The default permits nothing, and the deployment supplies the number.**
`RiskSettings.max_margin_utilisation` is a `Decimal` defaulting to `0`,
constrained `ge=0` with `allow_inf_nan=False` and no upper bound. Because the
comparison is strict, that default refuses every intent — absence of
configuration is not permission. No file under `config/` sets a value, because
any positive value is a trading policy and belongs to the deployment rather than
to the repository, for the reason ATLAS-TASK-0014 gave for refusing to default
an `ExecutionPolicy`. A process resolved to `production` **or** `demo` refuses
to start until the limit is above zero. `Environment.is_live` still means
`production` alone, and the debug, logging-format and postgres-password
invariants still apply to `production` alone; the start-up check was restructured
to collect violations from two conditions rather than one, not widened.

**A second edge out of risk, under a name allowlist.** `atlas.risk` →
`atlas.config` is the sixth edge between feature packages and the second out of
`atlas.risk`. It carries exactly one name, `get_settings` — enough to read this
package's own limit and nothing else — and the limit is read on every call
rather than held, so nothing caches a settings object, a section or a number at
import time. `tests/unit/risk/test_risk_boundary.py` gained the allowlist of
permitted names, and a separate scan asserting that no risk module reaches a
credential-bearing configuration name: reaching a database password through a
settings object requires no import at all, so an import allowlist cannot see
that far on its own. The graph is still acyclic, and `atlas.config` still
imports no feature package.

**ADR-0012 was brought under version control unmodified.** It had been accepted
and was present on disk but untracked, which is why this task treats committing
an unmodified file as distinct from writing or changing one: its blob is
`497ab06f8bfb5aad3b5344fd27319c34d3dd6537` both before the task and in the
commit, and it entered history as an addition. No ADR's content was created or
altered here.

**What this task does not claim.** There is no sizing algorithm, no drawdown
control, no correlation cap and no kill switch; the other three `RejectionReason`
members remain unimplemented, and the package's responsibility in the overview's
table still names four things this delivers one of. There is no risk engine and
no pipeline: nothing outside the test suite produces a `TradeIntent` or hands
one to `evaluate_exposure`, and no layer owns a `BrokerAdapter`, so the chain
the data flow draws is still not joined end to end. The behavioural half of the
first invariant still waits on something that drives a strategy, reaches a
verdict and calls the translation in sequence.

Fourteen places propagated the change. Eleven were prose statements that became
false: `README.md`, three passages in `docs/architecture/overview.md`, three in
`packages/risk/src/atlas/risk/README.md`, the package docstring, the
`RejectionReason` docstring, and the risk and strategy boundary-test docstrings.
The `config/production` header comment became incomplete rather than wrong — an
operator satisfying every invariant it listed would still have been refused
start-up. Three copies of the `atlas.risk.__all__` assertion are test assertions
rather than prose, and would have failed. `.env.example` stated nothing false;
it catalogued no variable for a limit a demo or production process now cannot
start without. One of the overview passages — a sentence in the overview
describing what the risk boundary test asserts — was found during implementation
rather than during specification, and the specification was amended once, after
its own final audit, to authorise that single sentence rather than let the
implementation quietly widen its own scope. That amendment is recorded in the
specification's §1.

84 tests were added: 29 for the control, 41 for the widened boundary and the
credential scan, and 14 for the configuration field and its start-up invariant.
The final count reconciles rather than being discovered — `3296 − 1 + 10 + 84 =
3389`, where the `−1` is `atlas.config` leaving the forbidden-package
parametrisation and the `+10` is the new module joining `RISK_SOURCES` in two
files. Six mutations of the control were each observed to fail at least one
test: `<` widened to `<=`, both disqualified arithmetic formulations, each of
the two guards removed, and a real credential access injected into the module.
Removing the equity guard is caught by exactly one test, which is the test that
exists because the specification shows that guard changes no verdict — only the
`detail` an operator reads.

This task reached `main` by direct push rather than through a pull request, as
ATLAS-TASK-0015 and ATLAS-TASK-0016 did, so there is no merge commit for the row
above to cite. It has one commit, `4147f12c`, covering 17 files. CI passed on
it, verified by `head_sha` rather than by recency: run `31733801506` against
`4147f12c`, concluded successful, so there is no gap of the kind recorded at ‡.
Locally: Ruff, Black and MyPy `--strict` clean, 3389 passed.

### ATLAS-TASK-0018 — indexing ADR-0012

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

`docs/adr/README.md` received exactly one inserted row, for ADR-0012. ADR-0012
was accepted, and ATLAS-TASK-0017 committed it, but that task's forbidden list
held the index, so the repository carried a committed ADR that its own committed
index did not list. This task added the row and did nothing else: one file, one
insertion, no deletion.

**Both cells were transcribed rather than written.** The index's Title column
has carried each ADR's own H1 with the `# ADR NNNN — ` prefix removed, and its
Status column that ADR's `**Status:**` field, for all eleven rows preceding this
one — checked against the eleven files rather than assumed. The new row's title
is ADR-0012's H1 less that prefix and its status is `Accepted`, the status the
ADR itself carries, so nothing about the decision is restated here in different
words. ADR-0012's content did not change: its blob is
`497ab06f8bfb5aad3b5344fd27319c34d3dd6537` before this task and in its commit.

**Nothing else was touched.** No source file, no test, no configuration, no
`.env` catalogue, no ADR's content, no task specification and no other document
changed. This roadmap did not change either — the entry you are reading is a
separate closeout, as ATLAS-TASK-0016 and ATLAS-TASK-0017 were closed out.

**The test suite does not verify this change.** No test reads
`docs/adr/README.md`. `tests/contract/test_repository_structure.py` asserts that
the directory `docs/adr` exists and asserts nothing about its contents, and no
other test parses the index or enumerates the ADR files. The suite would have
passed identically had the row been omitted, misspelled, given a status the ADR
does not carry, or pointed at a file that does not exist. Acceptance therefore
rested on mechanical checks of the file and its diff, not on a green suite: the
table parses to twelve rows numbered `0001` through `0012`, the link resolves to
a file on disk, the diff is one insertion and zero deletions, and deleting the
inserted line reproduces the previous blob byte for byte. The 3389 passing tests
— the baseline count, unchanged — are evidence that nothing else moved, which is
the only thing they can be evidence of here. A test that parsed the index and
required every ADR on disk to appear in it would close that gap; writing one was
outside this task's authorised scope.

**No specification file was written.** ATLAS-TASK-0014 through ATLAS-TASK-0017
each have one under `docs/tasks/`; this task has none. The change is one row in
one table, and a specification of the weight those carry would have cost more to
review than the line it governed. The scope was fixed and approved before any
edit was made, and the same gates were run, but that record is not in the
repository.

This task reached `main` by direct push rather than through a pull request, as
ATLAS-TASK-0015 through ATLAS-TASK-0017 did, so there is no merge commit for the
row above to cite. It has one commit, `dfc12899`, covering one file, and the
push was a fast-forward from `eb21d82f`: that commit is an ancestor of this one,
`main` advanced by exactly one commit, and `main` and `origin/main` are now the
same commit. CI passed, verified by `head_sha` rather than by recency: run
`31754787621` against `dfc12899`, Quality Gate and Container & Compose both
successful, so there is no gap of the kind recorded at ‡. Locally only the test
suite was run, because the change is documentation and touches no Python; Ruff,
Black and MyPy ran in CI's Quality Gate rather than on this machine.

### ATLAS-TASK-0019 — living-document correction after the first risk control

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

No source file changed. ATLAS-TASK-0017 gave `atlas.risk` its first control that
reaches a decision, and corrected three passages of
`docs/architecture/overview.md` and no others by its own explicit instruction —
so that document's status banner went on saying `atlas.risk` holds "none of the
controls that reach a decision", which is front matter denying the existence of
the repository's only risk control. The banner also still read "Status at
ATLAS-TASK-0014", four tasks behind the table above. This task corrects both
statements and does nothing else: one file, two passages, both inside the
banner, plus the specification that governs them.

**The banner was left behind rather than deferred.** ATLAS-TASK-0018 had a
recorded debt to discharge, listed in the section below. The banner had none:
the string `banner` does not appear anywhere in ATLAS-TASK-0017's specification,
and that section never carried an entry for it. Nothing is added there now —
the omission was found and closed in one pass, so there is no open debt for an
entry to describe.

**The count of implemented packages did not move, and precedent rather than
preference decided that.** The banner's first group names packages built out to
their responsibility; its second names packages holding a contract and a first
piece. ATLAS-TASK-0015 faced the identical question when ATLAS-TASK-0014 gave
`atlas.execution` its first working function, and left "Three packages hold
implementation" byte-identical while adding a second-group sentence instead.
`atlas.risk` already had a sentence of that shape, so its content was corrected
— one of the four controls its responsibility names, a portfolio
margin-utilisation limit, and none of the sizing, drawdown control or kill
switches beside it — and its position was not. Moving it into the first group
would assert a package built out to a responsibility that names four controls
and delivers one, which is the same falsehood pointing the other way.

**Two rows that look stale are not.** The `strategy` row of the package
responsibilities table names a lifecycle and an engine that do not exist, and
the `risk` row names four controls of which one does. Both stay verbatim:
ATLAS-TASK-0015 and ATLAS-TASK-0017 each ruled that the table states a package's
charter — what it owns and what it must not do — rather than what is built, and
a charter naming an unbuilt responsibility is that table working as designed.
The specification records both as checked and deliberately unchanged, alongside
eleven other passages verified still true, so a later reader finds a ruling
rather than an oversight.

**No architectural decision was taken.** No ADR was created or edited, no
contract, boundary, edge or behaviour changed, and the six edges between feature
packages are the six that were there before. The questions the repository is
actually blocked behind — what kind of rule governs `apps/`, where the layer
that owns a `BrokerAdapter` lives, whether a composition root should exist, who
owns account and portfolio state, and how order identity and idempotency work —
are named in the specification as out of scope, and none is closer to an answer
than it was.

**The test suite does not verify this change.** No test reads
`docs/architecture/overview.md`, and none was added: ATLAS-TASK-0013 and
ATLAS-TASK-0015 both declined to write one on the reasoning that a test which
read prose would make the wording of a banner a contract, and this task changes
that banner's date, which such a test would have frozen. The suite would have
passed identically had the banner been left stale, corrected wrongly or deleted.
Acceptance rested on reading the corrected banner against the code, and on
mechanical checks of the diff: one file, both hunks inside the banner, the three
ATLAS-TASK-0017 corrections byte-for-byte unchanged, and every ADR blob and this
file's blob unchanged. The 3389 passing tests — the baseline count, unchanged —
are evidence that nothing else moved, which is the only thing they can be
evidence of here.

**The specification was corrected before it was committed.** Unlike
ATLAS-TASK-0018 this task has one under `docs/tasks/`, and reviewing it against
the sources it cites found seven wrong cross-references: two section numbers for
rulings that sit in ATLAS-TASK-0015 §9, one for a rule that sits in
ATLAS-TASK-0016 §12.1, one line range in `README.md`, one in ADR-0012, and one
paragraph that credited this file's account of `README.md`'s version banner with
having decided something about the overview's banner. All seven were repaired
before the commit, so the file in history is the corrected one and no second
commit records the difference.

This task has one commit, `394df7debe6c77cbcf4e79cfe2cfc0ef798c1d8a`, covering
two files: the correction and its specification. It reached `main` by direct
commit rather than through a pull request, as ATLAS-TASK-0015 through
ATLAS-TASK-0018 did, so there is no merge commit for the row above to cite.
Unlike those four, this entry is written before the push rather than after it:
`origin/main` is `b1f7671a` as this is written and no CI run exists against
`394df7de`, so the row above records a task whose gates have passed locally and
not yet in CI. That is a gap against the definition of **Complete** at the top
of this file, of the kind ‡ records for ATLAS-TASK-0010, and unlike ‡ it is
closed by the push rather than by a correction here. Locally: Ruff, Black and
MyPy clean across 99 source files, 3389 passed.

### ATLAS-TASK-0020 — application ownership of `BrokerAdapter`

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

`apps/atlas-core/src/atlas/apps/core/broker_ownership.py` holds `BrokerOwner`:
the type that holds this process's adapter, sequences its connection and governs
what reaches it. ADR-0013 gave the application the adapter and named five
responsibilities; this implements the three that need no choice of
implementation — holding, lifecycle sequencing and access — and the fourth,
construction, only as far as accepting one from a caller. It is the first module
under `apps/` that names the port at all.

**The owner is handed an adapter and never builds one.** `BrokerOwner(adapter)`
stores the instance and does nothing else: no I/O, no connect, so an adapter
that arrived disconnected is still disconnected when the constructor returns. It
does not inspect, branch on or record which implementation it was given, and
none of `MockBrokerAdapter`, `MT5BrokerAdapter`, `MockVenue`, `MT5Config` or
`BaseBrokerAdapter` appears anywhere under `apps/`.

**Access is granted downward, and stopping revokes it rather than merely closing
it.** The adapter is reachable through one public member, which raises
`BrokerNotConnectedError` before `start` and again after `stop` — the port's own
name for "there is no session here", used rather than an application-local error
so that one condition does not acquire two vocabularies. No new exception type
was added. There is no module-level instance to import, no lookup by name, no
cache and no registry; the only name bound at module scope is `__all__`, and
`atlas.config`'s `@lru_cache` accessor precedent is deliberately not followed,
because a cached module-level accessor is importable from anywhere and that is
acquisition-upward wearing the owner's clothes. Reaching the port from below
requires a reference someone above chose to pass.

**Starting twice raises; stopping twice does not.** A second start is a caller's
mistake, and treating it as a silent no-op — or as a reason to re-establish the
session — would answer a question about recovery that no accepted decision
answers. Teardown is the opposite case: a stop that raised could strand an open
session, and a failed start must still be safe to unwind, so stop-before-start
and stop-after-stop are both no-ops. A `connect()` failure propagates unchanged
and unwrapped, the module holding no `except` clause at all, and leaves the
owner un-started.

**No adapter is constructed in a process, and that is the point.**
`__main__.py` is byte-identical and its tests pass unmodified. For the
entrypoint to build an adapter it would have to choose one, and neither choice
is available. `MockBrokerAdapter()` takes no configuration, so defaulting to it
would make a live process trade against a simulator that ADR-0006 exists to
make indistinguishable. `MT5BrokerAdapter` cannot be constructed at all,
because `AtlasSettings` carries no broker or venue section from which an
`MT5Config` could be built. ADR-0013 declined to add that section and this task
did not invent one — not as a settings model, a TOML block, an environment
variable, a placeholder with empty defaults, or a comment describing the shape a
later task should use. What is delivered is the near side of that break; when
the configuration decision is taken, the work it leaves is one call site.

**The structural tests are not an `apps/` import rule.** The four package
boundary tests each hold a closed `PERMITTED_ATLAS_PACKAGES` allowlist, a
positive statement of everything that package may import.
`tests/unit/test_core_broker_boundary.py` declares no such tuple, permits
nothing, and makes no claim about what an application may import in general.
Every assertion in it is a property this task creates — one module reaches the
port, it reaches it for the abstraction rather than an implementation, and
holding an adapter did not become supervising one or trading through it. Two of
its tests assert that about the file itself, pinning its own module-scope names
to a closed list, so the undecided rule cannot begin here by accident.

**What this task does not claim.** There is no composition root, no run loop, no
engine, no scheduler and no supervision. Nothing calls `reconnect()` or
`health()`, nothing polls, and no lock, condition, event, thread or task is
created — so the owner's own state transitions are unsynchronised, which the
module's docstring records plainly rather than solves. Nothing outside the test
suite hands an owner an adapter, so the chain the data flow draws is still not
joined end to end. Adapter selection and process startup, order identity and
idempotency, routing and reconciliation, dashboard access, the threading model
and the remaining risk-state contracts are all exactly where ADR-0013 left them.

200 tests were added and the suite went from 3389 to 3589 — 17 behavioural and
183 structural. The behavioural tests use no stub, `Mock` or hand-written
double, because ADR-0006 shipped the mock for this and a hand-rolled one would
test the double; the connect failure is injected through
`MockVenue.schedule_failure`, so the adapter takes its real failure path, base
class and all, and the test that matters asserts the venue's own error object
reaches the caller by identity rather than by type or message. 55 of the
structural tests exist only to prove the scanners can fail, on the
ATLAS-TASK-0012 standard that a scan which inspects nothing passes everything,
and 21 of those splice a forbidden line into the real source of a shipped
application module rather than into a snippet — including a port import spliced
into `__main__.py` under a `TYPE_CHECKING` guard, since a guard is not a hiding
place. The contract suite is still 191 and the four boundary tests still 757,
both unchanged, with no allowlist widened: the new file is a module rather than
a subpackage precisely so that `LEAF_MODULES` does not move.

This task reached `main` by direct push rather than through a pull request, as
ATLAS-TASK-0015 through ATLAS-TASK-0019 did, so there is no merge commit for the
row above to cite. It has one commit, `55fcbd61`, covering three files and 827
insertions with no deletion and no change to any existing file. The push was a
fast-forward from `a634da02`: that commit is an ancestor of this one, `main`
advanced by exactly one commit, and `main` and `origin/main` are now the same
commit. CI passed, verified by `head_sha` rather than by recency: run
`31850488760` of `.github/workflows/ci.yml` against
`55fcbd6161d49c986b0033f37493195c3226493e`, Quality Gate and Container &
Compose both successful, so there is no gap of the kind recorded at ‡. Locally:
Ruff, Black and MyPy `--strict` clean across 102 source files, 3589 passed.

`docs/architecture/overview.md:118-121` states that no layer owns a
`BrokerAdapter`. That became false when this commit landed. Correcting it is a
separate living-document task, per ATLAS-TASK-0020 §17.3 and the precedent of
ATLAS-TASK-0015, ATLAS-TASK-0016 and ATLAS-TASK-0019, and this file names no
number for it.

### ATLAS-TASK-0021 — living-document correction after application ownership

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

No source file changed. ATLAS-TASK-0020 gave `apps/atlas-core` the adapter, and
`docs/architecture/overview.md:118-121` went on saying that no layer owns a
`BrokerAdapter` — the entry above records that sentence becoming false on the
commit that landed it, and declines to number the task that would correct it.
This is that task. It corrects that passage and the document's status banner and
does nothing else: one file, two hunks, plus the specification that governs them.

**One clause of four was false, and only that clause moved.** The passage makes
four statements: the chain the data flow draws is not joined end to end, nothing
outside the test suite produces a `TradeIntent`, no layer owns a
`BrokerAdapter`, and so the `OrderRequest` `atlas.execution` builds is received
by nothing. ATLAS-TASK-0020 falsified the third alone; the other three were
checked against the repository and survive in substance. The specification's
§4.1 records that verdict clause by clause, because the failure mode here is not
missing the defect but over-correcting it — the false clause reads as the
premise of the true conclusion, and a reader who loses that conclusion infers
that an owner exists, therefore something places orders. Owning an adapter and
being able to place an order are separated by everything ADR-0013 declined to
decide. The corrected passage states that `apps/atlas-core` owns the adapter,
keeps the conclusion, and cites ADR-0013 rather than restating it.

**The owner is named as an application, not as a class.** `BrokerOwner` and its
module appear nowhere in the corrected text. The fact the overview records is
that an application owns the port; which type implements the holding is an
implementation detail this document has no precedent for naming, and naming one
would make the overview a second account of a module that already documents
itself.

**The banner is re-dated to the last completed row, not to this task.** It now
reads "Status at ATLAS-TASK-0020", two tasks forward from where ATLAS-TASK-0019
left it. Dating it to ATLAS-TASK-0021 was rejected on precedent and on the
specification's own terms: the banner has named the last task this table records
as **Complete** every time it has moved — `394df7de` set it to ATLAS-TASK-0018
and `5e730b47` left it at ATLAS-TASK-0014 — and when the correction was written
this file carried no ATLAS-TASK-0021 row for it to name. Specification §10 T-12
forbids the document naming a task number the status table does not contain, so
the alternative would have failed the task's own acceptance criteria. Nothing
else in the banner block moved.

**No architectural decision was taken.** No ADR was created, edited or
footnoted. ADR-0011's non-guarantee — that the broker-owning layer it names does
not exist — is left untouched, which is what ADR-0013 `:290-293` pre-recorded as
the immutability rule working as designed: the correction belongs in the living
documents, never in the ADR. No contract, boundary, edge or behaviour changed;
the six edges between feature packages are the six that were there before, and
the application-to-package edge ATLAS-TASK-0020 added was neither counted among
them nor ruled on. The broker and venue configuration surface, adapter
selection, startup wiring, supervision, what kind of rule an `apps/` boundary
is, whether `apps/dashboard` may hold an adapter, order identity and
idempotency, and the remaining risk-state contracts are all exactly where
ADR-0013 left them.

**The test suite does not verify this change, and no debt was opened.** No test
reads `docs/architecture/overview.md`. Three cite the filename in a comment and
all three cite what it says about `atlas.common` — dependency-free, and the home
of the clock — which is nowhere near the corrected passage. None was added, on
the reasoning ATLAS-TASK-0013, ATLAS-TASK-0015 and ATLAS-TASK-0019 each gave:
a test that read prose would make the wording of a banner a contract, and this
task moves that banner. Acceptance rested on reading the corrected passage
against the code and on mechanical checks of the diff — one file, two hunks,
both within the permitted lines, and every ADR blob unchanged. The
specification's §9 placed the "Known documentation debt" section below out of
scope, and this task opens no entry there: the correction it was written for is
discharged, not deferred.

This task has three commits and reached `main` by direct push rather than
through a pull request, as ATLAS-TASK-0015 through ATLAS-TASK-0020 did, so there
is no merge commit for the row above to cite.
`ad766252d33151298ad8a95a5ab5e9c98c4bae82` added the specification;
`c0401b1b3606eca7486ef86b2ac00f0d020be46e` corrected it, recording the banner
ruling the reviewer issued after the specification was written, so that the
committed specification matches the authorisation the work was done under; and
`d7a68cb4aa6aa1a3465e1305e2b04b432adf00da` is the implementation, which the row
above cites. Neither specification commit was amended. The push was a
fast-forward from `62d7ac47`: that commit is an ancestor of this one and `main`
advanced by exactly three commits. CI passed, verified by `head_sha` rather than
by recency: run `31858153277` of `.github/workflows/ci.yml` against
`d7a68cb4aa6aa1a3465e1305e2b04b432adf00da`, run number 39, attempt 1, with
Quality Gate and Container & Compose both successful and neither skipped, so
there is no gap of the kind recorded at ‡. Locally only the test suite was run,
because the change is documentation and touches no Python: 3589 passed, the
baseline count, unchanged, which is the only thing it can be evidence of here.
Ruff, Black and MyPy ran in CI's Quality Gate rather than on this machine.

### ATLAS-TASK-0022 — the broker configuration surface

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

`AtlasSettings` has a sixth section. `BrokerSettings` holds the four values a
trading session cannot be established without — `login: int`, `password:
SecretStr`, `server: str` and `terminal_path: Path` — and the ATLAS-TASK-0020
entry above names the absence of exactly that section as the dependency blocking
construction of a live adapter. ADR-0014 decided how it is represented; this
task built it and did nothing else. Five files, 357 insertions against four
deletions, and all four deletions sit inside one import block in a test.

**The four values are restated, not imported.** `MT5Config` already declares
them in `packages/broker`, and importing it would make the configuration package
depend on a feature package in order to learn its own shape. ADR-0014 chose the
duplication instead and recorded its cost — two declarations of overlapping
requirements can drift — because independence is what restating buys. The
section is written in `int`, `SecretStr`, `str` and `Path`;
`packages/config/src` contains no occurrence of `MT5Config`, `mt5`, `MetaTrader`
or `BrokerAdapter` in any casing, and no import of `atlas.broker` in any form,
a `TYPE_CHECKING` guard included. Twelve parametrised tests assert both across
every module in the package, and importing `atlas.config` loads no `atlas`
package other than itself.

**The defaults permit nothing, and there is no start-up invariant.** A login of
`0` and an empty server name are the not-configured values, and no session can
be opened from either. Absence is not permission here for the same reason it is
not in `RiskSettings` — but the refusal lands where a connection is assembled
rather than at start-up, because nothing assembles one yet. An invariant would
refuse every production process for want of configuration nothing reads, so
`_enforce_production_invariants` gained no broker clause and a `production`
process still starts with the section entirely unset. The test that says so is
what fails if an invariant ever arrives by accident.

**The section names types, not a venue.** No `venue`, `provider`, `broker_type`,
`kind`, `enabled` or `type` field exists, and the class docstring names no venue
or product — asserted rather than merely intended, by a test that scans the
docstring against seven venue names and the model fields against six
discriminator names. `timeout_ms`, `portable` and `server_utc_offset` are
deliberately absent: each has a defensible default where it is consumed, and
nothing here reads them. The last of the three is a real gap, named in advance
by the specification's §21.3 — a deployment against a server that does not
publish UTC cannot be corrected through this section as specified.

**Configuration takes the ordinary route and gains no new one.**
`ATLAS_BROKER__LOGIN`, `ATLAS_BROKER__PASSWORD`, `ATLAS_BROKER__SERVER` and
`ATLAS_BROKER__TERMINAL_PATH` resolve through the machinery that was already
there. `settings_customise_sources` is byte-identical, so the order is still
constructor, environment, `.env`, environment TOML, default TOML, field
defaults; no source was added and no second precedence order exists. No layer
under `config/` declares a `[broker]` block, all four layers are byte-identical,
and the password may never be committed to one: it is a `SecretStr` supplied
through the process environment, absent from `repr`, `str`, `model_dump()` and
`model_dump_json()`, with no `safe_*` accessor added to unwrap it.

**The startup record gained no key.** `__main__.py` is byte-identical.
`build_startup_record` still emits eight keys and `broker` is not among them —
`risk` is already a section it omits, no rule anywhere says which sections
appear, and inventing one here would put a live-trading credential a masking bug
away from a log line. One added test sets a broker login, password and server,
then asserts the section key is absent and that neither the login nor the
password reaches the rendered line.

**The risk boundary was not touched and did not need to be.**
`tests/unit/risk/test_risk_boundary.py` is byte-identical. A risk module
reaching the new credential would have to write
`get_settings().broker.password`, whose attribute names include `password` —
already in `CREDENTIAL_SYMBOLS`, so the credential was covered before this task
existed. Adding `"broker"` to that tuple would have been a broadening, and a
dangerous one: `_referenced_names` also records the last segment of an
`ast.alias`, so any module writing `import atlas.broker` would register the
name, and `atlas.risk` is permitted to import `atlas.broker` and does. The
denylist entry could therefore have failed a module touching no credential at
all.

**What this task does not do is most of what it enables.** No adapter is
constructed or selected, no branch on `environment` picks an implementation,
there is no composition root, nothing is built at process start, `BrokerOwner`
is neither modified nor instantiated, and the `BrokerSettings` to `MT5Config`
translation is described in the specification's §15 and implemented by nobody.
`packages/broker`, `packages/risk`, `packages/execution` and `apps/` are
untouched — not one file, not one line. ADR-0012's revisit condition, "when a
single wiring point exists and can be pointed at", remains unsatisfied:
supplying the values a wiring point would read is not building one.

25 tests were added and the suite went from 3589 to 3614. The baseline was
re-derived rather than assumed — deselecting exactly the four new test classes
and the one new entrypoint test collects 3589 — and an AST comparison of both
changed test files, decoded as UTF-8 on both sides, reports no pre-existing test
removed, renamed or modified. The contract suite is still 191 and the four
boundary tests still 757, both unchanged, with no `PERMITTED_ATLAS_PACKAGES`
tuple widened. Locally: Ruff, Black and MyPy `--strict` clean across 102 source
files with no `# type: ignore` added, all fourteen pre-commit hooks passing, and
`git diff --check` clean.

Three living documents went stale when this commit landed, and none of them is
corrected here. `tests/unit/risk/test_risk_boundary.py:150-159` derives
`CREDENTIAL_SYMBOLS` from "the two sections that lead anywhere
credential-bearing", and there are now three — the comment is stale while the
tuple it describes is still correct. ADR-0011 `:101-103` says there is no broker
or venue surface anywhere in the settings model, which is now false and which
the immutability rule leaves exactly where it is.
`docs/architecture/overview.md` describes five configuration sections where
there are six. All three were named in advance by the specification's §21.3,
and correcting them is a separate living-document task, per the precedent of
ATLAS-TASK-0015, ATLAS-TASK-0016, ATLAS-TASK-0019 and ATLAS-TASK-0021; this
file names no number for it.

This task has three commits and reached `main` by direct commit rather than
through a pull request, so there is no merge commit for the row above to cite.
`9bd447ab72087010ea6accf254e33f232fc3134a` accepted ADR-0014 and indexed it;
`e9596ac3e77ade6357ea54d9174f7fafaa8132d4` added the specification; and
`d0f5b709979a3b634c859b31c77fd5dc41c6ab7b` is the implementation, which the row
above cites. No commit was amended. Unlike ATLAS-TASK-0020 and ATLAS-TASK-0021,
this entry is written before the push rather than after it: `origin/main` is
`aaa959dd` as this is written, `main` is three commits ahead of it, and no CI
run exists against `d0f5b709`. The row above therefore records a task whose
gates have passed locally and not yet in CI. That is a gap against the
definition of **Complete** at the top of this file, of the kind ‡ records for
ATLAS-TASK-0010 and of the kind ATLAS-TASK-0019's entry recorded before its own
push, and like that one it is closed by the push rather than by a correction
here.

### ATLAS-TASK-0023 — constructing the broker adapter at startup

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

`apps/atlas-core` builds a broker adapter now. ADR-0015 decided that the
application selects `MT5BrokerAdapter`, translates the broker section of
`AtlasSettings` into an `MT5Config` at its own composition boundary, constructs
the adapter during start-up and hands it to a `BrokerOwner`, and that a broker
section no session could be opened from fails start-up at that translation. This
task performed that translation, that construction and that handoff, and nothing
else. Six files, 642 insertions against 49 deletions, three of the six being
test files.

**The selection lives in one module.**
`apps/atlas-core/src/atlas/apps/core/composition.py` is the only module beneath
`apps/` that may name the selected implementation, and `build_broker_owner` is
the only function in it. It reads the four values a session cannot be
established without and passes no others: `timeout_ms`, `portable` and
`server_utc_offset` keep the defaults `MT5Config` gives them, because no setting
corresponds to any of the three and inventing one would be a decision this task
does not hold. Construction contacts no terminal and imports no vendor package,
so the module runs unchanged on a host where MetaTrader 5 is absent. Opening the
session belongs to `BrokerOwner.start`, and no accepted decision yet says when
that happens.

**The refusal lands at the translation, and start-up now depends on it.**
`BrokerSettings` accepts its own not-configured defaults, because settings must
resolve for a process that holds no trading configuration; `MT5Config` accepts
no such thing. The `ValidationError` from the gap between them is re-raised as
`ConfigurationError`, in the configuration package's own vocabulary, so the
entrypoint's existing handler reports it rather than start-up gaining a second
way to fail. `main` builds the adapter before it writes the startup record, so a
broker section that could not open a session leaves stdout empty and exits `2`.
The entrypoint's documented exit codes were rewritten to say so, and
`.env.example`'s broker block — which had said the defaults permit nothing and a
process with the block unset still starts — now says all four values are
required.

**The adapter is constructed and dropped.** Nothing holds it after
`build_broker_owner` returns. ADR-0015 decided that start-up builds the adapter;
nothing yet decides what holds one afterwards, and giving it a home in the
entrypoint would answer a question no record has answered. No session is opened
and no loop runs. The startup record gained no key — `build_startup_record` is
untouched and still emits its eight — and neither the login nor the password
reaches the rendered line.

**The boundary test changed by permission, not by convenience.** ADR-0015
established, by running the scanners in
`tests/unit/test_core_broker_boundary.py` against a hypothetical translation
module, that three assertions in that file failed the moment an application
named `MT5Config` — and it recorded that before lifting the prohibition, on the
terms the file itself set: by a decision record rather than by an edit to a
test. The lift is bounded to the composition module
and the boundary is still asserted, not assumed — the file grants
`atlas.broker.mt5` and the two selected names to that module and to no other,
carries a test proving the composition edge rule can fire, and its `APP_SOURCES`
glob scans any new file under `apps/` automatically. The contract suite was left
at 191, the count ATLAS-TASK-0022 left it at.

This task has four commits and reached `main` by direct commit rather than
through a pull request, so there is no merge commit for the row above to cite.
`8db18fcd37b940c0cb5e6bad46fb5a5b33c57510` accepted ADR-0015;
`a83f9984446b2b0c871fa2274af39ecfd14f7fd8` indexed it in `docs/adr/README.md`;
`9b9e3df6b4b064b95117547bf5305ece61ec5ee6` added the specification; and
`6f5eff81361e904b746a37a8c975683b138972e7` is the implementation, which the row
above cites. No commit was amended.

The gates did not all pass on that commit. CI run 43 covered it, the Quality
Gate was green in full — Ruff, Black, MyPy and Pytest — and Container & Compose
failed, which is the gap recorded at ¶ under the status table.
ATLAS-TASK-0024 closed it in `2c4e7e8bdbf2839b11fe25e38b7b0d9bbd8c4732`, whose
run is green in both jobs. The row above therefore records a task whose local
and Quality Gate evidence held on its own tree and whose container evidence
arrived one commit later. The citation stays on the feature commit and the
history is not rewritten.

Documents went stale when this commit landed, and none of them is corrected
here. `docs/architecture/overview.md` says that although `apps/atlas-core` owns
the `BrokerAdapter`, no adapter is constructed outside the test suite for it to
hold, which is now false; the same file describes the `atlas-core` entrypoint as
resolving configuration, enforcing the environment's invariants, emitting a
startup record and exiting, which is now incomplete. ADR-0015's own closing
sentence — "Nothing in this record is implemented. No adapter is constructed, no
translation exists, no boundary test changes" — was true when written and is
false of the repository now; the immutability rule leaves it exactly where it
is, as it leaves ADR-0011's. The three items the ATLAS-TASK-0022 entry above
recorded are carried forward untouched as well: that entry's account of
`tests/unit/risk/test_risk_boundary.py:150-159`, of ADR-0011 `:101-103`, and of
`docs/architecture/overview.md`'s count of configuration sections all still
stand as it wrote them. Correcting any of this is a separate living-document
task, per the precedent of ATLAS-TASK-0015, ATLAS-TASK-0016, ATLAS-TASK-0019 and
ATLAS-TASK-0021; this file names no number for it.

### ATLAS-TASK-0024 — CI container self-check after broker startup construction

Newly specified rather than recovered from the repository record — see the note
marked † under the status table. This one has no specification file: the work
was authorised in session and implemented directly, so there is no
`docs/tasks/ATLAS-TASK-0024.md` and no specification commit. There is one
commit, `2c4e7e8bdbf2839b11fe25e38b7b0d9bbd8c4732`, subject "feat: implement
TASK-0024", whose parent is ATLAS-TASK-0023's implementation
`6f5eff81361e904b746a37a8c975683b138972e7`. ATLAS-TASK-0018 stands in the same
position — a row and a † with no specification file behind them — and this row
is written the same way.

ATLAS-TASK-0023 made building the trading adapter part of start-up, and the
repository's deployment surface still described a process that only resolved
configuration. This task brought that surface level with the application and did
nothing else. Eight files, 285 insertions against 23 deletions, and none of them
under `apps/` or `packages/`: no ADR, no `Dockerfile`, no `pyproject.toml`, no
script, and not one of ATLAS-TASK-0023's implementation files.

**CI states all four values rather than relying on what `MT5Config` tolerates.**
The Container & Compose job carries `ATLAS_BROKER__LOGIN`,
`ATLAS_BROKER__PASSWORD`, `ATLAS_BROKER__SERVER` and
`ATLAS_BROKER__TERMINAL_PATH` in its own environment, as throwaway values
supplied the way a deployment supplies real ones rather than baked into the
repository, and the steps hand them to `docker run` by name. Leaning on the
empty password and bare terminal path `MT5Config` currently accepts would have
made the job depend on the gap ATLAS-TASK-0023's specification records at §21.2
and declines to close, so tightening either one later would have broken CI for a
reason unconnected to what CI was checking.

**Two self-checks, and the second is the one that earns its keep.** The
configured check asserts more than an exit code: exactly one JSON line, exit
`0`, the event `atlas.core.startup`, exactly the eight keys ATLAS-TASK-0001
defined, and none of the four broker values anywhere in the rendered record —
tested before the record is echoed, so a leak is never printed. The new negative
check runs the same image with a password and nothing else, and requires exit
`2`, exactly one line, the event `atlas.core.startup_failed`, and no password in
the output. ADR-0015's refusal is observed in a container rather than inferred
from unit tests, and because stderr is merged into stdout, the single line is
also evidence that the startup record was never reached. A password is supplied
precisely so that the failure has a credential available to leak and is shown
not to leak it.

**Compose fails closed on all four.** `docker-compose.yml` interpolates them as
`${ATLAS_BROKER__LOGIN:?…}` and its three counterparts, each with its own
message, so `docker compose config` refuses an incomplete `.env` and names the
first value it is missing before anything starts. No credential is hard-coded
and no default is invented: a plausible-looking login and server would let a
deployment that cannot trade start up looking like one that can, and ADR-0015
had already rejected `MockBrokerAdapter` as a fallback rather than permit that.
`.env.example` keeps the four commented out for the same reason — unlike
`POSTGRES_PASSWORD`'s placeholder above them, which no service can be reached
with — and documents them as facts about a deployment. `README.md`,
`docs/runbooks/local-stack.md`, `infrastructure/docker/README.md` and
`infrastructure/deployment/README.md` were qualified to match, including a
runbook row for `invalid broker configuration` and the observation that compose
interpolates the whole file, so the refusal applies to `docker compose up -d
postgres redis` as much as to `atlas-core`.

**Nothing in the application was softened.** No flag, no branch on
`environment`, no fallback, no mock and no optional construction was introduced,
and construction stayed mandatory exactly where ATLAS-TASK-0023 put it. The
§21.2 gap is still open, deliberately: `MT5Config` still accepts an empty
password and a bare `terminal_path`, and this task worked around that by being
explicit rather than by closing it, which would have been a new invariant no
record has decided.

26 tests were added and the contract suite went from 191 to 217, all in
`tests/contract/test_repository_structure.py`; the full suite is 3699. Locally:
Ruff, Black and MyPy clean, `pre-commit run --all-files` green, and the pre-push
pytest hook green.

This commit is what closed ATLAS-TASK-0023's CI gap. Run 43 had failed at "Run
the image configuration self-check" because the job ran a container with no
broker configuration to start from, which is the gap recorded at ¶ under the
status table and described from that task's side in its entry above. CI run 44 —
id `31888673735`, head `2c4e7e8bdbf2839b11fe25e38b7b0d9bbd8c4732` — is green in
both jobs, Quality Gate and Container & Compose, with the configured self-check
and the negative self-check both passing. The row above therefore has no gap of
its own against the definition of **Complete** at the top of this file, and none
is recorded for it.

### ATLAS-TASK-0025 — living-document correction after adapter construction

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

No source file changed. ATLAS-TASK-0023 made building the trading adapter part
of start-up and the documents describing start-up went on describing a process
that only resolved configuration; ATLAS-TASK-0022 added a third
credential-bearing settings section and the comment deriving
`CREDENTIAL_SYMBOLS` went on saying there were two. Both entries above record
those statements becoming false on the commits that landed them, and both
decline to number the task that would correct them. This is that task. It
corrects three passages of `docs/architecture/overview.md` and one comment in
`tests/unit/risk/test_risk_boundary.py` and does nothing else: two files, four
hunks, 29 insertions against 14 deletions, plus the specification that governs
them.

**The false clause was a premise, and the conclusion it carried survives.**
`overview.md:118-123` said that although `apps/atlas-core` owns the
`BrokerAdapter`, no adapter is constructed outside the test suite for it to
hold — so the request `atlas.execution` builds is received by nothing.
ATLAS-TASK-0023 falsified the premise and left the conclusion true, which is
the shape ATLAS-TASK-0021 met in this same passage one cycle earlier. The
corrected text states that the application builds an adapter at start-up from
the broker configuration it resolves, and then states the two things still
absent — nothing holds it afterwards, and no session is opened with it — so
the conclusion now follows from what is true rather than from what was. Both
ADR-0013 and ADR-0015 are cited rather than restated.

**The entrypoint gained the step it had acquired, and the exit codes it always
had.** `:191-193` described a process that resolves configuration, enforces the
environment's invariants, emits a JSON startup record and exits. It now records
that it builds the broker adapter that configuration describes before it writes
the record, and that a run getting that far exits `0` while configuration it
cannot resolve — or a broker section it cannot translate — leaves stdout empty
and exits `2` instead. That is `__main__.py`'s documented behaviour, and
ATLAS-TASK-0024's two container self-checks assert both halves of it on every
push. The `At ATLAS-TASK-0001` marker on "has no run loop" is neither re-dated
nor removed: no run loop was added, and the sentence is still true.

**The banner is re-dated to the last completed row, not to this task.** It
reads "Status at ATLAS-TASK-0024", which is what the table above recorded as
**Complete** when the correction was written, and only the task number moved
inside it. This is the ruling ATLAS-TASK-0021 reached and recorded: the banner
has named the last **Complete** row every time it has moved, and naming
ATLAS-TASK-0025 would have made the document cite a row this file did not yet
carry.

**The comment was corrected and the tuple was not, which is the point.**
`CREDENTIAL_SYMBOLS` derived itself from "the two sections that lead anywhere
credential-bearing" and there are three — `postgres`, `redis` and `broker`. The
tuple is correct as it stands and is byte-identical: reaching
`get_settings().broker.password` requires `password`, `get_secret_value` or
`SecretStr`, each already in it, so the credential ATLAS-TASK-0022 added was
covered before that task existed. Adding `"broker"` would have been a
broadening and a false positive waiting to happen, because `_referenced_names`
records the last segment of an `ast.alias` and the entry would fire on `import
atlas.broker` — a form the boundary test expressly permits and one that reaches
no credential. The comment now says all of that, so the next reader who notices
the count meets a ruling rather than an oversight.

**The comment says what was verified, not what the specification predicted.**
Specification §10 T-10 stated that `atlas.risk` writes the triggering import
form "and does", and the ATLAS-TASK-0022 entry above had recorded the same
thing. Checked against the package rather than restated, it is false: every
risk module reaches the port through `from atlas.broker import …`, which
registers the imported symbol and never `broker`, and no risk module contains
the plain dotted form. The permanent comment therefore says the entry would be
a false positive waiting for the first module that wrote one, which is true,
rather than reproducing a claim that is not. A specification is not evidence
about the code it describes, and documentation that stopped matching the
repository is the entire subject of this task. The tuple, the boundary and
every assertion are unaffected either way.

**No test behaviour changed, and that is proved rather than asserted.** The
abstract syntax tree of `test_risk_boundary.py` is identical to the baseline's,
compared as `ast.dump` output with attributes excluded, and so is its token
stream with comments removed; no non-comment line changed, and
`CREDENTIAL_SYMBOLS`, `PERMITTED_CONFIG_ACCESS`, `PERMITTED_ATLAS_PACKAGES`,
`PERMITTED_CONFIG_NAMES` and `WHOLE_MODULE` are each identical. The suite still
collects 3699, the contract suite 217 and the boundary file 100 — the baseline
counts, unchanged, which is the only thing they can be evidence of here. No
test reads `docs/architecture/overview.md` and none was added, on the reasoning
ATLAS-TASK-0013, ATLAS-TASK-0015, ATLAS-TASK-0019 and ATLAS-TASK-0021 each
gave: a test that read prose would make the wording of a banner a contract, and
this task moves that banner.

**No architectural decision was taken.** No ADR was created, edited or indexed,
and no ADR-0016 exists. `BrokerOwner`, `composition.py`, `MT5Config` and
`MT5BrokerAdapter` appear nowhere in the corrected prose, which names an
application and a configuration section and no class — the rule
ATLAS-TASK-0021 set when it declined to name the owner as a type. Nothing was
decided about a run loop, a lifecycle, supervision, reconnection, failover, a
second adapter, venue or account, a downstream consumer of the `OrderRequest`,
or where a constructed adapter should eventually live; every sentence added
about any of those says that it does not exist. The six edges between feature
packages are the six that were there before, and ADR-0012's revisit condition
is not reopened.

**The specification contained a defect, and it is recorded rather than
repaired.** Its §3.2 lists `overview.md:121-122` among the passages that must
survive byte-for-byte, while its §5 and §8 authorise rewriting `:118-123`,
which contains them. Both cannot hold: line 121 opens with `that suite for it
to hold —`, the tail of the very claim P-1 exists to delete. The implementation
followed §10 T-3, which asks that the passage be preserved "in substance", and
the clause §3.2 actually quotes — "so the request `atlas.execution` builds is,
today, received by nothing" — survives verbatim with only its line break moved.
This is a contradiction inside the acceptance contract rather than a defect in
the diff; no correct implementation of P-1 could have satisfied both readings,
and the specification is left exactly as it was authorised and committed.

What this task did not correct is recorded in its §15 and stands. ADR-0011
`:99-103` still says there is no broker or venue surface anywhere in
`AtlasSettings`, and ADR-0015's closing sentence still says nothing in it is
implemented; both are false of the repository and both are immutable, which is
what ADR-0013 `:280-283` pre-recorded as the rule working as designed —
corrections belong in the living documents and never in an accepted record. The
ATLAS-TASK-0023 §21.2 gap is open, `MT5Config` still accepting an empty
password and a bare `terminal_path`, and closing it is a new invariant that
needs a decision rather than a documentation task. Nothing is added to the
"Known documentation debt" section below: the corrections this task was written
for are discharged, not deferred.

This task has three commits and reached `main` by direct commit rather than
through a pull request, as ATLAS-TASK-0015 through ATLAS-TASK-0024 did, so
there is no merge commit for the row above to cite.
`6e880e1986aa53fba69fbe7d6692478835c1e12e` added the specification;
`db92e7795055bc88f022c1a4b9932ef9fe586fe1` is the implementation, which the row
above cites; and this closeout is the third. No commit was amended. Locally:
3699 passed, 217 in the contract suite and 100 in the boundary file, Ruff,
Black and MyPy `--strict` clean across 104 source files, `git diff --check`
clean, and `pre-commit run --all-files` green with `check json` skipped for
want of a JSON file to check. As with ATLAS-TASK-0019's entry and
ATLAS-TASK-0022's, this one is written before the push rather than after it, so
no CI run exists against `db92e779` or against this closeout as it is written,
and the row above records a task whose gates have passed locally and not yet in
CI. That is a gap against the definition of **Complete** at the top of this
file, of the kind ‡ records for ATLAS-TASK-0010, and like ATLAS-TASK-0019's it
is closed by the push rather than by a correction here.

### ATLAS-TASK-0026 — enforcing the ADR-0016 startup validation boundary

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

A broker section that could not open a session already failed start-up for two
of its four values; it now fails for all four. ADR-0016 decided that
configuration which cannot open a session is refused where the session is
assembled, and that the refusal is confined to properties holding independently
of the machine doing the validating. This task added the two invariants that
decision names and nothing else: `MT5Config.password` gained `min_length=1`, and
`terminal_path` gained a validator that refuses the one value meaning nobody
supplied one. Six files, 1645 insertions against 8 deletions — one source file,
three test files, `.env.example`, and the specification itself.

**The behavioural change is the decision rather than a side effect.** A
deployment that sets `ATLAS_BROKER__LOGIN` and `ATLAS_BROKER__SERVER` and leaves
the password empty or the terminal path unset starts today and stops starting on
this commit. ADR-0016 `:227-230` names that cost in those terms and places the
record of it in the roadmap at implementation, which is this paragraph. The
deployments it stops are ones that could not have traded: they would have failed
at the first `connect()` instead, which is the deferral ADR-0015 ruled against.

**The empty password is refused in every environment.** An empty `SecretStr`
authorises nothing, and the repository had already ruled on the identical type
when `_enforce_production_invariants` refused an empty `postgres.password`. That
reasoning was followed and its placement was not: the rule lives in `MT5Config`,
beside the `gt=0` and `min_length=1` already there, because what opens a
MetaTrader session is venue knowledge and ADR-0014 exists to keep it out of
`atlas.config`. `_enforce_production_invariants` gained no broker clause, and
the test asserting that a `production` process resolves its settings with the
section entirely unset passes unmodified. The scope differs from the postgres
precedent deliberately: there is no MetaTrader equivalent of a passwordless
development database, so the password is refused everywhere `login` and `server`
already are.

**The terminal path is refused for being unset, and for nothing else.**
`BrokerSettings.terminal_path` defaults to `Path()`, which is `.` — a directory,
and the sentinel meaning nobody set it. That value is refused. Absoluteness,
existence, executability, filesystem accessibility and platform validity are
each declined as invariants, because each would make configuration validity a
property of the host doing the validating rather than of the configuration, and
the container this repository builds has no Windows terminal to find. A path
that is well-formed, absolute and points at nothing still starts the process and
still fails at `connect()`. That is not a gap left open by accident; it is what
ADR-0016 chose over an invariant that cannot be stated portably, and a Windows
path is accepted under POSIX semantics by a test that now runs on Linux in CI to
prove no absoluteness requirement arrived by the back door.

**Configuration validation performs no filesystem I/O, and it is proved twice
rather than asserted.** One proof intercepts twelve filesystem entry points
during validation and fails if any is reached; the other scans the model's
source for eighteen call names the interception cannot see, such as `iterdir`
and `glob`. Each has a control that deliberately trips it, because an instrument
never shown to fire proves nothing — which the ‖ note above records the cost of
learning. The two are complementary and neither is complete on its own: the
runtime patch catches indirection the scanner cannot follow, the scanner catches
calls the patch never wraps, and neither names `os.scandir`, `os.listdir` or
`os.readlink`. The proof covers the calls it enumerates and the source it scans,
which is what it claims and not more.

**The failure is the one that already existed.** No error surface, exit code,
stream or record was added. A rejected `MT5Config` raises `ValidationError`,
`composition.py` narrows it to `ConfigurationError`, and `main()` reports one
JSON object on stderr under `atlas.core.startup_failed` and exits `2` with
stdout empty. Translation still precedes construction, so no adapter is built,
no owner is created and no session is opened. No credential reaches either
stream: `SecretStr` masks in Pydantic's error output, reporting
`input_value=SecretStr('')` and never the value, and the startup record carries
no broker key at all. Nothing about the run loop, the owner's lifecycle or
supervision was decided, and `apps/` acquired no import and no line of diff.

**ADR-0016 remains `Proposed`.** This task implemented a record that has not
been accepted, on the owner's decision to implement it as written, and it
neither edited the record nor advanced its status. `docs/adr/README.md` lists it
as `Proposed` today. The ADR-0016 paragraph near the top of this file records
that this is the first time the sequence has worked in that order.

Two statements above become inaccurate on this commit, and both are left as
written. The ATLAS-TASK-0022 entry says that a login of `0` and an empty server
name "are the not-configured values"; there are four of them now, and its
sentence is answered here rather than corrected there, as ATLAS-TASK-0019's,
ATLAS-TASK-0020's, ATLAS-TASK-0021's and ATLAS-TASK-0022's entries have each
been left. The remainder of that same passage is untouched by this task and
stays true: `_enforce_production_invariants` still gained no broker clause. The
ATLAS-TASK-0025 entry says that no ADR-0016 exists, and that the
ATLAS-TASK-0023 §21.2 gap is open with `MT5Config` "still accepting an empty
password and a bare `terminal_path`" while "closing it is a new invariant that
needs a decision rather than a documentation task". Both were true when written;
ADR-0016 is the decision that entry said the closure required, and this task is
the closure. ATLAS-TASK-0026 §14 DOC-5 named the first of these in advance and
§22 excluded the roadmap from the task, which is why it lands in this closeout.

This task has three commits and reached `main` by direct commit rather than
through a pull request, as ATLAS-TASK-0015 through ATLAS-TASK-0025 did, so there
is no merge commit for the row above to cite.
`06418acf326a2c4f7964a8963ccfeae433c25db6` carries the specification and the
implementation together, which is what the row above cites;
`05421d5c0934413d314ce851c8ec451d3d79027c` is the test-control correction the ‖
note records; and this closeout is the third. No commit was amended. Unlike
ATLAS-TASK-0019's entry and ATLAS-TASK-0025's, this one is written after CI has
run: run 50 is green in both jobs on `05421d5`, on Linux under Python 3.12.13
with coverage active, at 3623 passed and 105 skipped — every skip vendor-gated
on the MetaTrader 5 wheel, none of them in this task's twenty-nine tests, which
the run executed and passed. Locally: 3728 passed, 217 in the contract suite,
Ruff, Black and MyPy `--strict` clean across 104 source files. The row above
therefore has one gap of its own against the definition of **Complete** at the
top of this file, the one ‖ records, and no other. No CI run exists against this
closeout as it is written; it changes one documentation file, which no test
reads.

### ATLAS-TASK-0027 — Execute broker lifecycle during startup

Newly specified rather than recovered from the repository record — see the note
marked † under the status table. This one has no specification file: the work was
authorised in session and implemented directly, so there is no
`docs/tasks/ATLAS-TASK-0027.md` and no specification commit. ATLAS-TASK-0018 and
ATLAS-TASK-0024 stand in the same position — a row and a † with no specification
file behind them — and this row is written the same way. ADR-0017 is the
governing record, and it was committed first, in
`f98b41ea2cb59d54980a1867a755c01ef8980937`, before any code was written against
it.

**The lifecycle now runs.** ATLAS-TASK-0020 built `BrokerOwner` and
ATLAS-TASK-0023 constructed the adapter and handed it to one; nothing then
started it. `main()` dropped the owner it had just been given, so six tasks'
worth of machinery had never been driven by anything outside the test suite.
This task calls `owner.start()`, and calls `owner.stop()` from a `finally`, so a
session that opened is closed on every path out of the block including the
failing one. That is the behavioural change in full.
`c5500dc58186dded011b52d62b227bd8d9e96872` is the commit, and it carries this
task and ATLAS-TASK-0028 together: eleven files, of which nine are this one's.

**Three outcomes, and the third is new.** A settings section that cannot resolve
or translate still raises `ConfigurationError`, still reports one JSON object on
stderr under `atlas.core.startup_failed`, and still exits `2`. A session that
will not open reports one JSON object on stderr under
`atlas.core.broker_connect_failed` and exits `3`, with stdout empty. A session
that opens leaves the startup record on stdout unchanged — its eight keys, and
no broker value among them — and exits `0`. Exit `1` is reserved by not being
produced. The two handlers are `ConfigurationError` then `BrokerError` in that
source order, and there is no bare `except` and no `except Exception`: a failure
this entrypoint has not been told how to report is not disguised as one it has.

**On Linux the answer is always `3`, by construction.** MetaTrader 5 publishes
Windows wheels only, so `pyproject.toml` marks it `sys_platform == "win32"`, the
`python:3.12-slim-bookworm` image has no terminal to reach, and the loader turns
the resulting `ImportError` into a `BrokerConnectionError` carrying no
credential. Every containerised run therefore stops at the venue. That is the
limit of what a Linux runner can observe rather than a defect — everything up to
the venue is proved there, and the session itself is proved on a Windows host or
not at all — and an exit `0` from a configured container would mean the
entrypoint had stopped opening a session, not that CI had found a broker.

**What this task does not claim.** It does not implement a long-running trading
process, and ADR-0017's own title says `atlas-core` is not one. No run loop, no
event loop, no scheduler, no supervision, no health timer, no reconnect, no
failover, no threading, no message bus and no persistence was introduced. No
strategy, no risk integration, no execution routing and no order placement
either: the entrypoint names exactly one symbol from `atlas.broker`,
`BrokerError`, which is the widening ADR-0017 authorised and bounded, and it
imports no pipeline package at all. `UNCALLED_PORT_OPERATIONS` and
`PIPELINE_PACKAGES` in `tests/unit/test_core_broker_boundary.py` are unchanged,
and the test asserting that one module and only one names the selected
implementation is unchanged and still passing. Nothing holds the adapter after
`main()` returns; the process ends where it always did, one step further along.

Locally at implementation time, and on this tree today: 3747 passed, 223 of them
in the contract suite, with Ruff and Black clean and MyPy clean across 104 source
files. CI run 54 — id `31963130750`, head
`c5500dc58186dded011b52d62b227bd8d9e96872`, which is the implementation commit
itself and not a later one — is green in both jobs, Quality Gate and Container &
Compose. The row above therefore has no gap of its own against the definition of
**Complete** at the top of this file, and none is recorded for it.

Two documents go stale on this commit and neither is corrected here.
`docs/architecture/overview.md` still carries a status banner reading
ATLAS-TASK-0024, which was already two rows behind before this work and is four
behind now; the same file's `## Processes` table still charters `atlas-core` as a
long-lived container that owns the event loop and runs the trading pipeline,
which is what ADR-0017's title says it is not, while the prose directly beneath
that row was brought level by this commit and now documents exits `0`, `2` and
`3`. `apps/atlas-core/src/atlas/apps/core/__init__.py` still opens by describing
the package as the long-lived process that owns the event loop and runs the
trading pipeline end to end, and still closes with the ATLAS-TASK-0001 sentence
saying its implementation is delivered by a later task — in a package that now
holds a working entrypoint and two implemented modules beside it. This file names
them and numbers nothing, as the ATLAS-TASK-0020, ATLAS-TASK-0022 and
ATLAS-TASK-0023 entries did before it.

### ATLAS-TASK-0028 — Strengthen CI container startup/refusal contracts

Newly specified rather than recovered from the repository record — see the note
marked † under the status table. This one has no specification file either: the
work was authorised in session and implemented directly, so there is no
`docs/tasks/ATLAS-TASK-0028.md`. It has no commit of its own. It was implemented
in `c5500dc58186dded011b52d62b227bd8d9e96872`, the same commit as
ATLAS-TASK-0027, and it is two of that commit's eleven files:
`.github/workflows/ci.yml` and `tests/contract/test_repository_structure.py`.
The two rows above are the first in that table to cite one commit. They stay
separate rows because they are separate scopes — one changed what the
application does, the other changed what CI proves about it.

**The refusal is observed in a container rather than inferred from unit tests.**
The Container & Compose job runs the image with all four broker values supplied
and requires exit `3`; that stdout is empty; that stderr holds exactly one JSON
line; and that the line's `event` is `atlas.core.broker_connect_failed`. The two
streams are captured apart rather than merged, because "stdout stayed empty" is
half of what the step exists to show and merging them would destroy the evidence
for it. The password is checked for absence from both streams before either is
echoed, so the step that would detect a leak never prints one.

**The startup-record coverage was kept rather than dropped.** Until this commit
the configured container ran through to exit `0`, and that step could assert the
two things about the record an exit code cannot show: that it carries exactly the
eight keys ATLAS-TASK-0001 defined — `event`, `app_name`, `environment`, `debug`,
`logging`, `postgres`, `redis`, `duckdb` — and that none of the four broker
values reaches it. A container that now stops at the venue can never emit that
record, so rather than lose the coverage the check moved into a step of its own:
same image, same configured environment, calling the same public
`build_startup_record` the entrypoint calls, one step short of the session it
cannot open.

**ADR-0016's refusal is still observed, unchanged.** The third step runs the same
image with a password and nothing else, and still requires exit `2`, exactly one
line, and the event `atlas.core.startup_failed`. A password is supplied precisely
so that the failure has a credential available to leak and is shown not to leak
it. ATLAS-TASK-0024 built that check and this task did not weaken it: what
changed around it is that the configured path now goes further, not that the
unconfigured path goes less far.

**Two existing contract tests were rewritten to follow the behaviour, and
neither was relaxed.** The test that checked one configured step passes each
broker variable is now parametrised over both steps that receive a complete
broker section, because both assert that a value did not leak and an assertion
that a withheld value is absent proves nothing. The test that pinned
`"atlas.core.startup"` to the configured step moved to the step that now carries
the record and gained three further assertions — `build_startup_record`, the
key-set check and the leak check. Two tests were added beside them, for the exit
`3` outcome and for the both-streams credential check. Nothing was skipped,
xfailed, marked or deleted, and the contract suite stands at 223.

CI run 54 — id `31963130750`, head
`c5500dc58186dded011b52d62b227bd8d9e96872` — is green in both jobs, and all three
of the steps this task wrote or reshaped passed on it: "Run the image start-up
check with broker configuration", "Verify the image still builds its startup
record", and "Run the image self-check without broker configuration". That run
covers the exact implementation commit rather than a later one, so the row above
has no gap against the definition of **Complete** at the top of this file, and no
marker in the ‡, §, ¶ or ‖ family is warranted for either of the two rows this
closeout adds.

## Known documentation debt

- **ADR-015 and ADR-016 do not exist and cannot be reconstructed.** They were
  named as dependencies of ATLAS-TASK-0004 by a specification that is not part
  of this repository, and no file here records what either was to decide.
  Writing them now would be inventing two architectural decisions and dating
  them to a task that is long closed, so they stay unwritten. The numbers do
  not fit either: `docs/adr/` numbers sequentially in four digits and ended at
  `0010` when this was written, so `015` and `016` name positions the sequence
  never reached. ATLAS-TASK-0014 has since written `0011`, and ADR-0012 was
  accepted for ATLAS-TASK-0017 and committed by it.

- **`docs/adr/README.md` did not index ADR-0012. Discharged by
  ATLAS-TASK-0018.** The index listed ADR-0001 through ADR-0011 while ADR-0012
  was accepted and, from ATLAS-TASK-0017, committed — so the repository held a
  committed ADR that its own committed index did not list. The omission predated
  ATLAS-TASK-0017, which recorded it rather than folding an unrelated correction
  into a diff that was to be reviewed against its own list of permitted files,
  which is why `docs/adr/README.md` was on that task's forbidden list.
  ATLAS-TASK-0018 added the one row it needed, in `dfc12899`, and the index now
  lists ADR-0001 through ADR-0012. This entry is kept as the record of a debt
  that is closed rather than one that is open.
