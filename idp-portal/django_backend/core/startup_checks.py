"""
Story 17.5: Startup secret validation module.

Validates that all critical secrets are properly configured before
the application starts. Raises ImproperlyConfigured in non-dev
environments if secrets are missing or contain insecure defaults.
"""

import os
import re

import structlog
from django.core.exceptions import ImproperlyConfigured

logger = structlog.get_logger(__name__)

# Secrets with forbidden default values in production
INSECURE_DEFAULTS = {
    'SECRET_KEY': ['django-insecure-', 'changeme'],
    'JWT_SECRET_KEY': ['change-me-in-production', 'changeme'],
    'ORACLE_PASSWORD': ['changeme'],
}

# Pattern to detect unreplaced placeholders
PLACEHOLDER_PATTERN = re.compile(r'^CHANGE_[A-Z_]+$|^<[A-Z_]+>$|^TODO:')


def validate_required_secrets(app_env: str, auth_dev_bypass: bool):
    """
    Validate that all critical secrets are configured correctly.

    Args:
        app_env: Application environment (development, staging, production)
        auth_dev_bypass: If True, skip SAML cert validation

    Raises:
        ImproperlyConfigured: If secrets are missing/insecure in non-dev environments

    Example:
        >>> validate_required_secrets('production', auth_dev_bypass=False)
        # Raises ImproperlyConfigured if secrets missing

        >>> validate_required_secrets('development', auth_dev_bypass=True)
        # Logs warnings but allows startup
    """
    is_dev = app_env.lower() == 'development'
    errors = []
    warnings = []

    for secret_name, forbidden_prefixes in INSECURE_DEFAULTS.items():
        secret_value = os.getenv(secret_name, '')

        if not secret_value:
            if is_dev:
                warnings.append(f"{secret_name} is not set - using insecure fallback")
            errors.append(f"{secret_name} is not set")
            continue

        for forbidden in forbidden_prefixes:
            if secret_value.startswith(forbidden):
                if is_dev:
                    warnings.append(f"{secret_name} uses default value (dev mode)")
                else:
                    errors.append(f"{secret_name} contains insecure default value")
                break

        if PLACEHOLDER_PATTERN.match(secret_value):
            errors.append(f"{secret_name} contains unreplaced placeholder: {secret_value}")

    # Validate SAML certs if authentication is required (not bypassed)
    if not auth_dev_bypass and not is_dev:
        saml_certs = ['SAML_SP_CERT_PATH', 'SAML_SP_KEY_PATH', 'SAML_IDP_CERT_PATH']
        for cert_var in saml_certs:
            cert_path = os.getenv(cert_var, '')
            if not cert_path:
                errors.append(f"{cert_var} required for SAML authentication in production")

    # Log warnings in dev
    if warnings:
        for warning in warnings:
            logger.warning("secret_validation_warning", message=warning, environment=app_env)
        logger.warning("dev_mode_active",
                        message="⚠️ DEV MODE: Using default secrets - DO NOT use in production")

    if auth_dev_bypass and is_dev:
        logger.warning("auth_dev_bypass_active",
                        message="⚠️ DEV MODE: AUTH_DEV_BYPASS activé - NE PAS utiliser en production")

    if auth_dev_bypass and not is_dev:
        logger.warning("auth_dev_bypass_production",
                        message="⚠️ DANGER: AUTH_DEV_BYPASS activé en PRODUCTION - risque sécurité élevé")

    # Fail-fast in non-dev
    if errors and not is_dev:
        error_msg = "\n".join([
            "❌ SECURITY: Secret validation failed",
            f"Environment: {app_env}",
            "Missing or insecure secrets:",
            *[f"  - {err}" for err in errors],
            "",
            "Fix by setting environment variables in .env or system environment.",
            "See .env.production.template for required variables.",
        ])
        logger.error("secret_validation_failed", errors=errors, environment=app_env)
        raise ImproperlyConfigured(error_msg)

    # Log success
    logger.info("secret_validation_success",
                message=f"✓ Configuration des secrets validée pour environnement {app_env}",
                environment=app_env, warnings_count=len(warnings), is_dev=is_dev)


# Story 17.11: Rate limiting configuration validation
# Valid formats: "<count>/<period>" where period is second/minute/hour/day (or abbreviations)
RATE_FORMAT_PATTERN = re.compile(
    r'^\d+/(second|sec|s|minute|min|m|hour|h|day|d)$', re.IGNORECASE
)


def validate_rate_limit_config():
    """
    Validate rate limit configuration at startup.

    Checks that all THROTTLE_*_RATE env vars use valid DRF rate format.
    Validates that RATELIMIT_ENABLED is a proper boolean value.
    Raises ImproperlyConfigured if any rate has an invalid format.
    """
    # Validate RATELIMIT_ENABLED is a boolean value
    ratelimit_enabled = os.getenv('RATELIMIT_ENABLED', 'true').lower()
    if ratelimit_enabled not in ('true', 'false', '1', '0'):
        error_msg = (
            "❌ RATE LIMIT: Invalid RATELIMIT_ENABLED value.\n"
            f"Current value: {os.getenv('RATELIMIT_ENABLED')}\n"
            "Expected: true, false, 1, or 0"
        )
        logger.error("rate_limit_enabled_invalid", value=os.getenv('RATELIMIT_ENABLED'))
        raise ImproperlyConfigured(error_msg)

    rate_vars = {
        'THROTTLE_AUTH_RATE': os.getenv('THROTTLE_AUTH_RATE', '10/minute'),
        'THROTTLE_TOKEN_REFRESH_RATE': os.getenv('THROTTLE_TOKEN_REFRESH_RATE', '20/minute'),
        'THROTTLE_EXECUTION_RATE': os.getenv('THROTTLE_EXECUTION_RATE', '30/minute'),
        'THROTTLE_API_RATE': os.getenv('THROTTLE_API_RATE', '100/minute'),
        'THROTTLE_PUBLIC_RATE': os.getenv('THROTTLE_PUBLIC_RATE', '50/minute'),
    }

    invalid = []
    for var_name, value in rate_vars.items():
        if not RATE_FORMAT_PATTERN.match(value):
            invalid.append(f"{var_name}={value}")

    if invalid:
        error_msg = (
            "❌ RATE LIMIT: Invalid rate format detected.\n"
            f"Invalid rates: {', '.join(invalid)}\n"
            "Expected format: <count>/<period> where period is second|minute|hour|day (or s|m|h|d)"
        )
        logger.error("rate_limit_config_invalid", invalid_rates=invalid)
        raise ImproperlyConfigured(error_msg)
