"""Application settings loaded from environment variables."""

from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import field_validator
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

    cors_origin: str = "http://localhost:5173"

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

    # Logging configuration (AC #8)
    log_level: LogLevel = LogLevel.INFO

    # Inventory sync configuration (Story 4.2, Task 1.5)
    inventory_api_url: str = ""
    inventory_api_timeout: int = 30
    inventory_api_token: str = ""
    inventory_sync_interval_hours: int = 1
    inventory_cache_ttl_seconds: int = 3600

    # Vault configuration (Story 4.2bis, Task 1.1)
    vault_addr: str = ""
    vault_token: str = ""
    vault_role_id: str = ""
    vault_secret_id: str = ""

    # Static files configuration (Story 4.9, LOW-9 fix)
    static_files_path: str = ""  # If empty, defaults to backend/static/

    # ServiceNow configuration (Story 4.5, Task 6.1)
    servicenow_base_url: str = ""  # e.g., https://desjardins.service-now.com
    servicenow_timeout: int = 30  # Timeout in seconds (NFR19)
    servicenow_retry_count: int = 1  # Number of retries on timeout
    servicenow_credential_ref: str = ""  # Vault path for ServiceNow credentials

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

    def get_static_path(self) -> Path:
        """Get the static files directory path (Story 4.9, LOW-9 fix).
        
        Returns:
            Path to static files directory. Defaults to backend/static/ if not configured.
        """
        if self.static_files_path:
            return Path(self.static_files_path)
        # Default: backend/static/ (relative to config.py location)
        return Path(__file__).parent.parent / "static"


settings = Settings()
