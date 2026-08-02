# Runbooks

Procedures for a specific operational situation: what to check, in what order,
and what to do about each outcome. A runbook is written for someone at 03:00
who did not write the code.

## Index

| Runbook | Situation |
|---|---|
| [Local stack](local-stack.md) | Bringing the development stack up, and what to do when it will not start |

## Format

Every runbook states, in this order:

1. **Symptom** — what the operator observed.
2. **Impact** — what is degraded, and whether trading is affected.
3. **Checks** — ordered diagnostic steps, each with its interpretation.
4. **Resolution** — the fix for each diagnosis.
5. **Escalation** — when to stop and who to wake.

A runbook step must be a command that can be copied and run. "Verify the
database is healthy" is not a step; `docker compose ps postgres` is.

## Scope at ATLAS-TASK-0001

Only the local development stack exists. Runbooks for live trading — broker
disconnection, kill-switch activation, reconciliation mismatch, drawdown breach
— arrive with the components whose failure they describe. Writing them now
would mean writing them against imagined behaviour.
