"""
Brain Engine — SQLAlchemy ORM models for the bank configuration database.

Pratibha's Excel model output populates these tables. All columns allow
nulls or carry sensible defaults so the import pipeline can start with
partial data and fill in as the model matures.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all brain engine models."""


# ─── Bank configuration ────────────────────────────────────────────────────────


class BankConfigModel(Base):
    """Per-bank configuration — one row per bank."""

    __tablename__ = "bank_config"

    bank_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    product_type: Mapped[Optional[str]] = mapped_column(
        String(20), default="conventional"
    )
    ptp_max_per_cycle: Mapped[Optional[int]] = mapped_column(Integer, default=2)
    ptp_window_days: Mapped[Optional[int]] = mapped_column(Integer, default=7)
    re_ptp_allowed: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    breach_action: Mapped[Optional[str]] = mapped_column(
        String(50), default="escalate"
    )
    legal_referral_dpd: Mapped[Optional[int]] = mapped_column(Integer, default=120)
    write_off_dpd: Mapped[Optional[int]] = mapped_column(Integer, default=180)
    aecb_reporting_enabled: Mapped[Optional[bool]] = mapped_column(
        Boolean, default=True
    )
    aecb_frequency: Mapped[Optional[str]] = mapped_column(
        String(20), default="monthly"
    )
    contact_window_start: Mapped[Optional[str]] = mapped_column(
        String(5), default="09:00"
    )
    contact_window_end: Mapped[Optional[str]] = mapped_column(
        String(5), default="20:00"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    dpd_buckets: Mapped[list["DPDBucketModel"]] = relationship(
        back_populates="bank", cascade="all, delete-orphan"
    )
    escalation_tiers: Mapped[list["EscalationTierModel"]] = relationship(
        back_populates="bank", cascade="all, delete-orphan"
    )
    settlement_authorities: Mapped[list["SettlementAuthorityModel"]] = relationship(
        back_populates="bank", cascade="all, delete-orphan"
    )


class DPDBucketModel(Base):
    """DPD bucket definition — one row per bucket per bank."""

    __tablename__ = "dpd_buckets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bank_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("bank_config.bank_id"), nullable=False
    )
    bucket_id: Mapped[str] = mapped_column(String(20), nullable=False)
    dpd_min: Mapped[int] = mapped_column(Integer, default=0)
    dpd_max: Mapped[int] = mapped_column(Integer, default=9999)
    label: Mapped[Optional[str]] = mapped_column(String(50))
    contact_frequency_cap_per_day: Mapped[Optional[int]] = mapped_column(
        Integer, default=3
    )
    contact_frequency_cap_per_week: Mapped[Optional[int]] = mapped_column(
        Integer, default=10
    )

    bank: Mapped["BankConfigModel"] = relationship(back_populates="dpd_buckets")


class EscalationTierModel(Base):
    """Escalation tier definition — one row per escalation tier per bank."""

    __tablename__ = "escalation_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bank_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("bank_config.bank_id"), nullable=False
    )
    tier_id: Mapped[str] = mapped_column(String(20), nullable=False)
    dpd_range: Mapped[str] = mapped_column(String(20), default="0-29")
    channel_mix: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    script_intensity_level: Mapped[Optional[int]] = mapped_column(
        Integer, default=1
    )
    human_handoff_condition: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )

    bank: Mapped["BankConfigModel"] = relationship(back_populates="escalation_tiers")


class SettlementAuthorityModel(Base):
    """Settlement authority per escalation tier — who can offer what discount."""

    __tablename__ = "settlement_authorities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bank_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("bank_config.bank_id"), nullable=False
    )
    tier_id: Mapped[str] = mapped_column(String(20), nullable=False)
    max_discount_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    max_waiver_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    requires_human_approval: Mapped[Optional[bool]] = mapped_column(
        Boolean, default=False
    )

    bank: Mapped["BankConfigModel"] = relationship(
        back_populates="settlement_authorities"
    )


# ─── Customer data ─────────────────────────────────────────────────────────────


class CustomerModel(Base):
    """Customer account data used by the collections engine."""

    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    bank_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("bank_config.bank_id"), nullable=False
    )
    name: Mapped[Optional[str]] = mapped_column(String(200))
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    product_type: Mapped[Optional[str]] = mapped_column(
        String(20), default="conventional"
    )
    outstanding_principal: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2), default=0
    )
    accrued_interest: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2), default=0
    )
    late_fees: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2), default=0
    )
    total_outstanding: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2), default=0
    )
    dpd_days: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    current_bucket: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    missed_payments: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    ptp_breaches: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    in_hardship_program: Mapped[Optional[bool]] = mapped_column(
        Boolean, default=False
    )
    customer_since: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    last_contact_date: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ─── Call outcomes (post-call logging) ─────────────────────────────────────────


class CallOutcomeModel(Base):
    """Record of a completed collections call and its result."""

    __tablename__ = "call_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("customers.customer_id"), nullable=False
    )
    bank_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("bank_config.bank_id"), nullable=False
    )
    call_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(
        String(30),
        default="completed",
        comment="completed | failed | ptp_set | hardship_offered | human_handoff | disconnected",
    )
    solution_accepted_id: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    amount_committed: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )