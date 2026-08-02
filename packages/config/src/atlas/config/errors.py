"""Exceptions raised while resolving Project Atlas configuration."""

from __future__ import annotations

__all__ = ["ConfigurationError"]


class ConfigurationError(RuntimeError):
    """Configuration could not be located, parsed, or is internally inconsistent.

    Raised eagerly at start-up rather than tolerated, so that a misconfigured
    process fails before it can act on incorrect settings.
    """
