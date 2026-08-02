# Broker Domain Models

The canonical vocabulary in which Project Atlas talks about accounts,
instruments, quotes, bars, orders, positions, fills and connectivity.

```python
from atlas.broker.models import Order, OrderSide, OrderStatus, OrderType
```

---

## Purpose

Everything above the broker boundary — strategy, risk, execution, research,
persistence, reporting — reads and writes these types and only these types. No
component outside `atlas.broker` should ever hold a value that came straight
off a venue API.

That gives Atlas four things:

| Guarantee | How |
| --- | --- |
| One meaning per concept | `Order` means the same thing in the risk engine, the backtester and the audit log |
| One place to change a rule | "prices are positive" is written once, in `primitives.py` |
| Substitutable venues | A second broker is a second adapter, not a second set of types |
| Testability without a venue | Every model can be constructed in a test with no network, no terminal, no credentials |

---

## Design philosophy

### Decimal, never float

Prices, volumes and money are `Decimal`. A five-digit FX quote such as
`1.16245` has no exact binary floating-point representation, and the error
compounds through position sizing, cost basis and P&L. Pydantic serialises
`Decimal` to a JSON **string**, so the exact value — including trailing zeros,
which carry the venue's precision — survives a round trip:

```python
>>> Tick.model_validate_json(tick.model_dump_json()).bid
Decimal('1.16240')
```

`latency_ms` is the one deliberate exception. It is a measurement with no
exact decimal value and no accounting consequence.

Non-finite decimals (`NaN`, `Infinity`) are rejected on **every** numeric
field, not only the bounded ones. A `NaN` profit propagates silently through
arithmetic and comparisons and surfaces as a decision made on nothing.

### Timezone-aware, normalised to UTC

Naive datetimes are rejected outright; aware ones are converted to UTC.
Brokers report times in server-local zones that shift twice a year, and a
naive timestamp crossing that boundary is a seasonal bug that appears in
March, disappears, and returns in October.

### Immutable

Every model sets `frozen=True`. Instances are hashable, safe to share between
components without defensive copying, and safe to hold in a cache. A state
change produces a new value:

```python
filled = Order.model_validate({**order.model_dump(), "status": OrderStatus.FILLED})
```

> **Do not use `model_copy(update=...)` for state transitions.** It writes the
> value straight into the new instance without validating it, so it will
> happily produce an `Order` whose `status` is a plain string or whose `price`
> is `None` on a `LIMIT` order. Round-trip through `model_validate` instead.
> A test pins this behaviour so the hazard cannot be forgotten.

### Closed to unknown fields

`extra="forbid"`. A misspelled field in an adapter becomes an immediate,
named error instead of an attribute that silently reads back as absent.

### Canonicalised codes

Symbol and currency codes are trimmed and uppercased on the way in. Case is a
broker-formatting detail, not information — one venue quotes `eurusd`, the
next `EURUSD` — and canonicalising here is what allows the rest of Atlas to
compare codes with `==` and use them as dictionary keys.

Opaque identifiers (`account_id`, `order_id`, `execution_id`, `position_id`)
are trimmed but **not** uppercased: at a venue that issues alphanumeric
tickets, changing the case could change which order you mean.

### Enums are strings whose value is their name

`OrderType.LIMIT.value == "LIMIT"`. Persisted records and bus messages stay
readable, reordering members later cannot silently reinterpret stored data,
and validation is exact — `"limit"` is rejected rather than quietly accepted.

### Structural validation only

The models refuse what is **malformed**. They do not refuse what is
**unwise**.

Enforced here, because the value is self-contradictory:

- an `ask` below the `bid`
- a bar whose `high` is not the highest of its four prices
- a `LIMIT` order with no limit price, or a `STOP_LIMIT` with no trigger
- `updated_at` before `created_at`, or `close_time` at or before `open_time`
- a `Symbol` whose `point` is not `10 ** -digits`
- a `Connection` whose `connected` flag contradicts its `state`
- a `margin_level` reported against zero margin — the ratio is *undefined*,
  not zero, and venues that send `0` here make every `margin_level < threshold`
  rule fire on a flat account

Deliberately **not** enforced here, because it requires state this layer
cannot see:

- whether a stop loss sits on the profitable side of the entry
- whether an order's volume is appropriate for the account
- whether a quote is too stale to act on
- whether a degraded connection should still be traded through

Those are risk and execution decisions. A model that made them would be a
policy engine wearing a data class's clothes, and the policy would be
unreachable from the place that owns it.

### Reported, not recomputed

`Account.equity` and `Position.profit` are recorded as the venue reported
them. Atlas does not re-derive them: doing so correctly needs the contract
size, the broker's own quote-to-deposit conversion rate at its own timestamp,
and the broker's rounding. Where Atlas would disagree with the broker's
arithmetic, the broker is right — it is the one settling the account.

---

## Relationship to `BrokerAdapter`

```
        strategy · risk · execution · research · persistence
                              │
                              │  reads and writes only these models
        ══════════════════════╪══════════════════════════════════════
                              │
                        BrokerAdapter                (ATLAS-TASK-0003)
                              │
             ┌────────────────┼────────────────┐
        MockBrokerAdapter   MT5Adapter    …future venues
          (TASK-0007)      (TASK-0011)
                              │
                    venue SDKs, sockets, terminals
```

The adapter's entire job is translation. It accepts whatever shape a venue
speaks — a `MqlTradeRequest`, a REST payload, a named tuple from a terminal —
and returns these models; it accepts these models and produces whatever the
venue requires. Validation happens at that boundary, once, on the way in.

This is what makes the direction of dependency the important part: **models
know nothing about adapters; adapters depend on models.** A new venue is a new
adapter and zero changes here. A change here is a change every adapter must
answer for — which is exactly the right cost, because it is a change to the
contract.

---

## Why these models are broker independent

Independence is a property of the code, not an intention, so it is enforced
mechanically. `tests/unit/broker/test_model_invariants.py` parses every module
in this package and asserts that its imports fall within:

```
__future__   datetime   decimal   enum   typing   pydantic   atlas.broker.models
```

Nothing else. No `MetaTrader5`, no HTTP client, no socket, no database driver,
no other Atlas package. The test names the offending file and import, and it
fails on a broker SDK imported "just for a type hint" — which is how this kind
of layering is normally lost.

The substantive independence is in the modelling itself:

- **No venue concepts leak in.** There is no `magic` number, no `MqlTick`, no
  terminal handle, no deal-vs-order-vs-position ticket taxonomy specific to one
  platform.
- **Fields are defined by what they mean, not by what one API returns.**
  `Symbol.spread` is documented as a moving snapshot rather than a term of the
  contract; `Tick.last` is optional because spot FX venues report no trades;
  `Candle.is_closed` is required, with no default, because whether a bar can
  still change is the single most consequential thing about it and no adapter
  should be able to leave it unstated.
- **Undefined is `None`, never a sentinel.** `margin_level`, `latency_ms` and
  `last_heartbeat` are `None` when unknown. Zero means zero.

---

## Files

| File | Contents |
| --- | --- |
| `primitives.py` | Constrained scalar types and the shared model config |
| `enums.py` | `OrderSide`, `OrderType`, `OrderStatus`, `PositionSide`, `ConnectionState`, `SymbolTradeMode`, `Timeframe` |
| `account.py` | `Account` |
| `symbol.py` | `Symbol` |
| `tick.py` | `Tick` |
| `candle.py` | `Candle` |
| `order.py` | `Order` |
| `position.py` | `Position` |
| `execution.py` | `Execution` |
| `connection.py` | `Connection` |

Import from the package (`atlas.broker.models`), not from its modules — the
module split is an implementation detail and the package is the contract.
