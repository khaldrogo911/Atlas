# `atlas.broker` — the broker port

```python
from atlas.broker import BrokerAdapter, OrderRequest, SupportsMarketData
```

This package defines **one interface** and the vocabulary it speaks. It contains
no venue integration, no networking, no retries and no caching. Every concrete
broker lives behind it.

| File | Holds |
| --- | --- |
| `adapter.py` | `BrokerAdapter` — 31 abstract methods, the whole contract |
| `protocols.py` | Five capability protocols a consumer can depend on individually |
| `types.py` | Identifier aliases, handler signatures, `OrderRequest`, `BrokerVersion`, `UNSET` |
| `models/` | The domain models every method returns — see [`models/README.md`](models/README.md) |

## Why an interface exists

Atlas will connect to more than one venue, and not at the same time by choice:
a strategy is developed against a replay engine, validated against a simulator,
paper traded against a demo server, and run against a live one. Those are four
different implementations of the same idea, and the strategy must be **the same
code** in all four. If it is not, then what was validated is not what trades.

A venue's own SDK cannot serve that role. MetaTrader 5 returns named tuples
with `bid`, `ask` and an integer `time`; FIX returns tag/value messages; OANDA
returns JSON with string prices; Interactive Brokers returns callbacks on a
socket thread. Each has its own error codes, its own idea of what a "lot" is,
its own clock and its own notion of an order ticket. Written against any one of
them directly, business logic absorbs all of it, and swapping the venue means
rewriting the logic — at which point the second venue never happens.

So the dependency is inverted. `BrokerAdapter` states what Atlas needs from a
venue; the venue's peculiarities are the implementer's problem. Everything the
interface hands back is an `atlas.broker.models` type with a `Decimal` price and
a UTC timestamp, whatever the venue actually sent.

## Why implementations remain hidden

Nothing outside this package should be able to tell which adapter is loaded.

That is not tidiness — it is the only thing that makes the four environments
above interchangeable. The moment one module does `if isinstance(broker,
MT5Adapter)`, or reads a field only MT5 populates, or catches an MT5 exception,
the substitution stops working and the validation story collapses with it.

Three rules keep it true, and each is enforced by a test rather than by
convention:

1. **Return types are domain models.** Never a dict, never `Any`, never a
   vendor object. A `dict` return type is how a typed contract quietly becomes
   a bag of strings whose keys differ per venue.
2. **The port imports nothing but `atlas.broker`.** No SDK, no HTTP client, no
   socket, no database. `test_adapter_contract.py` walks the AST of every
   module here and fails on anything outside a permitted set.
3. **Errors are the port's own.** An implementation translates whatever the
   venue raised into the `BrokerError` hierarchy documented in `adapter.py`.
   Callers handle Atlas exceptions; a venue error code never reaches them.

## Why business logic depends only on `BrokerAdapter`

A strategy, a risk check and an execution router should each be constructible
with a broker they cannot inspect. Concretely, this is the shape:

```python
def size_position(broker: BrokerAdapter, symbol: SymbolName, risk: Decimal) -> Volume:
    account = broker.get_account()
    contract = broker.get_symbol(symbol)
    ...
```

That function is testable without a terminal, a login or a network, and it
behaves identically in backtest and in production because there is only one
version of it.

Most callers need less than the whole port, and `protocols.py` lets them say
so. A component that only reads bars asks for `SupportsMarketData`; it then
*cannot* place an order, because the type it holds has no such method, and a
seven-method stub is enough to test it. The five capabilities are:

| Protocol | Covers |
| --- | --- |
| `SupportsConnection` | `connect`, `disconnect`, `reconnect`, `is_connected`, `health` |
| `SupportsMarketData` | symbols, ticks, candles, history — **pull only** |
| `SupportsStreaming` | tick and candle subscriptions |
| `SupportsTrading` | `place_order`, `modify_order`, `cancel_order`, `close_position` |
| `SupportsDiagnostics` | `ping`, `latency`, `server_time`, `version` |

`SupportsMarketData` deliberately excludes subscriptions. A replay engine and a
REST-only venue can serve every pull method and stream nothing; folding
streaming in would make the protocol unsatisfiable for exactly the data sources
most worth testing against.

Conformance is **structural**. Nothing inherits from these protocols — a
third-party adapter satisfies them by having the methods, without importing
Atlas at all.

Account and risk methods belong to no protocol. There is no consumer that wants
account state without a session, so factoring them out would add a name without
removing a dependency. If one appears, adding `SupportsAccount` is additive and
breaks nothing.

## How a future broker plugs in

Implement the interface. That is the entire integration surface.

```python
class FixAdapter(BrokerAdapter):
    def connect(self) -> Connection: ...
    # ... the remaining 30 methods
```

The abstract base does the enforcement: a subclass that misses a method cannot
be instantiated, so an incomplete adapter fails at construction rather than at
the first unusual code path in live trading.

What an implementer owns:

- **Translation.** Venue types in, `atlas.broker.models` out. Round every price
  through `Decimal` — never `float` — and normalise every timestamp to UTC.
- **Error mapping.** Venue failures become the documented `BrokerError`
  hierarchy. An unmapped error reaching a caller is a bug in the adapter.
- **Transport.** Sockets, sessions, heartbeats, rate limits, thread safety.
  None of it is visible above the port.
- **Capability refusal.** A venue that cannot do something raises
  `BrokerUnsupportedOperationError`. It does not return `None`, and it does not
  silently no-op — a subscription that quietly never fires is indistinguishable
  from a market that never moves.

What an implementer does *not* own, and must not change: the interface. If
adding a venue requires editing `adapter.py`, the abstraction has failed for
every venue already behind it. The correct response is a new method that all
adapters can implement, added deliberately, or a capability protocol — not a
venue-shaped parameter.

Shared machinery that most adapters want — reconnect loops, retry policy,
connection-state bookkeeping — belongs in `BaseBrokerAdapter` (ATLAS-TASK-0007),
a concrete class *between* the port and an implementation. It is not in the port
because a replay engine has nothing to reconnect to and should not inherit the
concept.

## Design decisions worth knowing

**The interface is synchronous.** Strategy execution must be deterministic and
reproducible: the same inputs in the same order must produce the same trades,
and an `async` surface makes the interleaving a property of the event loop
rather than of the strategy. Adapters are free to use threads or `asyncio`
internally — several must — but they present a blocking call.

**The interface publishes no events.** `subscribe_ticks` and `subscribe_candles`
take a plain callback and return a `SubscriptionID`. An implementation may
publish onto a message bus, and higher layers may build one, but a port that
required an event bus would make the bus a dependency of every adapter,
including the simulator.

Unsubscribing takes the **handle**, not the symbol. Two components may
independently stream the same instrument, and unsubscribing by symbol would
silently cut off the other one.

**`place_order` takes an `OrderRequest`, not an `Order`.** An `Order` carries a
ticket, a status and timestamps that only the venue can assign; requiring a
caller to invent them in order to ask for a fill would make every one of those
fields a lie. `OrderRequest` applies the same structural rules `Order` does, so
a request that validates here is not rejected on arrival.

It is also what makes the order path extensible without a breaking change.
Time in force, expiry and a client-supplied idempotency key are all missing
today, and every one of them can arrive later as an optional field with a
default — no signature moves, and no existing adapter stops compiling. A long
explicit parameter list on `place_order` would have made each of those an
interface change.

**`modify_order` uses a three-state sentinel.** Amending needs *leave as is*,
*set to this value*, and *remove entirely*; `None` expresses only two of those.
`UNSET` is a single-member `Enum` rather than an `object()` because type
checkers narrow `is UNSET` correctly.

**`get_candle` defaults to the last closed bar.** `include_forming=False` is the
default and is keyword-only. A backtest that reads the forming bar sees the
future; making that the quiet default would put look-ahead bias one careless
call away, so it must be asked for by name.

**The identifier aliases are transparent, not opaque.** `type OrderID =
Identifier` resolves to `str` for a type checker, so `cancel_order(order.order_id)`
needs no wrapping, and the same alias used as a pydantic field keeps the
validation rules of the primitive it names. The cost is real: nothing stops a
`PositionID` being passed where an `OrderID` was meant. Making that a checked
error needs `typing.NewType`, which the domain models in `models/` would have to
adopt in the same change — a change to their public contract, and therefore a
decision for its own ADR rather than a detail of this one.

## Testing against the port

Do not mock `BrokerAdapter`. A mock agrees with whatever the test asserts,
including the wrong thing. Use the mock adapter (ATLAS-TASK-0006), which is a
real implementation of the same interface and is bound by the same contract
tests as every other adapter.
