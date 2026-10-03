"""
Brain Engine — abstract backend interface.

Implementations:
- ``FixtureBackend`` — in-memory fixture data (default)
- ``DbBackend`` — SQLAlchemy-backed (when Pratibha's Excel model lands)

Each implementation must pre-compute all decisions. No live lookups during
a call — the agent receives everything it needs (balance, solutions, compliance
context) before the conversation starts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from payment_concierge.schemas.models import (
    BankConfig,
    CustomerAccount,
    SolutionItem,
)


class RuleEngineBackend(ABC):
    """Abstract interface for the brain engine backend.

    Pratibha's Excel model (due 7-8 Oct) defines the rule engine that
    determines customer treatment based on bank-specific tuning parameters.
    Once the Excel model is complete, the ``DbBackend`` will consume its
    output via the importer module.
    """

    @abstractmethod
    def get_bank_config(self, bank_id: str) -> Optional[BankConfig]:
        """Return the full bank configuration for *bank_id*.

        Returns ``None`` if the bank is not configured.
        """

    @abstractmethod
    def lookup_customer(
        self, identifier: str, bank_id: str = "EMIRATES_NBD"
    ) -> Optional[CustomerAccount]:
        """Look up a customer by account number, phone, or email.

        Returns ``None`` if no match is found.
        """

    @abstractmethod
    def get_bucket_for_dpd(
        self, dpd_days: int, bank_id: str = "EMIRATES_NBD"
    ) -> Optional[str]:
        """Return the DPD bucket ID for a given days-past-due value.

        Uses the bank's configured DPD buckets to classify the delinquency
        stage.
        """

    @abstractmethod
    def rank_solutions(
        self,
        customer: CustomerAccount,
        bank_id: str = "EMIRATES_NBD",
    ) -> list[SolutionItem]:
        """Pre-compute ranked payment solutions for a customer.

        This is the brain's core output — the agent receives these options
        before the call begins and presents them during the conversation.
        No live lookups occur during the call.
        """

    @abstractmethod
    def list_configured_banks(self) -> list[str]:
        """Return bank IDs for all configured banks in this backend."""