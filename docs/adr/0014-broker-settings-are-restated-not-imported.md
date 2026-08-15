# ADR 0014 — Broker settings are restated in the configuration package, not imported

**Status:** Accepted
**Date:** 2026-08-15

## Context

[ADR-0013](0013-the-application-owns-the-adapter.md) named the layer that owns a
`BrokerAdapter` and deliberately left that adapter unconfigurable. Its decision
section says so in as many words: "**The broker or venue surface in
`AtlasSettings` is not decided here.** … What section it becomes, what it is
called, what fields it carries and how credentials reach it are a separate
decision. This record fixes only which layer is responsible for the assembly."
Its non-guarantees repeat it — "**No configuration surface is created.** The
broker section of `AtlasSettings` remains undecided and unwritten."

[ADR-0011](0011-execution-builds-the-request-another-layer-owns-the-port.md)
recorded the absence from the other side: "`AtlasSettings` holds `logging`,
`postgres`, `redis` and `duckdb`, and there is no broker or venue surface
anywhere in it." That is still true. Searching `packages/config/src` for
`broker`, `venue` or `mt5` returns nothing at all, so this record creates the
first such surface rather than amending one.

One arrow is missing, and only one:

```
AtlasSettings ──✗──▶ MT5Config ──▶ MT5BrokerAdapter
```

The second and third arrows exist and are tested. `MT5Session` takes an
`MT5Config`; `MT5BrokerAdapter` takes an `MT5Config` and touches no terminal
until `connect()` is called, "so an instance can be built during composition on
a machine where the MetaTrader5 package is not installed."

Four facts constrain the answer rather than following from it.

**The adapter cannot read configuration, and this is enforced.**
`tests/unit/broker/test_adapter_contract.py` permits the port package exactly
two imports — `PERMITTED_ATLAS_PACKAGES: Final = ("atlas.broker",
"atlas.common")`. The only occurrences of `atlas.config` anywhere under
`packages/broker/src` are two sentences of prose. Whatever holds broker
settings, it cannot be the broker package, and no decision here can change that
without rewriting a boundary test.

**The port already names where its configuration comes from.** `BrokerAdapter`'s
own docstring, under a heading called *Credentials*: "No method takes
credentials. An adapter receives its configuration when it is constructed, from
`atlas.config`, so a secret cannot reach a call site in business logic."
`MT5Config` gives the reason for the same arrangement — "an adapter that sources
its own credentials cannot be pointed at a second account in a test, and Atlas
would have two configuration systems."

**`MT5Config` requires four values and defaults three.** `login` (`gt=0`),
`password` (`SecretStr`), `server` (`min_length=1`) and `terminal_path` have no
defaults. `timeout_ms` defaults to 60 000, `portable` to `False`, and
`server_utc_offset` to a `default_factory` reading `ServerClock`, whose own
docstring records that the offset "cannot be discovered and must be configured"
and that the default of zero "is correct only for a server that publishes UTC".
The minimum surface is therefore four values, not seven and not five.

**A settings surface may exist before anything reads it.**
`risk.max_margin_utilisation` was defined, validated, defaulted to a refusing
value and gated by a production invariant while nothing consumed it. That
precedent is what lets this decision be answered completely without deciding
anything about runtime.

## Decision

**`AtlasSettings` owns a dedicated broker/venue section, and that section is
written in `atlas.config`'s own primitives. `atlas.config` does not import
`atlas.broker`, and `MT5Config` is neither embedded in the settings model nor
named by it.**

The section restates the four values `MT5Config` cannot default:

| Value | Type |
|---|---|
| `login` | `int` |
| `password` | `SecretStr` |
| `server` | `str` |
| `terminal_path` | `Path` |

These are the configuration package's own types, already used by the sections
beside them. `PostgresSettings.password` and `RedisSettings.password` are
`SecretStr` today; the broker password is the third of its kind and not a new
kind of thing.

**The translation belongs to the application.** Whatever wiring point eventually
constructs an adapter reads these four values and builds an `MT5Config` from
them. ADR-0013 already assigned that assembly: "`apps/atlas-core` is responsible
for obtaining and assembling whatever an adapter needs in order to be
constructed, and for handing it over." This record supplies the values that
assembly reads; it does not build the assembly.

**Credential handling is
[ADR-0003](0003-layered-configuration.md)'s, unchanged.** "Structure in files,
secrets in the environment." The password is `SecretStr` supplied through the
process environment, and "No file in `config/` may contain a credential" governs
the new section without amendment. The masking convention that pairs `dsn` with
`safe_dsn` and `url` with `safe_url` is available if the section ever needs a
composite, and nothing here requires one.

### The dependency direction is fixed by omission

No edge `atlas.config → atlas.broker` is created, because none is needed. The
six edges between feature packages that `docs/architecture/overview.md`
enumerates stay six, every one of them still running downward, and no boundary
test changes or weakens.

### The section names primitives, so it names no venue

A section of `int`, `SecretStr`, `str` and `Path` is compatible with an MT5
adapter and commits to nothing. It does not say that Atlas trades MetaTrader 5,
that a live adapter is what gets constructed, or that anything is constructed at
all. Adapter selection remains exactly as open as ADR-0013 left it.

## Why restate rather than import

**It keeps the configuration package's shape its own.**
[ADR-0012](0012-risk-is-handed-its-state-and-reads-its-own-limits.md) rejected
letting a feature package define a section of `AtlasSettings` partly because "it
would put the configuration package in the position of importing a feature
package to know its own shape". Restating is the alternative that rejection
implies, and ADR-0012 took it: the risk section "is defined in `atlas.config`
alongside the others, not in `atlas.risk`". This is the same rule applied one
package over.

**It does not settle venue identity as a side effect.** A section typed
`MT5Config` would name MetaTrader 5 in the configuration root before adapter
selection has been decided. Primitives do not.

**The values are already `atlas.config`'s vocabulary.** All four types appear in
the settings model today — `DuckDBSettings` carries a `Path`, two sections carry
a `SecretStr`, ports and pool sizes are `int`. Nothing has to be taught.

**It costs one thing and that thing is visible.** Two declarations of overlapping
requirements can drift. That is recorded under *Costs* rather than argued away.

## Alternatives considered

**`atlas.config` imports and embeds `MT5Config` as the section type.** Rejected,
and it is the closest call. It would make drift impossible by construction, and
— unlike the risk case ADR-0012 ruled on — it forms no cycle, because
`atlas.broker` cannot import `atlas.config` and the boundary test guarantees it.
Exactly one of ADR-0012's two grounds transfers, and it is sufficient on its own:
the configuration package would import a feature package to learn its own shape.
The second objection is this record's own — a section typed `MT5Config` decides
which venue Atlas is configured for, which is a decision ADR-0013 left open and
which this record has no authority to close.

**An external configuration or secrets service.** Deferred, not rejected, on
ADR-0003's own terms: it is "worth revisiting when there is a fleet to
configure", and there is one process that resolves settings, prints a JSON record
and exits. It is also orthogonal — it answers how values arrive, not what they
are, and would enter through `settings_customise_sources` as another source
ranked in the existing precedence. It can be adopted later on top of this record
without superseding it.

**Configuration held in `apps/atlas-core` rather than in `atlas.config`.**
Rejected. The port's docstring names `atlas.config` as the origin of an adapter's
configuration, and ADR-0012 refused a parallel route in general terms: "A second
way to configure Atlas is a second precedence order, and nobody would be able to
state either from memory."

**The adapter reads its own environment.** Rejected, and already rejected three
times over — impossible under `test_adapter_contract.py`'s permitted set, refused
in prose by `MT5Config`'s docstring, and covered by ADR-0012's ruling on second
precedence orders. It is recorded here so that it is not re-proposed as though it
were open.

## Consequences

### Guaranteed

- **The missing arrow has an owner.** `AtlasSettings` is where broker
  configuration lives, and the question ADR-0013 deferred is answered for the
  first half of it.
- **No new import edge exists in either direction.** `atlas.config` does not
  import `atlas.broker`; `atlas.broker` still may not import `atlas.config`. The
  feature-package graph is untouched and so is every boundary test.
- **Credentials keep one mechanism.** There is still exactly one precedence
  order, one secret type and one masking convention, and the broker password
  enters through the route the other two already use.
- **The port stays configuration-source agnostic.** ADR-0013's guarantee holds
  without qualification, and `MT5Config` remains what it is: frozen,
  `extra="forbid"`, constructed by somebody else and handed in.
- **Adapter selection stays open.** Nothing in a section of primitives chooses
  between `MockBrokerAdapter` and `MT5BrokerAdapter`.

### Not guaranteed, deliberately

- **No section is written.** This record adds no field, no model, no environment
  variable, no TOML key and no test. `AtlasSettings` has five sections today and
  has five after it.
- **No adapter is constructed and no wiring point is created.** ADR-0013's
  non-guarantees are all still in force, unchanged and unweakened.
- **Nothing is placed.** `apps/atlas-core` still has no run loop. Its entrypoint
  resolves configuration, emits a startup record and exits.
- **ADR-0012's revisit condition is still not satisfied.** "When a single wiring
  point exists and can be pointed at" remains unmet; deciding where settings live
  is not building the thing that reads them.

### Costs

- **The two declarations can drift, and nothing yet asserts they agree.**
  `MT5Config` and the section are separate statements of overlapping
  requirements. If `MT5Config` gains a required field, the section will not know,
  and the failure would surface at the wiring point rather than at validation.
  Independence is what restating buys and this is what it costs. The task that
  implements the section is free to pin the correspondence with a test; this
  record does not require one, because requiring it would decide the shape of a
  translation that does not exist.
- **The risk boundary's credential scan is keyed to today's section names.**
  `tests/unit/risk/test_risk_boundary.py` scans for `CREDENTIAL_SYMBOLS`, and its
  comment derives that set from "the two sections that lead anywhere
  credential-bearing". A broker password would trip the scan on `password`,
  `SecretStr` and `get_secret_value` regardless, so the credential itself stays
  covered; what goes stale is the section enumeration and the sentence that
  explains it. Whoever implements the section should read that comment and decide
  whether the new name belongs beside `postgres` and `redis`.
- **Three optional fields are left unresolved, and one of them is not
  cosmetic.** `server_utc_offset` defaults to zero, and `ServerClock`'s docstring
  says that default is correct only for a server publishing UTC. A deployment
  against a server that is not on UTC needs the field exposed. This record leaves
  the question open on purpose, but it is open, not answered.
- **The startup-record convention is unstated.** `build_startup_record` emits
  `logging`, `postgres`, `redis` and `duckdb`, and omits `risk` with no rule
  anywhere saying which sections appear. A broker section inherits that silence.

## What this record does not decide

- **Adapter selection.** Whether the application constructs a
  `MockBrokerAdapter` or an `MT5BrokerAdapter`, and on what basis.
- **When an adapter is constructed**, if it is constructed at all.
- **Where the composition or wiring point exists.**
- **Whether construction occurs at startup.**
- **Whether broker configuration appears in the startup record.**
- **External configuration or secrets services.** Deferred above on ADR-0003's
  terms, and still deferred.
- **The exact section name.**
- **The validation mechanism.** Required field, conservative default or
  production invariant — ADR-0012 fixed the principle and explicitly left the
  mechanism free: "Whether that is achieved by a required field, by a
  conservative default, or by a production invariant … The principle is fixed
  here; the mechanism is not."
- **Whether `timeout_ms`, `portable` or `server_utc_offset` are exposed.**
- **Everything ADR-0013 listed as undecided**, all of which remains undecided:
  the `apps/` import rule, whether `apps/dashboard` may hold an adapter, any
  mechanism for granting access, the run loop and threading design, order
  identity, idempotency, routing, fills, reconciliation, and account or portfolio
  state ownership.

## Relationship to ADR-0013

**ADR-0013 is not superseded, not edited and not reopened.** Its five
responsibilities stand exactly as written, and `apps/atlas-core` remains the
layer that constructs, holds, governs access to, sequences and supervises a
`BrokerAdapter`.

This record answers one of the questions ADR-0013 listed as outside itself —
"The broker or venue configuration schema. No section name, field, environment
variable or secrets mechanism is decided or invented here" — and answers only
the part of it that is a configuration question. Where ADR-0013 says the
application assembles whatever an adapter needs, this says what the application
reads in order to assemble it. Section name, environment variables and the
validation mechanism stay where ADR-0013 put them.

## Relationship to ADR-0012

**ADR-0012 is not superseded, not edited and not reopened.** The exposure limit
is still read by the control from frozen process configuration, and is still not
a parameter any caller can supply.

Two of its rulings are adopted here rather than revisited. Its placement rule —
a section "defined in `atlas.config` alongside the others, not in" the feature
package — is followed exactly. Its rejection of a feature package owning a
section is the reason the embedding alternative was refused, on the one of its
two grounds that transfers to a package which cannot import `atlas.config`.

Its revisit condition is untouched. "When a single wiring point exists and can
be pointed at" is not satisfied by this record, and this record does not satisfy
it: naming where broker settings live creates no wiring point, no engine, no
registry and no consumer.

## Relationship to ADR-0011

ADR-0011's statement that "there is no broker or venue surface anywhere in it"
was true when written and is true today — this record writes no section. It
becomes inaccurate when the decision is implemented, which is the immutability
rule working as designed. Per ADR-0013, the correction "belongs in the roadmap
and the living documents, never in ADR-0011 itself."

## Relationship to ADR-0003

ADR-0003 is extended by one section and amended in no respect. The six-level
precedence is unchanged, the layered TOML source keeps its ranking below the
environment sources, `extra="forbid"` still catches a mistyped key inside a
section, and the rule that no file under `config/` may contain a credential
covers the broker password from the moment it exists. The configuration service
ADR-0003 deferred stays deferred, on the trigger it named.
