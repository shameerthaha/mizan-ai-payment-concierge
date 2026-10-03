"""
Brain Engine — Excel/JSON import pipeline.

Pratibha's Excel model (50-100 parameters per bank, due 7-8 Oct) defines
the rule engine that determines customer treatment. This module consumes
her Excel output and prepares it for database insertion.

The expected workflow:
1. Pratibha exports the Excel model to JSON
2. ``validate_import_data()`` checks the data shape
3. ``import_bank_config_from_json()`` produces ORM-ready bank configs
4. ``import_customers_from_json()`` produces ORM-ready customer records
5. A database write step (manual or scripted) persists the data

The ``get_expected_excel_schema()`` function documents the exact format
Pratibha's export should follow.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional


def get_expected_excel_schema() -> dict:
    """Return the JSON schema that Pratibha's Excel export should match.

    The engine expects one JSON file per bank with the following structure.
    """
    return {
        "type": "object",
        "title": "BankConfigExport",
        "description": "Per-bank collections configuration exported from Excel",
        "properties": {
            "bank_id": {
                "type": "string",
                "description": "Unique bank identifier (e.g. EMIRATES_NBD)",
            },
            "product_type": {
                "type": "string",
                "enum": ["conventional", "islamic"],
                "description": "Bank product type",
            },
            "ptp_policy": {
                "type": "object",
                "properties": {
                    "max_ptp_per_cycle": {"type": "integer"},
                    "ptp_window_days": {"type": "integer"},
                    "re_ptp_allowed": {"type": "boolean"},
                    "breach_action": {"type": "string"},
                },
            },
            "legal_referral_dpd": {"type": "integer"},
            "write_off_dpd": {"type": "integer"},
            "contact_window_start": {"type": "string", "pattern": "^\\d{2}:\\d{2}$"},
            "contact_window_end": {"type": "string", "pattern": "^\\d{2}:\\d{2}$"},
            "aecb_reporting": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "frequency": {"type": "string"},
                },
            },
            "dpd_buckets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "bucket_id": {"type": "string"},
                        "dpd_min": {"type": "integer"},
                        "dpd_max": {"type": "integer"},
                        "label": {"type": "string"},
                        "contact_frequency_cap_per_day": {"type": "integer"},
                        "contact_frequency_cap_per_week": {"type": "integer"},
                    },
                },
            },
            "escalation_tiers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tier_id": {"type": "string"},
                        "dpd_range": {"type": "string"},
                        "channel_mix": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "script_intensity_level": {"type": "integer"},
                        "human_handoff_condition": {"type": "string"},
                    },
                },
            },
            "settlement_authority_matrix": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tier_id": {"type": "string"},
                        "max_discount_pct": {"type": "number"},
                        "max_waiver_amount": {"type": "number"},
                        "requires_human_approval": {"type": "boolean"},
                    },
                },
            },
            "customers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "name": {"type": "string"},
                        "phone": {"type": "string"},
                        "email": {"type": "string"},
                        "product_type": {
                            "type": "string",
                            "enum": ["conventional", "islamic"],
                        },
                        "outstanding_principal": {"type": "number"},
                        "accrued_interest": {"type": "number"},
                        "late_fees": {"type": "number"},
                        "total_outstanding": {"type": "number"},
                        "dpd_days": {"type": "integer"},
                        "missed_payments": {"type": "integer"},
                        "ptp_breaches": {"type": "integer"},
                        "in_hardship_program": {"type": "boolean"},
                    },
                },
            },
        },
        "required": ["bank_id"],
    }


def validate_import_data(data: dict) -> list[str]:
    """Validate a bank config export dict.

    Returns a list of error messages. An empty list means the data is valid.
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["Import data must be a dict (bank config export)"]

    if "bank_id" not in data:
        errors.append("Missing required field: bank_id")

    product_type = data.get("product_type", "conventional")
    if product_type not in ("conventional", "islamic"):
        errors.append(
            f"Invalid product_type: '{product_type}'. Must be 'conventional' or 'islamic'."
        )

    dpd_buckets = data.get("dpd_buckets", [])
    if not isinstance(dpd_buckets, list):
        errors.append("dpd_buckets must be an array")
    else:
        for i, bucket in enumerate(dpd_buckets):
            if not isinstance(bucket, dict):
                errors.append(f"dpd_buckets[{i}]: expected object")
                continue
            if "bucket_id" not in bucket:
                errors.append(f"dpd_buckets[{i}]: missing bucket_id")

    escalation_tiers = data.get("escalation_tiers", [])
    if not isinstance(escalation_tiers, list):
        errors.append("escalation_tiers must be an array")

    customers = data.get("customers", [])
    if not isinstance(customers, list):
        errors.append("customers must be an array")
    else:
        for i, c in enumerate(customers):
            if not isinstance(c, dict):
                errors.append(f"customers[{i}]: expected object")
                continue
            for field in ("customer_id", "name", "phone"):
                if field not in c:
                    errors.append(f"customers[{i}]: missing required field '{field}'")

    return errors


def import_bank_config_from_json(data: dict) -> dict:
    """Prepare a validated bank config dict for DB insertion.

    Returns a dict matching BankConfigModel fields. The caller is responsible
    for persisting it (e.g. via SQLAlchemy INSERT or a management script).

    Raises ``ValueError`` with details if validation fails.
    """
    errors = validate_import_data(data)
    if errors:
        raise ValueError(f"Import validation failed:\n" + "\n".join(errors))

    now = datetime.utcnow()
    ptp = data.get("ptp_policy", {})
    aecb = data.get("aecb_reporting", {})

    return {
        "bank_id": data["bank_id"],
        "product_type": data.get("product_type", "conventional"),
        "ptp_max_per_cycle": ptp.get("max_ptp_per_cycle", 2),
        "ptp_window_days": ptp.get("ptp_window_days", 7),
        "re_ptp_allowed": ptp.get("re_ptp_allowed", True),
        "breach_action": ptp.get("breach_action", "escalate"),
        "legal_referral_dpd": data.get("legal_referral_dpd", 120),
        "write_off_dpd": data.get("write_off_dpd", 180),
        "aecb_reporting_enabled": aecb.get("enabled", True),
        "aecb_frequency": aecb.get("frequency", "monthly"),
        "contact_window_start": data.get("contact_window_start", "09:00"),
        "contact_window_end": data.get("contact_window_end", "20:00"),
        "created_at": now,
        "updated_at": now,
    }


def import_customers_from_json(data: dict) -> list[dict]:
    """Prepare a list of validated customer dicts for DB insertion.

    Returns a list of dicts matching CustomerModel fields.
    Returns an empty list if no customers are in the data.
    """
    customers_raw = data.get("customers", [])
    if not customers_raw:
        return []

    if not isinstance(customers_raw, list):
        return []

    now = datetime.utcnow()
    bank_id = data.get("bank_id", "UNKNOWN")
    results: list[dict] = []

    for c in customers_raw:
        if not isinstance(c, dict):
            continue
        results.append(
            {
                "customer_id": c.get("customer_id", ""),
                "bank_id": bank_id,
                "name": c.get("name", ""),
                "phone": c.get("phone", ""),
                "email": c.get("email"),
                "product_type": c.get("product_type", "conventional"),
                "outstanding_principal": Decimal(str(c.get("outstanding_principal", 0))),
                "accrued_interest": Decimal(str(c.get("accrued_interest", 0))),
                "late_fees": Decimal(str(c.get("late_fees", 0))),
                "total_outstanding": Decimal(str(c.get("total_outstanding", 0))),
                "dpd_days": c.get("dpd_days", 0),
                "missed_payments": c.get("missed_payments", 0),
                "ptp_breaches": c.get("ptp_breaches", 0),
                "in_hardship_program": c.get("in_hardship_program", False),
                "created_at": now,
                "updated_at": now,
            }
        )

    return results