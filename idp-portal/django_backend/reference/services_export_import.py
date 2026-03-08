"""
Export/import service for Reference Data (engines, categories) in YAML format.
Story 64.1 - IaC round-trip for reference data.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from core.exceptions import InvalidStateError
from core.models import AuditActionType, AuditEntityType
from core.services import AuditService
from core.services_iac_utils import (
    _apply_field_changes,
    parse_yaml,
    serialize_to_yaml,
    update_sync_tracking,
    validate_envelope,
)
from reference.models import RefCategory, RefEngine

# Actor for audit when no user context (sync command, Celery, etc.)
SYSTEM_ACTOR = "system"


def export_reference_yaml(ref_type: str) -> bytes:
    """
    Export reference data (engines or categories) as a YAML bytes envelope.

    Args:
        ref_type: Either 'engines' or 'categories'.

    Returns:
        UTF-8 encoded YAML bytes.

    Raises:
        InvalidStateError: If ref_type is unknown.
    """
    if ref_type == "engines":
        items = RefEngine.objects.all().order_by("display_order", "code")
        spec = []
        for e in items:
            entry = {
                "code": e.code,
                "label": e.label,
                "display_order": e.display_order,
                "is_active": bool(e.is_active),
            }
            if e.icon_url:
                entry["icon_url"] = e.icon_url
            spec.append(entry)

    elif ref_type == "categories":
        items = RefCategory.objects.all().order_by("display_order", "code")
        spec = [
            {
                "code": c.code,
                "label": c.label,
                "display_order": c.display_order,
                "is_active": bool(c.is_active),
            }
            for c in items
        ]

    else:
        raise InvalidStateError(
            code="INVALID_REF_TYPE",
            message=f"Type '{ref_type}' inconnu. Valeurs acceptées : 'engines', 'categories'.",
        )

    root = {
        "apiVersion": "idp/v1",
        "kind": "ReferenceData",
        "metadata": {"type": ref_type},
        "spec": spec,
    }
    return serialize_to_yaml(root)


@transaction.atomic
def import_reference_yaml(
    content: bytes, ref_type: str, mode: str = "additive", user: Any = None
) -> tuple[int, int, int]:
    """
    Import reference data from a YAML bytes envelope (create-or-update).

    Args:
        content: UTF-8 encoded YAML bytes.
        ref_type: Either 'engines' or 'categories'.
        mode: "additive" (default) or "full" — reserved for future use.
        user: Optional Django user instance for audit logging.

    Returns:
        Tuple (created, updated, unchanged).

    Raises:
        InvalidStateError: If the YAML is invalid, the envelope is wrong, or ref_type is unknown.
    """
    if mode not in ("additive", "full"):
        raise InvalidStateError(
            code="INVALID_IMPORT_MODE",
            message=f"Mode invalide '{mode}'. Valeurs acceptées : 'additive', 'full'.",
        )
    parsed = parse_yaml(content)
    validate_envelope(parsed, expected_kind="ReferenceData")

    yaml_type = parsed.get("metadata", {}).get("type")
    if yaml_type != ref_type:
        raise InvalidStateError(
            code="TYPE_MISMATCH",
            message=f"metadata.type='{yaml_type}' ne correspond pas au type attendu '{ref_type}'.",
        )

    Model: type[RefEngine] | type[RefCategory]
    if ref_type == "engines":
        Model = RefEngine
    elif ref_type == "categories":
        Model = RefCategory
    else:
        raise InvalidStateError(
            code="INVALID_REF_TYPE",
            message=f"Type '{ref_type}' inconnu. Valeurs acceptées : 'engines', 'categories'.",
        )

    spec_raw = parsed.get("spec")
    if not isinstance(spec_raw, list):
        raise InvalidStateError(
            code="INVALID_SPEC",
            message="Le champ 'spec' doit être une liste d'objets.",
        )
    spec = spec_raw
    created = updated = unchanged = 0

    for idx, item in enumerate(spec):
        if not isinstance(item, dict):
            raise InvalidStateError(
                code="INVALID_SPEC_ITEM",
                message=f"L'élément spec[{idx}] doit être un objet (dict), reçu : {type(item).__name__}.",
            )
        code = item.get("code")
        if not code:
            raise InvalidStateError(
                code="MISSING_CODE",
                message=f"L'item spec[{idx}] est manquant du champ 'code' obligatoire.",
            )
        defaults = {
            "label": item.get("label", code),
            "display_order": item.get("display_order", 0),
            "is_active": 1 if item.get("is_active", True) else 0,
        }
        if ref_type == "engines":
            defaults["icon_url"] = item.get("icon_url")  # None si absent → efface le champ en DB

        item_yaml = serialize_to_yaml({
            "apiVersion": "idp/v1",
            "kind": "ReferenceData",
            "metadata": {"type": ref_type},
            "spec": [item],
        })

        obj, was_created = Model.objects.get_or_create(code=code, defaults=defaults)
        if was_created:
            created += 1
            update_sync_tracking(obj, item_yaml)
        else:
            changed = _apply_field_changes(obj, defaults)
            if changed:
                obj.save()
                updated += 1
                update_sync_tracking(obj, item_yaml)
            else:
                unchanged += 1

    actor_id = (
        str(user.id) if user and getattr(user, "id", None) else SYSTEM_ACTOR
    )
    AuditService.create_entry(
        user_id=actor_id,
        action_type=AuditActionType.CONFIG_SYNC_REFERENCE_IMPORT,
        entity_type=AuditEntityType.REFERENCE_DATA,
        entity_id=0,  # 0 = opération groupée (BigIntegerField NOT NULL, pas de single entity)
        details={
            "source": "yaml_import",
            "ref_type": ref_type,
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "mode": mode,
        },
    )

    return (created, updated, unchanged)
