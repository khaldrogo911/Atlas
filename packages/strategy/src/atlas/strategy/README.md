# `atlas.strategy`

The package that proposes, and may do nothing else.

```python
from atlas.strategy import Strategy
```

---

## The boundary

```
observation ──▶ Strategy.propose ──▶ TradeIntent | None ──▶ atlas.risk ──▶ RiskVerdict ──▶ atlas.execution
```

A strategy proposes; risk decides; execution places. `atlas.risk` defined the
vocabulary of that sentence in ATLAS-TASK-0011; this package defines its
subject. A `Strategy` is shown an observation and answers with a `TradeIntent`
or with `None`, and that is the whole of its authority — it cannot size against
an account, cannot approve itself, and cannot reach a venue.

**An intent is a recommendation, not an instruction.** Returning one asserts
nothing about whether the trade is affordable, permitted or wise. Those are
`atlas.risk`'s questions, asked against state a strategy cannot see, and the
only thing that may licence an order is a `RiskVerdict` whose status is
`APPROVED`.

*[ADR-0010](../../../../../docs/adr/0010-the-risk-boundary-is-a-verdict-on-an-intent.md)*

---

## `Strategy` — the contract

```python
@runtime_checkable
class Strategy[InputT](Protocol):
    def propose(self, observation: InputT, /) -> TradeIntent | None: ...
```

One method. Three decisions in it are load bearing.

### It is a protocol, not a base class

Structural typing, for the reason `atlas.broker.protocols` gives for the
capability protocols: nothing has to inherit from these. A strategy is a
*behaviour*, and requiring inheritance would mean a research notebook, a replay
harness and a production component could not all be the same thing unless they
all imported the same base class.

It would also hand this package a concrete class to put shared behaviour in, and
the first thing that lands in one is a lifecycle. The lifecycle is not this
task's, and the responsibilities table in `docs/architecture/overview.md` does
not let a contract module quietly acquire it.

`@runtime_checkable` makes `isinstance(obj, Strategy)` legal, which checks that
`propose` exists and nothing about its signature. That is enough for a registry
to refuse an obvious mistake at wiring time; it is not a substitute for the type
checker, and no code here treats it as one.

### The input is a type parameter this package does not name

A strategy is shown *something*. What that something is — a bar, a tick, a
feature vector, a regime label — belongs to `atlas.market`, `atlas.features` and
`atlas.regime`, which are all still empty stubs. Naming it here would fix their
shape before they exist, from the package with the least standing to do it.

So `InputT` is whatever the component wiring a strategy up decides it is. The
parameter appears only as an argument, which makes the protocol contravariant in
it: a strategy willing to look at `object` satisfies `Strategy[Candle]`, and not
the other way round. That is the correct direction — a more accommodating
strategy is substitutable for a fussier one.

`observation` is positional-only. A caller holding a `Strategy` has no business
knowing what one implementation calls its argument, and without the `/` the
protocol would silently require every implementation to spell the parameter the
same way.

### `None` is the answer to "no opinion"

Most observations do not warrant a trade, and a strategy that trades one session
in five says so four times as often as it says anything else. `None` is an
ordinary answer and not an error.

The alternative — an empty intent, or a sentinel meaning "ignore me" — puts a
value into the pipeline that *looks* tradeable, and the first consumer that
forgets to check it sends it to risk. There is no such object here to forget
about.

---

## The four names taken from `atlas.broker`

A `TradeIntent` is stated in `SymbolName`, `OrderSide`, `Price` and `Volume`, so
anything that builds one names those four. A strategy module may import exactly
those, from `atlas.broker` or `atlas.broker.models`, and nothing else.

**Forbidden, and each for its own reason:** `BrokerAdapter` is a route to a
venue. `OrderRequest`, `OrderType` and `OrderStatus` are execution's vocabulary
— an intent that named `LIMIT` would be instructing rather than recommending.
`place_order`, `modify_order`, `cancel_order` and `close_position` are the acts
themselves.

ADR-0010 anticipated this edge and accepted it in advance, under the heading
that a transitive type dependency is not a call path: "Strategy depends on the
vocabulary the port defines, not on the port — it still cannot obtain a
`BrokerAdapter`, cannot construct an `OrderRequest`, and has no route to place
anything."

In practice the dependency is *direct* rather than transitive, and the type
checker is what makes it so. `mypy` runs strict with `init_typed = True`, so
`TradeIntent(side="BUY")` is an error even though `OrderSide` is a `StrEnum` and
the string works perfectly at runtime. A strategy that constructs an intent and
passes CI must therefore name `OrderSide` itself. The reasoning ADR-0010
recorded is unchanged — vocabulary, not port — but the import is real, visible,
and enumerated rather than assumed.

The four names are **not** re-exported through `atlas.risk` to make the import
look shorter. A re-export would widen the risk package's surface in order to
disguise an edge that exists either way, and the honest version is the one a
reader can see.

`tests/unit/strategy/test_strategy_boundary.py` asserts all of this by walking
the AST of every module in this package rather than by trusting the paragraphs
above — permitted imports, forbidden imports, forbidden names, and that
`atlas.risk` still contains no import of `atlas.strategy`.

---

## `ConstantStrategy` — a reference implementation, not a strategy

```python
from atlas.strategy.reference import ConstantStrategy

ConstantStrategy().propose(anything)                       # None — abstains

ConstantStrategy.proposing(
    symbol="EURUSD", side=OrderSide.BUY, volume=Decimal("0.10")
).propose(anything)                                        # the same TradeIntent, always
```

An abstraction with no implementations is an abstraction nobody has tried.
`MockBrokerAdapter` exists for the same reason on the other side of the system:
the second implementation is what demonstrates a contract was designed against a
specification rather than around one caller.

`ConstantStrategy` is deliberately the least interesting implementation that can
be written. It answers with the intent it was constructed with, every time,
whatever it is shown. It reads no market data, performs no I/O, holds no clock,
draws no random number and calls no venue. Its output is a function of its
constructor arguments and of nothing else.

**That inertness is the design, not a limitation to be lifted later.** A
reference implementation that could see a price is one edit away from being a
trading strategy, and the edit is the kind nobody reviews closely because the
file already existed. `MockVenue` records the same hazard from the venue side —
simulated fills produce "a strategy that appears to make money" — and
[ADR-0006](../../../../../docs/adr/0006-mock-adapter-simulates-bookkeeping-not-price.md)
calls that the worst kind of wrong answer.

It makes no claim about profitability, has no edge, and must not be deployed or
extended into something that trades. A real strategy belongs to the task that
specifies it, with the inputs, the evidence and the review that implies.

It is **not** exported from `atlas.strategy` — the same reason
`MockBrokerAdapter` is absent from `atlas.broker`. A reference implementation
that appears in the package's public surface is one an unrelated caller can
reach for by accident.

The named constructor is why the package imports the broker primitives at all.
`proposing` builds the intent *in a strategy module*, which is the only way this
package exercises the permission it was granted; a reference implementation
handed a ready-made intent would import none of the four, and the import rule
would be asserting something about source that does not exist.

---

## What this package does not do yet

`atlas.strategy` holds the contract and none of the machinery. There is no
lifecycle, no registry, no engine, no scheduling and no event subscription;
those arrive with the tasks that implement them.

There is also no *real* strategy, and no data for one to look at. `atlas.market`,
`atlas.features` and `atlas.regime` are still empty stubs, so `InputT` has
nothing concrete to be, and `atlas.execution` is still a stub, so nothing
consumes a verdict. What exists today is the producing half of the boundary
ATLAS-TASK-0011 defined: a strategy can be written, type-checked and asserted
against, and it cannot reach past risk while doing it.
