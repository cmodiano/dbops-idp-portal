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
