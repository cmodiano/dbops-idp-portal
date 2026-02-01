"""Application settings loaded from environment variables."""

from enum import Enum
import json
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings


class LogLevel(str, Enum):
    """Valid log levels following architecture convention (AC #8)."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    model_config = {"env_prefix": ""}

    app_env: str = "development"
    app_debug: bool = False

    oracle_dsn: str = "localhost:1521/FREEPDB1"
    oracle_user: str = "idp_app"
    oracle_password: str = "changeme"
    oracle_min_pool: int = 2
    oracle_max_pool: int = 10

    # CORS: allow one or many origins. Supports env vars:
    # - CORS_ORIGIN (legacy, single origin)
    # - CORS_ORIGINS (preferred, comma-separated or JSON list)
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"],
        validation_alias=AliasChoices("CORS_ORIGINS", "CORS_ORIGIN"),
    )

    # Frontend/SPA base URL used for browser redirects (e.g., SAML callback redirect target).
    # Keep separate from CORS so the API can run without a portal UI.
    frontend_base_url: str = "http://localhost:5173"

    # JWT settings
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_hours: int = 8

    # SAML SP settings
    saml_sp_entity_id: str = "https://idp-portal.example.com/metadata"
    saml_sp_acs_url: str = "http://localhost:8000/api/v1/auth/saml/callback"
    saml_idp_entity_id: str = "https://idp.example.com/entity"
    saml_idp_sso_url: str = "https://idp.example.com/sso"
    saml_idp_slo_url: str = "https://idp.example.com/slo"
    saml_idp_cert_path: str = ""
    saml_sp_key_path: str = ""
    saml_sp_cert_path: str = ""

    # Dev bypass (for local development without IdP)
    auth_dev_bypass: bool = False

    # SAML callback response type:
    # - "redirect": redirect browser to FRONTEND_BASE_URL with access_token fragment (portal flow)
    # - "json": return tokens in JSON (API-only flow)
    saml_callback_mode: Literal["redirect", "json"] = "redirect"

    # Logging configuration (AC #8)
    log_level: LogLevel = LogLevel.INFO

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        """Accept comma-separated strings or JSON lists for CORS origins."""
        if v is None:
            return ["http://localhost:5173"]
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            raw = v.strip()
            if not raw:
                return ["http://localhost:5173"]
            # Allow JSON list: '["http://a","http://b"]'
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        origins = [str(x).strip() for x in parsed if str(x).strip()]
                        return origins or ["http://localhost:5173"]
                except Exception:
                    # Fall back to comma-separated parsing
                    pass
            origins = [p.strip() for p in raw.split(",") if p.strip()]
            return origins or ["http://localhost:5173"]
        return [str(v).strip()] if str(v).strip() else ["http://localhost:5173"]

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v: str | LogLevel) -> LogLevel:
        """Validate log_level is one of the allowed values."""
        if isinstance(v, LogLevel):
            return v
        try:
            return LogLevel(v.upper())
        except ValueError:
            raise ValueError(
                f"Invalid log_level '{v}'. Must be one of: "
                f"{', '.join(level.value for level in LogLevel)}"
            )

    @property
    def cors_origin(self) -> str:
        """Legacy single-origin accessor (first configured origin)."""
        return self.cors_origins[0] if self.cors_origins else ""


settings = Settings()
