"""
Payment Concierge — Application settings.
Loaded from environment variables with sensible defaults for local dev.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Settings:
    # ── Server ──────────────────────────────────────────────────────────────
    host: str = os.getenv("PC_HOST", "0.0.0.0")
    port: int = int(os.getenv("PC_PORT", "8000"))
    log_level: str = os.getenv("PC_LOG_LEVEL", "info")

    # ── ElevenLabs integration ──────────────────────────────────────────────
    elevenlabs_api_key: Optional[str] = os.getenv("ELEVENLABS_API_KEY")
    elevenlabs_base_url: str = os.getenv(
        "ELEVENLABS_BASE_URL", "https://api.elevenlabs.io"
    )
    elevenlabs_agent_id: Optional[str] = os.getenv("ELEVENLABS_AGENT_ID")

    # ── Brain engine (Pratibha's model → DB) ───────────────────────────────
    # Backend: "fixture" (in-memory, default) or "db" (SQLAlchemy-backed)
    rule_engine_backend: str = os.getenv(
        "RULE_ENGINE_BACKEND", "fixture"
    )
    # Database URL for the DB backend (required when backend=db)
    database_url: Optional[str] = os.getenv("DATABASE_URL")
    # Path to Pratibha's Excel export for the import pipeline
    excel_import_path: Optional[str] = os.getenv("EXCEL_IMPORT_PATH")
    rule_engine_db_url: Optional[str] = os.getenv("RULE_ENGINE_DB_URL")
    default_bank_id: str = os.getenv("DEFAULT_BANK_ID", "EMIRATES_NBD")

    # ── CBUAE compliance floor ──────────────────────────────────────────────
    contact_window_start: str = "09:00"
    contact_window_end: str = "20:00"
    two_missed_payment_notice_enabled: bool = True
    mandatory_contact_dpd: int = 30
    mandatory_written_notice_dpd: int = 60
    monthly_notice_while_in_arrears: bool = True
    call_recording_retention_years: int = 5

    # ── CORS ────────────────────────────────────────────────────────────────
    allowed_origins: list[str] = field(
        default_factory=lambda: os.getenv(
            "PC_ALLOWED_ORIGINS",
            "http://localhost:8000,http://127.0.0.1:8000",
        ).split(",")
    )


settings = Settings()