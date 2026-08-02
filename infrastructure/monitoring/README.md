# Monitoring Infrastructure

**Nothing is implemented at ATLAS-TASK-0001.** This document records what is
planned and, more importantly, what each signal would be for. Dashboards built
before the thing they measure exists tend to measure the wrong thing.

## Foundations already in place

- **Structured logs.** `atlas-core` emits its startup record as a single JSON
  line on stdout; failures go to stderr in the same shape. `logging.format`
  defaults to `json` everywhere and is *required* to be `json` in production.
- **Container log rotation.** Every compose service caps logs at 3 × 10 MB, so
  a chatty failure cannot fill the host disk.
- **Health checks.** `postgres` and `redis` expose them; `atlas-core` will once
  it is long-lived.

## Planned signals

| Signal | Question it answers | Arrives with |
|---|---|---|
| Event bus lag | Is the pipeline keeping up with the market? | `atlas.events` |
| Data gap alerts | Did a feed stop, or arrive late? | `atlas.market` |
| Risk utilisation | How close are we to each limit? | `atlas.risk` |
| Order reject rate | Is the broker refusing us, and why? | `atlas.execution` |
| Reconciliation drift | Does our position match the broker's? | `atlas.execution` |
| Model input drift | Are features outside their training distribution? | `atlas.ai` |
| Realised vs expected | Is live behaviour matching the backtest? | `atlas.analytics` |

## Principles

**Alert on symptoms, not causes.** "No fill in 30 minutes during London" is
actionable. "CPU is at 80%" is not.

**Every alert needs a runbook.** An alert with no documented response trains
operators to ignore alerts. The link goes in the alert body.

**The most important signal is silence.** A trading process that has stopped
producing events is indistinguishable from a quiet market unless something is
explicitly watching for absence. Dead-man's-switch monitoring is a requirement,
not an enhancement.

**Reconciliation is a monitoring concern, not just an execution one.** The
authoritative position is the broker's. Any divergence is an incident.
