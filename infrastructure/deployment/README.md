# Deployment Infrastructure

**No target platform has been chosen, and none is assumed.** Choosing one
before there is a service to deploy would be a decision made with the least
information anyone will ever have about the requirements.

## What is settled

The unit of deployment is a **container image**, built by the root `Dockerfile`:
multi-stage, non-root (uid 1000), carrying only the virtual environment and
application source. That much is platform-independent and already validated in
CI, which builds the image on every merge and runs its start-up check twice:
once with throwaway broker configuration, which must exit `3` — since ADR-0017
the check opens a session, and a Linux image has no MetaTrader 5 terminal to
open one against — and once without it, which must exit `2` before it ever gets
that far. A platform that cannot deliver the four `ATLAS_BROKER__*` values to
the process therefore cannot run this image, and a Linux platform cannot
complete the check at all.

## What is not settled

| Question | Depends on |
|---|---|
| Orchestrator (Compose, Nomad, Kubernetes) | how many processes there are, and whether they scale independently |
| Host and region | broker endpoint proximity, once a broker is chosen |
| Secret delivery | the platform's own secret mechanism |
| Rollout strategy | whether the core service can be restarted without losing in-flight orders |

That last one is a design constraint on `atlas.execution`, not a deployment
detail. Order handling must be idempotent and recoverable across a restart
before any rollout strategy can be called safe.

## Non-negotiables for any platform

1. **Secrets arrive through the environment.** No credential in an image layer,
   a config file or a repository. The `.dockerignore` excludes `.env`.
2. **`ATLAS_ENV` is exported explicitly.** It selects the configuration layer
   and is read before the settings model exists.
3. **Production invariants are enforced by the process, not the platform.** A
   misconfigured container exits `2` on start-up regardless of what deployed it.
4. **The image is immutable and tagged by version.** No `latest` in production.
5. **A restore must have been rehearsed.** An untested restore procedure is a
   hypothesis.

## What lands here

Manifests, Terraform, or a deployment script — whichever the chosen platform
needs — plus an ADR recording why that platform was chosen over the
alternatives.
