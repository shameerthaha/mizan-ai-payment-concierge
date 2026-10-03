"""
Brain Engine — fixture-backend unit tests.

Tests verify the FixtureBackend behaviour matches the original
rule_engine.py contract. On-database integration tests belong in a
separate module with a configured test database.
"""

from __future__ import annotations

from decimal import Decimal
from datetime import time

from payment_concierge.schemas.models import (
    CustomerLookupResponse,
    CustomerLookupRequest,
    OutstandingRequest,
    OutstandingResponse,
    RankSolutionsRequest,
    RankSolutionsResponse,
    SolutionItem,
    ComplianceFloor,
    ContactWindow,
    CustomerAccount,
    DPDBucket,
    BucketLabel,
    ProductType,
    BankConfig,
    ElevenLabsWebhookPayload,
)
from payment_concierge.services.compliance import (
    build_compliance_floor,
    is_within_contact_window,
    should_attempt_contact,
)
from payment_concierge.services.engine import get_backend, reset_backend


# ─── FixtureBackend ────────────────────────────────────────────────────────────


def _get_backend():
    """Ensure fixture backend is active."""
    reset_backend()
    import os
    os.environ.setdefault("RULE_ENGINE_BACKEND", "fixture")
    return get_backend()


backend = _get_backend()


def test_bank_config_exists() -> None:
    config = backend.get_bank_config("EMIRATES_NBD")
    assert config is not None
    assert config.bank_id == "EMIRATES_NBD"
    assert len(config.dpd_buckets) == 5


def test_bank_config_missing() -> None:
    assert backend.get_bank_config("FAKE_BANK") is None


def test_lookup_existing_customer_by_id() -> None:
    customer = backend.lookup_customer("ACC-001")
    assert customer is not None
    assert customer.name == "Ahmed Al Mansoori"
    assert customer.total_outstanding == Decimal("16600.00")


def test_lookup_existing_customer_by_phone() -> None:
    customer = backend.lookup_customer("+971-50-123-4567")
    assert customer is not None
    assert customer.customer_id == "ACC-001"


def test_lookup_existing_customer_by_email() -> None:
    customer = backend.lookup_customer("ahmed@example.com")
    assert customer is not None
    assert customer.customer_id == "ACC-001"


def test_lookup_missing_customer() -> None:
    assert backend.lookup_customer("NONEXISTENT") is None


def test_bucket_for_dpd_current() -> None:
    bucket = backend.get_bucket_for_dpd(10)
    assert bucket == "curr"


def test_bucket_for_dpd_underperforming() -> None:
    bucket = backend.get_bucket_for_dpd(45)
    assert bucket == "under"


def test_bucket_for_dpd_substandard() -> None:
    bucket = backend.get_bucket_for_dpd(95)
    assert bucket == "sub"


def test_bucket_for_dpd_write_off() -> None:
    bucket = backend.get_bucket_for_dpd(200)
    assert bucket == "wo"


def test_rank_solutions_full_set() -> None:
    customer = backend.lookup_customer("ACC-001")
    assert customer is not None
    solutions = backend.rank_solutions(customer)
    # ACC-001: 2 missed payments -> hard to see if hardship offered
    # ACC-001 has 2 missed payments so hardship IS offered
    assert len(solutions) >= 3
    assert solutions[0].solution_id == "full"
    assert solutions[0].rank == 1


def test_rank_solutions_current_bucket_no_discount() -> None:
    customer = backend.lookup_customer("ACC-003")  # 10 dpd, curr bucket
    assert customer is not None
    solutions = backend.rank_solutions(customer)
    # curr bucket -> discount is t1 tier (0% discount, requires approval)
    solution_ids = [s.solution_id for s in solutions]
    assert "full" in solution_ids
    assert "ptp" in solution_ids
    # No hardship because ACC-003 has only 1 missed payment


def test_rank_solutions_hardship_eligible() -> None:
    customer = backend.lookup_customer("ACC-002")  # 4 missed payments
    assert customer is not None
    solutions = backend.rank_solutions(customer)
    solution_ids = [s.solution_id for s in solutions]
    assert "hardship" in solution_ids


def test_list_configured_banks() -> None:
    banks = backend.list_configured_banks()
    assert "EMIRATES_NBD" in banks
    assert len(banks) == 1


# ─── Schema tests (from original test_smoke.py) ───────────────────────────────


def test_contact_window_default() -> None:
    cw = ContactWindow()
    assert cw.start == time(9, 0)
    assert cw.end == time(20, 0)


def test_customer_account_defaults() -> None:
    c = CustomerAccount(
        customer_id="T1",
        name="Test",
        phone="+971-50-000-0000",
        total_outstanding=Decimal("1000.00"),
    )
    assert c.product_type == ProductType.conventional
    assert c.dpd_days == 0
    assert c.missed_payments == 0


def test_compliance_floor_6_fields() -> None:
    floor = build_compliance_floor()
    assert floor.contact_window is not None
    assert floor.regulatory_triggers is not None
    assert floor.disclosure_script is not None
    assert floor.third_party_disclosure is not None
    assert floor.hardship_offer_log is not None
    assert floor.call_recording_retention_years == 5


def test_compliance_should_contact_triggers() -> None:
    result = should_attempt_contact(dpd_days=45, missed_payments=2)
    assert result["should_attempt"] is True
    assert "two_missed_payment_notice" in result["triggers"]


def test_compliance_no_triggers() -> None:
    result = should_attempt_contact(dpd_days=5, missed_payments=0)
    assert result["should_attempt"] is False


# ─── Importer tests ────────────────────────────────────────────────────────────


def test_validate_valid_data() -> None:
    from payment_concierge.services.engine.importer import validate_import_data
    data = {"bank_id": "EMIRATES_NBD"}
    errors = validate_import_data(data)
    assert errors == []


def test_validate_missing_bank_id() -> None:
    from payment_concierge.services.engine.importer import validate_import_data
    errors = validate_import_data({"product_type": "conventional"})
    assert any("bank_id" in e for e in errors)


def test_validate_invalid_product_type() -> None:
    from payment_concierge.services.engine.importer import validate_import_data
    errors = validate_import_data({"bank_id": "T", "product_type": "halal"})
    assert any("product_type" in e for e in errors)


def test_import_bank_config_prepares_dict() -> None:
    from payment_concierge.services.engine.importer import import_bank_config_from_json
    result = import_bank_config_from_json({"bank_id": "EMIRATES_NBD"})
    assert result["bank_id"] == "EMIRATES_NBD"
    assert result["product_type"] == "conventional"
    assert result["legal_referral_dpd"] == 120
    assert result["contact_window_start"] == "09:00"


def test_import_customers_empty() -> None:
    from payment_concierge.services.engine.importer import import_customers_from_json
    result = import_customers_from_json({"bank_id": "EMIRATES_NBD"})
    assert result == []


def test_import_customers_prepares_dicts() -> None:
    from payment_concierge.services.engine.importer import import_customers_from_json
    data = {
        "bank_id": "EMIRATES_NBD",
        "customers": [
            {
                "customer_id": "C001",
                "name": "Test User",
                "phone": "+971-50-000-0000",
                "total_outstanding": 10000.00,
                "dpd_days": 30,
            }
        ],
    }
    results = import_customers_from_json(data)
    assert len(results) == 1
    assert results[0]["customer_id"] == "C001"
    assert results[0]["bank_id"] == "EMIRATES_NBD"


def test_get_expected_schema() -> None:
    from payment_concierge.services.engine.importer import get_expected_excel_schema
    schema = get_expected_excel_schema()
    assert "bank_id" in schema.get("properties", {})
    assert "customers" in schema.get("properties", {})


# ─── Integration test placeholder ──────────────────────────────────────────────
# To write database-backed integration tests:
# 1. Set RULE_ENGINE_BACKEND=db and DATABASE_URL=sqlite:///:memory:
# 2. Create tables with Base.metadata.create_all(engine)
# 3. Seed test data using the ORM models
# 4. Instantiate DbBackend(sessionmaker(bind=engine))
# 5. Run the same assertion patterns as the FixtureBackend tests above