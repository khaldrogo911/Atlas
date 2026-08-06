# `atlas.broker.mock` — the in-memory adapter

```python
from atlas.broker.mock import MockBrokerAdapter, MockVenue
```

## Purpose

Give the port a second implementation, and give tests something real to hold.

Two jobs, and the second one is the reason this package is in `packages/broker`
rather than in `tests/`.

**A port with one implementation is not a port.** Every decision in
`atlas.broker.adapter` could have been an accident of MetaTrader 5 until
something unrelated satisfied the same contract. This does. The places where it
satisfies the contract *better* than the terminal are where that shows:
`server_time` returns a clock, `subscribe_ticks` pushes, all four trading
methods trade, and `get_historical_data` can tell "the period contains no
trading" apart from "history does not reach back that far". Seven methods that
raise `NotImplementedError` in `atlas.broker.mt5` work here, which is the
evidence the contract was designed against a specification rather than around a
vendor.

**Tests must not mock `BrokerAdapter`.** The broker README forbids it, because a
mock agrees with whatever the test asserts — including the wrong thing — and a
suite built on one keeps passing on the day the real adapter's behaviour
changes underneath it. This class is bound by the same conformance tests as
every other adapter (`tests/unit/broker/test_adapter_conformance.py`), so a test
that passes against it has been checked against the contract rather than against
itself.

It is importable from a shipped package for the same reason: consumers of
`atlas.broker` in other packages test against it too, and a fixture that lives
in one package's test tree is not available to another's.

## Architecture

Two modules, and the split between them is the load-bearing decision.

```
venue.py    the broker: state, and what a broker does with it   → models + exceptions
   ↓
adapter.py  the BrokerAdapter implementation                    → venue + port
```

| Module | Holds | Deliberately does not hold |
| --- | --- | --- |
| `venue.py` | `MockVenue`: the clock, the instruments, the quotes and bars, the order book, positions, fills, subscriptions, the account, and the scheduled-failure queue | Any notion of a session, any `BrokerError`, any opinion about what the port promises |
| `adapter.py` | `MockBrokerAdapter`: session state, code resolution, argument validation, and which `BrokerError` a venue condition amounts to | Any state a broker would own — no order, no quote, no position is stored here |

Because the adapter stores nothing, a test asserting through `adapter.venue` and
a test asserting through the port's own read methods are **two independent
readings that can disagree**. That is what makes them worth writing. A design
where the adapter cached what it had returned would make the second reading a
restatement of the first.

`MockVenue` raises `ValueError`, never a `BrokerError`. Filling an order that is
already filled, or closing more than a position holds, is a fault in the *test*
rather than a condition the port describes, and the two should not be caught by
the same `except` clause.

## Determinism

Nothing here reads the host clock and nothing here is random.

- The venue owns its clock. It starts at `DEFAULT_START` (2020-01-01 UTC) and
  moves only when a test calls `set_time` or `advance`.
- Identifiers are sequential from 1 per kind: `order-1`, `position-1`,
  `execution-1`, `tick-sub-1`, `candle-sub-1`. The same sequence of calls
  produces the same identifiers on every run and on every machine.
- No spread is invented, no slippage is applied, no latency is simulated.
  `latency()` returns the number on the venue's `latency_ms` dial.

A test written against this adapter cannot pass in the morning and fail at a
period boundary in the evening, and a failure reproduces from the same inputs.

## Simulation boundary

**This adapter fills a market order at the quote a test published, and nothing
else happens on its own.** ADR-0006 records the decision; this is the list.

| Not simulated | Why |
| --- | --- |
| **A resting order filling because a price reached it** | Needs a rule for which side of the spread triggers it, what a gap does to the fill price, and whether the touch is the trade. Each is a choice a backtest engine makes deliberately; making it here silently makes this package the authority on it |
| **Revaluation of an open position** | `profit` stays at zero and `current_price` stays at the entry. Converting a move into the deposit currency needs a cross rate the venue does not have, and a wrong one is worse than an obvious zero |
| **The account responding to trading** | Balance, equity, margin and free margin are whatever a test set. A trade does not move them |
| **Partial fills** | `Order` carries no filled-quantity field, so a `PARTIALLY_FILLED` order would tell a caller that some unknowable amount had traded. Fill twice against two orders instead |
| **Commission and swap** | Reported as zero, which is the truth about this venue rather than a placeholder for a number it declines to compute |
| **Bar close times** | A test supplies whole `Candle` models; nothing is derived from a tick stream |

Each of these fails loudly in the one place where silence would be dangerous:
`stop_loss` and `take_profit` are **refused** with
`BrokerUnsupportedOperationError` rather than accepted and ignored, on
`place_order` and on `modify_order` alike. `Position` has nowhere to report a
protective level, so an accepted stop would be invisible for exactly as long as
the position is open — the silent no-op the port's README forbids.

The venue offers the primitives instead. A test that wants a resting order to
fill calls `venue.fill(order_id, price)` and names the price. A test that wants
a position marked to market calls `venue.revalue(...)`. Both are explicit, both
are in the test that depends on them, and neither pretends to be a market.

## Driving the venue

The port is what the code under test sees; `MockVenue` is what the test itself
drives. The methods a test reaches for:

| Concern | Methods |
| --- | --- |
| Clock | `now`, `set_time`, `advance` |
| Instruments | `add_symbol`, `symbol`, `symbols` |
| Market data | `publish_tick`, `quote`, `publish_candle`, `candles` |
| Orders and fills | `submit`, `fill`, `close`, `cancel`, `amend`, `store_order`, `order`, `orders`, `position`, `positions`, `executions` |
| Revaluation | `revalue` |
| Account | `account`, `set_account` |
| Subscriptions | `subscription_ids`, `close_subscription`, `handler_failures` |
| Fault injection | `schedule_failure`, `scheduled_failures` |

`add_symbol` on a code the venue already holds **replaces** it, which is how a
test changes dealing terms — a trade mode, a volume step — mid-test without
building a second venue.

Two adapters constructed against the same venue share its state and not each
other's sessions. That is the shape a multi-strategy test needs, and it is
tested.

### Fault injection

`schedule_failure(operation, error)` queues a `BrokerError` against a port
method by name; the next call to that method raises it and the queue moves on.
It is how a caller's error handling is tested without breaking the venue.

Two guards make it a contract rather than a string lookup:

- The operation must be a `BrokerAdapter` method. `venue.schedule_failure("get_quote", ...)`
  raises `ValueError` rather than queueing a failure that can never fire.
- The operation must be one the port permits to raise. `disconnect`, `health`,
  `is_connected`, `unsubscribe_ticks` and `unsubscribe_candles` are refused,
  because the port requires them to succeed.

A scheduled failure is consumed only when the call actually reaches the venue. A
guarded method called without a session raises `BrokerNotConnectedError` and
**leaves the failure queued** — the session check comes first, and a queued
failure that silently vanished would make the next assertion in the test wrong.

## Errors

Every failure that leaves `adapter.py` is an `atlas.broker.exceptions` type or a
`ValueError`. This package defines no exception classes of its own.

| Condition | Raised |
| --- | --- |
| Any guarded method without a session | `BrokerNotConnectedError` |
| Unknown instrument code | `BrokerSymbolNotFoundError` |
| Known instrument, no quote or no bars | `BrokerDataUnavailableError` |
| Requested period starts before the history does | `BrokerDataUnavailableError` |
| Unknown or already-terminal order | `BrokerOrderNotFoundError` / `BrokerOrderRejectedError` |
| Unknown position | `BrokerPositionNotFoundError` |
| Trade mode, account permission, volume bounds or step, missing quote | `BrokerOrderRejectedError` |
| Order larger than free margin | `BrokerInsufficientMarginError` |
| An attached `stop_loss` or `take_profit` | `BrokerUnsupportedOperationError` |
| A malformed argument — count below 1, naive datetime, end not after start, empty subscription | `ValueError` |

`ValueError` is deliberate for the last row and is raised **before** the session
is checked. An argument that is wrong is wrong whether or not a broker is
reachable, and reporting "not connected" for it would send the caller looking in
the wrong place.

Margin is `volume * contract_size * price / leverage`, evaluated at the ask for a
buy and the bid for a sell. It is stated here because a test asserting on a
required margin is asserting on this formula, and the formula is a simplification
— no per-instrument margin rate, no tiering, no hedged-position netting.

## Current limitations

- **Not thread safe**, in the same way and for the same reason the MetaTrader 5
  adapter is not. The port requires adapters to be callable from several
  threads; that locking belongs in `BaseBrokerAdapter` (ATLAS-TASK-0007),
  written once rather than repeated in each adapter. Two adapters now needing
  the same guarantee is the evidence it belongs in one place.
- **`can_trade` reports permission, not market hours.** The venue has no session
  schedule. This matches the MT5 adapter's limitation exactly, which is useful:
  a caller that gets it wrong gets it wrong identically in both.
- **No `close_by` and no netting.** Two buys are two positions. A venue that
  nets would answer differently, and the port does not say which it is.
- **Subscriptions deliver synchronously**, inside the `publish_tick` call, on
  the calling thread. A handler that throws is caught, recorded on
  `venue.handler_failures`, and does not stop the other subscribers — so a test
  can assert that one bad consumer does not take down a stream.

## Future work

| Task | What it changes here |
| --- | --- |
| **ATLAS-TASK-0007** — `BaseBrokerAdapter` | Takes over thread safety, and any retry or reconnection policy, from this adapter and the MT5 one |
| *(unscheduled)* — replay engine | A separate implementation that *does* trigger on price, built where a fill model is the subject rather than a side effect. This package's boundary is what keeps that decision available |
