"""Behavioural tests for the atlas-core process's ownership of a broker adapter.

ADR-0013 puts the adapter in the application: `apps/atlas-core` constructs the
instance, holds it, sequences its lifecycle and governs what receives access to
it. ATLAS-TASK-0020 implements the holding, the sequencing and the granting.
These tests are what make those three real rather than asserted.

They run against a **real** ``MockBrokerAdapter``. ADR-0006 shipped that adapter
so that a caller could be exercised without a venue, and a hand-written double
here would test the double: it would report whatever connection state the test
told it to, including a state the port cannot actually produce. The connect
failure in :class:`TestAConnectFailurePropagates` is injected through the mock
venue's own fault surface for the same reason — the adapter takes its real
failure path, base class and all.

Nothing here constructs an adapter *in a process*. That would mean choosing an
implementation, and the entrypoint is deliberately untouched by this task; see
`docs/tasks/ATLAS-TASK-0020.md` §11.2. A test may choose one, because a test is
not a process and names the one it wants.
"""

from __future__ import annotations

import pytest

from atlas.apps.core import broker_ownership
from atlas.apps.core.broker_ownership import BrokerOwner
from atlas.broker import BrokerConnectionError, BrokerNotConnectedError
from atlas.broker.mock import MockBrokerAdapter

pytestmark = pytest.mark.unit


class TestConstruction:
    def test_construction_does_not_connect(self) -> None:
        """C-4: building an owner performs no I/O and leaves the adapter alone."""
        adapter = MockBrokerAdapter()

        BrokerOwner(adapter)

        assert adapter.is_connected() is False

    def test_the_owner_holds_the_exact_instance_it_was_given(self) -> None:
        """T-1: identity, not a copy, a wrapper or a re-derived adapter."""
        adapter = MockBrokerAdapter()
        owner = BrokerOwner(adapter)

        owner.start()

        assert owner.adapter is adapter

    def test_two_owners_hold_their_own_adapters(self) -> None:
        """H-1: the instance lives on the owner, not somewhere both of them share."""
        first, second = MockBrokerAdapter(), MockBrokerAdapter()
        first_owner, second_owner = BrokerOwner(first), BrokerOwner(second)

        first_owner.start()
        second_owner.start()

        assert first_owner.adapter is first
        assert second_owner.adapter is second


class TestAccessIsGoverned:
    def test_the_adapter_is_unreachable_before_start(self) -> None:
        """T-2, A-2: refused with the port's own name for a missing session."""
        owner = BrokerOwner(MockBrokerAdapter())

        with pytest.raises(BrokerNotConnectedError):
            _ = owner.adapter

    def test_the_adapter_is_unreachable_again_after_stop(self) -> None:
        """T-6, A-2: stopping revokes access, it does not merely disconnect."""
        owner = BrokerOwner(MockBrokerAdapter())
        owner.start()
        owner.stop()

        with pytest.raises(BrokerNotConnectedError):
            _ = owner.adapter

    def test_exactly_one_public_member_reaches_the_adapter(self) -> None:
        """A-1: three public names, and only one of them is a route to the port."""
        owner = BrokerOwner(MockBrokerAdapter())

        assert {name for name in dir(owner) if not name.startswith("_")} == {
            "adapter",
            "start",
            "stop",
        }

    def test_the_module_exposes_no_owner_and_no_adapter_to_import(self) -> None:
        """A-3, H-2: access is granted downward, so there is nothing here to acquire."""
        assert broker_ownership.__all__ == ["BrokerOwner"]

        instances = {
            name
            for name, value in vars(broker_ownership).items()
            if isinstance(value, BrokerOwner | MockBrokerAdapter)
        }

        assert instances == set()


class TestStart:
    def test_start_connects_the_adapter_and_opens_access(self) -> None:
        """T-4, H-5."""
        adapter = MockBrokerAdapter()
        owner = BrokerOwner(adapter)

        owner.start()

        assert adapter.is_connected() is True
        assert owner.adapter is adapter

    def test_starting_twice_raises(self) -> None:
        """T-5, H-6: not a silent no-op, which would decide a recovery policy."""
        owner = BrokerOwner(MockBrokerAdapter())
        owner.start()

        with pytest.raises(RuntimeError):
            owner.start()

    def test_a_refused_second_start_does_not_disturb_the_first(self) -> None:
        """T-5: the session that was already established survives the failed call."""
        adapter = MockBrokerAdapter()
        owner = BrokerOwner(adapter)
        owner.start()

        with pytest.raises(RuntimeError):
            owner.start()

        assert adapter.is_connected() is True
        assert owner.adapter is adapter


class TestStop:
    def test_stop_disconnects_the_adapter(self) -> None:
        """T-6, H-7."""
        adapter = MockBrokerAdapter()
        owner = BrokerOwner(adapter)
        owner.start()

        owner.stop()

        assert adapter.is_connected() is False

    def test_stop_before_start_does_nothing_and_does_not_raise(self) -> None:
        """T-7, H-8: an unwind path that raises can strand a session."""
        adapter = MockBrokerAdapter()
        owner = BrokerOwner(adapter)

        owner.stop()

        assert adapter.is_connected() is False
        with pytest.raises(BrokerNotConnectedError):
            _ = owner.adapter

    def test_stopping_twice_does_not_raise(self) -> None:
        """T-8, H-8."""
        adapter = MockBrokerAdapter()
        owner = BrokerOwner(adapter)
        owner.start()
        owner.stop()

        owner.stop()

        assert adapter.is_connected() is False


class TestAConnectFailurePropagates:
    """T-9, H-10: the owner reports what the venue did and decides nothing about it."""

    @staticmethod
    def _owner_whose_connect_will_fail() -> (
        tuple[BrokerOwner, MockBrokerAdapter, BrokerConnectionError]
    ):
        adapter = MockBrokerAdapter()
        failure = BrokerConnectionError("the venue refused the session")
        adapter.venue.schedule_failure("connect", failure)
        return BrokerOwner(adapter), adapter, failure

    def test_the_venues_own_error_reaches_the_caller_unchanged(self) -> None:
        owner, _, failure = self._owner_whose_connect_will_fail()

        with pytest.raises(BrokerConnectionError) as raised:
            owner.start()

        assert raised.value is failure

    def test_a_failed_start_leaves_the_owner_un_started(self) -> None:
        owner, adapter, _ = self._owner_whose_connect_will_fail()

        with pytest.raises(BrokerConnectionError):
            owner.start()

        assert adapter.is_connected() is False
        with pytest.raises(BrokerNotConnectedError):
            _ = owner.adapter

    def test_a_failed_start_can_still_be_unwound(self) -> None:
        owner, adapter, _ = self._owner_whose_connect_will_fail()

        with pytest.raises(BrokerConnectionError):
            owner.start()

        owner.stop()

        assert adapter.is_connected() is False

    def test_the_owner_can_start_once_the_venue_stops_refusing(self) -> None:
        """The failure was one scheduled call, not a state the owner got stuck in."""
        owner, adapter, _ = self._owner_whose_connect_will_fail()
        with pytest.raises(BrokerConnectionError):
            owner.start()

        owner.start()

        assert adapter.is_connected() is True
        assert owner.adapter is adapter
