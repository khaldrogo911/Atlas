# ADR 0016 — Unusable broker configuration refuses startup; the terminal path is not probed

**Status:** Proposed
**Date:** 2026-08-15

## Context

ADR-0015 decided that `apps/atlas-core` translates `BrokerSettings` into an
`MT5Config` at startup and constructs an `MT5BrokerAdapter` from it, and
decided what an unusable broker section means: **the process does not start.**
Its words were that "a deployment whose broker configuration cannot produce an
`MT5Config` is a deployment that cannot trade, and it says so at startup rather
than at the first order", and it forbade the application to "defer the failure
to first use, or to an indefinite later point".

ATLAS-TASK-0023 implemented that translation and, in the same breath, recorded
that the intent is only half met. Its §15 verified by construction that
`MT5Config` rejects two of the four not-configured defaults and accepts the
other two, and its §21.2 named the result exactly: "A deployment that sets only
`ATLAS_BROKER__LOGIN` and `ATLAS_BROKER__SERVER` therefore starts, constructs
an adapter, and fails at the first connect instead of at startup… **The gap is
recorded, not closed.**" It could not close the gap, because closing it adds an
invariant, and ADR-0015 had guaranteed "No new field, no new invariant, no new
environment variable".

That is why this record exists. The gap is not a defect in the implementation,
which did what it was told; it is a decision nobody had the authority to take.
Only a decision record can lift ADR-0015's own constraint, and this is it.

`BrokerSettings` gave a reason for locating the refusal away from startup: the
defaults "permit nothing all the same… but the refusal lands where a connection
is assembled rather than at start-up, **because nothing assembles one yet**, and
a start-up invariant would refuse every process for want of configuration
nothing reads". Since ATLAS-TASK-0023, something does assemble one,
unconditionally, on every startup in every environment. The reason has expired
on its own terms, and its consequence has already arrived: an `atlas-core` with
no broker configuration exits `2` today, in development as much as in
production, because `login=0` and `server=""` are refused. What this record
decides is therefore not whether broker configuration can refuse a process — it
already can — but which further values join the two that already do.

One precedent governs the shape of the answer.
`AtlasSettings._enforce_production_invariants` already refuses to start when
`postgres.password` is empty. The repository has therefore already ruled that an
empty `SecretStr` password is not configuration but its absence.

## Decision

**Broker configuration that cannot open a session is refused where the session
is assembled, and the refusal is confined to properties that hold independently
of the machine performing the validation.**

Four fields, four verdicts.

### `login` and `server` are already correct and are not touched

`MT5Config.login` is `gt=0` and `MT5Config.server` is `min_length=1`. `0` is not
an account number and `""` is not a trade server, and both are the
not-configured defaults `BrokerSettings` ships. Nothing here changes either
constraint, widens it or narrows it. Any description of them elsewhere that is
more generous than this paragraph is wrong.

### An empty password is refused, in every environment

A trade account is authenticated by a password. `BrokerSettings` calls its four
values "what a trading session needs in order to be established",
`MT5Session.connect` passes the password straight into the terminal's
`initialize`, and an empty one authorises nothing. This record treats the empty
password as the same kind of thing the empty server already is: the absence of
configuration wearing a value's clothes.

The refusal applies in **every environment**, not only in production, and that
differs from the postgres precedent deliberately. `postgres.password` is scoped
to `is_live` because a local process can legitimately run against a passwordless
development database. There is no corresponding MetaTrader mode, and `login` and
`server` are already refused everywhere, so scoping the password differently
from the two values beside it would be an inconsistency with nothing behind it.

**Where the evidence is indirect, this record says so.** No repository artefact
enumerates MetaTrader authentication modes. The conclusion rests on the vendor
call signature, on `BrokerSettings`' own description of what a session needs,
and on the postgres precedent for the identical type. It is a judgement on
strong indirect evidence, not a proof, and a future venue that authenticates
without a password would be grounds to supersede this record rather than to work
around it.

### The not-configured terminal path is refused, and nothing else about it is

`BrokerSettings.terminal_path` defaults to `Path()`, which is `.` — a directory,
and the sentinel meaning that nobody set it. It is refused on the same grounds
as `server=""`: it is the absence of a value rather than a value.

**No other property of the path is validated, and this is the more important
half of the decision.** Absoluteness, existence, executability, filesystem
accessibility and platform-specific validity are each refused as invariants,
because each makes configuration validity a property of the machine doing the
validating rather than of the configuration.

- **Absoluteness cannot be tested portably.** `atlas-core` ships in
  `python:3.12-slim-bookworm`. Under POSIX semantics,
  `Path("C:/Program Files/MetaTrader 5/terminal64.exe").is_absolute()` is
  `False`. An absoluteness invariant would therefore reject correct production
  configuration inside the container this repository builds. The field's
  description says "Absolute path to terminal64.exe", and that remains the
  operator's obligation — but an obligation stated in a description is not the
  same thing as an invariant a validator can enforce, and this record declines
  to promote it into one.
- **Existence, executability and accessibility are filesystem probes.** They
  would put I/O inside a configuration validator, make settings resolution
  depend on mount order and image contents, and fail in every container that
  validates configuration without the Windows terminal installed.

**No filesystem I/O occurs during configuration validation.** This is a rule of
this record and not merely a consequence of the fields it declines to check.

The terminal path's real validation is the terminal starting, and that belongs
to `connect()`. ADR-0015's four-stage table already assigns "no terminal
contact" to adapter construction and the venue to connection, and this record
moves no work out of those rows.

### Not configured, and unusable on this machine, are different failures

This record turns on a distinction it states rather than assumes:

- **Not configured** — a value that is the section's own default, or that is
  empty. It is unusable everywhere, on every host, in every environment, and
  nothing about the machine could make it work. This refuses startup.
- **Configured but unusable on this machine** — a value somebody chose, which
  this host cannot honour: a path to a terminal that is not installed here, a
  password the trade server will reject, a server name that does not resolve.
  This is a connect-time failure, and it stays one.

Deferring the second class is not the deferral ADR-0015 forbade. ADR-0015
forbade deferring a refusal that *could* have been made at startup; a refusal
that cannot be made portably, or cannot be made without I/O, is not one of
those. A validator that tried to make it would be reporting the state of a
filesystem, not the validity of a configuration.

### The refusal is the one that already exists

No new error surface, exit code, stream or record is created. A rejected
`MT5Config` raises `ValidationError`, which `composition.py` already narrows to
`ConfigurationError`, which `main()` already reports as one JSON object on
stderr under `atlas.core.startup_failed`, exiting `2` with stdout empty.
Translation precedes adapter construction, so no adapter is built, no owner is
created and no session is opened.

**Credentials appear on neither stream.** `SecretStr` masks in Pydantic's error
output — a length violation reports `input_value=SecretStr('')`, never the value
— and the startup record carries no broker key at all. A refusal added by this
record discloses no more than the refusals already present.

### The site is the translation boundary

The rules belong to `MT5Config`, beside the `gt=0` and `min_length=1` already
there, and not to `AtlasSettings._enforce_production_invariants`. `atlas.config`
restates the broker section in its own primitives precisely so that it need not
know what a venue requires (ADR-0014), and a rule about what opens a MetaTrader
session is venue knowledge. `BrokerSettings` said the refusal "lands where a
connection is assembled", and ADR-0015's table put it in the translation row.
All three agree, and this record follows them.

## Alternatives considered

**Leave the validation as it is.** Rejected: it is the state ADR-0015 ruled
against and ATLAS-TASK-0023 §21.2 recorded as a gap awaiting exactly this
record. A process that starts, reports success and cannot trade is the failure
mode ADR-0015 named.

**Refuse the empty password only.** Rejected as incomplete: `LOGIN`, `SERVER`
and `PASSWORD` with no terminal path still starts a process that cannot trade,
which is the same defect one field over.

**Refuse a fully validated terminal path — absolute, existing, executable.**
Rejected on evidence, and this is the alternative that looked most attractive
and is most wrong. It would reject valid Windows configuration whenever
validated on Linux, which is where the shipped container validates it. It also
converts an operator's obligation into a dependency on machine state, so the
same configuration would be valid or invalid according to which host resolved
it.

**Put the invariants in `_enforce_production_invariants`, following the postgres
precedent.** Rejected: it would make `atlas.config` encode what a trading
session requires, which is the coupling ADR-0014 exists to prevent, and it would
scope to production alone two values whose neighbours `login` and `server` are
already refused everywhere.

**Refuse at `BrokerSettings` instead, so the section rejects its own defaults.**
Rejected: every section of `AtlasSettings` is built by `default_factory`, so a
process holding no trading configuration must still resolve its settings.
Refusing there would break settings resolution for every process that never
reads the broker section at all.

## Consequences

### Guaranteed

- A process that starts has broker configuration from which an `MT5Config` was
  constructed, carrying a login, a server, a non-empty password and a terminal
  path somebody chose.
- ADR-0015's sentence "`MT5Config` refuses them", which lists four unusable
  values, becomes accurate for all four — without ADR-0015 being edited.
- The failure is the existing one: `ConfigurationError`, one JSON line on
  stderr, empty stdout, exit `2`, no adapter constructed, no owner created, no
  session opened and no credential printed.
- Configuration validation performs no filesystem I/O, so resolving settings
  stays a pure function of the configuration and the environment.
- Nothing about the run loop, the owner's lifecycle, supervision or any consumer
  changes. `docker-compose.yml`'s `restart: "no"` remains correct, and its
  comment — that restarting cannot fix "a broker configuration that cannot open
  a session" — becomes true of one further class of such configuration.

### Not guaranteed, deliberately

- **That a started process can reach its terminal.** The path is not probed. A
  wrong, relative or absent path still fails at `connect()`, and this record
  chooses that over an invariant that cannot be stated portably.
- **That the password is correct.** Only that one is present. Authentication is
  the trade server's verdict and is not anticipated here.
- **That the terminal path is absolute.** It stays an operator's obligation,
  stated in the field's description.
- **That `server_utc_offset` is right.** Untouched; ATLAS-TASK-0023 §21.2's
  inherited gap stands exactly as it was.

### Costs

- **A deployment that today starts with an empty password or a bare terminal
  path stops starting.** This is the decision rather than a side effect, and the
  deployments it stops are ones that could not have traded. It is a behavioural
  change all the same, and belongs in the roadmap when it is implemented.
- **ATLAS-TASK-0023 §15's verified statement that an empty password and
  `terminal_path='.'` are accepted becomes historical.** Task specifications are
  immutable records of what was true when they were written and are not edited;
  the statement stands as written, and this record is what changes the fact.
- **Two more values must be supplied to run `atlas-core` locally.** Small, and
  already true of `login` and `server`.
- **A future venue that authenticates without a password would need this record
  superseded.** That is the cost of deciding on indirect evidence, accepted
  knowingly rather than discovered later.

## What this record does not decide

- **`BrokerOwner`'s lifecycle**, when `start()` is called, and by what.
- **The run loop**, and any consumer of the owner or of an `OrderRequest`.
- **Supervision, health checks, reconnection and failover.**
- **Multiple adapters, venues or accounts.**
- **The general `apps/` import rule**, which ADR-0013 `:242-249` left open and
  ADR-0015 left there. This record adds no import anywhere.
- **How risk obtains its limits.** ADR-0012's revisit condition stays exactly as
  satisfied, and as unexercised, as ATLAS-TASK-0023 left it.
- **Dependency injection, registries, factories and service locators.**
- **Any external secrets mechanism.** ADR-0003 governs secrets unchanged.
- **Order lifecycle, routing, idempotency, fills and reconciliation.**
- **Account and portfolio state ownership.**
- **`server_utc_offset`**, and the correction of any gap other than the one
  named above.
- **Any new configuration field or environment variable.** This record adds
  none. It constrains only values the existing four fields already accept.

## Relationship to ADR-0015

**ADR-0015 is not superseded, not edited and not reopened.** Its selection of
`MT5BrokerAdapter`, its placement of construction at startup, its four-stage
failure table and its rule that unusable broker configuration must not start the
process all stand as written.

This record supplies the invariant ADR-0015 declined to add. Its guarantee "No
new field, no new invariant, no new environment variable" was a statement about
what that record introduced; it stays true of ADR-0015, and is lifted only here,
deliberately, and only for the invariant half — no field and no environment
variable is added by this record either. The refusal stays in the second row of
ADR-0015's own table.

## Relationship to ADR-0014

**ADR-0014 is not superseded, not edited and not reopened.** The section remains
four values in `atlas.config`'s own primitives, `atlas.config` still does not
import `atlas.broker`, and no rule about what a trading session requires is
added to the configuration package. Locating these invariants in `MT5Config` is
what keeps that true, and is why the postgres precedent's *placement* was not
followed even though its *reasoning* was.

## Relationship to ADR-0012 and ADR-0013

**Neither is superseded, edited or reopened.** Nothing here reads
`settings.risk`, imports `atlas.risk`, or names an engine, a registry or a
consumer. `PIPELINE_PACKAGES` is unchanged and `apps/atlas-core` acquires no
import. ADR-0013's five responsibilities stand, and this record claims none of
the sequencing or supervision it left downstream.

## Relationship to ADR-0003

**ADR-0003 is untouched.** Secrets stay in the process environment. Requiring a
password to be non-empty adds no file, no field and no route:
`ATLAS_BROKER__PASSWORD` is unchanged, no file under `config/` may carry it, and
`SecretStr` masking means the new refusal prints no more than the existing ones
do.
