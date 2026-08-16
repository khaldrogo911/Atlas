"""Process entrypoint for the Atlas core service.

At ATLAS-TASK-0001 the core service has no trading pipeline to run. What it
does have is a configuration contract, and the most valuable thing this
entrypoint can do is prove that contract holds in the environment it was
deployed into: resolve every setting, enforce the environment's invariants,
construct the broker adapter those settings describe, open a session with it,
close that session again, emit a machine-readable startup record, and exit.

ADR-0017 decided that opening the session *is* the verification. A session that
was established is the evidence, so nothing here polls the adapter afterwards
and nothing holds it open. This process is a start-up connectivity check rather
than a long-running trading process: it acquires no run loop, and it holds no
session once :func:`main` returns.

Exit codes:
    0: configuration resolved, satisfies every invariant, and a broker session
       was opened, verified and closed again.
    1: not produced by this module, and reserved by not being produced. It is
       what CPython returns when an exception reaches the top of the process,
       so it is left to mean exactly that: something failed here that no branch
       below anticipated. Nothing is caught in order to report it, because a
       failure nobody predicted has no accurate record to write, and a
       traceback says more than an invented one would.
    2: configuration is missing, unreadable or invalid, or its broker section
       cannot be translated into a usable session configuration.
    3: configuration was usable, but the broker session could not be opened.
"""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, Any

from atlas.apps.core.composition import build_broker_owner
from atlas.broker import BrokerError
from atlas.config import ConfigurationError, load_settings

if TYPE_CHECKING:
    from atlas.config import AtlasSettings

__all__ = ["build_startup_record", "main"]

EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_BROKER_ERROR = 3


def build_startup_record(settings: AtlasSettings) -> dict[str, Any]:
    """Summarise resolved settings for the startup log.

    Only masked forms of connection strings are included, so the record is safe
    to ship to a log aggregator.

    Args:
        settings: The resolved settings object.

    Returns:
        A JSON-serialisable summary of the effective configuration.
    """
    return {
        "event": "atlas.core.startup",
        "app_name": settings.app_name,
        "environment": settings.environment.value,
        "debug": settings.debug,
        "logging": {"level": settings.logging.level, "format": settings.logging.format},
        "postgres": settings.postgres.safe_dsn,
        "redis": settings.redis.safe_url,
        "duckdb": str(settings.duckdb.path),
    }


def main() -> int:
    """Verify the deployment's configuration and its broker session, and report.

    Returns:
        ``EXIT_OK`` when a session was opened and closed again,
        ``EXIT_CONFIG_ERROR`` when the configuration is unusable, and
        ``EXIT_BROKER_ERROR`` when it was usable but no session could be opened.

    Notes:
        A broker section that cannot open a session leaves stdout empty, and so
        does one that could not be translated into a session configuration at
        all. The two are separate outcomes because only the second is fixed by
        editing configuration.
    """
    try:
        settings = load_settings()
        owner = build_broker_owner(settings)
    except ConfigurationError as exc:
        record = {"event": "atlas.core.startup_failed", "error": str(exc)}
        sys.stderr.write(json.dumps(record) + "\n")
        return EXIT_CONFIG_ERROR

    # ADR-0017: the owner is retained for the rest of this function, and stopped
    # unconditionally. `stop` is nested inside so that it runs before either
    # outcome is reported — a record written while the session was still open
    # would describe a process that had not finished checking. It is a
    # documented no-op after a failed `start`, and its disconnect does not
    # raise, so unwinding cannot mask the error that caused it.
    try:
        try:
            owner.start()
        finally:
            owner.stop()
    except BrokerError as exc:
        record = {"event": "atlas.core.broker_connect_failed", "error": str(exc)}
        sys.stderr.write(json.dumps(record) + "\n")
        return EXIT_BROKER_ERROR

    sys.stdout.write(json.dumps(build_startup_record(settings)) + "\n")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
