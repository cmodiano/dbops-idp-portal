"""
Export/import YAML services for core entities (FeatureFlags).
Story 64.2 - IaC FeatureFlags management.
"""

from typing import Any

from django.db import transaction

from core.exceptions import InvalidStateError
from core.models import AuditActionType, AuditEntityType, FeatureFlag
from core.services import AuditService
from core.services_iac_utils import (
    _apply_field_changes,
    parse_yaml,
    serialize_to_yaml,
    update_sync_tracking,
    validate_envelope,
)


def export_feature_flags_yaml() -> bytes:
    """
    Export all FeatureFlags to YAML bytes.

    Returns:
        UTF-8 YAML bytes with envelope apiVersion: idp/v1 / kind: FeatureFlags.
    """
    flags = FeatureFlag.objects.all().order_by("flag_key")
    spec = [
        {
            "flag_key": f.flag_key,
            "enabled": f.enabled,
            "rollout_percent": f.rollout_percent,
            "description": f.description,
        }
        for f in flags
    ]
    root = {
        "apiVersion": "idp/v1",
        "kind": "FeatureFlags",
        "metadata": {},
        "spec": spec,
    }
    return serialize_to_yaml(root)


@transaction.atomic
def import_feature_flags_yaml(content: bytes, user: Any | None = None) -> tuple[int, int, int]:
    """
    Import FeatureFlags from YAML bytes (create-or-update on flag_key).

    Args:
        content: UTF-8 YAML bytes.
        user: Optional user performing the import (for audit and updated_by).

    Returns:
        Tuple (created, updated, unchanged).

    Raises:
        InvalidStateError: If YAML is invalid, envelope is wrong, or flag_key is missing.
    """
    parsed = parse_yaml(content)
    validate_envelope(parsed, expected_kind="FeatureFlags")

    spec = parsed.get("spec") or []
    created = updated = unchanged = 0

    for item in spec:
        flag_key = item.get("flag_key", "").strip() if isinstance(item, dict) else ""
        if not flag_key:
            raise InvalidStateError(
                code="MISSING_FLAG_KEY",
                message="Chaque feature flag doit avoir un 'flag_key' non vide.",
            )

        defaults = {
            "enabled": item.get("enabled", False),
            "rollout_percent": item.get("rollout_percent", 0),
            "description": item.get("description", ""),
        }
        if user:
            defaults["updated_by"] = (
                user.username if hasattr(user, "username") else str(user)
            )

        item_yaml = serialize_to_yaml({
            "apiVersion": "idp/v1",
            "kind": "FeatureFlags",
            "metadata": {},
            "spec": [item],
        })

        obj, was_created = FeatureFlag.objects.get_or_create(
            flag_key=flag_key, defaults=defaults
        )
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

    AuditService.create_entry(
        user_id=str(user.id) if user and hasattr(user, "id") else "",
        action_type=AuditActionType.CONFIG_SYNC_FEATURE_FLAGS_IMPORT,
        entity_type=AuditEntityType.FEATURE_FLAG,
        entity_id=0,
        details={
            "source": "yaml_import",
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
        },
    )

    return (created, updated, unchanged)
