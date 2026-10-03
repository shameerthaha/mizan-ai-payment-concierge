"""
Brain Engine — database backend implementation.

Queries the SQLAlchemy ORM models to serve bank configuration, customer
data, and settlement solutions. Activated by setting
``RULE_ENGINE_BACKEND=db`` and providing a ``DATABASE_URL``.

Pratibha's Excel model output populates the database via the ``importer``
module. Until that model lands, the backend raises ``NotImplementedError``
for operations requiring the scoring logic (``rank_solutions``).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session as SASession, sessionmaker

from payment_concierge.schemas.models import (
    AECBReporting,
    BankConfig,
    CustomerAccount,
    DPDBucket,
    EscalationTier,
    ProductType,
    PTPPolicy,
    SettlementAuthority,
    SolutionItem,
)
from payment_concierge.services.engine.db_models import (
    BankConfigModel,
    CustomerModel,
    DPDBucketModel,
    EscalationTierModel,
    SettlementAuthorityModel,
)
from payment_concierge.services.engine.interfaces import RuleEngineBackend


def _orm_bank_to_pydantic(orm_row: BankConfigModel) -> BankConfig:
    """Convert an ORM BankConfigModel row to a Pydantic BankConfig."""
    return BankConfig(
        bank_id=orm_row.bank_id,
        product_type=(
            ProductType.conventional
            if orm_row.product_type == "conventional"
            else ProductType.islamic
        ),
        dpd_buckets=[
            DPDBucket(
                bucket_id=b.bucket_id,
                dpd_min=b.dpd_min,
                dpd_max=b.dpd_max,
                label=b.label,  # type: ignore[arg-type]
                contact_frequency_cap_per_day=b.contact_frequency_cap_per_day or 3,
                contact_frequency_cap_per_week=b.contact_frequency_cap_per_week or 10,
            )
            for b in (orm_row.dpd_buckets or [])
        ],
        escalation_tiers=[
            EscalationTier(
                tier_id=e.tier_id,
                dpd_range=e.dpd_range,
                channel_mix=e.channel_mix or [],
                script_intensity_level=e.script_intensity_level or 1,
                human_handoff_condition=e.human_handoff_condition,
            )
            for e in (orm_row.escalation_tiers or [])
        ],
        settlement_authority_matrix=[
            SettlementAuthority(
                tier_id=s.tier_id,
                max_discount_pct=s.max_discount_pct,
                max_waiver_amount=s.max_waiver_amount,
                requires_human_approval=s.requires_human_approval or False,
            )
            for s in (orm_row.settlement_authorities or [])
        ],
        ptp_policy=PTPPolicy(
            max_ptp_per_cycle=orm_row.ptp_max_per_cycle or 2,
            ptp_window_days=orm_row.ptp_window_days or 7,
            re_ptp_allowed=orm_row.re_ptp_allowed or True,
            breach_action=orm_row.breach_action or "escalate",
        ),
        legal_referral_dpd=orm_row.legal_referral_dpd or 120,
        write_off_dpd=orm_row.write_off_dpd or 180,
        aecb_reporting=AECBReporting(
            enabled=orm_row.aecb_reporting_enabled or True,
            frequency=orm_row.aecb_frequency or "monthly",
        ),
    )


def _orm_customer_to_pydantic(orm_row: CustomerModel) -> CustomerAccount:
    """Convert an ORM CustomerModel row to a Pydantic CustomerAccount."""
    return CustomerAccount(
        customer_id=orm_row.customer_id,
        name=orm_row.name or "",
        phone=orm_row.phone or "",
        email=orm_row.email,
        product_type=(
            ProductType.conventional
            if orm_row.product_type == "conventional"
            else ProductType.islamic
        ),
        outstanding_principal=orm_row.outstanding_principal or Decimal("0"),
        accrued_interest=orm_row.accrued_interest or Decimal("0"),
        late_fees=orm_row.late_fees or Decimal("0"),
        total_outstanding=orm_row.total_outstanding or Decimal("0"),
        dpd_days=orm_row.dpd_days or 0,
        current_bucket=orm_row.current_bucket,
        missed_payments=orm_row.missed_payments or 0,
        ptp_breaches=orm_row.ptp_breaches or 0,
        in_hardship_program=orm_row.in_hardship_program or False,
        customer_since=orm_row.customer_since,
        last_contact_date=orm_row.last_contact_date,
    )


class DbBackend(RuleEngineBackend):
    """Database-backed rule engine implementation.

    Requires a configured database populated by Pratibha's Excel model
    output (via the ``importer`` module).
    """

    def __init__(self, session_factory: sessionmaker[SASession]) -> None:
        """Store the session factory; sessions are opened per-query."""
        self._session_factory = session_factory

    def _get_session(self) -> SASession:
        """Open a new database session."""
        return self._session_factory()

    def get_bank_config(self, bank_id: str) -> Optional[BankConfig]:
        """Query the database for the given bank configuration."""
        with self._get_session() as session:
            row = (
                session.query(BankConfigModel)
                .filter(BankConfigModel.bank_id == bank_id)
                .first()
            )
            if row is None:
                return None
            return _orm_bank_to_pydantic(row)

    def lookup_customer(
        self, identifier: str, bank_id: str = "EMIRATES_NBD"
    ) -> Optional[CustomerAccount]:
        """Look up a customer by ID, phone, or email in the database."""
        with self._get_session() as session:
            # Try customer_id first
            row = (
                session.query(CustomerModel)
                .filter(
                    CustomerModel.customer_id == identifier,
                    CustomerModel.bank_id == bank_id,
                )
                .first()
            )
            if row is not None:
                return _orm_customer_to_pydantic(row)

            # Try phone
            row = (
                session.query(CustomerModel)
                .filter(
                    CustomerModel.phone == identifier,
                    CustomerModel.bank_id == bank_id,
                )
                .first()
            )
            if row is not None:
                return _orm_customer_to_pydantic(row)

            # Try email
            row = (
                session.query(CustomerModel)
                .filter(
                    CustomerModel.email == identifier,
                    CustomerModel.bank_id == bank_id,
                )
                .first()
            )
            if row is not None:
                return _orm_customer_to_pydantic(row)

        return None

    def get_bucket_for_dpd(
        self, dpd_days: int, bank_id: str = "EMIRATES_NBD"
    ) -> Optional[str]:
        """Classify *dpd_days* into a DPD bucket using bank config from DB."""
        config = self.get_bank_config(bank_id)
        if not config:
            return None
        for bucket in config.dpd_buckets:
            if bucket.dpd_min <= dpd_days <= bucket.dpd_max:
                return bucket.bucket_id
        return config.dpd_buckets[-1].bucket_id if config.dpd_buckets else None

    def rank_solutions(
        self,
        customer: CustomerAccount,
        bank_id: str = "EMIRATES_NBD",
    ) -> list[SolutionItem]:
        """TODO: Implement when Pratibha's Excel scoring logic lands.

        The fixture backend has a working implementation that can be used as
        a reference, but the production scoring engine will be data-driven
        from Pratibha's Excel parameter model (50-100 params per bank).
        """
        raise NotImplementedError(
            "rank_solutions requires Pratibha's Excel scoring logic. "
            "The DbBackend will implement this once her model parameters "
            "are imported via the importer module."
        )

    def list_configured_banks(self) -> list[str]:
        """Return all bank IDs present in the database."""
        with self._get_session() as session:
            rows = session.query(BankConfigModel.bank_id).all()
            return [row[0] for row in rows]