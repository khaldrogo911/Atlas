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
| ATLAS-TASK-0006 | `MockBrokerAdapter` | ✅ Complete | `PENDING` |
| ATLAS-TASK-0007 | `BaseBrokerAdapter` | ⬜ Not started | — |

Nothing beyond ATLAS-TASK-0007 is defined. The tasks above are the ones the
repository itself declares; this file does not speculate past them.

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

## Next

### ATLAS-TASK-0007 — `BaseBrokerAdapter`

A concrete class between the port and its implementations, taking over thread
safety and any retry or reconnection policy from every adapter including the
MT5 one. It is not in the port itself because a replay engine has nothing to
reconnect to and should not inherit the concept.

## Known documentation debt

- **ADR-015 and ADR-016** were declared dependencies of ATLAS-TASK-0004 but do
  not exist. `docs/adr/` currently ends at 0006.
- **Version.** ATLAS-TASK-0004 was specified as `v0.2.0-alpha`; `pyproject.toml`
  and `README.md` still declare `v0.1.0-alpha`. A contract test ties the
  `atlas-core` image tag to `[project].version`, so a bump touches all three.
- Several `docs/` pages carry a "Status at ATLAS-TASK-0001" banner that predates
  the broker work.
