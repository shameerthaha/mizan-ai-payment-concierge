"""\
Payment Concierge — Rule engine thin facade.

This module is preserved as a backward-compatible facade. New code should
import directly from ``payment_concierge.services.engine``.

The real logic lives in:
- ``engine.fixture_backend.FixtureBackend`` (default, in-memory test data)
- ``engine.db_backend.DbBackend`` (database-backed, when Pratibha's model lands)

Switch the active backend by setting ``RULE_ENGINE_BACKEND=db`` in the
environment and providing a ``DATABASE_URL``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from payment_concierge.schemas.models import BankConfig, CustomerAccount, SolutionItem
from payment_concierge.services.engine import get_backend

_backend = get_backend()


def get_bank_config(bank_id: str) -> Optional[BankConfig]:
    """Thin delegate — see :meth:`RuleEngineBackend.get_bank_config`."""
    return _backend.get_bank_config(bank_id)


def lookup_customer(
    identifier: str, bank_id: str = "EMIRATES_NBD"
) -> Optional[CustomerAccount]:
    """Thin delegate — see :meth:`RuleEngineBackend.lookup_customer`."""
    return _backend.lookup_customer(identifier, bank_id)


def get_bucket_for_dpd(
    dpd_days: int, bank_id: str = "EMIRATES_NBD"
) -> Optional[str]:
    """Thin delegate — see :meth:`RuleEngineBackend.get_bucket_for_dpd`."""
    return _backend.get_bucket_for_dpd(dpd_days, bank_id)


def rank_solutions(
    customer: CustomerAccount,
    bank_id: str = "EMIRATES_NBD",
) -> list[SolutionItem]:
    """Thin delegate — see :meth:`RuleEngineBackend.rank_solutions`."""
    return _backend.rank_solutions(customer, bank_id)