# ADR 0021 — Filling mode and deviation are configured, not chosen

**Status:** Proposed
**Date:** 2026-08-21

## Context

Four methods on `MT5BrokerAdapter` — `place_order`, `modify_order`, `cancel_order`,
`close_position` — raise `NotImplementedError` today, and all four cite the same
unfinished business. `atlas.broker.mt5.adapter`'s module docstring names it once:
"filling mode per instrument, a deviation policy, and reading deals back to
report a fill at the price it actually happened." The shared constant every one
of the four methods raises through, `_TRADING_DEFERRED`, says it again: "order
submission also needs a filling mode per instrument, a deviation policy, and a
read of the resulting deals to report the price a fill actually got." `place_order`'s
own docstring narrows it to the two decisions this record answers: "The remaining
decisions are filling-mode selection per instrument and a deviation policy;
neither has an obviously right answer, which is why they are not settled here."
The package's `README.md` says it a fourth time, once in prose and once in its
"Future work" table.

That is four independent citations of the same gap, and all four agree on a
detail worth noticing before anything else: every one of them qualifies filling
mode with "per instrument", and none of them ever qualifies deviation the same
way. That asymmetry is not a stylistic accident. MetaTrader 5 exposes filling-mode
support as a property of the instrument as the broker configured it — a venue
may accept an immediate-or-cancel fill on one symbol and require fill-or-kill on
another, and sending a mode the symbol does not accept is rejected at the trade
server. Deviation — how many points of slippage a request tolerates before the
terminal itself declines to fill it — is not tied to a symbol's capability in
the same way; it is a tolerance the caller sets. Nothing in this repository
states that distinction outright, but it is the only fact that explains why the
same four sources describe one value as varying by instrument and the other as
a single policy, without exception, every time.

### The question was named once already, and deliberately left open

[ADR-0011](0011-execution-builds-the-request-another-layer-owns-the-port.md)
already found this gap while explaining why `atlas.execution` does not choose
an order type on the caller's behalf: "Filling-mode selection per instrument
and a deviation policy are named in `atlas.broker.mt5.adapter` as the two
questions order submission still has to answer, with the observation that
'neither has an obviously right answer, which is why they are not settled
here'." ADR-0011 used that fact to justify a different decision — that
`ExecutionPolicy` carries no default — and explicitly did not resolve the
question itself. This record is the one that does, one layer down from where
ADR-0011 left it.

`ExecutionPolicy`, in `packages/execution/src/atlas/execution/contracts.py`,
states its own scope in its class docstring: "The two answers a `RiskVerdict`
does not carry, and no others" — `order_type` and `price`. Its module docstring
calls this "Presentation is supplied, not chosen" and gives the reason nothing
here reopens: "choosing MARKET on the caller's behalf would settle filling mode
and deviation — the two questions `atlas.broker.mt5.adapter` says have no
'obviously right answer' — in the package least likely to be read as policy."
Filling mode and deviation answer a different question than `order_type` and
`price` do. `ExecutionPolicy` says what a venue is asked for — a market order or
a limit at a stated price, a choice that varies by trade and belongs to whoever
is presenting the order. Filling mode and deviation say how the MetaTrader 5
terminal is instructed to attempt that fill at the wire level — which of the
three `ORDER_FILLING_*` semantics `order_send` is told to use, and how many
points of adverse movement it is allowed to accept before declining rather than
filling. That is a property of one venue's trade-request format, not a
trade-by-trade presentation choice, and it is why the question belongs in
`atlas.broker.mt5` rather than in execution's policy.

### The precedent for where an MT5-specific value lives already exists

[ADR-0015](0015-broker-adapter-selection.md) drew the line this record stands
on: "What is MT5-specific is `MT5Config` — its `gt=0`, its `min_length=1`, its
`timeout_ms`, its `portable`, its `server_utc_offset` — and that type stays in
`atlas.broker.mt5`, where it already is." `MT5Config`, defined in
`packages/broker/src/atlas/broker/mt5/connection.py`, already carries exactly
this kind of value: mechanical facts about how this adapter talks to this
venue, validated at construction, that no other broker implementation would
share the shape of. Filling mode and deviation are that kind of value. They are
not a trading policy in the sense `RiskSettings.max_margin_utilisation` or
ADR-0020's polling instrument are — values [ADR-0012](0012-risk-is-handed-its-state-and-reads-its-own-limits.md)
and [ADR-0020](0020-the-runtime-polls-a-configured-instrument-on-a-configured-interval.md)
placed in `atlas.config` because they are venue-neutral facts about what a
deployment is permitted or configured to trade. Filling mode and deviation are
facts about how one specific vendor's `order_send` call must be shaped, in that
vendor's own vocabulary, and `atlas.config` names no venue and imports no
broker type — a rule ADR-0014 and ADR-0015 both hold and this record does not
disturb.

### Fail-closed is not a new principle here

ADR-0012 handed a risk control its limit rather than let a caller supply one,
and refused to let absence mean permission. ADR-0016's rule — restated in
ADR-0020 — is that a value which is unusable everywhere refuses at
configuration, and that configuration validation performs no I/O to decide
that. ADR-0020 applied the same fail-closed stance to the polling instrument
and interval: "A runtime with no configured instrument, or no configured
polling interval, does not start. It does not poll with a value it chose for
itself." Every one of those records rejected the same shortcut in a different
place: guessing a value that "usually works" instead of naming the gap. This
record is that principle's next application, not a new one, and ADR-0020 named
this record's territory directly in its own refusal list: "`place_order`'s
implementation, filling mode and deviation policy."

## Decision

**Filling mode and deviation are configuration owned by `atlas.broker.mt5`, not
values `ExecutionPolicy` carries or the adapter chooses at the call site.
Filling mode is configured per instrument, because whether a symbol accepts a
given fill semantics is the venue's own restriction. Deviation is configured as
a single value, because tolerance for adverse slippage is one policy applied
uniformly, not a per-symbol capability. Neither has a default that permits a
trade to proceed on a guess.**

### The two values do not share a shape, and this record does not force one

A per-instrument mapping and a single scalar are different kinds of
configuration, and collapsing them into one shape — a single filling mode for
every instrument, or a deviation that varies by instrument for symmetry with
filling mode — would misrepresent what each of them is. Filling mode varies
because MetaTrader 5 symbols vary in which `ORDER_FILLING_*` semantics their
broker accepts; naming one filling mode for every instrument would be correct
for some symbols and a rejected order for others, discovered only when an
untested instrument is first traded. Deviation has no comparable venue-side
constraint to track per symbol; it is Atlas's own tolerance, and varying it by
instrument would be a trading decision with no venue fact to justify the extra
shape.

### Both live in `atlas.broker.mt5`, and neither reopens `ExecutionPolicy`

`ExecutionPolicy` keeps exactly the two fields it has today: `order_type` and
`price`. This record adds no field to it, no default to it, and no
configuration-reading behaviour to `atlas.execution`. `atlas.execution` still
imports only `atlas.risk` and `atlas.broker`, per ADR-0011's implementation
constraints, and still names no configuration package.

The configuration this record authorises is read by `atlas.broker.mt5` alone,
at the point where a trade request is translated into an `order_send` call. It
is not supplied by `atlas.execution`, not supplied by whatever eventually calls
`place_order`, and not read from `atlas.config` — for the same reason
`MT5Config`'s other MT5-specific fields are not: `atlas.config` names no venue
and imports no broker type, and this record does not widen that boundary.

```
ExecutionPolicy          →  order_type, price          (what the caller asks for)
MT5Config (this record)  →  fill policy, deviation      (how MT5 is told to attempt it)
```

**No field name, no Python type name, no environment-variable name and no TOML
key is chosen here.** Whether the new configuration is added directly to
`MT5Config` or to a value it is composed from is the implementing task's
choice, exactly as ADR-0012 left the exposure limit's field names to its
implementation.

### Absence is not permission, and the two values fail differently

Neither value may be defaulted to a guess. Specifically, and because each of
these is a plausible shortcut a reasonable implementation would take without
noticing:

- The adapter does not try each `ORDER_FILLING_*` value in turn until the
  terminal accepts one. That would discover a working filling mode by making
  live requests against a real venue at trade time, and it would mean the mode
  actually used for a given symbol is whatever the venue happened to accept
  first on a given day, reviewable by nobody.
- The adapter does not assume `ORDER_FILLING_RETURN` — or any other single
  mode — as a value that "usually works". A mode that is wrong for a symbol is
  discovered as a rejected order, at the worst possible time to discover it.
- The adapter does not treat an unconfigured deviation as zero deviation. Zero
  is a real, very strict tolerance — an order that must fill at exactly the
  requested price or not at all — and is nothing like "not configured". Reusing
  it as the unconfigured sentinel is the same mistake ADR-0016 named for a
  price of `0.0` on a broker field, applied to points of slippage instead of a
  price.

The two values reach that refusal by different mechanisms, because they can be
validated at different times.

**Deviation can be validated eagerly**, the way `MT5Config.login`, `.server`
and `.terminal_path` already are: a single required value with no default,
rejected at construction if it is missing or the sentinel that means nobody
supplied one. Nothing about deviation depends on which instrument is later
traded, so nothing prevents checking it before any trade request exists.

**Filling mode cannot be validated eagerly with the same completeness**, and
this is a structural fact, not a preference. A mapping from instrument to
filling mode can only be required to be *exhaustive* if the universe of
instruments this adapter will ever be asked to trade is already known, and no
record — including this one — decides that universe. ADR-0020 named exactly
one instrument for the polling path and was explicit that this was "an initial
scope boundary and is recorded as one rather than as a permanent shape", not a
constraint on what `place_order` may be asked to trade. Requiring the mapping
to cover every instrument MetaTrader 5 offers would mean asking the venue for
that list during configuration validation, which ADR-0016's rule against I/O
during validation already forbids. **The refusal for an unmapped instrument
therefore happens no earlier than the call that names it** — at `place_order`,
`modify_order`, `cancel_order` or `close_position`, whichever is asked to trade
an instrument the configured mapping does not cover — and it refuses there
rather than falling back to a default filling mode for that call.

### This record's acceptance unblocks all four trading methods, not only `place_order`

`modify_order`, `cancel_order` and `close_position` each raise
`NotImplementedError` today citing "the reason given on `place_order`", and
each is documented to need `order_send` under a different `TRADE_ACTION_*`
value than placement uses. All three depend on the same filling-mode and
deviation questions this record answers, because all three submit a request
through the same terminal call `place_order` does. Accepting this record is a
prerequisite for implementing any of the four, not a prerequisite for
`place_order` alone.

### What this settles about the venue-specific vocabulary

`atlas.broker.mt5` is authorised to name MetaTrader 5's own filling-mode and
deviation vocabulary — `ORDER_FILLING_FOK`, `ORDER_FILLING_IOC`,
`ORDER_FILLING_RETURN`, and `order_send`'s `deviation` parameter — in order to
express this configuration and translate it. That vocabulary already lives
behind this package's boundary; nothing above `atlas.broker` gains a route to
it, and no new name crosses the boundary this record's translation sits behind.

## Consequences

### Guaranteed

- **The question ADR-0011 named and declined to answer has an owner.** Filling
  mode and deviation are `atlas.broker.mt5`'s to configure, not
  `atlas.execution`'s, and not the caller's.
- **`ExecutionPolicy` is untouched.** It keeps exactly `order_type` and `price`,
  and ADR-0011's implementation constraints on `atlas.execution` are
  undisturbed.
- **`atlas.config` gains no venue knowledge.** No new edge into or out of
  `atlas.config` is created; the configuration this record authorises is read
  where `MT5Config`'s other MT5-specific values already are.
- **Neither value can be silently guessed.** A deployment that has not
  configured deviation cannot construct a usable `MT5Config`; a request naming
  an instrument absent from the filling-mode configuration is refused rather
  than sent with an assumed mode.
- **All four trading methods share one prerequisite**, named once, rather than
  each rediscovering the same gap independently when its own task is scoped.

### Not guaranteed, deliberately

- **That any trading method is implemented.** This record authorises the
  configuration; it implements no method, calls `order_send` nowhere, and
  leaves all four `NotImplementedError`s exactly where they are today.
- **That a configured filling mode is accepted by the venue.** Like ADR-0020's
  polling instrument, this is validated as configuration and not by asking the
  venue; a mode the symbol does not in fact accept still fails, at the trade
  server, when it is sent.
- **That deviation or filling mode are sensible values.** Each is the
  deployment's to choose, and no bound on either is decided here.
- **A read of the resulting deals, or a fill reported at the price it actually
  got.** Every citation in the Context section names that as a third piece of
  unfinished business alongside filling mode and deviation. This record
  answers the two questions it names in its title and no more; the deal-read
  problem is untouched and unscoped.

### Costs

- **A second configuration surface lives inside `atlas.broker.mt5` rather than
  in `atlas.config`.** A reader used to finding trading-adjacent configuration
  in one package now has to know that MT5-specific mechanics live beside the
  values `MT5Config` already carries instead. The mitigation is the same one
  ADR-0015 already accepted for `timeout_ms` and `server_utc_offset`: this is
  where the venue-specific validation already is.
- **The per-instrument mapping's refusal surfaces at call time, not at
  start-up.** A misconfigured deployment that never trades an unmapped
  instrument will not discover the gap until the first request that names one.
  This is the same trade-off ADR-0020 accepted for an instrument the venue does
  not offer — configuration validation cannot know what it has not been told to
  check — and it is accepted here for the same structural reason.
- **Two more values a deployment must supply before any of the four trading
  methods can be implemented usefully**, on top of the four broker values
  ADR-0016 already requires and the two polling values ADR-0020 added.

## Alternatives considered

**Add filling mode and deviation to `ExecutionPolicy`.** Rejected. It is the
alternative ADR-0011 already refused in substance, by naming these as the two
questions execution's policy does not answer and explaining why: a caller
choosing them would be choosing MT5-specific wire mechanics through a contract
that is deliberately venue-neutral in its own module docstring — "The order
vocabulary stays the broker's" is ADR-0011's rule for `OrderType` and `Price`,
which the port already defines; filling mode and deviation are not part of
that vocabulary, they are part of how one adapter presents an order built from
it.

**A single filling mode for every instrument.** Rejected. Every citation this
record found describes filling mode as a per-instrument fact, and the
underlying reason — a MetaTrader 5 symbol's broker-configured filling
capability — does not go away by ignoring it. A single mode would work for
whichever instruments happen to share a capability and fail, at the trade
server, for the rest.

**Autodetect the filling mode by trying each `ORDER_FILLING_*` value until the
terminal accepts one.** Rejected, and named explicitly because it is the
shortcut a MetaTrader 5 integration most commonly reaches for. It resolves the
configuration gap by making live, order-shaped requests against the venue at
trade time rather than by configuring anything, and the mode a given symbol
ends up trading under becomes whatever the terminal happened to accept first —
a fact discoverable only by reading trade history, not by reading a
configuration file. It is the exact failure ADR-0016 already named for a
different value: a plausible-looking answer standing in for one nobody chose.

**Default deviation to zero.** Rejected. Zero deviation is not "unconfigured";
it is the strictest possible tolerance a caller could deliberately choose — no
adverse slippage accepted at all. Treating it as the unconfigured sentinel
means a deployment that actually wants zero tolerance cannot express that
choice, and a deployment that configured nothing trades under the tightest
possible constraint without having chosen it.

**Validate the filling-mode mapping for completeness against every instrument
the venue offers, at start-up.** Rejected. It would require calling the venue
during configuration validation — the same network round trip ADR-0016 and
ADR-0020 both already forbid at that stage — and it would require this record
to name a bounded universe of tradable instruments, which nothing in the
repository has decided and which is explicitly out of scope: ADR-0020 named
one instrument for polling and took no position on what `place_order` may be
asked to trade.

**Leave the question to whichever task first implements `place_order`.**
Rejected, for the reason ADR-0015 gave when the same alternative was proposed
for adapter selection: it is what the repository already tried, across
ATLAS-TASK-0005 and every docstring quoted in the Context section above, and
the result is four `NotImplementedError`s that agree on the gap and none that
close it. Answering it in an implementation task rather than a record would
decide architecture in a diff, which is the failure mode ADR-0018 and every
record since exist to prevent.

## What this record does not decide

- **The concrete filling mode for any instrument**, and no default table
  mapping symbols to modes.
- **The concrete deviation value**, in points or in any other unit.
- **Field names, Python type names, environment-variable names and TOML keys**,
  and any value for any of them in any layer of `config/`.
- **Whether the configuration is a new field on `MT5Config` or a value composed
  into it.** Either satisfies this record.
- **The `order_send` call itself, or any part of `place_order`, `modify_order`,
  `cancel_order` or `close_position`'s implementation.**
- **Reading the resulting deals back, or reporting a fill at the price it
  actually got.** Named in the Context section as a third open question; not
  this record's.
- **Session schedules, `can_trade`'s market-open gap, or anything else this
  package's README lists as a current limitation** other than the trading
  methods' filling-mode and deviation dependency.
- **Retry or reconnection policy for a trading call.**
- **Any change to `ExecutionPolicy`, `OrderRequest`, `OrderType` or `Price`.**
- **Any change to the broker port**, `BrokerAdapter`, or any adapter other than
  `MT5BrokerAdapter`.

## Relationship to ADR-0011

**Not superseded, not edited, not reopened.** `atlas.execution` still builds a
request and reaches no port; `ExecutionPolicy` still carries exactly
`order_type` and `price`, still has no default, and still reads no
configuration.

ADR-0011 named this record's territory and declined to settle it, in the
sentence this record's Context quotes in full. Its reasoning for refusing
execution a default is untouched by this record answering the question one
layer down: "a default chosen inside execution would settle both by accident,
in the package least likely to be read as policy." This record settles them on
purpose, on the record, in `atlas.broker.mt5` — the package ADR-0011 itself
named as the one that would eventually have to answer.

## Relationship to ADR-0012

**Not superseded, not edited, not reopened.** No exposure limit, risk model or
`RiskSettings` field is touched.

This record follows ADR-0012's fail-closed stance and its split between a fixed
principle and an open mechanism — "The principle is fixed here; the mechanism
is not" applies here exactly as it did there. It does not follow ADR-0012's
*placement*: the exposure limit lives in `atlas.config` because it is a
venue-neutral trading policy every deployment answers the same way regardless
of which adapter is behind the port. Filling mode and deviation are not that;
they are facts about one vendor's wire format, and this record places them
where ADR-0015 already places every other MT5-specific value.

## Relationship to ADR-0015

**Not superseded, not edited, not reopened.** No adapter selection is
reopened, and `apps/atlas-core`'s authority to name `MT5Config` and
`MT5BrokerAdapter` is unchanged.

This record leans on the distinction ADR-0015 drew and restates it for a new
pair of values: "What is MT5-specific is `MT5Config` … and that type stays in
`atlas.broker.mt5`, where it already is." Filling mode and deviation join
`timeout_ms`, `portable` and `server_utc_offset` as facts this adapter needs
that no other implementation of the port would share the shape of, and by
ADR-0015's own reasoning they belong beside them rather than in
`atlas.config`.

## Relationship to ADR-0019 and ADR-0020

**Neither is superseded, edited or reopened.** The runtime's shape, its
serialised pipeline, and the polling path's configuration and fail-closed
behaviour are all untouched.

ADR-0020 listed this record's subject in its own refusal list —
"`place_order`'s implementation, filling mode and deviation policy" — as one of
the things it deliberately left undecided. This record is that item, answered.
It also reuses ADR-0020's reasoning directly: the distinction between a value
that is unusable everywhere (refused at configuration) and a value this
adapter cannot yet validate without deciding a scope boundary nothing has set
(refused at the call that first needs it) is the same distinction ADR-0020
drew between an instrument that is configured but wrong and an instrument that
is simply absent, applied here to a per-instrument mapping instead of a single
value.

## Dependency and implementation sequencing

**No task is created by this record.** This section describes the boundary a
future task would work inside, so its scope can be judged before it is
authorised.

Hard prerequisite:

1. **This record, accepted.** Not yet — it is `Proposed`.

Once accepted, an implementing task may add the configuration this record
authorises to `atlas.broker.mt5`, implement the fail-closed behaviour described
above for both values, and proceed to implement `place_order` over
`order_send`. `modify_order`, `cancel_order` and `close_position` depend on the
same configuration and may be implemented in the same task or a later one; none
of the three can be implemented without it, for the reason given above — each
submits a request through the same terminal call `place_order` does.

Downstream, and not sequenced here:

- Reading the resulting deals back and reporting a fill at the price it
  actually got, which every citation in the Context section names as a further
  piece of unscoped work.
- Anything that calls `place_order` — no strategy, execution wiring or runtime
  change is authorised or implied by this record.

Premature under this record, and named because each looks like a small
addition:

- **A default filling mode**, "for now", to unblock a task faster.
- **Deviation expressed per instrument**, for symmetry with filling mode, on no
  venue fact that requires it.
- **Validating the filling-mode mapping against the venue's full symbol list**
  at start-up, which requires an I/O call this record's reasoning already
  forbids at that stage.
