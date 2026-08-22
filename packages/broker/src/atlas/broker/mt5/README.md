# `atlas.broker.mt5` — MetaTrader 5 adapter

## Purpose

Validate the `BrokerAdapter` port against a real broker, without changing the
port.

A contract written in the abstract is a guess. This package is the first
implementation behind `atlas.broker.adapter.BrokerAdapter`, and its job is to
find out which parts of that contract a real venue can honour, which parts it
honours only with a correction applied, and which parts it cannot honour at all.
Every gap found is recorded below rather than papered over, because a gap that
is hidden by a plausible return value is a gap that gets discovered in
production.

The port was not modified to accommodate MetaTrader 5. Where the two disagree,
the disagreement is documented at the method and appears in **Current
limitations**.

**Demo accounts only at this stage.** The four trading methods do not send
anything to a venue.

## Architecture

Four modules in strict dependency order. Nothing points backwards, so there are
no cycles by construction rather than by convention.

```
constants.py   wire values, translation tables      → imports atlas.broker.models only
     ↓
mapper.py      pure translation into domain models  → constants + models
     ↓
connection.py  config, vendor import, session       → constants + mapper
     ↓
adapter.py     the BrokerAdapter implementation     → all of the above
```

| Module | Holds | Deliberately does not hold |
| --- | --- | --- |
| `constants.py` | Every MetaTrader 5 integer Atlas depends on, and the tables built from them | Any logic |
| `mapper.py` | Pure functions from vendor structures to domain models, and the `Protocol`s describing those structures | Terminal calls, clock reads, global state |
| `connection.py` | `MT5Config`, the lazy `import MetaTrader5`, the `Terminal` protocol, the session state machine, and both error-code → `BrokerError` tables | Domain models, exception classes of its own |
| `adapter.py` | Which terminal call answers which port method | Translation tables, field arithmetic, connection state |

The split between `adapter.py` and `mapper.py` is the load-bearing one. It means
the translation can be tested against hand-built structures with no session
present, and it means a reader auditing "what does Atlas do with the `sl` field"
has exactly one place to look. The task brief requires no mapping logic in
`adapter.py`; the arrangement above is what makes that requirement checkable
rather than aspirational.

## Dependency boundaries

**Inward.** `MetaTrader5` is imported in exactly one place: the body of
`load_terminal()` in `connection.py`. Not at module scope, and not anywhere
else.

That is a hard requirement, not a stylistic preference. `tests/contract/
test_repository_structure.py` imports every package under the `atlas` namespace,
including this one, and CI runs on Linux where the MetaTrader5 wheel does not
exist — the vendor publishes Windows wheels only. A module-level import would
fail the build of a package that is merely present in the tree.

The dependency is declared as an optional extra with a platform marker:

```toml
[project.optional-dependencies]
mt5 = ['MetaTrader5>=5.0.45,<6.0; sys_platform == "win32"']
```

so `poetry install` works everywhere and `poetry install --extras mt5` adds the
SDK where it can exist.

**Outward.** No MetaTrader 5 value leaves this package. Callers receive
`atlas.broker.models` types or an exception. No named tuple, no NumPy record, no
dict, no `Any`.

The vendor surface is untyped — the wheel ships no `py.typed` — so rather than
letting `Any` spread inward, every structure Atlas reads is described by a
`Protocol` that names exactly the fields used: `MT5AccountInfo`, `MT5SymbolInfo`,
`MT5Tick`, `MT5RateRow`, `MT5Position`, `MT5Order`, `MT5Deal` in `mapper.py`, and
`Terminal` and `MT5TerminalInfo` in `connection.py`. Those protocols are the
complete written statement of Atlas's dependency on MetaTrader 5. A function or
field absent from them is one Atlas does not use, and a vendor rename breaks a
declared contract instead of failing at an attribute lookup three layers away.

The `ignore_missing_imports` exemption in `mypy.ini` is scoped to the
`MetaTrader5` module alone for the same reason.

`atlas.broker.__init__` does not export anything from this package. Composition
imports `atlas.broker.mt5` explicitly; business logic imports `atlas.broker` and
never learns which venue is behind it.

## Mapping philosophy

Translate faithfully, correct only what is provably distorted, and never invent
a value.

Four corrections are applied, and each one prevents a specific silent failure.

**Server time is not UTC.** A MetaTrader 5 timestamp is the trade server's wall
clock encoded as a Unix epoch. On a UTC+3 server — the default for a large share
of retail brokers — the epoch reported for a bar that opened at 12:00 server time
is the epoch of 12:00 UTC, three hours after the instant the bar actually opened.
Read naively, every bar and every tick is silently wrong by the server's offset.
`ServerClock` is the one place that correction happens. Nothing in the terminal
API reports the offset, so it is configured on `MT5Config.server_utc_offset` and
defaults to zero — correct only for a server that publishes UTC. A wrong non-zero
guess would be worse than an explicit "not configured".

Despite the name, `ServerClock` is **not** a source of time and has nothing to do
with `atlas.common.clock`. It converts an instant the server sent; it never says
what time it is. The instant this adapter stamps on a heartbeat comes from the
`Clock` the base was given — `SystemClock` unless a test injects otherwise, which
is what `MT5BrokerAdapter._now` returns. See ADR-0008.

**Zero means absent.** MetaTrader 5 has no null. An unset stop loss, take profit
or last-trade price arrives as `0.0`, which the domain models would accept as a
real price of zero. `_optional_price` maps it back to `None`. The same convention
bites harder on the account: a flat account reports `margin_level` as `0.0` where
the ratio is in fact undefined, and passed through it reads as the most severe
margin call representable and fires every `margin_level < threshold` rule in the
system. It is mapped to `None`.

**Decimal by way of `str`.** `Decimal(0.1)` is the binary expansion of a float and
carries fifty digits of noise; `Decimal(str(0.1))` is `Decimal("0.1")`. Every
number crossing this boundary takes the second route.

**Stop-limit prices are inverted.** MetaTrader 5 puts the *trigger* in
`price_open` and the *limit* in `price_stoplimit`. Atlas puts the limit in `price`
and the trigger in `stop_price`. Getting this backwards produces an order that
validates, transmits, and triggers at the wrong price. `_working_prices` is the
one place it is handled, and only for `STOP_LIMIT`.

Two further rules:

- **Tables are declared once and inverted programmatically.** A hand-written
  reverse table is a second source of truth that drifts.
- **An unmappable value raises.** An unknown order type, order state, position
  type or symbol trade mode fails loudly and names the ticket. `ORDER_TYPE_CLOSE_BY`
  is the expected case: it is a netting instruction with no direction, and
  guessing a side for it would be worse than refusing.

## Current limitations

Six of the port's thirty-one methods raise `NotImplementedError`. None is a
placeholder that could have been filled with a plausible value.

All six are satisfied by `atlas.broker.mock` (ATLAS-TASK-0006), which is the
evidence that they are limitations of this venue and of the work not yet scoped
against it — not defects in the contract.

### Trading — not scoped to a task

`modify_order`, `cancel_order`, `close_position`.

The terminal capability exists (`order_send`), and since ATLAS-TASK-0005 so does
the translation of its verdict: `error_from_retcode` in `connection.py` turns any
`TRADE_RETCODE_*` into `BrokerOrderRejectedError`,
`BrokerInsufficientMarginError`, `BrokerTimeoutError`, `BrokerConnectionError`,
`BrokerAuthenticationError` or `BrokerPositionNotFoundError`, keeping the venue's
own number and comment on the exception.

What is missing is the rest of order submission, and none of it is translation: a
filling mode chosen per instrument, a deviation policy, and a read of the
resulting deals so a fill is reported at the price it actually got rather than
the price that was asked for. ATLAS-TASK-0005 stopped at the boundary
deliberately, and no task has scoped the remainder.

### Streaming — no push channel exists

`subscribe_ticks`, `subscribe_candles`.

The MetaTrader 5 Python API polls. It registers no callbacks and opens no push
channel of any kind. A subscription can only be built by Atlas running its own
polling loop, which means owning a scheduler, a change-detection rule and a
backpressure policy — a design decision in its own right, not something to
smuggle in as a side effect of a mapping task.

If polling is later rejected as a design, the correct permanent answer becomes
`BrokerUnsupportedOperationError`, which the port already anticipates for a venue
that cannot stream.

`unsubscribe_ticks` and `unsubscribe_candles` are **implemented as no-ops**, and
that is the contract rather than a stub: the port requires them to succeed
silently for a handle that is unknown or already cancelled, and since no handle
is ever issued, every handle is unknown. Raising would break a cleanup path for
no benefit.

### `server_time` — the terminal exposes no clock

There is no server-time call in the MetaTrader 5 Python API. The nearest thing is
the timestamp on the last quote of some instrument, which is the time of the last
trade-server *event* rather than the current time — over a weekend it is Friday's
close — and it would require naming an instrument that the port's signature has
no parameter for. Returning it would look like a clock and behave like a stale
one.

This is the one place the task brief and the no-fabrication rule conflict:
`server_time()` appears in the brief's list of methods to implement, and it cannot
be implemented truthfully. The no-fabrication rule wins.

### Gaps in methods that *are* implemented

- **`can_trade` does not establish that the market is open.** It reports venue
  permission: instrument not disabled, account allowed to trade. The terminal
  publishes session schedules through a symbol-info call this adapter does not
  make, so an instrument enabled outside its trading hours answers `True` here and
  rejects the order.
- **`latency` measures the terminal's link to the trade server, not the local IPC
  hop.** It reads `terminal_info().ping_last`, refreshed by the call. Measuring
  the IPC hop instead would produce a reassuring fraction of a millisecond that
  says nothing about whether an order reaches the venue in time.
- **`get_positions` costs one extra call per position.** The domain requires a
  position's commission and MetaTrader 5 does not report one — commission is
  charged against the *deals* that opened the position. It is read back per
  position from deal history. If the terminal returns no deals for a position, the
  call raises rather than reporting zero, because zero in an accounting field is a
  fabricated number.
- **`get_symbols` fails whole rather than skipping an instrument it cannot map.**
  Skipping would mean Atlas reports that a venue does not offer an instrument it
  does offer, with no way for the caller to find out otherwise.
- **`get_ticks` is a loop.** The terminal offers no batch quote call, so the
  quotes are microseconds apart rather than simultaneous. That is as close to one
  snapshot as MetaTrader 5 allows.
- **Thread safe at the session, not across requests.** ATLAS-TASK-0008 put the
  locking in `BaseBrokerAdapter`, written once for every adapter rather than
  repeated in each, and this one inherits it without naming a lock: the lifecycle
  is serialised, and `health()` still answers while a connect is parked in a
  terminal that has stopped responding — the situation in which somebody asks.
  What is *not* guaranteed is ordering between requests. The MetaTrader 5 Python
  API is a single IPC channel with its own ordering, and no lock here adds a
  second one on top of it. A request racing a lifecycle change fails with an
  error already in its documented `Raises:` contract rather than returning a
  wrong answer. ADR-0007 has the contract in full.
- **Bar close times are nominal.** MetaTrader 5 reports only a bar's open time.
  The close is derived by adding the timeframe's nominal duration, so a daily bar
  spanning a daylight-saving transition closes an hour away from the derived
  value. The domain model requires the field, so leaving it unset is not
  available.

## Errors

Every failure that leaves this package is an `atlas.broker.exceptions` type. This
package defines no exception classes of its own, and no MetaTrader 5 number
reaches a caller uninterpreted.

MetaTrader 5 reports failure as an integer in two unrelated spaces, and
`connection.py` classifies them with two separate tables that must never be
merged:

| Space | Source | Answers | Classified by |
| --- | --- | --- | --- |
| `RES_E_*` | `last_error()` | did the request reach a trade server | `MT5Session.error_from_terminal` |
| `TRADE_RETCODE_*` | an order result's `retcode` | what the server did with the order | `error_from_retcode` |

Both are total. An unrecognised `RES_E_*` becomes a bare `BrokerError`, because
guessing a category would tell a caller to retry something it should not. An
unrecognised `TRADE_RETCODE_*` becomes `BrokerOrderRejectedError`, because
reaching that table already establishes that a server saw the order and declined
it — only the reason is unknown, and the reason changes the message rather than
what the caller must do.

The venue's own code is preserved as `error.code` and its comment as
`error.reason`, so a MetaTrader 5-specific diagnosis is still possible after the
classification has deliberately thrown the distinction away.

Two mappings are worth stating because they are judgement calls:

- `SERVER_DISABLES_AT` and `CLIENT_DISABLES_AT` classify as
  `BrokerAuthenticationError`, not as connection faults. Retrying cannot enable
  algorithmic trading; a human has to. This matches the existing treatment of
  `RES_E_AUTO_TRADING_DISABLED`.
- **No retcode maps to `BrokerOrderNotFoundError`.** MetaTrader 5 has none that
  means "no such order" — `INVALID_ORDER` (10035) means the order *type* is
  prohibited, which is a rejection. An adapter learns that an order is missing
  from an empty `orders_get`, so claiming a retcode for it would be a
  correspondence the vendor does not support.

## Future work

| Task | What it changes here |
| --- | --- |
| *(unscheduled)* — retry and reconnection policy in `BaseBrokerAdapter` | Would arrive the way locking did in ATLAS-TASK-0008: written once in the base and inherited here unnamed. Nothing retries anything today, and a dropped session is the supervisor's problem |
| *(unscheduled)* — trading | `order_send` behind the four trading methods: filling mode per instrument, a deviation policy, and reading deals back to report the price a fill actually got |
| *(unscheduled)* — streaming | A polling loop behind `subscribe_ticks` and `subscribe_candles`, or a decision that this venue does not stream |
| *(unscheduled)* — session schedules | Reading trading hours so `can_trade` can answer about the market rather than only about permission |
| *(unscheduled)* — server clock offset discovery | Currently configured. Recovering it by comparing a fresh tick's timestamp against the host clock during an active session is possible but needs care around weekends and stale quotes |
