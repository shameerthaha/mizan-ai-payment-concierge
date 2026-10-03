"""
Payment Concierge — Brain Engine.

The brain engine precomputes ALL decisions before a call is placed (no live
lookups during the call). It evaluates bank-specific configuration, customer
data, and compliance rules to determine the outstanding amount, DPD bucket,
and ranked settlement solutions that the ElevenLabs agent presents during
the conversation.

Two backends exist:
- ``fixture`` — in-memory test data (default, works out of the box)
- ``db`` — SQLAlchemy-backed (activate when Pratibha's model lands)

Switch with ``RULE_ENGINE_BACKEND=db`` in environment.
"""

from __future__ import annotations

from payment_concierge.config.settings import settings
from payment_concierge.services.engine.fixture_backend import FixtureBackend
from payment_concierge.services.engine.interfaces import RuleEngineBackend

# Lazy-loaded backend singleton
_backend: RuleEngineBackend | None = None


def get_backend() -> RuleEngineBackend:
    """Return the active rule engine backend (singleton per process)."""
    global _backend
    if _backend is not None:
        return _backend

    if settings.rule_engine_backend == "db":
        from payment_concierge.services.engine.db_backend import DbBackend
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        if not settings.database_url:
            raise RuntimeError(
                "DATABASE_URL must be set when RULE_ENGINE_BACKEND=db"
            )
        engine = create_engine(settings.database_url)
        Session = sessionmaker(bind=engine)
        _backend = DbBackend(Session)
    else:
        _backend = FixtureBackend()

    return _backend


def reset_backend() -> None:
    """Reset the backend singleton (useful in tests)."""
    global _backend
    _backend = None


__all__ = [
    "get_backend",
    "reset_backend",
    "FixtureBackend",
    "RuleEngineBackend",
]