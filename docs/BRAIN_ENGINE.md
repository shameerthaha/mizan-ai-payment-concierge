# Brain Engine — architecture and usage guide

## Principle: no live lookups during a call

The brain engine pre-computes **every decision** before the ElevenLabs agent
places a call. The agent receives the outstanding amount, DPD classification,
compliance context, and ranked settlement options as pre-computed data. No
live API calls or database queries happen during the conversation itself.

This makes the voice agent:
- **Fast** — no latency from backend lookups mid-conversation
- **Deterministic** — the agent always knows what to offer
- **Compliant** — the compliance floor is enforced before the call starts

## Architecture

```
Batch job (overnight / per-batch)         Call-time
┌─────────────────────────┐              ┌──────────────┐
│ Pratibha's Excel Model  │              │ ElevenLabs   │
│ (50-100 params per bank)│              │ Agent        │
│ → JSON export           │              │ (pre-loaded) │
└───────────┬─────────────┘              └──────┬───────┘
            │                                   │
            ▼                                   │
┌───────────────────────┐                       │
│ Importer Module       │                       │
│ (importer.py)         │                       │
│ → validate            │                       │
│ → import_bank_config  │                       │
│ → import_customers    │                       │
└───────────┬───────────┘                       │
            │                                   │
            ▼                                   │
┌───────────────────────┐                       │
│ Database (PostgreSQL) │                       │
│ BankConfigModel       │◄──── query ───────────┤
│ CustomerModel         │    (pre-computed      │
│ DPDBucketModel        │     via backend)      │
│ CallOutcomeModel      │                       │
└───────────────────────┘                       │
            ▲                                   │
            │                                   │
┌───────────┴───────────┐                       │
│ Backend Factory       │                       │
│ fixture / db          │──────── query ────────┘
└───────────────────────┘
```

## Pratibha's Excel output contract

The importer module (`services/engine/importer.py`) expects a JSON structure
that Pratibha's Excel model exports. The schema is documented in:

```
get_expected_excel_schema() -> dict
```

The export should be a single JSON file per bank with:

### Required fields
- `bank_id` — unique bank identifier (e.g. "EMIRATES_NBD")

### Bank configuration
- `product_type` — "conventional" or "islamic"
- `ptp_policy` — PTP terms: max_ptp_per_cycle, ptp_window_days, re_ptp_allowed, breach_action
- `legal_referral_dpd` — DPD threshold for legal referral
- `write_off_dpd` — DPD threshold for write-off
- `contact_window_start` / `contact_window_end` — format "HH:MM"
- `aecb_reporting` — enabled (bool), frequency (string)

### DPD buckets
An array of bucket definitions:
- `bucket_id`, `dpd_min`, `dpd_max`, `label`
- `contact_frequency_cap_per_day`, `contact_frequency_cap_per_week`

### Escalation tiers
An array of escalation definitions:
- `tier_id`, `dpd_range`, `channel_mix`, `script_intensity_level`
- `human_handoff_condition`

### Settlement authority matrix
An array of authority definitions:
- `tier_id`, `max_discount_pct`, `max_waiver_amount`, `requires_human_approval`

### Customers (optional)
An array of customer records for seeding.

## Adding a new bank

1. Pratibha adds the bank's parameters to the Excel model
2. Export as JSON using the schema above
3. Validate: `python -c "from payment_concierge.services.engine.importer import validate_import_data; print(validate_import_data(data))"`
4. Import: run the import pipeline script (when available)
5. Set `DEFAULT_BANK_ID=<new_bank_id>` in environment

## Fixture → DB migration path

| Step | When | Action |
|------|------|--------|
| 1 | Now (Oct 3) | Fixture backend active — 3 test customers, Emirates NBD config |
| 2 | Pratibha completes Excel (Oct 7-8) | Export to JSON, validate with importer |
| 3 | After validation | Create PostgreSQL DB, set DATABASE_URL, run import |
| 4 | After import | Set RULE_ENGINE_BACKEND=db, restart service |
| 5 | After migration | Run DbBackend tests against live data |

The service API does not change during migration. The same endpoints serve
the same data structures regardless of backend.

## Backend factory pattern

```
get_backend() → RuleEngineBackend
    ├── FixtureBackend  (RULE_ENGINE_BACKEND=fixture, default)
    └── DbBackend       (RULE_ENGINE_BACKEND=db + DATABASE_URL)
```

The factory is in `services/engine/__init__.py`. All client code (routers,
webhooks) imports from the facade or directly from the engine module and
never instantiates backends directly.

## Call-outcome tracking (post-call)

The `CallOutcomeModel` table logs every call result:
- call_timestamp, duration_seconds
- outcome: completed / failed / ptp_set / hardship_offered / human_handoff / disconnected
- solution_accepted_id, amount_committed

This is populated by the ElevenLabs webhook after a call completes.
TODO: implement the webhook handler for post-call logging.

## Key dependencies

- `services/engine/interfaces.py` — abstract interface (Pratibha's code implements this)
- `services/engine/fixture_backend.py` — in-memory fixture data
- `services/engine/db_backend.py` — SQLAlchemy-backed queries
- `services/engine/db_models.py` — ORM models for bank config, customers, outcomes
- `services/engine/importer.py` — Excel JSON import pipeline
- `services/engine/__init__.py` — backend factory and exports
- `services/rule_engine.py` — backward-compatible facade (delegates to engine)