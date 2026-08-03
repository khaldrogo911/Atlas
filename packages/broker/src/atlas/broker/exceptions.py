"""The failures a :class:`~atlas.broker.adapter.BrokerAdapter` is allowed to raise.

Every ``Raises:`` clause in the port names a class from this module. That is the
whole purpose of the hierarchy: a caller writes ``except BrokerTimeoutError``
and gets the same behaviour from every venue, because the venue-specific code
that produced it was classified at the adapter boundary rather than passed up as
a number for the caller to interpret.

Shape
-----
The tree is arranged around *what a caller can do next*, which is the only
question an exception type is useful for answering::

    BrokerError
    ├── BrokerConnectionError          the venue is unreachable — retry later
    │   ├── BrokerNotConnectedError    no session — connect first
    │   └── BrokerTimeoutError         no answer in time — may have happened
    ├── BrokerAuthenticationError      credentials or permission — a human fixes it
    ├── BrokerRequestError             the venue refused a well-formed request
    │   ├── BrokerSymbolNotFoundError
    │   ├── BrokerOrderNotFoundError
    │   ├── BrokerPositionNotFoundError
    │   ├── BrokerOrderRejectedError   refused this order — read the reason
    │   └── BrokerInsufficientMarginError   resize or free margin
    ├── BrokerDataUnavailableError     reachable, but holds nothing matching
    └── BrokerUnsupportedOperationError  this venue cannot do this at all

Two placements are deliberate and worth stating, because the obvious
alternatives are actively harmful:

``BrokerAuthenticationError`` is **not** under ``BrokerConnectionError``. A
supervision loop retries connection faults; rejected credentials will never
succeed on retry, and burying them under the retryable branch produces a bot
that hammers a venue with a password that cannot work.

``BrokerTimeoutError`` is under ``BrokerConnectionError`` but means something
sharper than its parent: the request may have been *executed*. A caller
recovering from a timeout on an order must reconcile against
:meth:`~atlas.broker.adapter.BrokerAdapter.get_orders` rather than assume
failure. The port says so at every method that can raise it.

Structured context
------------------
Every class carries its detail as attributes, never only inside the message.
Code that needs to know which symbol was missing reads ``error.symbol``; it does
not parse a sentence that a later edit may reword. :attr:`BrokerError.context`
collects whatever a given instance carries, which is what a structured log
record wants.

Constructors do no validation, no normalisation and no I/O. These objects are
built on the failure path — often a degraded one, sometimes while the venue is
already unreachable — and an exception whose construction can itself fail is a
liability exactly when it is needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from atlas.broker.models import Money

__all__ = [
    "BrokerAuthenticationError",
    "BrokerConnectionError",
    "BrokerDataUnavailableError",
    "BrokerError",
    "BrokerInsufficientMarginError",
    "BrokerNotConnectedError",
    "BrokerOrderNotFoundError",
    "BrokerOrderRejectedError",
    "BrokerPositionNotFoundError",
    "BrokerRequestError",
    "BrokerSymbolNotFoundError",
    "BrokerTimeoutError",
    "BrokerUnsupportedOperationError",
]


class BrokerError(Exception):
    """Base of every failure raised by a broker adapter.

    Catching this catches everything the port can raise, which is what a
    supervision loop wants and what a caller making a trading decision does
    not: the subclasses exist so that "the venue is down" and "this order was
    refused" are not handled by the same branch.

    Attributes:
        message: What failed, in prose.
        venue: Which broker produced it, for a log record that may cover
            several adapters at once.
        code: The venue's own numeric code, unmapped and unaltered. Kept so
            that a specific broker quirk can still be diagnosed after the
            classification has thrown away the distinction.
    """

    def __init__(self, message: str, *, venue: str | None = None, code: int | None = None) -> None:
        """Build the error.

        Args:
            message: What failed.
            venue: The broker that produced it, if known.
            code: The venue's own numeric code, if it supplied one.
        """
        super().__init__(message)
        self.message = message
        self.venue = venue
        self.code = code

    @property
    def context(self) -> dict[str, object]:
        """The structured detail this instance carries.

        Returns:
            Every attribute that was actually set, excluding ``message``, which
            a log record carries in its own right. Subclasses need not override
            this: whatever fields they assign appear here automatically.
        """
        return {
            name: value
            for name, value in vars(self).items()
            if name != "message" and value is not None
        }


class BrokerConnectionError(BrokerError):
    """The venue could not be reached.

    The retryable branch of the tree. A caller may back off and try again; the
    condition is expected to be transient and outside Atlas's control.
    """


class BrokerNotConnectedError(BrokerConnectionError):
    """A request was issued before a session was established.

    Distinct from its parent because this one is Atlas's own fault and is fixed
    by calling :meth:`~atlas.broker.adapter.BrokerAdapter.connect`, not by
    waiting.
    """


class BrokerTimeoutError(BrokerConnectionError):
    """The venue did not answer in time.

    The request may still have been executed. For anything that changes state —
    placing, modifying, cancelling, closing — a caller must reconcile rather
    than assume it failed and retry, which is how an order gets sent twice.

    Attributes:
        operation: Which call timed out, so a recovery path knows whether
            reconciliation is needed at all. A ``get_symbols`` timeout is safe
            to retry blindly; a ``place_order`` timeout is not.
    """

    def __init__(
        self,
        message: str,
        *,
        operation: str | None = None,
        venue: str | None = None,
        code: int | None = None,
    ) -> None:
        """Build the error.

        Args:
            message: What failed.
            operation: The port method that timed out, if known.
            venue: The broker that produced it, if known.
            code: The venue's own numeric code, if it supplied one.
        """
        super().__init__(message, venue=venue, code=code)
        self.operation = operation


class BrokerAuthenticationError(BrokerError):
    """The venue rejected the credentials, or trading permission is withheld.

    Deliberately not a :class:`BrokerConnectionError`: retrying cannot fix it.
    Someone has to correct a credential or enable algorithmic trading, and a
    retry loop that treats this as transient will hammer the venue with a login
    that is never going to work.

    Carries no credential detail, by construction. It is raised on a path that
    is about to be logged.
    """


class BrokerRequestError(BrokerError):
    """The venue was reached and understood the request, and refused it.

    Nothing here is fixed by retrying the identical request. Either the request
    must change or the account must.
    """


class BrokerSymbolNotFoundError(BrokerRequestError):
    """The venue does not offer the requested instrument.

    Attributes:
        symbol: The instrument that was asked for. Venues differ on suffixes —
            ``EURUSD`` against ``EURUSD.pro`` — so the code that was actually
            sent is the useful thing to record.
    """

    def __init__(
        self,
        message: str,
        *,
        symbol: str | None = None,
        venue: str | None = None,
        code: int | None = None,
    ) -> None:
        """Build the error.

        Args:
            message: What failed.
            symbol: The instrument code that was not found.
            venue: The broker that produced it, if known.
            code: The venue's own numeric code, if it supplied one.
        """
        super().__init__(message, venue=venue, code=code)
        self.symbol = symbol


class BrokerOrderNotFoundError(BrokerRequestError):
    """The venue does not know the given order.

    Attributes:
        order_id: The ticket that was not found. Commonly the order filled or
            was cancelled between the read and the amendment.
    """

    def __init__(
        self,
        message: str,
        *,
        order_id: str | None = None,
        venue: str | None = None,
        code: int | None = None,
    ) -> None:
        """Build the error.

        Args:
            message: What failed.
            order_id: The order ticket that was not found.
            venue: The broker that produced it, if known.
            code: The venue's own numeric code, if it supplied one.
        """
        super().__init__(message, venue=venue, code=code)
        self.order_id = order_id


class BrokerPositionNotFoundError(BrokerRequestError):
    """The venue does not know the given position, or it is already closed.

    Attributes:
        position_id: The ticket that was not found.
    """

    def __init__(
        self,
        message: str,
        *,
        position_id: str | None = None,
        venue: str | None = None,
        code: int | None = None,
    ) -> None:
        """Build the error.

        Args:
            message: What failed.
            position_id: The position ticket that was not found.
            venue: The broker that produced it, if known.
            code: The venue's own numeric code, if it supplied one.
        """
        super().__init__(message, venue=venue, code=code)
        self.position_id = position_id


class BrokerOrderRejectedError(BrokerRequestError):
    """The venue refused the order.

    The catch-all verdict of a trade server: market closed, price off, volume
    outside the instrument's bounds, instrument in close-only mode, and dozens
    of others that differ by venue. The classification stops here on purpose —
    inventing one Atlas type per venue reason would put every venue's quirks
    into the domain vocabulary.

    Attributes:
        reason: The venue's own explanation, verbatim and unparsed.

    Note:
        :attr:`~BrokerError.code` holds the venue's numeric verdict, so a caller
        that genuinely needs to distinguish two reasons at the same venue still
        can, without every other caller inheriting the vocabulary.
    """

    def __init__(
        self,
        message: str,
        *,
        reason: str | None = None,
        venue: str | None = None,
        code: int | None = None,
    ) -> None:
        """Build the error.

        Args:
            message: What failed.
            reason: The venue's own explanation of the refusal.
            venue: The broker that produced it, if known.
            code: The venue's numeric verdict, if it supplied one.
        """
        super().__init__(message, venue=venue, code=code)
        self.reason = reason


class BrokerInsufficientMarginError(BrokerRequestError):
    """The account cannot support the order.

    Separate from :class:`BrokerOrderRejectedError` because the response is
    different in kind: this one is answered by sending a smaller order or
    freeing margin, and it is the one rejection a sizing layer can act on
    automatically.

    Attributes:
        required: What the venue said the order would cost in margin.
        available: What the account had free.

    Note:
        Both are optional because not every venue reports them on a refusal.
        When a venue does not, the fields stay ``None`` rather than being
        filled with a plausible figure — an invented margin number is worse
        than an absent one to anything that resizes on it.
    """

    def __init__(
        self,
        message: str,
        *,
        required: Money | None = None,
        available: Money | None = None,
        venue: str | None = None,
        code: int | None = None,
    ) -> None:
        """Build the error.

        Args:
            message: What failed.
            required: Margin the order needed, if the venue reported it.
            available: Margin the account had free, if the venue reported it.
            venue: The broker that produced it, if known.
            code: The venue's own numeric code, if it supplied one.
        """
        super().__init__(message, venue=venue, code=code)
        self.required = required
        self.available = available


class BrokerDataUnavailableError(BrokerError):
    """The venue is reachable but holds no data satisfying the request.

    Not a :class:`BrokerRequestError`: nothing was refused. The instrument
    exists, the request was valid, and the venue simply has no quote yet, no
    bars that far back, or no deal history for the ticket. A caller may
    legitimately treat this as "not yet" rather than as a fault.
    """


class BrokerUnsupportedOperationError(BrokerError):
    """This venue cannot perform the operation at all.

    A permanent property of the venue, not of the request: a replay source
    cannot stream, a snapshot feed has no order entry. Distinct from
    ``NotImplementedError``, which says Atlas has not written the code yet —
    this says there is no code to write.

    Attributes:
        operation: The port method the venue does not support.
    """

    def __init__(
        self,
        message: str,
        *,
        operation: str | None = None,
        venue: str | None = None,
        code: int | None = None,
    ) -> None:
        """Build the error.

        Args:
            message: What failed.
            operation: The port method that is unsupported.
            venue: The broker that produced it, if known.
            code: The venue's own numeric code, if it supplied one.
        """
        super().__init__(message, venue=venue, code=code)
        self.operation = operation
