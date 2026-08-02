"""Deployment environment identifiers.

The environment selects which layer of the ``config/`` tree is overlaid on top
of ``config/default/`` and governs the safety assertions applied in
:mod:`atlas.config.settings`.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["Environment"]


class Environment(StrEnum):
    """Deployment environment a process is running in.

    The member values are also the directory names under ``config/``.
    """

    DEVELOPMENT = "development"
    DEMO = "demo"
    PRODUCTION = "production"

    @property
    def is_live(self) -> bool:
        """Whether this environment is permitted to touch a real-money account.

        Returns:
            ``True`` for :attr:`PRODUCTION`, ``False`` otherwise.
        """
        return self is Environment.PRODUCTION
