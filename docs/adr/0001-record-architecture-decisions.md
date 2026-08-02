# ADR 0001 — Record architecture decisions

**Status:** Accepted
**Date:** 2026-08-02

## Context

Atlas will be developed over a long horizon, and the expensive questions in a
trading platform are rarely about syntax. They are about why the risk engine
sits where it does, why a datastore was chosen, why a boundary exists. Six
months later the reasoning is gone, and the usual outcome is that someone
removes a constraint whose purpose they cannot reconstruct.

Code records what the system does. Nothing in the repository records *why*.

## Decision

Every architecturally significant decision is recorded as a numbered Markdown
ADR in `docs/adr/`, following Michael Nygard's format.

A decision is architecturally significant if reversing it would require
changing more than one package, would alter an external contract, or would
change the platform's safety properties.

ADRs are immutable once accepted. A decision that changes gets a new ADR that
supersedes the old one; the original is marked `Superseded by ADR-NNNN` and
otherwise left alone.

## Consequences

- Every non-obvious constraint has a written justification with a stable link,
  and the README's decision table can point at it.
- Reviewers can challenge a decision's *reasoning* rather than re-deriving it.
- A pull request that changes architecture without an ADR is incomplete; this
  is listed in the contribution checklist.
- The cost is a page of writing per significant decision. That is deliberate
  friction: a decision not worth a page of justification probably is not
  architecturally significant.

## Alternatives considered

**Wiki or external documentation tool.** Rejected: documentation that does not
live in the repository is not reviewed with the change, and drifts within
weeks. ADRs are versioned with the code they describe.

**Commit messages and pull request descriptions.** Rejected: they are
chronological, not topical. Finding "why does risk sit between strategy and
execution" means archaeology across hundreds of commits.

**No formal record.** Rejected: this is the status quo that produces
constraints nobody dares touch and nobody can explain.
