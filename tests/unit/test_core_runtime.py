"""Behavioural tests for the atlas-core runtime entrypoint.

ADR-0019 decided four things this file has to make real rather than asserted:
one session for the life of the process, one evaluation at a time in a fixed
order, supervision that owns recovery, and a shutdown that closes what it
opened. Everything else the record deliberately left undecided — the polling
interval, the retry policy, the health threshold, the instrument and the
strategy — and the tests here are written so that none of them is smuggled in
as an assertion.

They run against a **real** ``MockBrokerAdapter`` over a real ``MockVenue``, for
the reason ``test_core_broker_ownership.py`` gives: a hand-written double would
report whatever session state the test told it to, including states the port
cannot produce. :class:`RecordingAdapter` and :class:`CountingOwner` subclass
the real things and note each call before delegating to ``super()``, so the
order recorded is the order the runtime actually called them in and every call
still takes its real path, failure handling and all.

Time is :class:`~atlas.common.ManualClock`, whose ``sleep`` is instant. A loop
that polls therefore costs the suite nothing, and no test here can pass or fail
on how busy the machine was.

Not in ``tests/integration/``: that directory is reserved for tests that
exercise PostgreSQL, Redis and DuckDB, and ATLAS-TASK-0029 §23 forbids wiring
any of them. A whole run of the pipeline over a real adapter and a real venue,
with no service to bring up, belongs here.
"""

from __future__ import annotations

import inspect
from decimal import Decimal
from typing import TYPE_CHECKING, NamedTuple

import pytest

from atlas.apps.core import runtime as runtime_module
from atlas.apps.core.broker_ownership import BrokerOwner
from atlas.apps.core.runtime import CoreRuntime, run_runtime
from atlas.broker import BrokerConnectionError, BrokerNotConnectedError
from atlas.broker.mock import DEFAULT_START, MockBrokerAdapter, MockVenue
from atlas.broker.models import OrderSide, OrderType, Symbol, SymbolTradeMode, Tick
from atlas.common import ManualClock
from atlas.config import ConfigurationError
from atlas.execution import ExecutionPolicy, build_order_request
from atlas.risk import TradeIntent, evaluate_exposure

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from atlas.broker.models import Account, Connection, Order
    from atlas.broker.types import OrderRequest
    from atlas.config import AtlasSettings
    from atlas.risk import RiskVerdict

pytestmark = pytest.mark.unit

#: The instrument the venue quotes. Ordinary retail terms, so a rejection in a
#: test is caused by what the test set up rather than by the fixture.
EURUSD = Symbol(
    symbol="EURUSD",
    description="Euro vs US Dollar",
    base_currency="EUR",
    quote_currency="USD",
    digits=5,
    point=Decimal("0.00001"),
    tick_size=Decimal("0.00001"),
    contract_size=Decimal("100000"),
    min_volume=Decimal("0.01"),
    max_volume=Decimal("50"),
    volume_step=Decimal("0.01"),
    spread=12,
    trade_mode=SymbolTradeMode.FULL,
)

#: A size well inside the instrument's bounds and on its step.
VOLUME = Decimal("0.10")

#: A poll interval, chosen by a *test* rather than by the runtime.
#:
#: ADR-0019 left the interval undecided and the runtime has no default, so every
#: caller states one. The value is arbitrary and nothing asserts on it: against
#: a manual clock the loop takes no time whatever it is.
POLL_SECONDS = 1.0

#: A margin-utilisation limit that permits the venue's default account to trade.
#:
#: ``RiskSettings.max_margin_utilisation`` defaults to zero, which permits
#: nothing, so a test wanting risk to *approve* has to raise it. This sets an
#: existing configuration field; ADR-0019 adds none.
PERMISSIVE_LIMIT = "0.5"

#: The stages one full cycle visits, in the order ADR-0019 decided.
FULL_CYCLE = (
    "is_connected",
    "ping",
    "observe",
    "propose",
    "get_account",
    "evaluate_exposure",
    "build_order_request",
    "place_order",
)


class LoopEndedError(Exception):
    """Raised by an observation source that has no other way to end a loop.

    :func:`~atlas.apps.core.runtime.run_runtime` builds the runtime it runs, so
    a caller has no handle on it until the loop is already over and cannot ask
    it to stop from inside a cycle. A test that needs a bounded run through
    that function therefore ends it the only way an outside caller can, which
    doubles as the abnormal-exit case: the session must still be closed.
    """


class Recorder:
    """A log of what the runtime did, in the order it did it."""

    def __init__(self) -> None:
        """Start an empty log."""
        self.steps: list[str] = []

    def note(self, step: str) -> None:
        """Append one step to the log.

        Args:
            step: The name of the stage being entered.
        """
        self.steps.append(step)


class RecordingAdapter(MockBrokerAdapter):
    """A real mock adapter that notes the six operations ADR-0019 granted.

    Every override delegates to ``super()``, so the session state, the failure
    paths and the venue's bookkeeping stay the adapter's own.
    """

    def __init__(self, venue: MockVenue, recorder: Recorder) -> None:
        """Bind a recording adapter to a venue.

        Args:
            venue: The venue to trade against.
            recorder: Where each call is noted.
        """
        super().__init__(venue)
        self._recorder = recorder

    def is_connected(self) -> bool:
        """Note the check, then answer it."""
        self._recorder.note("is_connected")
        return super().is_connected()

    def ping(self) -> bool:
        """Note the round trip, then make it."""
        self._recorder.note("ping")
        return super().ping()

    def reconnect(self) -> Connection:
        """Note the recovery attempt, then make it."""
        self._recorder.note("reconnect")
        return super().reconnect()

    def get_account(self) -> Account:
        """Note the read, then perform it."""
        self._recorder.note("get_account")
        return super().get_account()

    def place_order(self, request: OrderRequest) -> Order:
        """Note the submission, then make it."""
        self._recorder.note("place_order")
        return super().place_order(request)


class CountingOwner(BrokerOwner):
    """A real owner that counts the lifecycle calls made against it.

    Subclassed rather than wrapped so the counted calls are the ones the runtime
    made on the object it holds, and so the owner's real semantics survive: a
    second ``start`` still raises, a redundant ``stop`` still does not.
    """

    def __init__(self, adapter: MockBrokerAdapter) -> None:
        """Bind a counting owner to an adapter.

        Args:
            adapter: The adapter whose session this owner sequences.
        """
        super().__init__(adapter)
        self.starts = 0
        self.stops = 0

    def start(self) -> None:
        """Count the call, then open the session."""
        self.starts += 1
        super().start()

    def stop(self) -> None:
        """Count the call, then close the session."""
        self.stops += 1
        super().stop()


class RecordingStrategy:
    """A strategy that notes being asked and answers with a fixed intent.

    Satisfies :class:`~atlas.strategy.Strategy` structurally, which is all that
    protocol asks. It is not a trading strategy and claims no edge; what it
    exists to prove is that the runtime asked, and asked at the right point.
    """

    def __init__(self, recorder: Recorder, intent: TradeIntent | None) -> None:
        """Fix the answer this strategy will give.

        Args:
            recorder: Where each call is noted.
            intent: What to propose, or ``None`` for no opinion.
        """
        self._recorder = recorder
        self._intent = intent
        self.observations: list[str] = []

    def propose(self, observation: str, /) -> TradeIntent | None:
        """Note the question and give the fixed answer.

        Args:
            observation: Whatever the runtime observed.

        Returns:
            The fixed intent, or ``None``.
        """
        self._recorder.note("propose")
        self.observations.append(observation)
        return self._intent


class Cycles:
    """An observation source that ends the loop after a fixed number of cycles.

    Stopping from *inside* a cycle is deliberate: it is the only way to show the
    loop re-reads the flag between cycles rather than checking it once, and it
    is how a real shutdown would arrive.
    """

    def __init__(
        self,
        recorder: Recorder,
        limit: int,
        *,
        observation: str | None = "tick",
        during: Callable[[BrokerOwner], None] | None = None,
    ) -> None:
        """Configure how many cycles to allow and what to observe.

        Args:
            recorder: Where each call is noted.
            limit: How many cycles to run before asking the loop to stop.
            observation: What to hand the strategy, or ``None`` for nothing.
            during: An extra action to take inside the cycle, such as dropping
                the session so the next cycle has something to recover.
        """
        self._recorder = recorder
        self._limit = limit
        self._observation = observation
        self._during = during
        self.count = 0
        self.runtime: CoreRuntime[str] | None = None

    def __call__(self, owner: BrokerOwner) -> str | None:
        """Observe once, and end the loop if this was the last cycle.

        Args:
            owner: The session holder, as the runtime hands it over.

        Returns:
            The configured observation.

        Raises:
            LoopEndedError: If no runtime was attached, which is the
                :func:`~atlas.apps.core.runtime.run_runtime` case.
        """
        self.count += 1
        self._recorder.note("observe")
        if self._during is not None:
            self._during(owner)
        if self.count >= self._limit:
            if self.runtime is None:
                raise LoopEndedError
            self.runtime.request_stop()
        return self._observation


class Harness(NamedTuple):
    """Everything one wired runtime exposes to a test."""

    runtime: CoreRuntime[str]
    owner: CountingOwner
    adapter: RecordingAdapter
    venue: MockVenue
    strategy: RecordingStrategy
    cycles: Cycles


def _venue() -> MockVenue:
    """Build a venue quoting one instrument.

    Returns:
        A venue offering EURUSD with a standing quote.
    """
    venue = MockVenue()
    venue.add_symbol(EURUSD)
    venue.publish_tick(
        Tick(
            symbol="EURUSD",
            bid=Decimal("1.10000"),
            ask=Decimal("1.10012"),
            timestamp=DEFAULT_START,
        )
    )
    return venue


def _intent() -> TradeIntent:
    """Build the intent the recording strategy proposes.

    No protective levels: the mock refuses an order carrying them, and a stop
    distance chosen here would be a trading decision this task does not make.

    Returns:
        A minimal, valid intent.
    """
    return TradeIntent(symbol="EURUSD", side=OrderSide.BUY, requested_volume=VOLUME)


def _build(
    recorder: Recorder,
    cycles: Cycles,
    *,
    intent: TradeIntent | None = None,
    venue: MockVenue | None = None,
    observe: Callable[[BrokerOwner], str | None] | None = None,
) -> Harness:
    """Wire a runtime over a real owner, a real adapter and a real venue.

    Args:
        recorder: Where each stage is noted.
        cycles: The observation source, which also ends the loop.
        intent: What the strategy will propose.
        venue: The venue to trade against, or ``None`` for a fresh one.
        observe: An observation source to use instead of ``cycles``, for the
            cases that need one which misbehaves.

    Returns:
        The runtime and everything behind it.
    """
    built_venue = _venue() if venue is None else venue
    adapter = RecordingAdapter(built_venue, recorder)
    owner = CountingOwner(adapter)
    strategy = RecordingStrategy(recorder, intent)
    runtime = CoreRuntime(
        owner,
        clock=ManualClock(DEFAULT_START),
        observe=cycles if observe is None else observe,
        strategy=strategy,
        policy=ExecutionPolicy(order_type=OrderType.MARKET),
        poll_interval_seconds=POLL_SECONDS,
    )
    cycles.runtime = runtime
    return Harness(runtime, owner, adapter, built_venue, strategy, cycles)


def _drop_the_session(owner: BrokerOwner) -> None:
    """Close the session behind the owner's back, as a venue timeout would.

    Args:
        owner: The session holder.
    """
    owner.adapter.disconnect()


@pytest.fixture
def permissive_risk(isolated_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Raise the exposure limit so risk approves the venue's default account.

    Returns:
        The hermetic working directory.
    """
    monkeypatch.setenv("ATLAS_RISK__MAX_MARGIN_UTILISATION", PERMISSIVE_LIMIT)
    return isolated_env


@pytest.fixture
def announced_pipeline(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    """Note the two pipeline functions the runtime calls, then call them.

    Wrapped rather than replaced, for the reason the entrypoint tests give:
    replacing them would record the order the runtime was *supposed* to use.

    Returns:
        The recorder the wrappers write to.
    """
    recorder = Recorder()

    def announced_evaluate(intent: TradeIntent, account: Account) -> RiskVerdict:
        recorder.note("evaluate_exposure")
        return evaluate_exposure(intent, account)

    def announced_build(verdict: RiskVerdict, policy: ExecutionPolicy) -> OrderRequest | None:
        recorder.note("build_order_request")
        return build_order_request(verdict, policy)

    monkeypatch.setattr(runtime_module, "evaluate_exposure", announced_evaluate)
    monkeypatch.setattr(runtime_module, "build_order_request", announced_build)
    return recorder


class TestConstruction:
    def test_construction_opens_no_session(self) -> None:
        """Building a runtime performs no I/O, exactly as building an owner does."""
        recorder = Recorder()

        harness = _build(recorder, Cycles(recorder, 1))

        assert recorder.steps == []
        assert harness.owner.starts == 0
        assert harness.adapter.is_connected() is False

    def test_the_constructor_takes_no_policy_it_was_not_given(self) -> None:
        """§19 and §20: no retry policy, no threshold, no configuration.

        Pinned as a signature rather than as prose, because each of those would
        arrive as a parameter and each is a decision ADR-0019 deferred. The four
        values the record left undecided are present and have no defaults, so a
        caller cannot obtain a running loop without stating all four.
        """
        parameters = inspect.signature(CoreRuntime.__init__).parameters

        assert list(parameters) == [
            "self",
            "owner",
            "clock",
            "observe",
            "strategy",
            "policy",
            "poll_interval_seconds",
        ]
        assert [
            name
            for name, parameter in parameters.items()
            if parameter.default is not inspect.Parameter.empty
        ] == []


class TestTheSessionLifecycle:
    def test_the_session_is_opened_once_and_closed_once(self) -> None:
        """A session is a process-lifetime resource, not a per-cycle one.

        Three cycles, one ``start`` and one ``stop``. A loop built out of
        ``start()``/``stop()`` would pass every other test in this class and
        fail this one.
        """
        recorder = Recorder()
        harness = _build(recorder, Cycles(recorder, 3))

        harness.runtime.run()

        assert harness.cycles.count == 3
        assert harness.owner.starts == 1
        assert harness.owner.stops == 1

    def test_the_same_session_is_held_across_every_cycle(self) -> None:
        held: list[object] = []
        recorder = Recorder()

        def note_the_owner(owner: BrokerOwner) -> None:
            held.append(owner)

        harness = _build(recorder, Cycles(recorder, 3, during=note_the_owner))

        harness.runtime.run()

        assert held == [harness.owner, harness.owner, harness.owner]

    def test_the_session_is_closed_when_the_loop_stops(self) -> None:
        recorder = Recorder()
        harness = _build(recorder, Cycles(recorder, 1))

        harness.runtime.run()

        assert harness.adapter.is_connected() is False

    def test_access_is_revoked_when_the_loop_stops(self) -> None:
        """Stopping the runtime stops the owner, and stopping the owner revokes access."""
        recorder = Recorder()
        harness = _build(recorder, Cycles(recorder, 1))

        harness.runtime.run()

        with pytest.raises(BrokerNotConnectedError):
            _ = harness.owner.adapter

    def test_a_shutdown_asked_for_before_the_first_cycle_runs_none(self) -> None:
        """The flag is read before a cycle, so a stop can never arrive too early."""
        recorder = Recorder()
        harness = _build(recorder, Cycles(recorder, 1))

        harness.runtime.request_stop()
        harness.runtime.run()

        assert harness.runtime.stop_requested is True
        assert harness.cycles.count == 0
        assert recorder.steps == []
        assert harness.owner.starts == 1
        assert harness.owner.stops == 1

    def test_stop_requested_is_false_until_it_is_asked_for(self) -> None:
        recorder = Recorder()
        harness = _build(recorder, Cycles(recorder, 1))

        assert harness.runtime.stop_requested is False

    def test_a_failed_start_unwinds_and_the_failure_reaches_the_caller(self) -> None:
        """A session that would not open is not a cycle that ran and failed."""
        recorder = Recorder()
        venue = _venue()
        failure = BrokerConnectionError("the venue refused the session")
        venue.schedule_failure("connect", failure)
        harness = _build(recorder, Cycles(recorder, 1), venue=venue)

        with pytest.raises(BrokerConnectionError) as raised:
            harness.runtime.run()

        assert raised.value is failure
        assert harness.cycles.count == 0
        assert harness.owner.stops == 1
        assert harness.adapter.is_connected() is False

    def test_an_error_inside_a_cycle_still_closes_the_session(self) -> None:
        """The unwind is a `finally`, so a stranded session is not possible."""
        recorder = Recorder()

        def explode(_owner: BrokerOwner) -> str | None:
            msg = "the observation source failed"
            raise ValueError(msg)

        harness = _build(recorder, Cycles(recorder, 1), observe=explode)

        with pytest.raises(ValueError, match="observation source"):
            harness.runtime.run()

        assert harness.owner.stops == 1
        assert harness.adapter.is_connected() is False

    def test_a_stopped_runtime_is_not_restarted(self) -> None:
        """ADR-0019: stopping is terminal, and the refusal is the runtime's own.

        Asserted on the owner as well as on the exception, because a runtime
        that raised *after* re-opening a session would satisfy the first
        assertion and strand a session on the venue.
        """
        recorder = Recorder()
        harness = _build(recorder, Cycles(recorder, 1))
        harness.runtime.run()

        with pytest.raises(RuntimeError, match="already been run"):
            harness.runtime.run()

        assert harness.owner.starts == 1
        assert harness.adapter.is_connected() is False


class TestThePipelineOrder:
    def test_one_cycle_visits_every_stage_in_the_decided_order(
        self, permissive_risk: Path, announced_pipeline: Recorder
    ) -> None:
        """Observation, strategy, risk, execution, submission — after supervision."""
        assert permissive_risk.exists()
        recorder = announced_pipeline
        harness = _build(recorder, Cycles(recorder, 1), intent=_intent())

        harness.runtime.run()

        assert tuple(recorder.steps) == FULL_CYCLE

    def test_one_evaluation_completes_before_the_next_begins(
        self, permissive_risk: Path, announced_pipeline: Recorder
    ) -> None:
        """Two cycles, and not one stage of the second appears inside the first.

        Equality against the concatenation is the assertion: any overlap, any
        reordering and any dropped stage changes the sequence.
        """
        assert permissive_risk.exists()
        recorder = announced_pipeline
        harness = _build(recorder, Cycles(recorder, 2), intent=_intent())

        harness.runtime.run()

        assert tuple(recorder.steps) == FULL_CYCLE * 2

    def test_an_approved_intent_reaches_the_venue(self, permissive_risk: Path) -> None:
        """The end of the pipeline is a fill on the venue, not a call that was made."""
        assert permissive_risk.exists()
        recorder = Recorder()
        harness = _build(recorder, Cycles(recorder, 1), intent=_intent())

        harness.runtime.run()

        assert [execution.volume for execution in harness.venue.executions()] == [VOLUME]

    def test_nothing_observed_ends_the_cycle_before_the_strategy(
        self, permissive_risk: Path, announced_pipeline: Recorder
    ) -> None:
        """A poll with no new data is an ordinary outcome, not a failure."""
        assert permissive_risk.exists()
        recorder = announced_pipeline
        harness = _build(recorder, Cycles(recorder, 1, observation=None), intent=_intent())

        harness.runtime.run()

        assert tuple(recorder.steps) == ("is_connected", "ping", "observe")

    def test_no_opinion_ends_the_cycle_before_risk(
        self, permissive_risk: Path, announced_pipeline: Recorder
    ) -> None:
        """A strategy with nothing to say costs no account read and no verdict."""
        assert permissive_risk.exists()
        recorder = announced_pipeline
        harness = _build(recorder, Cycles(recorder, 1), intent=None)

        harness.runtime.run()

        assert tuple(recorder.steps) == ("is_connected", "ping", "observe", "propose")

    def test_a_rejected_verdict_ends_the_cycle_before_submission(
        self, isolated_env: Path, announced_pipeline: Recorder
    ) -> None:
        """Risk refusing is risk working, so execution builds nothing and nothing ships.

        The limit is left at its default of zero, which permits nothing, so the
        rejection comes from the real control rather than from a stub.
        """
        assert isolated_env.exists()
        recorder = announced_pipeline
        harness = _build(recorder, Cycles(recorder, 1), intent=_intent())

        harness.runtime.run()

        assert tuple(recorder.steps) == FULL_CYCLE[:-1]
        assert harness.venue.executions() == ()

    def test_the_strategy_is_asked_about_what_was_observed(self) -> None:
        """The observation is handed on unchanged rather than re-derived."""
        recorder = Recorder()
        harness = _build(recorder, Cycles(recorder, 2, observation="the-observation"))

        harness.runtime.run()

        assert harness.strategy.observations == ["the-observation", "the-observation"]


class TestSupervision:
    def test_supervision_precedes_the_pipeline_in_every_cycle(self) -> None:
        """A cycle that traded on a dead session would be a cycle that never checked."""
        recorder = Recorder()
        harness = _build(recorder, Cycles(recorder, 2))

        harness.runtime.run()

        assert recorder.steps == ["is_connected", "ping", "observe", "propose"] * 2

    def test_a_healthy_session_is_never_reconnected(self) -> None:
        """Recovery answers evidence; it is not something the loop does anyway."""
        recorder = Recorder()
        harness = _build(recorder, Cycles(recorder, 3))

        harness.runtime.run()

        assert "reconnect" not in recorder.steps

    def test_a_lost_session_is_recovered_by_the_next_cycle(self) -> None:
        """The runtime owns recovery: no other application module calls `reconnect`."""
        recorder = Recorder()
        harness = _build(recorder, Cycles(recorder, 2, during=_drop_the_session))

        harness.runtime.run()

        assert "reconnect" in recorder.steps
        assert harness.cycles.count == 2

    def test_recovery_is_reattempted_on_the_following_cycle(self) -> None:
        """No retry loop inside a cycle, and no attempt budget across them.

        The venue refuses the first rebuild. That cycle ends there and the next
        one asks again — which is what "the runtime decides no retry policy"
        looks like from outside. Nothing here asserts how many attempts a single
        cycle makes, because ADR-0019 does not say and this task may not.
        """
        recorder = Recorder()
        venue = _venue()
        harness = _build(recorder, Cycles(recorder, 3, during=_drop_the_session), venue=venue)
        venue.schedule_failure("reconnect", BrokerConnectionError("not yet"))

        harness.runtime.run()

        assert recorder.steps.count("reconnect") > 1
        assert harness.cycles.count == 3

    def test_a_broker_failure_in_a_cycle_does_not_end_the_process(self) -> None:
        """Ending on the first failure would put recovery out of reach by design."""
        recorder = Recorder()
        venue = _venue()
        failure = BrokerConnectionError("the venue dropped the session")
        harness = _build(recorder, Cycles(recorder, 3, during=_drop_the_session), venue=venue)
        venue.schedule_failure("reconnect", failure)

        harness.runtime.run()

        assert harness.cycles.count == 3
        assert harness.runtime.last_broker_error is failure
        assert harness.owner.stops == 1

    def test_a_run_with_no_failure_records_none(self) -> None:
        """The record is evidence, so it stays empty when there is nothing to report."""
        recorder = Recorder()
        harness = _build(recorder, Cycles(recorder, 2))

        harness.runtime.run()

        assert harness.runtime.last_broker_error is None


class TestRunRuntime:
    def test_the_runtime_is_composed_through_the_shared_path(
        self, permissive_risk: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The same `build_broker_owner` start-up uses, over a mock the test names.

        Composition is the only step replaced, for the reason the entrypoint
        tests give: letting it build what the settings describe would try to
        reach a MetaTrader 5 terminal from the suite. The loop ends by raising,
        which is also the assertion that the session is closed on a path the
        runtime did not choose.
        """
        assert permissive_risk.exists()
        recorder = Recorder()
        owner = CountingOwner(RecordingAdapter(_venue(), recorder))
        builds: list[BrokerOwner] = []

        def build(_settings: AtlasSettings) -> BrokerOwner:
            builds.append(owner)
            return owner

        monkeypatch.setattr(runtime_module, "build_broker_owner", build)

        with pytest.raises(LoopEndedError):
            run_runtime(
                clock=ManualClock(DEFAULT_START),
                observe=Cycles(recorder, 1),
                strategy=RecordingStrategy(recorder, _intent()),
                policy=ExecutionPolicy(order_type=OrderType.MARKET),
                poll_interval_seconds=POLL_SECONDS,
            )

        assert builds == [owner]
        assert owner.starts == 1
        assert owner.stops == 1
        assert recorder.steps == ["is_connected", "ping", "observe"]

    def test_unusable_broker_configuration_propagates(self, isolated_env: Path) -> None:
        """No second exit-code surface: the caller sees what composition raised.

        ADR-0016 makes unusable broker configuration refuse start-up and
        ADR-0017 owns the exit code that reports it. Minting another one here
        would decide the process contract ADR-0019 left to deployment.
        """
        assert isolated_env.exists()
        recorder = Recorder()

        with pytest.raises(ConfigurationError):
            run_runtime(
                clock=ManualClock(DEFAULT_START),
                observe=Cycles(recorder, 1),
                strategy=RecordingStrategy(recorder, None),
                policy=ExecutionPolicy(order_type=OrderType.MARKET),
                poll_interval_seconds=POLL_SECONDS,
            )
