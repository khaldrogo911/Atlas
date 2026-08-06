# ADR 0006 — The mock adapter simulates bookkeeping, not price

**Status:** Accepted
**Date:** 2026-08-06

## Context

ATLAS-TASK-0006 adds `MockBrokerAdapter`, the second implementation of
`atlas.broker.adapter.BrokerAdapter`. It exists for two reasons: to prove the
port is a contract rather than a description of MetaTrader 5, and to give tests
a real adapter to hold instead of a mocked interface that agrees with whatever
the test asserts.

Both reasons are served by a complete, honest implementation of the port's
*bookkeeping*: sessions, instruments, quotes, bars, an order book, positions,
fills, subscriptions, an account. None of that is in question.

What is in question is how far into **market behaviour** the package should go.
Once a venue holds a resting order and receives a quote, the obvious next step
is to fill the order when the quote reaches it. That step looks small and is
not:

- **Which side triggers.** Does a buy limit at 1.0900 fill when the bid touches
  it, or the ask? Both conventions exist and they differ by the spread on every
  trade.
- **What a gap does.** If the quote jumps from 1.0920 to 1.0880, does the order
  fill at its limit or at the gapped price? The answer is the difference between
  a backtest that is optimistic and one that is not.
- **Whether a touch is a trade.** At the limit price exactly, with no volume
  information, there is no fact of the matter.
- **Revaluation.** Marking a position to market requires converting a price move
  into the deposit currency, which needs a cross rate this venue does not have.
- **The account.** If a trade moves equity, it must also move margin and free
  margin, which means a margin model — per-instrument rates, tiering, netting of
  hedged positions.

Each answer is a legitimate modelling choice. None of them belongs to *this*
package, and every one of them, made here, silently becomes the authority on
behaviour nobody deliberately chose — including for the future replay and
backtest engines, which would then either inherit it or contradict it.

There is a further constraint from the domain models. `Position` has no
stop-loss or take-profit field, and `Order` has no filled-quantity field. A
`stop_loss` accepted on an order would be unreportable for exactly as long as
the position is open; a partially filled order would report a volume with no way
to say how much of it had traded.

## Decision

**`MockBrokerAdapter` fills a market order at the quote a test published, and
nothing else happens on its own.**

Specifically:

| Simulated | Not simulated |
| --- | --- |
| Market orders filling at the published bid or ask | A resting order filling because a price reached it |
| Positions opening, closing, and closing in part | Revaluation of an open position — `profit` stays zero |
| Orders resting, being amended, and being cancelled | The account responding to a trade |
| Margin checked against free margin at submission | Commission, swap, slippage, latency |
| Trade-mode and volume-bound rejections | Partial fills, netting, `close_by` |

Two rules make the boundary safe rather than merely narrow:

1. **Nothing is silently ignored.** An attached `stop_loss` or `take_profit` is
   refused with `BrokerUnsupportedOperationError` on both `place_order` and
   `modify_order`, rather than accepted and dropped. A refusal is visible in the
   first test that hits it; a silent no-op is discovered in production.
2. **The primitives are exposed instead.** `MockVenue.fill(order_id, price)`,
   `MockVenue.close(...)` and `MockVenue.revalue(...)` let a test produce any of
   the outcomes above by naming the price it wants. The choice moves into the
   test that depends on it, where it is visible and local.

The venue is also **deterministic by construction**: it owns its clock (starting
at 2020-01-01 UTC and moving only when asked), issues sequential identifiers
from 1, and contains no randomness. Nothing in it reads the host clock.

`MockVenue` signals misuse with `ValueError` and never with a `BrokerError`.
Filling an already-filled order is a fault in the test; a `BrokerError` is a
condition the port describes to a caller. Keeping them in different exception
spaces keeps a test's own bug from being caught by the error handling it is
testing.

## Consequences

- The port now has two implementations, and the seven methods that MetaTrader 5
  cannot honour — the four trading methods, both subscribe methods, and
  `server_time` — are all satisfied here. The contract is demonstrably not
  shaped around one vendor.
- A test that wants a resting order to fill must say at what price. This is more
  typing and it is the point: the fill assumption is stated in the test rather
  than inherited from a package that guessed.
- Tests are reproducible across machines and across runs. A failure reproduces
  from the same inputs, and no test can pass or fail according to the wall
  clock.
- The package is shipped in `packages/broker`, not in `tests/`, so consumers of
  `atlas.broker` in other packages can test against it. It is exported from
  `atlas.broker.mock`, never from `atlas.broker`, so business logic still cannot
  discover which adapter it holds.
- A future replay or backtest engine will need a fill model. It gets to choose
  one deliberately, on its own record, without contradicting or inheriting a
  choice smuggled in here.
- The account being a fixture rather than a ledger means a test asserting on
  margin after a trade is asserting on what it set, not on what trading did.
  That is a real limitation, and it is recorded in the package README rather
  than worked around.

## Alternatives considered

**A full simulation: trigger resting orders, revalue positions, run an account
ledger.** Rejected. It answers five modelling questions that belong to a
backtest engine, makes this package the de facto specification for all of them,
and does so in a package whose stated job is to prove a *contract*. The bugs it
would produce are the worst kind: a strategy passing its tests because the mock's
fill convention is generous.

**Accept `stop_loss` and `take_profit` and ignore them.** Rejected on the
strength of the port's own rule against silent no-ops. `Position` cannot report
a protective level, so acceptance would hide the gap for precisely the interval
during which it matters.

**Model partial fills.** Rejected because `Order` carries no filled quantity. A
`PARTIALLY_FILLED` status with no way to say how much filled tells a caller less
than nothing. Two orders filled separately expresses the same scenario honestly.

**Put the package under `tests/`.** Rejected: a fixture in one package's test
tree is unavailable to every other package, and the second implementation of the
port is a deliverable of the system rather than a detail of its test suite.

**Make `MockVenue` raise `BrokerError` for misuse.** Rejected. It would let a
test's own bug be swallowed by the `except BrokerError` branch the test was
written to exercise.
