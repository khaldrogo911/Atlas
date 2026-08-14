"""Ownership of this process's broker adapter.

ADR-0013 gives the application the adapter: it holds the instance, sequences the
instance's lifecycle, and governs what receives access to it. This module is the
type that does the holding.

An owner is handed an adapter. It never builds one and never chooses one, and it
does not look at which one it was given: building would mean naming an
implementation, and nothing an owner does depends on the answer. What is
delivered here is the near side of that seam — the holding, the sequencing and
the granting — for whatever adapter a caller supplies.

Access is granted downward, never acquired upward. The adapter is reachable
through one member of an owner and through nothing else. There is no
module-level instance to import and no lookup by name, so reaching the port from
below would require a reference that someone above chose to pass.

Not synchronised
    An owner's own state — whether it has started — is protected by no lock, and
    ``start`` and ``stop`` are not safe to call from two threads at once. The
    locks inside the adapter (ADR-0007) serialise its session and know nothing
    about this object. Nothing in the application calls these methods
    concurrently, because nothing calls them at all: this limit is recorded
    here, not solved here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from atlas.broker import BrokerNotConnectedError

if TYPE_CHECKING:
    from atlas.broker import BrokerAdapter

__all__ = ["BrokerOwner"]


class BrokerOwner:
    """Holds one broker adapter and sequences its connection.

    Constructed with the adapter it will own and holding it for its own
    lifetime: there is no setter, no second adapter, and no way to release the
    one it was given. ADR-0007 assigns lifecycle sequencing to a caller, because
    "check then act" cannot be made atomic inside an adapter; this is that
    caller.

    Construction connects nothing. An adapter that starts disconnected is still
    disconnected once an owner is built around it, and :meth:`start` is the only
    thing that changes that.

    Every attribute is private by name. There is exactly one public route to the
    adapter, :attr:`adapter`, and it refuses before :meth:`start` and after
    :meth:`stop`.
    """

    def __init__(self, adapter: BrokerAdapter) -> None:
        """Take ownership of an adapter.

        Args:
            adapter: The port implementation this owner will hold, supplied by
                the caller. An owner neither builds one nor chooses between
                implementations, and it does not record or branch on which one
                it received.

        Notes:
            Performs no I/O. The adapter is stored and nothing else happens, so
            one that was disconnected when it arrived is disconnected when this
            returns.
        """
        self._adapter = adapter
        self._started = False

    @property
    def adapter(self) -> BrokerAdapter:
        """The adapter this owner holds.

        Returns:
            The instance it was constructed with, once the owner has started.

        Raises:
            BrokerNotConnectedError: If the owner has not been started, or has
                been stopped. The port's own name for "there is no session
                here", used rather than an application-local error so that one
                condition does not acquire two vocabularies.
        """
        if not self._started:
            msg = "the broker owner is not started; no adapter is available"
            raise BrokerNotConnectedError(msg)
        return self._adapter

    def start(self) -> None:
        """Connect the held adapter.

        Returns:
            Nothing. The connection snapshot the port hands back describes the
            adapter's session, and an owner has no use for it.

        Raises:
            RuntimeError: If this owner has already been started. A second start
                is a caller's mistake; treating it as a silent no-op, or as a
                reason to re-establish the session, would answer a question
                about recovery that no accepted decision answers.
            BrokerError: Whatever the adapter raised while connecting, unchanged
                and unwrapped. What to do about a venue that will not accept a
                session is not decided here, and an owner whose start failed is
                left un-started.
        """
        if self._started:
            msg = "the broker owner is already started"
            raise RuntimeError(msg)
        self._adapter.connect()
        self._started = True

    def stop(self) -> None:
        """Disconnect the held adapter, if this owner ever connected it.

        Returns:
            Nothing.

        Notes:
            A no-op on an owner that was never started and on one that has
            already been stopped. Teardown that raises can strand an open
            session, and a start that failed must still be safe to unwind.
        """
        if self._started:
            self._adapter.disconnect()
            self._started = False
