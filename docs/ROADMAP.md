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
| ATLAS-TASK-0005 | Broker exception hierarchy | ⬜ Not started | — |
| ATLAS-TASK-0006 | `MockBrokerAdapter` | ⬜ Not started | — |
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
missing MT5 capability named at the call site — the four trading methods (they
need the 0005 hierarchy to distinguish rejection from insufficient margin from
timeout), `subscribe_ticks` and `subscribe_candles` (the MT5 Python API polls
and opens no push channel), and `server_time` (the terminal exposes no clock).

`MetaTrader5` is imported inside exactly one function, behind a typed protocol,
never at module scope, and is an optional Windows-marked extra — so the
distribution installs and the whole suite runs on a Linux runner with no wheel
and no terminal.

## Next

### ATLAS-TASK-0005 — broker exception hierarchy

**Blocked nothing; blocks the four MT5 trading methods.** Delivers the
`BrokerError` tree the port's docstrings already reference. Replaces every
temporary exception in `atlas/broker/mt5/connection.py`, each of which carries
a `TODO(ATLAS-TASK-0005)` naming its permanent replacement, and unblocks the
`TRADE_RETCODE_*` table that `constants.py` deliberately does not yet define.

### ATLAS-TASK-0006 — `MockBrokerAdapter`

A second implementation of the port. This is what proves the contract is not
shaped around MetaTrader 5, and it is what tests use instead of mocking
`BrokerAdapter` — a mock agrees with whatever the test asserts, including the
wrong thing.

### ATLAS-TASK-0007 — `BaseBrokerAdapter`

A concrete class between the port and its implementations, taking over thread
safety and any retry or reconnection policy from every adapter including the
MT5 one. It is not in the port itself because a replay engine has nothing to
reconnect to and should not inherit the concept.

## Known documentation debt

- **ADR-015 and ADR-016** were declared dependencies of ATLAS-TASK-0004 but do
  not exist. `docs/adr/` currently ends at 0005.
- **Version.** ATLAS-TASK-0004 was specified as `v0.2.0-alpha`; `pyproject.toml`
  and `README.md` still declare `v0.1.0-alpha`. A contract test ties the
  `atlas-core` image tag to `[project].version`, so a bump touches all three.
- Several `docs/` pages carry a "Status at ATLAS-TASK-0001" banner that predates
  the broker work.
