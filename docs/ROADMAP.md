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

Nothing beyond ATLAS-TASK-0007 is defined, and nothing here declares what
ATLAS-TASK-0008 will be. The tasks above are the ones the repository itself
declares; this file does not speculate past them.

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
- **Locking.** Still nowhere. Both adapters remain not thread safe, and both
  READMEs still say so. Serialising access is behaviour *neither* adapter has,
  which makes it an addition rather than part of this move — the reason it was
  left out of a refactor whose brief was not to change behaviour. `base.py` is
  where it belongs when it is written.

The class is deliberately not exported from `atlas.broker`. That namespace is
what a caller depends on, and a caller has no use for a base class; an adapter
author imports from `atlas.broker.base`. `base.py` is also in the port's AST
import scan, so the same rule that keeps a venue SDK out of the port keeps one
out of the base.

No ADR was added or changed. Nothing recorded in an existing one was reversed —
the boundary above is reasoning about *this* class, and it lives in its module
docstring where an implementer reading the class will find it.

## Known documentation debt

- **ADR-015 and ADR-016** were declared dependencies of ATLAS-TASK-0004 but do
  not exist. `docs/adr/` currently ends at 0006.
- **Version.** ATLAS-TASK-0004 was specified as `v0.2.0-alpha`; `pyproject.toml`
  and `README.md` still declare `v0.1.0-alpha`. A contract test ties the
  `atlas-core` image tag to `[project].version`, so a bump touches all three.
- Several `docs/` pages carry a "Status at ATLAS-TASK-0001" banner that predates
  the broker work.
