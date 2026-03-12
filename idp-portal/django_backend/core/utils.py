"""Core utility functions shared across apps."""

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

from django.utils import timezone


def ensure_utc_isoformat(dt: datetime | None) -> str | None:
    """Convert datetime to UTC-aware ISO 8601 string with explicit timezone.

    If the datetime is naive (no timezone info), it is assumed to be UTC and
    made timezone-aware before serialization.

    Args:
        dt: datetime object (aware or naive) or None.

    Returns:
        ISO 8601 string ending with ``Z`` (e.g. ``"2026-02-09T14:30:00Z"``)
        or ``None`` if ``dt`` is ``None``.
    """
    if dt is None:
        return None

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone=dt_timezone.utc)

    # Fast path: if already UTC, skip astimezone()
    if dt.tzinfo == dt_timezone.utc:
        return dt.isoformat().replace("+00:00", "Z")

    dt_utc = dt.astimezone(dt_timezone.utc)
    return dt_utc.isoformat().replace("+00:00", "Z")


# --- Audit sanitization (Story 61.5) ---

# NEW-BE-B: Single source of truth for sensitive key detection.
# Used by:
#   - sanitize_audit_changes() for audit entries
#   - SENSITIVE_PARAM_KEYS (re-exported) for execution parameter sanitization
# Keys with partial matching (substring): password, passwd, token, secret, credential,
# api_key, apikey, config, private_key, client_secret.
# Exact-match key _env_config is kept in the execution-specific set below.
_SENSITIVE_AUDIT_FIELD_KEYWORDS = frozenset({
    'password', 'passwd', 'token', 'secret', 'credential',
    'api_key', 'apikey', 'config', 'private_key', 'client_secret',
})

# Canonical set of exact (lowercased) parameter key names to redact from execution logs.
# Superset of _SENSITIVE_AUDIT_FIELD_KEYWORDS for execution-specific keys.
# Import this in executions/services.py instead of maintaining a local copy.
SENSITIVE_PARAM_KEYS: frozenset[str] = frozenset({
    'password', 'passwd', 'secret', 'api_key', 'apikey', 'token',
    'private_key', 'credential', 'client_secret', '_env_config',
})

# Champs dont le nom contient un mot-clé sensible mais qui ne sont pas
# des secrets (références structurelles, endpoints, clés étrangères).
_NON_SENSITIVE_AUDIT_FIELDS = frozenset({
    'token_url',        # URL du endpoint OAuth — pas un token
    'secret_service_id',  # Clé étrangère vers le vault — pas le secret lui-même
})


def _is_sensitive_audit_field(field_name: str) -> bool:
    """Return True if field_name contains any sensitive keyword (case-insensitive)."""
    if field_name in _NON_SENSITIVE_AUDIT_FIELDS:
        return False
    field_lower = field_name.lower()
    return any(kw in field_lower for kw in _SENSITIVE_AUDIT_FIELD_KEYWORDS)


def sanitize_audit_changes(changes: dict) -> dict:
    """Masque les valeurs old/new des champs sensibles dans un dict changes d'audit.

    Pour chaque champ dont le nom contient un mot-clé sensible (password, token,
    secret, credential, api_key, config, etc.), remplace old et new par "***".
    Les champs non-sensibles passent sans modification.

    Format standard (Story 72.2) — Toute entrée d'audit de modification de statut
    doit utiliser le format suivant dans details:

        details = {
            'action_id': ...,
            'action_name': ...,
            'changes': sanitize_audit_changes({
                'status': {'old': 'RUNNING', 'new': 'COMPLETED'},  # ou autre champ
            }),
        }

    Le dict ``changes`` doit toujours être passé par sanitize_audit_changes()
    avant d'être inclus dans AuditService.create_entry pour masquer les champs
    sensibles et garantir la cohérence avec catalog/profiles/integrations.

    Args:
        changes: Dict au format {field: {"old": ..., "new": ...}} ou
                 {field: {"updated": True}} (champs JSON volumineux — non masqués).

    Returns:
        Nouveau dict avec les champs sensibles masqués.

    Example:
        >>> sanitize_audit_changes({"name": {"old": "A", "new": "B"},
        ...                         "credential_ref": {"old": "ref1", "new": "ref2"}})
        {"name": {"old": "A", "new": "B"}, "credential_ref": {"old": "***", "new": "***"}}
    """
    if not changes:
        return changes
    sanitized = {}
    for field, value in changes.items():
        if _is_sensitive_audit_field(field) and isinstance(value, dict) and 'old' in value:
            sanitized[field] = {"old": "***", "new": "***"}
        else:
            sanitized[field] = value
    return sanitized


def build_audit_status_changes(old_status: str, new_status: str) -> dict:
    """Construit et assainit un dict changes pour audit de changement de statut (Story 72.2).

    Helper réutilisable pour garantir le format standard {status: {old, new}}
    avec sanitization des champs sensibles.

    Args:
        old_status: Statut avant la modification.
        new_status: Statut après la modification.

    Returns:
        Dict prêt à inclure dans details['changes'] d'une entrée d'audit.
    """
    return sanitize_audit_changes({'status': {'old': old_status, 'new': new_status}})
