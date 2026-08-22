"""What the adapters must still do identically now that a base class exists.

`BaseBrokerAdapter` took over the session bookkeeping both adapters were
carrying separately. A refactor of that kind has exactly one failure mode worth
testing for: the two implementations stop agreeing about something they used to
agree about, and each one's own test suite keeps passing because each was only
ever compared against itself.

So the tests here are written the other way round. An adapter is not named; it
is *discovered*, by the same walk `test_adapter_conformance.py` uses, and put
through the same sequence as every other adapter. :data:`CASES` says how to
build each one, and :class:`TestTheRegistry` fails if a discovered adapter has
no entry — so a third implementation is held to this the moment it exists,
rather than the moment somebody remembers.

Three things are proved, in the order the task asks for them:

Session lifecycle
    Fresh, connected, measured, disconnected, reconnected. What ``health`` says
    at each stage, and that ``is_connected`` never disagrees with it.

Connection guards
    Every port method that has to refuse without a session, called on both
    adapters with no session. The interesting assertion is
    :meth:`TestTheTwoAdaptersAgree.test_they_agree_on_every_method_neither_defers`,
    which compares the two outcome maps directly instead of checking each
    against a transcribed expectation.

Conformance
    That reaching the port through an intermediate class leaves the adapters
    conforming — same signatures, nothing abstract left, and the two reads
    genuinely inherited rather than shadowed.

The expectation tables below are transcribed from observed behaviour and then
frozen. `test_the_method_stops_refusing_once_connected` is the control: a method
that refused unconditionally would satisfy every guard test here, and that test
is the one it would fail.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

import pytest
from pydantic import SecretStr

from atlas.broker.adapter import BrokerAdapter
from atlas.broker.base import BaseBrokerAdapter
from atlas.broker.exceptions import BrokerNotConnectedError
from atlas.broker.mock import MockBrokerAdapter, MockVenue
from atlas.broker.models import ConnectionState, OrderSide, OrderType, Timeframe
from atlas.broker.mt5.adapter import MT5BrokerAdapter
from atlas.broker.mt5.connection import MT5Config, MT5Session
from atlas.broker.types import OrderRequest
from tests.unit.broker.mt5.conftest import SERVER_OFFSET, FakeTerminal, as_terminal
from tests.unit.broker.test_adapter_conformance import ADAPTERS
from tests.unit.broker.test_adapter_contract import ALL_MANDATED, PINNED_SIGNATURES

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.unit

#: The five methods that drive the session rather than needing one. Excluded
#: from the call table below because calling them is how a state is reached.
LIFECYCLE: Final = ("connect", "disconnect", "reconnect", "is_connected", "health")

#: The three state hooks the base asks a subclass for.
STATE_HOOKS: Final = ("_session_broker", "_session_server", "_session_state")

#: The three lifecycle hooks the base calls with the session lock held. Their
#: existence is the reason no adapter writes a lock: the public method is the
#: base's, the venue-specific half is the adapter's.
LIFECYCLE_HOOKS: Final = ("_connect", "_disconnect", "_reconnect")

#: Everything the base asks a subclass for.
HOOKS: Final = STATE_HOOKS + LIFECYCLE_HOOKS

#: A start far enough back that the mock venue's clock — which begins at
#: 2020-01-01 — is after it. A period ending before it began is rejected as a
#: bad argument *before* the session is checked, which would make
#: ``get_historical_data`` look unguarded.
HISTORY_START: Final = datetime(2019, 1, 1, tzinfo=UTC)

#: A well-formed order request. Never reaches a venue in this module: every call
#: below is made either without a session or against a terminal that refuses.
REQUEST: Final = OrderRequest(
    symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=Decimal("0.10")
)

#: How to call every port method that is not lifecycle, with arguments that are
#: valid in themselves — so that what comes back is the adapter's answer about
#: the *session* rather than about the arguments.
CALLS: Final[dict[str, Callable[[BrokerAdapter], object]]] = {
    "get_symbols": lambda adapter: adapter.get_symbols(),
    "get_symbol": lambda adapter: adapter.get_symbol("EURUSD"),
    "get_tick": lambda adapter: adapter.get_tick("EURUSD"),
    "get_ticks": lambda adapter: adapter.get_ticks(["EURUSD"]),
    "get_candle": lambda adapter: adapter.get_candle("EURUSD", Timeframe.M1),
    "get_candles": lambda adapter: adapter.get_candles("EURUSD", Timeframe.M1, 1),
    "get_historical_data": lambda adapter: adapter.get_historical_data(
        "EURUSD", Timeframe.M1, HISTORY_START
    ),
    "subscribe_ticks": lambda adapter: adapter.subscribe_ticks(["EURUSD"], lambda _tick: None),
    "unsubscribe_ticks": lambda adapter: adapter.unsubscribe_ticks("1"),
    "subscribe_candles": lambda adapter: adapter.subscribe_candles(
        ["EURUSD"], Timeframe.M1, lambda _candle: None
    ),
    "unsubscribe_candles": lambda adapter: adapter.unsubscribe_candles("1"),
    "place_order": lambda adapter: adapter.place_order(REQUEST),
    "modify_order": lambda adapter: adapter.modify_order("1", price=Decimal("1.10000")),
    "cancel_order": lambda adapter: adapter.cancel_order("1"),
    "close_position": lambda adapter: adapter.close_position("1"),
    "get_account": lambda adapter: adapter.get_account(),
    "get_positions": lambda adapter: adapter.get_positions(),
    "get_orders": lambda adapter: adapter.get_orders(),
    "get_open_positions": lambda adapter: adapter.get_open_positions(),
    "margin_required": lambda adapter: adapter.margin_required(
        "EURUSD", OrderSide.BUY, Decimal("0.10")
    ),
    "margin_available": lambda adapter: adapter.margin_available(),
    "can_trade": lambda adapter: adapter.can_trade("EURUSD"),
    "ping": lambda adapter: adapter.ping(),
    "latency": lambda adapter: adapter.latency(),
    "server_time": lambda adapter: adapter.server_time(),
    "version": lambda adapter: adapter.version(),
}

#: Refused with :class:`~atlas.broker.exceptions.BrokerNotConnectedError` by
#: every adapter when there is no session. The behaviour under test.
GUARDED: Final = (
    "can_trade",
    "get_account",
    "get_candle",
    "get_candles",
    "get_historical_data",
    "get_open_positions",
    "get_orders",
    "get_positions",
    "get_symbol",
    "get_symbols",
    "get_tick",
    "get_ticks",
    "latency",
    "margin_available",
    "margin_required",
    "place_order",
    "version",
)

#: The port forbids these from raising at all. A cleanup path cannot know what
#: is still live, and ``ping`` reporting failure *is* its answer — an exception
#: would make "the venue went away" the caller's problem to catch.
NEVER_REFUSES: Final = ("ping", "unsubscribe_candles", "unsubscribe_ticks")

#: The seven the MetaTrader 5 adapter cannot honour. It names the missing
#: capability rather than the session, and does so before looking at the
#: session — which is correct: a caller who connects first still gets nothing.
#: The mock implements all seven and guards them like anything else.
MT5_DEFERRED: Final = (
    "cancel_order",
    "close_position",
    "modify_order",
    "server_time",
    "subscribe_candles",
    "subscribe_ticks",
)

#: What :func:`_outcome` reports when a call returned instead of raising.
RETURNED: Final = "returned"


# --- Building an adapter of each kind ----------------------------------------


@dataclass(frozen=True)
class AdapterCase:
    """One implementation of the port, and how to get a disconnected instance.

    Attributes:
        adapter_type: The class, for the conformance assertions.
        build: Returns a fresh instance that has never connected. A factory
            rather than a fixture because most tests below need two or three
            independent instances, each in a different state.
        broker: What the fixture's brokerage is called once a session exists.
            Transcribed so that the snapshot's two identity fields can be told
            apart — asserting only that both are non-empty passes just as
            happily when they are swapped.
        server: What the fixture's trade server is called.
    """

    adapter_type: type[BaseBrokerAdapter]
    build: Callable[[], BaseBrokerAdapter]
    broker: str
    server: str


def _mock() -> MockBrokerAdapter:
    """Build a disconnected mock adapter.

    Returns:
        An adapter bound to a venue of its own, offering no instruments. The
        empty venue is deliberate: a guarded method must refuse before it
        discovers there is nothing to answer with.
    """
    return MockBrokerAdapter(MockVenue())


def _mt5() -> MT5BrokerAdapter:
    """Build a disconnected MetaTrader 5 adapter.

    Returns:
        An adapter wired to the fake terminal the MT5 tests use, so nothing here
        imports the vendor package or starts a terminal.
    """
    config = MT5Config(
        login=9001234,
        password=SecretStr("not-a-real-password"),
        server="Example-Demo",
        terminal_path=Path("C:/Program Files/Example/terminal64.exe"),
        server_utc_offset=SERVER_OFFSET,
        deviation_points=20,
        filling_mode_by_instrument={},
    )
    return MT5BrokerAdapter(
        config, session=MT5Session(config, terminal_factory=lambda: as_terminal(FakeTerminal()))
    )


CASES: Final = (
    AdapterCase(MockBrokerAdapter, _mock, broker="Mock Broker", server="mock-server"),
    AdapterCase(MT5BrokerAdapter, _mt5, broker="Example Brokerage", server="Example-Demo"),
)


def _case_id(case: AdapterCase) -> str:
    """Name a parametrised case after its adapter.

    Args:
        case: The case.

    Returns:
        The adapter class's name.
    """
    return case.adapter_type.__name__


def _connected(case: AdapterCase) -> BaseBrokerAdapter:
    """Build an adapter and bring its session up.

    Args:
        case: Which adapter to build.

    Returns:
        The connected adapter.
    """
    adapter = case.build()
    adapter.connect()
    return adapter


def _outcome(adapter: BrokerAdapter, method: str) -> str:
    """Call a port method and report what happened, as a name.

    Args:
        adapter: The adapter to call it on.
        method: Which method, keyed into :data:`CALLS`.

    Returns:
        The name of the exception type it raised, or :data:`RETURNED`. A name
        rather than the exception itself, so that two adapters' behaviour can be
        compared with one equality assertion.
    """
    try:
        CALLS[method](adapter)
    except Exception as raised:
        return type(raised).__name__
    return RETURNED


def _probe(state: ConnectionState) -> BaseBrokerAdapter:
    """Build the smallest possible subclass of the base, in a chosen state.

    Args:
        state: What its ``_session_state`` hook reports.

    Returns:
        An instance. Every abstract member is a stub, including the three
        lifecycle hooks; only the three state hooks answer, which is what allows
        the base's own behaviour to be tested without a venue and in states no
        adapter fixture can reach.
    """
    members: dict[str, object] = dict.fromkeys(
        BaseBrokerAdapter.__abstractmethods__, lambda *_args, **_kwargs: None
    )
    members["_session_state"] = property(lambda _self: state)
    members["_session_broker"] = property(lambda _self: "Probe Brokerage")
    members["_session_server"] = property(lambda _self: "Probe-Demo")
    return cast("BaseBrokerAdapter", type("ProbeAdapter", (BaseBrokerAdapter,), members)())


# --- The base class itself ----------------------------------------------------


class TestTheBaseIsAnAbstractLayer:
    def test_it_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            BaseBrokerAdapter()  # type: ignore[abstract]

    def test_conformance_discovery_still_skips_it(self) -> None:
        # The discovery in test_adapter_conformance.py keeps only concrete
        # subclasses. An intermediate class that became instantiable would join
        # the adapters there and be held to behaviour it has none of.
        assert inspect.isabstract(BaseBrokerAdapter)
        assert BaseBrokerAdapter not in ADAPTERS

    def test_it_implements_exactly_the_session_lifecycle(self) -> None:
        # "Minimal" as an assertion rather than a claim in a docstring. The base
        # now answers all five lifecycle methods and nothing else; anything else
        # moved into it has to be added here deliberately.
        implemented = BrokerAdapter.__abstractmethods__ - BaseBrokerAdapter.__abstractmethods__

        assert implemented == set(LIFECYCLE)

    def test_it_asks_a_subclass_for_exactly_six_things(self) -> None:
        added = BaseBrokerAdapter.__abstractmethods__ - BrokerAdapter.__abstractmethods__

        assert added == set(HOOKS)

    def test_the_lifecycle_hooks_are_private_so_the_port_surface_is_unchanged(self) -> None:
        # The base took over three public methods and delegates to three new
        # ones. Public replacements would have widened the interface every
        # caller depends on, which the task forbids.
        assert all(hook.startswith("_") for hook in LIFECYCLE_HOOKS)

    @pytest.mark.parametrize("hook", HOOKS)
    def test_a_subclass_that_omits_a_hook_cannot_be_built(self, hook: str) -> None:
        members = dict.fromkeys(
            BaseBrokerAdapter.__abstractmethods__ - {hook}, lambda *_args, **_kwargs: None
        )
        partial = type("PartialAdapter", (BaseBrokerAdapter,), members)

        assert inspect.isabstract(partial)

    def test_the_hooks_are_the_only_reason_the_probe_is_concrete(self) -> None:
        # Guards every _probe-based test below: if the stub dictionary stopped
        # covering the port, the probe would be abstract and those tests would
        # fail for a reason that has nothing to do with what they assert.
        assert type(_probe(ConnectionState.CONNECTED)).__abstractmethods__ == frozenset()


class TestTheBaseHoldsTheSessionReadings:
    def test_a_new_instance_has_measured_nothing(self) -> None:
        # None rather than zero: a latency of 0.0 claims a measurement was taken
        # and came back instant, which is a different statement.
        probe = _probe(ConnectionState.DISCONNECTED)

        assert probe._last_latency_ms is None
        assert probe._last_heartbeat is None

    def test_clearing_the_readings_forgets_both(self) -> None:
        probe = _probe(ConnectionState.CONNECTED)
        probe._last_latency_ms = 12.5
        probe._last_heartbeat = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)

        probe._clear_session_readings()

        # Read back through the snapshot rather than the attributes: what a
        # caller can observe is the assertion worth making, and it is the same
        # two fields.
        health = probe.health()
        assert health.latency_ms is None
        assert health.last_heartbeat is None

    def test_the_snapshot_carries_the_readings_through(self) -> None:
        probe = _probe(ConnectionState.CONNECTED)
        probe._last_latency_ms = 12.5
        probe._last_heartbeat = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)

        health = probe.health()

        assert health.latency_ms == 12.5
        assert health.last_heartbeat == datetime(2026, 8, 2, 12, 0, tzinfo=UTC)

    def test_the_snapshot_names_what_the_hooks_report(self) -> None:
        health = _probe(ConnectionState.CONNECTED).health()

        assert health.broker == "Probe Brokerage"
        assert health.server == "Probe-Demo"

    @pytest.mark.parametrize("state", list(ConnectionState), ids=lambda state: state.name)
    def test_connected_is_derived_from_the_state_rather_than_tracked(
        self, state: ConnectionState
    ) -> None:
        # Connection rejects the two disagreeing, and the way they come to
        # disagree is a lifecycle path that updates one of them. Every state is
        # exercised, including DEGRADED, which is usable, and RECONNECTING,
        # which is not — the two a boolean flag gets wrong.
        health = _probe(state).health()

        assert health.state is state
        assert health.connected is state.is_usable

    @pytest.mark.parametrize("state", list(ConnectionState), ids=lambda state: state.name)
    def test_is_connected_answers_the_same_question_as_the_snapshot(
        self, state: ConnectionState
    ) -> None:
        probe = _probe(state)

        assert probe.is_connected() is probe.health().connected

    @pytest.mark.parametrize("state", list(ConnectionState), ids=lambda state: state.name)
    def test_health_never_raises_in_any_state(self, state: ConnectionState) -> None:
        # The method is only interesting when the venue is unreachable, so it
        # must answer in the states that describe exactly that.
        assert _probe(state).health().state is state


# --- The registry the cross-adapter tests run on ------------------------------


class TestTheRegistry:
    def test_it_names_every_discovered_adapter(self) -> None:
        # The assertion that keeps this module honest. A third adapter is
        # discovered by the conformance walk automatically and would silently
        # skip every cross-adapter test below without this.
        assert {case.adapter_type for case in CASES} == set(ADAPTERS)

    @pytest.mark.parametrize("case", CASES, ids=_case_id)
    def test_the_factory_builds_what_it_claims(self, case: AdapterCase) -> None:
        assert isinstance(case.build(), case.adapter_type)

    @pytest.mark.parametrize("case", CASES, ids=_case_id)
    def test_the_factory_builds_an_adapter_that_has_never_connected(
        self, case: AdapterCase
    ) -> None:
        # Every guard assertion below would pass vacuously if a factory handed
        # back something already connected, because the refusals would never be
        # reached and the calls would fail for other reasons.
        assert case.build().is_connected() is False

    @pytest.mark.parametrize("case", CASES, ids=_case_id)
    def test_each_factory_builds_an_independent_adapter(self, case: AdapterCase) -> None:
        first = case.build()
        first.connect()

        assert case.build().is_connected() is False


# --- Session lifecycle --------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=_case_id)
class TestSessionLifecycleIsIdentical:
    def test_a_fresh_adapter_is_not_connected(self, case: AdapterCase) -> None:
        assert case.build().is_connected() is False

    def test_a_fresh_adapter_reports_a_disconnected_snapshot(self, case: AdapterCase) -> None:
        health = case.build().health()

        assert health.state is ConnectionState.DISCONNECTED
        assert health.connected is False

    def test_a_fresh_adapter_has_taken_no_readings(self, case: AdapterCase) -> None:
        health = case.build().health()

        assert health.latency_ms is None
        assert health.last_heartbeat is None

    def test_a_fresh_adapter_still_names_a_broker_and_a_server(self, case: AdapterCase) -> None:
        # health() has to answer before the first connect, and Connection
        # requires both names to be non-empty — so an adapter that learns the
        # brokerage from the venue must name its ignorance rather than omit it.
        health = case.build().health()

        assert health.broker
        assert health.server

    def test_connecting_names_the_broker_and_the_server_the_right_way_round(
        self, case: AdapterCase
    ) -> None:
        # Both fields are non-empty names of similar shape, so "both are set"
        # is satisfied by an adapter that has them the wrong way round. This is
        # the assertion that distinguishes them.
        health = _connected(case).health()

        assert health.broker == case.broker
        assert health.server == case.server

    def test_connecting_makes_it_connected(self, case: AdapterCase) -> None:
        adapter = _connected(case)

        assert adapter.is_connected() is True
        assert adapter.health().state is ConnectionState.CONNECTED

    def test_connect_returns_the_snapshot_health_then_repeats(self, case: AdapterCase) -> None:
        adapter = case.build()

        assert adapter.connect() == adapter.health()

    def test_connecting_records_a_heartbeat(self, case: AdapterCase) -> None:
        # Which clock stamped it is each adapter's own business — the host's for
        # MetaTrader 5, the venue's for the mock. That one was taken is not.
        assert _connected(case).health().last_heartbeat is not None

    def test_connecting_takes_no_latency_reading(self, case: AdapterCase) -> None:
        # Connecting is not a measurement. Reporting one here would put a number
        # on a dashboard that no round trip produced.
        assert _connected(case).health().latency_ms is None

    def test_measuring_latency_caches_it_for_health(self, case: AdapterCase) -> None:
        adapter = _connected(case)

        measured = adapter.latency()

        assert adapter.health().latency_ms == measured

    def test_disconnecting_makes_it_not_connected(self, case: AdapterCase) -> None:
        adapter = _connected(case)

        adapter.disconnect()

        assert adapter.is_connected() is False
        assert adapter.health().state is ConnectionState.DISCONNECTED

    def test_disconnecting_clears_the_readings(self, case: AdapterCase) -> None:
        # The readings describe a session that no longer exists. Keeping them is
        # what makes a supervision dashboard actively misleading: a healthy
        # latency reported for a venue nothing can reach.
        adapter = _connected(case)
        adapter.latency()

        adapter.disconnect()

        assert adapter.health().latency_ms is None
        assert adapter.health().last_heartbeat is None

    def test_the_readings_were_actually_set_before_disconnect_cleared_them(
        self, case: AdapterCase
    ) -> None:
        # Without this, the test above would pass against an adapter that never
        # recorded anything in the first place.
        adapter = _connected(case)

        adapter.latency()

        assert adapter.health().latency_ms is not None
        assert adapter.health().last_heartbeat is not None

    def test_disconnecting_twice_is_not_an_error(self, case: AdapterCase) -> None:
        adapter = _connected(case)

        adapter.disconnect()
        adapter.disconnect()

        assert adapter.is_connected() is False

    def test_disconnecting_without_ever_connecting_is_not_an_error(self, case: AdapterCase) -> None:
        adapter = case.build()

        adapter.disconnect()

        assert adapter.is_connected() is False

    def test_reconnecting_leaves_it_connected(self, case: AdapterCase) -> None:
        adapter = _connected(case)

        assert adapter.reconnect().state is ConnectionState.CONNECTED
        assert adapter.is_connected() is True

    def test_health_still_answers_after_the_session_has_gone(self, case: AdapterCase) -> None:
        adapter = _connected(case)
        adapter.disconnect()

        assert adapter.health().connected is False

    def test_is_connected_agrees_with_the_snapshot_at_every_stage(self, case: AdapterCase) -> None:
        adapter = case.build()
        assert adapter.is_connected() == adapter.health().connected

        adapter.connect()
        assert adapter.is_connected() == adapter.health().connected

        adapter.disconnect()
        assert adapter.is_connected() == adapter.health().connected


# --- Connection guards --------------------------------------------------------


class TestTheCallTable:
    def test_it_covers_every_port_method_that_is_not_lifecycle(self) -> None:
        assert set(CALLS) == set(ALL_MANDATED) - set(LIFECYCLE)

    def test_the_expectation_tables_partition_it(self) -> None:
        # Three disjoint sets covering the table exactly, so a method cannot be
        # dropped from one expectation without appearing in another.
        assert set(GUARDED) | set(NEVER_REFUSES) | set(MT5_DEFERRED) == set(CALLS)
        assert len(GUARDED) + len(NEVER_REFUSES) + len(MT5_DEFERRED) == len(CALLS)


@pytest.mark.parametrize("case", CASES, ids=_case_id)
class TestConnectionGuardsAreIdentical:
    @pytest.mark.parametrize("method", GUARDED)
    def test_the_method_refuses_when_there_is_no_session(
        self, case: AdapterCase, method: str
    ) -> None:
        with pytest.raises(BrokerNotConnectedError):
            CALLS[method](case.build())

    @pytest.mark.parametrize("method", GUARDED)
    def test_the_refusal_names_the_venue_that_produced_it(
        self, case: AdapterCase, method: str
    ) -> None:
        # A log line covering several adapters at once has to say which one.
        with pytest.raises(BrokerNotConnectedError) as caught:
            CALLS[method](case.build())

        assert caught.value.venue

    @pytest.mark.parametrize("method", GUARDED)
    def test_the_method_stops_refusing_once_connected(self, case: AdapterCase, method: str) -> None:
        # The control. A method wired to raise BrokerNotConnectedError
        # unconditionally would satisfy both tests above; this is the one it
        # fails. What it raises instead is not this module's business — an empty
        # venue and a terminal with no bars both refuse for their own reasons.
        assert _outcome(_connected(case), method) != BrokerNotConnectedError.__name__

    @pytest.mark.parametrize("method", NEVER_REFUSES)
    def test_the_method_answers_rather_than_refusing(self, case: AdapterCase, method: str) -> None:
        assert _outcome(case.build(), method) == RETURNED


class TestTheTwoAdaptersAgree:
    def test_they_agree_on_every_method_neither_defers(self) -> None:
        # The refactor's actual claim, in one assertion: with no session, the
        # two adapters are indistinguishable through the port outside the seven
        # MetaTrader 5 cannot implement at all.
        methods = [method for method in sorted(CALLS) if method not in set(MT5_DEFERRED)]

        assert {method: _outcome(_mock(), method) for method in methods} == {
            method: _outcome(_mt5(), method) for method in methods
        }

    @pytest.mark.parametrize("method", MT5_DEFERRED)
    def test_mt5_names_the_missing_capability_rather_than_the_session(self, method: str) -> None:
        assert _outcome(_mt5(), method) == NotImplementedError.__name__

    @pytest.mark.parametrize("method", MT5_DEFERRED)
    def test_the_mock_guards_what_mt5_defers(self, method: str) -> None:
        # The evidence that the deferral is MetaTrader 5's limitation and not
        # the port's: the same seven methods are implemented and guarded here.
        assert _outcome(_mock(), method) == BrokerNotConnectedError.__name__


# --- Conformance, after the change of base ------------------------------------


@pytest.mark.parametrize("case", CASES, ids=_case_id)
class TestInheritingTheBaseKeepsThePortSatisfied:
    def test_the_adapter_is_still_a_subclass_of_the_port(self, case: AdapterCase) -> None:
        assert issubclass(case.adapter_type, BrokerAdapter)

    def test_it_now_reaches_the_port_through_the_base(self, case: AdapterCase) -> None:
        assert issubclass(case.adapter_type, BaseBrokerAdapter)

    def test_it_has_no_abstract_member_left(self, case: AdapterCase) -> None:
        assert case.adapter_type.__abstractmethods__ == frozenset()

    def test_it_answers_the_hooks_the_base_asks_for(self, case: AdapterCase) -> None:
        adapter = case.build()

        assert isinstance(adapter._session_state, ConnectionState)
        assert adapter._session_broker
        assert adapter._session_server

    @pytest.mark.parametrize("hook", LIFECYCLE_HOOKS)
    def test_it_supplies_the_lifecycle_hook_itself(self, case: AdapterCase, hook: str) -> None:
        # The other half of the arrangement: the base owns the public method,
        # the adapter owns the venue-specific body. An adapter that inherited
        # the hook too would have no lifecycle at all.
        assert hook in vars(case.adapter_type)

    @pytest.mark.parametrize("method", LIFECYCLE)
    def test_the_inherited_method_keeps_the_ports_pinned_signature(
        self, case: AdapterCase, method: str
    ) -> None:
        signature = str(inspect.signature(getattr(case.adapter_type, method)))

        assert signature == PINNED_SIGNATURES[method]

    @pytest.mark.parametrize("method", LIFECYCLE)
    def test_the_method_comes_from_the_base_and_not_from_the_port(
        self, case: AdapterCase, method: str
    ) -> None:
        assert getattr(case.adapter_type, method) is getattr(BaseBrokerAdapter, method)
        assert getattr(case.adapter_type, method) is not getattr(BrokerAdapter, method)

    @pytest.mark.parametrize("method", LIFECYCLE)
    def test_the_adapter_no_longer_defines_the_method_itself(
        self, case: AdapterCase, method: str
    ) -> None:
        # The duplication is gone rather than shadowed, and for the three
        # lifecycle methods it is also what makes the locking unskippable: an
        # adapter that kept its own copy would pass every behavioural test in
        # this module while taking no lock at all.
        assert method not in vars(case.adapter_type)
