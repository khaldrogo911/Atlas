"""Process entrypoint for the Atlas core service.

At ATLAS-TASK-0001 the core service has no trading pipeline to run. What it
does have is a configuration contract, and the most valuable thing this
entrypoint can do is prove that contract holds in the environment it was
deployed into: resolve every setting, enforce the environment's invariants,
construct the broker adapter those settings describe, emit a machine-readable
startup record, and exit.

Exit codes:
    0: configuration resolved, satisfies every invariant, and describes a
       broker session that could be opened.
    2: configuration is missing, unreadable or invalid, or its broker section
       cannot be translated into a usable session configuration.
"""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, Any

from atlas.apps.core.composition import build_broker_owner
from atlas.config import ConfigurationError, load_settings

if TYPE_CHECKING:
    from atlas.config import AtlasSettings

__all__ = ["build_startup_record", "main"]

EXIT_OK = 0
EXIT_CONFIG_ERROR = 2


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
    """Validate the deployment's configuration and report the outcome.

    Returns:
        ``EXIT_OK`` when configuration is valid, ``EXIT_CONFIG_ERROR`` otherwise.

    Notes:
        The adapter is built before the startup record is written, so a broker
        section that cannot open a session leaves stdout empty and is reported
        the same way every other configuration failure is.
    """
    try:
        settings = load_settings()
        # Constructed and dropped. ADR-0015 decided that startup builds the
        # adapter; nothing yet decides what holds one afterwards, and inventing
        # a home for it here would answer a question no record has answered.
        build_broker_owner(settings)
    except ConfigurationError as exc:
        record = {"event": "atlas.core.startup_failed", "error": str(exc)}
        sys.stderr.write(json.dumps(record) + "\n")
        return EXIT_CONFIG_ERROR

    sys.stdout.write(json.dumps(build_startup_record(settings)) + "\n")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
