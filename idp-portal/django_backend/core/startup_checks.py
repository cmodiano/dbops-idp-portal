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


def validate_required_secrets(app_env: str, auth_dev_bypass: bool) -> None:
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


def validate_rate_limit_config() -> None:
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
        'THROTTLE_API_KEY_TOKEN_RATE': os.getenv('THROTTLE_API_KEY_TOKEN_RATE', '10/minute'),  # MEDIUM-3: scope api_key_token was unvalidated
        'THROTTLE_SERVICE_LOGIN_RATE': os.getenv('THROTTLE_SERVICE_LOGIN_RATE', '5/minute'),
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


# Story 17.12: Feature flags configuration validation
def validate_feature_flags_config() -> None:
    """
    Validate feature flags configuration at startup.

    Checks:
    - FEATURE_FLAGS_SOURCE is 'env' or 'database'
    - FEATURE_FLAGS_ENABLED is a boolean
    - FEATURE_FLAGS_CACHE_TTL is a positive integer
    - FEATURE_FLAGS JSON is valid (when source=env)

    Raises ImproperlyConfigured if critical configuration is invalid in production.
    """
    import json

    app_env = os.getenv('APP_ENV', 'development').lower()
    is_dev = app_env == 'development'

    # Validate FEATURE_FLAGS_SOURCE
    source = os.getenv('FEATURE_FLAGS_SOURCE', 'env').lower()
    if source not in ('env', 'database'):
        error_msg = (
            "❌ FEATURE FLAGS: Invalid FEATURE_FLAGS_SOURCE value.\n"
            f"Current value: {source}\n"
            "Expected: env or database"
        )
        logger.error("feature_flags_source_invalid", value=source)
        raise ImproperlyConfigured(error_msg)

    # Validate FEATURE_FLAGS_ENABLED
    enabled_raw = os.getenv('FEATURE_FLAGS_ENABLED', 'true').lower()
    if enabled_raw not in ('true', 'false', '1', '0'):
        error_msg = (
            "❌ FEATURE FLAGS: Invalid FEATURE_FLAGS_ENABLED value.\n"
            f"Current value: {os.getenv('FEATURE_FLAGS_ENABLED')}\n"
            "Expected: true, false, 1, or 0"
        )
        logger.error("feature_flags_enabled_invalid", value=os.getenv('FEATURE_FLAGS_ENABLED'))
        raise ImproperlyConfigured(error_msg)

    # Validate FEATURE_FLAGS_CACHE_TTL
    ttl_raw = os.getenv('FEATURE_FLAGS_CACHE_TTL', '300')
    try:
        ttl = int(ttl_raw)
        if ttl < 0:
            raise ValueError("negative")
    except (ValueError, TypeError):
        error_msg = (
            "❌ FEATURE FLAGS: Invalid FEATURE_FLAGS_CACHE_TTL value.\n"
            f"Current value: {ttl_raw}\n"
            "Expected: positive integer (seconds)"
        )
        logger.error("feature_flags_cache_ttl_invalid", value=ttl_raw)
        raise ImproperlyConfigured(error_msg)

    # Validate FEATURE_FLAGS JSON (when source=env)
    if source == 'env':
        raw_flags = os.getenv('FEATURE_FLAGS', '{}')
        if raw_flags:
            try:
                parsed = json.loads(raw_flags)
                if not isinstance(parsed, dict):
                    raise ValueError("must be a JSON object")
                flag_count = len(parsed)
            except (json.JSONDecodeError, ValueError) as e:
                if is_dev:
                    logger.warning(
                        "feature_flags_json_invalid",
                        error=str(e),
                        message="Invalid FEATURE_FLAGS JSON - using empty config",
                    )
                    flag_count = 0
                else:
                    error_msg = (
                        "❌ FEATURE FLAGS: Invalid FEATURE_FLAGS JSON.\n"
                        f"Error: {e}\n"
                        "Expected: valid JSON object"
                    )
                    logger.error("feature_flags_json_invalid", error=str(e))
                    raise ImproperlyConfigured(error_msg)
        else:
            flag_count = 0
    else:
        flag_count = 0  # Database source - count not available at startup

    # Story 20.7: Validate Redis pub/sub configuration if enabled
    pubsub_enabled_raw = os.getenv('FEATURE_FLAGS_PUBSUB_ENABLED', 'false').lower()
    if pubsub_enabled_raw not in ('true', 'false', '1', '0'):
        error_msg = (
            "❌ FEATURE FLAGS: Invalid FEATURE_FLAGS_PUBSUB_ENABLED value.\n"
            f"Current value: {os.getenv('FEATURE_FLAGS_PUBSUB_ENABLED')}\n"
            "Expected: true, false, 1, or 0"
        )
        logger.error("feature_flags_pubsub_enabled_invalid", value=os.getenv('FEATURE_FLAGS_PUBSUB_ENABLED'))
        raise ImproperlyConfigured(error_msg)

    pubsub_enabled = pubsub_enabled_raw in ('true', '1')
    if pubsub_enabled:
        redis_url = os.getenv('REDIS_URL', '')
        if not redis_url:
            error_msg = (
                "❌ FEATURE FLAGS: REDIS_URL required when FEATURE_FLAGS_PUBSUB_ENABLED=true.\n"
                "Set REDIS_URL in environment (e.g., redis://localhost:6379/0)"
            )
            logger.error("feature_flags_redis_url_missing")
            raise ImproperlyConfigured(error_msg)

        # Validate Redis URL format (basic check)
        if not redis_url.startswith(('redis://', 'rediss://')):
            error_msg = (
                "❌ FEATURE FLAGS: Invalid REDIS_URL format.\n"
                f"Current value: {redis_url}\n"
                "Expected: redis:// or rediss:// URL"
            )
            logger.error("feature_flags_redis_url_invalid", redis_url=redis_url)
            raise ImproperlyConfigured(error_msg)

        logger.info("feature_flags_redis_pubsub_enabled", redis_url=redis_url.split('@')[-1])  # Hide credentials

    # Story 22.16: Validate cache backend compatibility with anti-thundering herd lock
    if source == 'database':
        from django.conf import settings
        cache_backend = settings.CACHES.get('default', {}).get('BACKEND', '')

        # LocMemCache only provides per-process locking, not inter-process
        if 'locmem' in cache_backend.lower():
            if is_dev:
                logger.warning(
                    "feature_flags_cache_backend_warning",
                    message="⚠️ DEV: LocMemCache provides per-process locking only. "
                            "Anti-thundering herd lock will NOT work across multiple workers. "
                            "Use Redis/Memcached in production.",
                    cache_backend=cache_backend,
                )
            else:
                error_msg = (
                    "❌ FEATURE FLAGS: LocMemCache incompatible with database source in production.\n"
                    f"Current cache backend: {cache_backend}\n"
                    "The anti-thundering herd lock requires a distributed cache (Redis/Memcached) "
                    "to prevent concurrent DB loads across multiple workers.\n"
                    "Either:\n"
                    "  1. Change FEATURE_FLAGS_SOURCE to 'env', OR\n"
                    "  2. Configure CACHES['default'] to use Redis/Memcached"
                )
                logger.error(
                    "feature_flags_cache_backend_incompatible",
                    cache_backend=cache_backend,
                    source=source,
                )
                raise ImproperlyConfigured(error_msg)

    # Validate FEATURE_FLAGS_LOCK_TIMEOUT
    lock_timeout_raw = os.getenv('FEATURE_FLAGS_LOCK_TIMEOUT', '3')
    try:
        lock_timeout = int(lock_timeout_raw)
        if lock_timeout <= 0:
            raise ValueError("must be positive")
    except (ValueError, TypeError):
        error_msg = (
            "❌ FEATURE FLAGS: Invalid FEATURE_FLAGS_LOCK_TIMEOUT value.\n"
            f"Current value: {lock_timeout_raw}\n"
            "Expected: positive integer (seconds)"
        )
        logger.error("feature_flags_lock_timeout_invalid", value=lock_timeout_raw)
        raise ImproperlyConfigured(error_msg)

    logger.info(
        "feature_flags_config_validated",
        source=source,
        enabled=enabled_raw in ('true', '1'),
        cache_ttl=int(ttl_raw),
        lock_timeout=lock_timeout,
        flag_count=flag_count,
        pubsub_enabled=pubsub_enabled,
    )


# Story 59.4 SEC-4: CORS configuration validation
def validate_cors_config(debug: bool) -> None:
    """
    SEC-4: Validate CORS configuration at startup.

    If DEBUG=False and CORS_ORIGIN is not defined, the app would accept
    cross-origin requests from http://localhost:5173 (hardcoded default),
    which is a security risk in production.

    Args:
        debug: True if Django DEBUG=True (development mode)

    Raises:
        ImproperlyConfigured: If DEBUG=False and CORS_ORIGIN is not set
    """
    if debug:
        # Dev mode: default localhost origin is acceptable
        logger.info("cors_config_validated", debug=True,
                    message="Dev mode — default localhost CORS origin acceptable")
        return

    cors_origin = (os.getenv('CORS_ORIGIN') or '').strip()
    is_blank = not cors_origin
    is_placeholder = bool(PLACEHOLDER_PATTERN.match(cors_origin))
    is_localhost = cors_origin.lower().startswith('http://localhost')
    if is_blank or is_placeholder or is_localhost:
        error_msg = "\n".join([
            "❌ SECURITY: CORS configuration invalid for production",
            "DEBUG=False but CORS_ORIGIN environment variable is not set.",
            "The default value 'http://localhost:5173' is NOT safe for production.",
            "",
            "Fix: Set CORS_ORIGIN to your frontend URL.",
            "Example: CORS_ORIGIN=https://idp.internal",
            "See .env.production.template for required variables.",
        ])
        logger.error("cors_config_missing_production", debug=debug)
        raise ImproperlyConfigured(error_msg)

    logger.info("cors_config_validated", debug=False, cors_origin=cors_origin)


# Story 59.5 SEC-5: Superuser fallback configuration validation
def validate_superuser_fallback_config(debug: bool, allow_superuser_fallback: bool) -> None:
    """
    SEC-5: Validate ALLOW_SUPERUSER_FALLBACK configuration at startup.

    ALLOW_SUPERUSER_FALLBACK allows superusers to bypass RBAC entirely.
    This is acceptable ONLY in development/bootstrapping scenarios.
    Activating it in production violates the principle of least privilege
    and SOC1 compliance requirements.

    Args:
        debug: True if Django DEBUG=True (development mode)
        allow_superuser_fallback: Value of settings.ALLOW_SUPERUSER_FALLBACK

    Raises:
        ImproperlyConfigured: If allow_superuser_fallback=True and debug=False
    """
    if debug:
        # Dev mode: superuser fallback acceptable for bootstrapping
        logger.info(
            "superuser_fallback_config_validated",
            debug=True,
            allow_superuser_fallback=allow_superuser_fallback,
            message="Dev mode — ALLOW_SUPERUSER_FALLBACK acceptable in development",
        )
        return

    if allow_superuser_fallback:
        error_msg = "\n".join([
            "❌ SECURITY: ALLOW_SUPERUSER_FALLBACK is not allowed in production",
            "DEBUG=False but ALLOW_SUPERUSER_FALLBACK=True.",
            "This setting bypasses all RBAC for Django superusers.",
            "",
            "Fix: Set ALLOW_SUPERUSER_FALLBACK=false in production environment.",
            "In production, superusers MUST have an explicit admin profile.",
            "See .env.production.template for required variables.",
        ])
        logger.error(
            "superuser_fallback_forbidden_production",
            debug=debug,
            allow_superuser_fallback=allow_superuser_fallback,
        )
        raise ImproperlyConfigured(error_msg)

    logger.info(
        "superuser_fallback_config_validated",
        debug=debug,
        allow_superuser_fallback=allow_superuser_fallback,
    )
