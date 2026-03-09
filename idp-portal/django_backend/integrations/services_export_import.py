"""
Export/import YAML services for Integration.
Story 64.4 - CaC Integration management.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from django.db import transaction

from core.exceptions import InvalidStateError
from core.models import AuditActionType, AuditEntityType
from core.services import AuditService
from core.services_cac_utils import (
    _apply_field_changes,
    parse_yaml,
    serialize_to_yaml,
    update_sync_tracking,
    validate_envelope,
)
from integrations.models import Integration, IntegrationTypeCatalogue

logger = logging.getLogger(__name__)


def _mask_credential_ref(credential_ref: str | None) -> str | None:
    """
    Mask the last path segment of a Vault credential path.
    Example: 'secret/integrations/aap-prod' -> 'secret/integrations/***'
    """
    if not credential_ref:
        return None
    parts = credential_ref.rsplit("/", 1)
    if len(parts) == 2:
        return f"{parts[0]}/***"
    return "***"


def export_integration_yaml(name: str) -> bytes:
    """
    Export a single Integration as YAML bytes.

    Args:
        name: Integration.name (unique lookup key).

    Returns:
        UTF-8 YAML bytes with envelope apiVersion: idp/v1 / kind: Integration.

    Raises:
        InvalidStateError: If the integration does not exist.
    """
    try:
        obj = Integration.objects.select_related("secret_service").get(name=name)
    except Integration.DoesNotExist:
        raise InvalidStateError(
            code="INTEGRATION_NOT_FOUND",
            message=f"Integration '{name}' introuvable.",
        )

    spec: dict[str, Any] = {
        "base_url": obj.base_url,
    }
    if obj.auth_flow:
        spec["auth_flow"] = obj.auth_flow
    if obj.token_url:
        spec["token_url"] = obj.token_url
    spec["credential_ref"] = _mask_credential_ref(obj.credential_ref)
    if obj.icon:
        spec["icon"] = obj.icon
    if obj.secret_service:
        spec["secret_service_ref"] = obj.secret_service.name
    if obj.config:
        try:
            spec["config"] = json.loads(obj.config)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(
                "Integration '%s' (id=%s) has malformed config JSON: %s",
                obj.name,
                obj.id,
                e,
            )
            spec["config"] = None

    root = {
        "apiVersion": "idp/v1",
        "kind": "Integration",
        "metadata": {
            "name": obj.name,
            "type": obj.type,
        },
        "spec": spec,
    }
    return serialize_to_yaml(root)


@transaction.atomic
def import_integration_yaml(
    content: bytes, mode: str = "additive", user: Any | None = None
) -> tuple[int, int, int]:
    """
    Import an Integration from YAML bytes.

    Two-pass strategy:
      Pass 1 — Create or update the integration WITHOUT resolving secret_service.
      Pass 2 — Resolve secret_service_ref (the referenced integration must already exist in DB).

    Args:
        content: UTF-8 YAML bytes.
        mode: "additive" (default) or "full" — reserved for future use.
        user: Optional user performing the import (for audit).

    Returns:
        Tuple (created, updated, unchanged).

    Raises:
        InvalidStateError: If YAML is invalid, envelope is wrong, type not found, or ref not found.
    """
    if mode not in ("additive", "full"):
        raise InvalidStateError(
            code="INVALID_IMPORT_MODE",
            message=f"Mode invalide '{mode}'. Valeurs acceptées : 'additive', 'full'.",
        )

    parsed = parse_yaml(content)
    validate_envelope(parsed, expected_kind="Integration")

    metadata = parsed.get("metadata", {})
    spec = parsed.get("spec", {})

    name = (metadata.get("name") or "").strip()
    integration_type = (metadata.get("type") or "").strip()

    if not name:
        raise InvalidStateError(
            code="MISSING_NAME",
            message="Le champ 'metadata.name' est requis.",
        )

    # Validate type against IntegrationTypeCatalogue
    if not IntegrationTypeCatalogue.objects.filter(code=integration_type).exists():
        raise InvalidStateError(
            code="REF_NOT_FOUND",
            message=f"Type d'intégration '{integration_type}' introuvable dans IntegrationTypeCatalogue.",
        )

    # Validate base_url (required, non-empty)
    base_url = (spec.get("base_url") or "").strip()
    if not base_url:
        raise InvalidStateError(
            code="INVALID_SPEC",
            message=f"Le champ 'spec.base_url' est requis et doit être une URL non vide pour l'intégration '{name}' (type={integration_type}).",
        )

    # Pass 1: Build defaults without secret_service
    # Use values as-is for optional string fields to avoid "" vs None spurious diffs in _apply_field_changes
    defaults: dict[str, Any] = {
        "type": integration_type,
        "base_url": base_url,
        "auth_flow": spec.get("auth_flow"),
        "token_url": spec.get("token_url"),
        "icon": spec.get("icon"),
    }
    # Only set credential_ref when spec provides a non-masked value (masked export contains '***')
    # When masked, omit from defaults so existing DB value is left untouched on update
    cred_ref = spec.get("credential_ref")
    if cred_ref and "***" not in str(cred_ref):
        defaults["credential_ref"] = cred_ref
    if spec.get("config") is not None:
        defaults["config"] = json.dumps(spec["config"], sort_keys=True)
    else:
        defaults["config"] = None

    obj, was_created = Integration.objects.get_or_create(name=name, defaults=defaults)
    if was_created:
        created, updated, unchanged = 1, 0, 0
        update_sync_tracking(obj, content)
    else:
        changed = _apply_field_changes(obj, defaults)
        if changed:
            obj.save()
            created, updated, unchanged = 0, 1, 0
            update_sync_tracking(obj, content)
        else:
            created, updated, unchanged = 0, 0, 1

    # Pass 2: Resolve secret_service_ref
    secret_service_ref = spec.get("secret_service_ref")
    if secret_service_ref:
        try:
            ref_integration = Integration.objects.get(name=secret_service_ref)
        except Integration.DoesNotExist:
            raise InvalidStateError(
                code="REF_NOT_FOUND",
                message=f"Integration référencée '{secret_service_ref}' (secret_service_ref) introuvable.",
            )
        if obj.secret_service_id != ref_integration.id:
            obj.secret_service_id = ref_integration.id
            obj.save(update_fields=["secret_service_id"])
            update_sync_tracking(obj, content)
            if unchanged:
                unchanged, updated = 0, 1
    elif obj.secret_service_id is not None and not was_created:
        # Clear secret_service_ref if absent from YAML but set in DB
        obj.secret_service_id = None
        obj.save(update_fields=["secret_service_id"])
        update_sync_tracking(obj, content)
        if unchanged:
            unchanged, updated = 0, 1

    AuditService.create_entry(
        user_id=str(user.id) if user and hasattr(user, "id") else "",
        action_type=AuditActionType.CONFIG_SYNC_INTEGRATION_IMPORT,
        entity_type=AuditEntityType.INTEGRATION,
        entity_id=obj.id,
        details={
            "source": "yaml_import",
            "name": name,
            "type": integration_type,
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "mode": mode,
        },
    )

    return (created, updated, unchanged)


# ---------------------------------------------------------------------------
# Bulk export (Story 64.8)
# ---------------------------------------------------------------------------

def export_integrations_yaml() -> bytes:
    """Export all integrations as multi-document YAML (one document per integration)."""
    names = list(Integration.objects.values_list('name', flat=True).order_by('name'))
    if not names:
        return b''
    docs = [export_integration_yaml(n).decode('utf-8') for n in names]
    return ('---\n' + '---\n'.join(docs)).encode('utf-8')
