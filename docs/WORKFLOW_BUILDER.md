# Workflow Builder — architecture guidance for Venkata Sairam

## What it is

The workflow builder is a **visual policy configuration tool** that lets bank
collections teams define their collections policies and notification rules
without writing code. It is a core product component (not a nice-to-have) and
operates at a different level than the ElevenLabs agent call flows.

## Where the workflow builder fits

```
┌─────────────────────────────────────────────────────────┐
│                  Workflow Builder (UI)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ DPD Bucket   │  │ Escalation   │  │ Settlement   │   │
│  │ Configuration│  │ Tier Mapping │  │ Authority    │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ PTP Policy   │  │ Channel Mix  │  │ Compliance   │   │
│  │ Rules        │  │ Assignment   │  │ Overrides    │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
                  ┌──────────────────────┐
                  │   Brain Engine DB     │
                  │  (BankConfig tables)  │
                  └──────────────────────┘
                           │
                           ▼
                  ┌──────────────────────┐
                  │   Backend Services    │
                  │  (pre-compute engine) │
                  └──────────────────────┘
                           │
                           ▼
                  ┌──────────────────────┐
                  │   ElevenLabs Agent    │
                  │  (call execution)     │
                  └──────────────────────┘
```

**The workflow builder feeds the brain engine database.** It does not directly
control the ElevenLabs agent. Banks configure policies here, those policies
are stored as bank configuration data, and the brain engine reads that data to
pre-compute call decisions.

## Core concepts to design for

### 1. Policy = a set of rules per bank
Each bank has one active policy composed of:
- DPD bucket definitions (segmentation)
- Escalation tiers (intensity progression)
- Settlement authority matrix (who can offer what)
- PTP policy rules (how many, window, breach handling)
- Channel mix per stage (SMS, phone, email, registered post)

### 2. Visual node types
The builder should support these node categories:

| Node Type | What it configures | Example |
|-----------|-------------------|---------|
| **Bucket** | DPD range + label | 30-89 days = "Underperforming" |
| **Action** | What to do | Call, SMS, Email, Escalate |
| **Condition** | Branching logic | If PTP breaches >= 2 → escalate |
| **Authority** | Settlement limits | Tier 3 can offer 15% discount |
| **Compliance** | Regulatory guardrails | Must offer hardship before legal |

### 3. Validation layer
The builder must prevent invalid configurations:
- DPD ranges must not overlap within a bank's policy
- Escalation tiers must form a progression (no gaps)
- Settlement authority at each tier must be >= the previous tier
- Compliance floor fields cannot be widened (enforced server-side)

## Separation of concerns

**Venkata owns:**
- The visual workflow builder UI (frontend or node-based config tool)
- The configuration export format (what gets saved to the database)

**Brain engine owns:**
- The database schema that stores the configured policies
- The runtime engine that reads policies and pre-computes decisions
- The compliance floor enforcement

**ElevenLabs agent owns:**
- The call flow scripts
- The conversation with the customer
- The execution of the pre-computed decisions

## Recommended approach

### Phase 1 (this week — hackathon scope)
Build a **JSON-based policy editor** rather than a full drag-and-drop builder:
- Form-based UI to configure each policy section
- Preview panel showing the resulting policy as JSON
- Validate and save button → POST to backend /policy endpoint
- Focus on getting the data model right, not the visual polish

### Phase 2 (post-hackathon)
Upgrade to a true visual builder:
- Drag-and-drop node editor (React Flow, Node-RED, or Rete.js)
- Real-time validation showing issues on the canvas
- Version history and audit trail
- Role-based access (read-only vs. configure)

## Data model integration

The workflow builder produces bank configuration data that maps directly to
the brain engine's database models:

```
Workflow Builder Output
├── bank_id, product_type
├── dpd_buckets[]
│   ├── bucket_id, dpd_min, dpd_max, label
│   └── frequency caps
├── escalation_tiers[]
│   ├── tier_id, dpd_range
│   ├── channel_mix[]
│   └── human_handoff_condition
├── settlement_authority_matrix[]
│   ├── tier_id, max_discount_pct
│   └── requires_human_approval
├── ptp_policy
│   ├── max_ptp_per_cycle, ptp_window_days
│   └── breach_action
└── compliance settings (read-only)
    ├── contact_window (locked to 09:00-20:00)
    └── regulatory triggers (locked constants)
```

See `payment-concierge/services/engine/db_models.py` for the full schema.

## Questions for our pairing session

1. What's your tech stack preference for the workflow builder?
   - React + React Flow for a visual node editor
   - Vue + Vue Flow
   - Plain form-based UI (faster to ship, less visual)

2. Should the policy config be a standalone frontend app or served as part of
   the backend (via FastAPI HTML templates)?

3. Do you want to start with JSON editing mode and add the visual builder later,
   or go straight to the drag-and-drop interface?

4. What format should the policy export take? JSON (most flexible) or YAML?

## Related files
- `payment-concierge/services/engine/db_models.py` — database schema
- `payment-concierge/services/engine/interfaces.py` — abstract interface
- `docs/BRAIN_ENGINE.md` — brain engine architecture
- `docs/ARCHITECTURE.md` — overall system architecture
- `payment-concierge/schemas/models.py` — Pydantic schema