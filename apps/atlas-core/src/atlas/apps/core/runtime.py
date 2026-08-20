"""The runtime entrypoint: one session, one loop, one ordered evaluation.

ADR-0017 gave ``atlas-core`` an entrypoint that opens a broker session, proves
it works and closes it — a one-shot verification, deliberately not a process
that trades. ADR-0018 deferred the shape of the long-lived process. ADR-0019
decided it: a *second* entrypoint, in the same application, holding one session
open for the life of the process and driving the decision pipeline over it.
This module is that entrypoint. The verification entrypoint in
``atlas.apps.core.__main__`` is untouched and still exits after one round trip.

What the runtime owns
    The :class:`~atlas.apps.core.broker_ownership.BrokerOwner` it composes, the
    loop, supervision of the session, recovery when the session is lost, the
    polling that stands in for the push subscription MetaTrader 5 does not
    offer, and the ordering of strategy, risk, execution and submission.

What the runtime does not own
    Order lifecycle beyond submission, routing, fills, reconciliation,
    idempotency, persistence, multi-venue failover, and process restart. Each
    of those is another decision, and none of them is ADR-0019's.

Threads
    None. ADR-0007 put the only locks in the base adapter and ADR-0019 did not
    move them; :class:`BrokerOwner` records that ``start`` and ``stop`` are not
    safe to call from two threads at once. A single thread runs the loop, so
    one evaluation finishes before the next begins by construction rather than
    by policy, and backpressure cannot arise because nothing is ever queued.

The values this module refuses to choose
    The poll interval, the observation source, the strategy and the execution
    policy are parameters without defaults. ADR-0019 left the polling interval,
    the traded instrument, the strategy algorithm and the execution policy
    undecided; ADR-0011 already refused to let execution keep a default policy
    for the same reason. A default here would be a trading decision written
    into the layer least likely to be read as one, so there is none: a caller
    that wants a running process has to state all four.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from atlas.apps.core.composition import build_broker_owner
from atlas.broker import BrokerError
from atlas.config import load_settings
from atlas.execution import build_order_request
from atlas.risk import evaluate_exposure

if TYPE_CHECKING:
    from collections.abc import Callable

    from atlas.apps.core.broker_ownership import BrokerOwner
    from atlas.common import Clock
    from atlas.execution import ExecutionPolicy
    from atlas.strategy import Strategy

__all__ = ["CoreRuntime", "run_runtime"]


class CoreRuntime[ObservationT]:
    """Holds one broker session open and drives one ordered cycle at a time.

    The runtime is generic over what it observes because nothing at this layer
    is entitled to name a market data model: ADR-0019 granted the application
    three names from the broker package and no read operation, so the read
    itself belongs to the ``observe`` callable the caller supplies. What the
    runtime owns is the *timing* of that read, not its shape.

    A runtime instance runs once. :meth:`run` refuses a second call, which is
    how ADR-0019's "the runtime never restarts a stopped session" is enforced
    here rather than by tightening :class:`BrokerOwner`, whose own contract —
    double start rejected, redundant stop harmless — is left exactly as it is.
    """

    def __init__(
        self,
        owner: BrokerOwner,
        *,
        clock: Clock,
        observe: Callable[[BrokerOwner], ObservationT | None],
        strategy: Strategy[ObservationT],
        policy: ExecutionPolicy,
        poll_interval_seconds: float,
    ) -> None:
        """Store the collaborators; open nothing.

        Construction has no side effect on the venue. The session is opened by
        :meth:`run` and by nothing else, so a runtime that is built and never
        run has cost a caller nothing.

        Args:
            owner: The session boundary, already composed but not started.
            clock: ADR-0008's injected clock. The loop waits through it so a
                test can drive many cycles without spending the wall time.
            observe: Reads one observation through the owner, or returns
                ``None`` when there is nothing to look at yet.
            strategy: Turns an observation into an intent, or into no opinion.
            policy: The execution policy applied to an approved verdict.
            poll_interval_seconds: How long the loop waits between cycles.
        """
        self._owner = owner
        self._clock = clock
        self._observe = observe
        self._strategy = strategy
        self._policy = policy
        self._poll_interval_seconds = poll_interval_seconds
        self._stop = threading.Event()
        self._ran = False
        self._last_broker_error: BrokerError | None = None

    @property
    def stop_requested(self) -> bool:
        """Whether shutdown has been asked for."""
        return self._stop.is_set()

    @property
    def last_broker_error(self) -> BrokerError | None:
        """The most recent broker failure a cycle absorbed, if there was one.

        A cycle that raised is not a reason to end the process — the next cycle
        supervises the session and may recover it. Absorbing the failure
        silently would be, so it is kept here where a caller can read it.
        """
        return self._last_broker_error

    def request_stop(self) -> None:
        """Ask the loop to finish the current cycle and stop.

        Safe to call from another thread, and safe to call more than once.
        ADR-0019 deferred signal handling and shutdown-grace semantics, so this
        is the whole of the shutdown surface: a flag the loop reads.
        """
        self._stop.set()

    def run(self) -> None:
        """Open the session, cycle until stop is asked for, then close it.

        Exactly one :meth:`BrokerOwner.start` for the life of the runtime, and
        a :meth:`BrokerOwner.stop` on every exit path, including a start that
        failed and a cycle that raised something the loop does not absorb.

        Raises:
            RuntimeError: If the runtime has already been run. Stopping is
                terminal; a caller that wants another session builds another
                runtime, and therefore another owner.
        """
        if self._ran:
            msg = "the runtime has already been run; a stopped runtime is not restarted"
            raise RuntimeError(msg)
        self._ran = True
        try:
            self._owner.start()
            while not self._stop.is_set():
                self._run_once()
                self._clock.sleep(self._poll_interval_seconds)
        finally:
            self._owner.stop()

    def _run_once(self) -> None:
        """Run one cycle, absorbing a broker failure into the runtime's record."""
        try:
            self._cycle()
        except BrokerError as exc:
            self._last_broker_error = exc

    def _cycle(self) -> None:
        """Supervise the session, then take the pipeline in its decided order.

        Observation, then strategy, then risk, then execution, then submission.
        Each stage may end the cycle: no observation, no opinion, or a verdict
        execution declines to build a request from. Nothing is queued and
        nothing is deferred, so the next cycle cannot overlap this one.
        """
        self._supervise()
        observation = self._observe(self._owner)
        if observation is None:
            return
        intent = self._strategy.propose(observation)
        if intent is None:
            return
        verdict = evaluate_exposure(intent, self._owner.adapter.get_account())
        request = build_order_request(verdict, self._policy)
        if request is None:
            return
        self._owner.adapter.place_order(request)

    def _supervise(self) -> None:
        """Check the session is usable and ask for one reconnection if it is not.

        ``is_connected`` is the local view and costs nothing; ``ping`` is the
        round trip that catches a session the venue has dropped without saying
        so, and the port promises it returns ``False`` rather than raising. How
        many attempts to make, how long to wait between them and which failures
        deserve which treatment are retry-policy questions ADR-0009 answers
        with a value nobody has chosen yet, so this asks once and lets the next
        cycle ask again.
        """
        adapter = self._owner.adapter
        if adapter.is_connected() and adapter.ping():
            return
        adapter.reconnect()


def run_runtime[ObservationT](
    *,
    clock: Clock,
    observe: Callable[[BrokerOwner], ObservationT | None],
    strategy: Strategy[ObservationT],
    policy: ExecutionPolicy,
    poll_interval_seconds: float,
) -> CoreRuntime[ObservationT]:
    """Compose a runtime from configuration, run it, and return it once stopped.

    The same composition path as the verification entrypoint: settings are
    loaded, and :func:`~atlas.apps.core.composition.build_broker_owner` selects
    and constructs the adapter. The runtime is what differs, not the wiring.

    ``ConfigurationError`` and ``BrokerError`` are deliberately not caught. The
    exit-code surface belongs to ADR-0017's entrypoint, and minting a second
    one would decide the process contract ADR-0019 left to deployment.

    Args:
        clock: ADR-0008's injected clock.
        observe: Reads one observation through the owner.
        strategy: Turns an observation into an intent.
        policy: The execution policy applied to an approved verdict.
        poll_interval_seconds: How long the loop waits between cycles.

    Returns:
        The runtime that was run, so a caller can read what it recorded.
    """
    runtime = CoreRuntime(
        build_broker_owner(load_settings()),
        clock=clock,
        observe=observe,
        strategy=strategy,
        policy=policy,
        poll_interval_seconds=poll_interval_seconds,
    )
    runtime.run()
    return runtime
