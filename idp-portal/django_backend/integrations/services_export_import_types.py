"""
Export/import YAML services for IntegrationTypeCatalogue and IntegrationAction.
Story 64.3 - CaC Integration Type Catalogue management.
"""

from __future__ import annotations

import json
from typing import Any

from django.db import transaction

from core.exceptions import InvalidStateError
from core.middleware import get_correlation_id
from core.models import AuditActionType, AuditEntityType
from core.services import AuditService
from core.services_cac_utils import (
    _apply_field_changes,
    parse_yaml,
    serialize_to_yaml,
    update_sync_tracking,
    validate_envelope,
)
from integrations.models import IntegrationAction, IntegrationTypeCatalogue


def export_integration_types_yaml(code: str) -> bytes:
    """
    Export a single IntegrationTypeCatalogue (with its actions) as YAML bytes.

    Args:
        code: IntegrationTypeCatalogue PK code.

    Returns:
        UTF-8 YAML bytes with envelope apiVersion: idp/v1 / kind: IntegrationTypeCatalogue.

    Raises:
        InvalidStateError: If the code does not exist.
    """
    try:
        obj = IntegrationTypeCatalogue.objects.get(code=code)
    except IntegrationTypeCatalogue.DoesNotExist:
        raise InvalidStateError(
            code="INTEGRATION_TYPE_NOT_FOUND",
            message=f"IntegrationTypeCatalogue '{code}' introuvable.",
        )

    actions = obj.actions.all().order_by("action_code")
    actions_spec = []
    for a in actions:
        entry = {
            "action_code": a.action_code,
            "action_label": a.action_label,
            "description": a.description,
            "is_active": a.is_active,
            "required_params": a.get_required_params(),
            "optional_params": a.get_optional_params(),
            "response_format": a.get_response_format(),
        }
        actions_spec.append(entry)

    root = {
        "apiVersion": "idp/v1",
        "kind": "IntegrationTypeCatalogue",
        "metadata": {
            "code": obj.code,
            "name": obj.name,
        },
        "spec": {
            "description": obj.description,
            "version": obj.version,
            "is_active": obj.is_active,
            "integration_role": obj.integration_role,
            "actions": actions_spec,
        },
    }
    return serialize_to_yaml(root)


@transaction.atomic
def import_integration_types_yaml(
    content: bytes, mode: str = "additive", user: Any | None = None
) -> tuple[int, int, int]:
    """
    Import an IntegrationTypeCatalogue (with its actions) from YAML bytes.

    Args:
        content: UTF-8 YAML bytes.
        mode: "additive" (default, orphan actions left intact) or "full" (orphan actions deactivated).
        user: Optional user performing the import (for audit).

    Returns:
        Tuple (created, updated, unchanged) for the parent IntegrationTypeCatalogue.

    Raises:
        InvalidStateError: If YAML is invalid, envelope is wrong, or action_code is missing.
    """
    if mode not in ("additive", "full"):
        raise InvalidStateError(
            code="INVALID_IMPORT_MODE",
            message=f"Mode invalide : '{mode}'. Valeurs acceptées : 'additive', 'full'.",
        )

    parsed = parse_yaml(content)
    validate_envelope(parsed, expected_kind="IntegrationTypeCatalogue")

    metadata = parsed.get("metadata")
    spec = parsed.get("spec")
    if not isinstance(metadata, dict):
        raise InvalidStateError(
            code="INVALID_METADATA",
            message="Le champ 'metadata' doit être un objet YAML.",
        )
    if not isinstance(spec, dict):
        raise InvalidStateError(
            code="INVALID_SPEC",
            message="Le champ 'spec' doit être un objet YAML.",
        )

    code_val = metadata.get("code")
    if not isinstance(code_val, str):
        raise InvalidStateError(
            code="MISSING_CODE",
            message="Le champ 'metadata.code' est requis et doit être une chaîne.",
        )
    code = code_val.strip()
    if not code:
        raise InvalidStateError(
            code="MISSING_CODE",
            message="Le champ 'metadata.code' est requis.",
        )

    defaults = {
        "name": metadata.get("name", code),
        "description": spec.get("description", ""),
        "version": spec.get("version", "1.0"),
        "is_active": spec.get("is_active", True),
        "integration_role": spec.get("integration_role", "platform"),
    }

    obj, was_created = IntegrationTypeCatalogue.objects.get_or_create(
        code=code, defaults=defaults
    )
    if was_created:
        created = 1
        updated = unchanged = 0
        update_sync_tracking(obj, content)
    else:
        changed = _apply_field_changes(obj, defaults)
        if changed:
            obj.save()
            updated = 1
            created = unchanged = 0
            update_sync_tracking(obj, content)
        else:
            unchanged = 1
            created = updated = 0

    # --- Réconciliation des IntegrationAction ---
    yaml_actions_raw = spec.get("actions")
    yaml_actions: list[dict[str, Any]] = []
    if isinstance(yaml_actions_raw, list):
        # Pre-validate: each item must be a dict with unique non-empty action_code
        seen_codes: set[str] = set()
        for idx, action_item in enumerate(yaml_actions_raw):
            if not isinstance(action_item, dict):
                raise InvalidStateError(
                    code="INVALID_ACTION_ITEM",
                    message=f"L'élément actions[{idx}] doit être un objet YAML.",
                )
            action_code = (action_item.get("action_code") or "").strip()
            if not action_code:
                raise InvalidStateError(
                    code="MISSING_ACTION_CODE",
                    message="Chaque action doit avoir un 'action_code' non vide.",
                )
            if action_code in seen_codes:
                raise InvalidStateError(
                    code="DUPLICATE_ACTION_CODE",
                    message=f"action_code en doublon : '{action_code}'.",
                )
            seen_codes.add(action_code)
            yaml_actions.append(action_item)

    existing_actions = {
        a.action_code: a
        for a in IntegrationAction.objects.filter(integration_type=obj)
    }

    actions_created = actions_updated = actions_unchanged = 0

    for action_item in yaml_actions:
        action_code = (action_item.get("action_code") or "").strip()

        action_defaults = {
            "action_label": action_item.get("action_label", action_code),
            "description": action_item.get("description", ""),
            "is_active": action_item.get("is_active", True),
            "required_params": json.dumps(action_item.get("required_params") or {}, sort_keys=True),
            "optional_params": json.dumps(action_item.get("optional_params") or {}, sort_keys=True),
            "response_format": json.dumps(action_item.get("response_format") or {}, sort_keys=True),
        }

        if action_code in existing_actions:
            existing = existing_actions.pop(action_code)
            changed = _apply_field_changes(existing, action_defaults)
            if changed:
                existing.save()
                actions_updated += 1
            else:
                actions_unchanged += 1
        else:
            IntegrationAction.objects.create(
                integration_type=obj,
                action_code=action_code,
                **action_defaults,
            )
            actions_created += 1

    # Orphelins : actions en DB mais absentes du YAML
    if mode == "full":
        for orphan in existing_actions.values():
            if orphan.is_active:
                orphan.is_active = False
                orphan.save()
                actions_updated += 1
    # mode additive : orphelins laissés intacts

    AuditService.create_entry(
        user_id=str(user.id) if user and hasattr(user, "id") else "",
        action_type=AuditActionType.CONFIG_SYNC_INTEGRATION_TYPE_IMPORT,
        entity_type=AuditEntityType.INTEGRATION_TYPE_CATALOGUE,
        entity_id=0,
        details={
            "source": "yaml_import",
            "code": code,
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "actions_created": actions_created,
            "actions_updated": actions_updated,
            "actions_unchanged": actions_unchanged,
            "mode": mode,
        },
        correlation_id=get_correlation_id(),
    )

    return (created, updated, unchanged)


# ---------------------------------------------------------------------------
# Bulk export (Story 64.8)
# ---------------------------------------------------------------------------

def export_all_integration_types_yaml() -> bytes:
    """Export all integration type catalogues as multi-document YAML (one document per type)."""
    codes = list(IntegrationTypeCatalogue.objects.values_list('code', flat=True).order_by('code'))
    if not codes:
        return b''
    docs = [export_integration_types_yaml(c).decode('utf-8') for c in codes]
    return ('---\n' + '---\n'.join(docs)).encode('utf-8')
