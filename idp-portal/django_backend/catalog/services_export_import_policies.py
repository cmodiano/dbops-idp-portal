"""
Export/import YAML services for BusinessRulePolicy.
Story 64.5 - CaC Business Rule Policy management.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from catalog.models import BusinessRulePolicy
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


def export_policy_yaml(name: str) -> bytes:
    """
    Export a single BusinessRulePolicy as YAML bytes.

    Args:
        name: BusinessRulePolicy.name (unique lookup key).

    Returns:
        UTF-8 YAML bytes with envelope apiVersion: idp/v1 / kind: BusinessRulePolicy.

    Raises:
        InvalidStateError: If the policy does not exist.
    """
    try:
        obj = BusinessRulePolicy.objects.get(name=name)
    except BusinessRulePolicy.DoesNotExist:
        raise InvalidStateError(
            code="POLICY_NOT_FOUND",
            message=f"BusinessRulePolicy '{name}' introuvable.",
        )

    spec: dict[str, Any] = {
        "is_active": obj.is_active,
        "policy_json": obj.policy_json,  # OracleJSONField retourne dict directement
    }
    if obj.description:
        spec["description"] = obj.description

    root = {
        "apiVersion": "idp/v1",
        "kind": "BusinessRulePolicy",
        "metadata": {
            "name": obj.name,
        },
        "spec": spec,
    }
    return serialize_to_yaml(root)


@transaction.atomic
def import_policy_yaml(
    content: bytes, mode: str = "additive", user: Any | None = None
) -> tuple[int, int, int]:
    """
    Import a BusinessRulePolicy from YAML bytes.

    Args:
        content: UTF-8 YAML bytes.
        mode: "additive" (default) or "full" — reserved for future use.
        user: User performing the import (required when creating a new policy).

    Returns:
        Tuple (created, updated, unchanged).

    Raises:
        InvalidStateError: If YAML is invalid, envelope is wrong, mode invalid,
                           or user is None when creating.
    """
    if mode not in ("additive", "full"):
        raise InvalidStateError(
            code="INVALID_IMPORT_MODE",
            message=f"Mode invalide '{mode}'. Valeurs acceptées : 'additive', 'full'.",
        )

    parsed = parse_yaml(content)
    validate_envelope(parsed, expected_kind="BusinessRulePolicy")

    metadata = parsed.get("metadata", {})
    spec = parsed.get("spec", {})

    if not isinstance(spec, dict):
        raise InvalidStateError(
            code="INVALID_SPEC",
            message="Le champ 'spec' doit être un objet YAML.",
        )

    name = (metadata.get("name") or "").strip()

    if not name:
        raise InvalidStateError(
            code="MISSING_NAME",
            message="Le champ 'metadata.name' est requis.",
        )

    policy_json = spec.get("policy_json")
    if policy_json is None:
        raise InvalidStateError(
            code="MISSING_POLICY_JSON",
            message="Le champ 'spec.policy_json' est requis.",
        )
    if not isinstance(policy_json, dict):
        raise InvalidStateError(
            code="INVALID_POLICY_JSON",
            message="Le champ 'spec.policy_json' doit être un objet YAML.",
        )
    is_active = spec.get("is_active", True)
    description = spec.get("description") or None

    def _raise_validation_error(exc: ValidationError) -> None:
        msg = str(exc) if exc.messages else "Données de policy invalides."
        details = getattr(exc, "message_dict", {}) or {}
        raise InvalidStateError(
            code="VALIDATION_ERROR",
            message=msg,
            details=details,
        ) from exc

    # Check if policy already exists (determines whether we need user for created_by)
    existing = BusinessRulePolicy.objects.filter(name=name).first()

    if existing is None:
        # Creating a new policy — user is required for created_by
        if user is None:
            raise InvalidStateError(
                code="MISSING_USER",
                message="Un utilisateur est requis pour créer une BusinessRulePolicy (created_by).",
            )
        # Validate model fields before persisting (create path only)
        obj_to_validate = BusinessRulePolicy(
            name=name,
            policy_json=policy_json,  # type: ignore[misc]
            is_active=is_active,
            description=description,
            created_by=user,
        )
        try:
            obj_to_validate.full_clean()
        except ValidationError as e:
            _raise_validation_error(e)
        defaults: dict[str, Any] = {
            "policy_json": policy_json,
            "is_active": is_active,
            "description": description,
            "created_by": user,
        }
        obj, was_created = BusinessRulePolicy.objects.get_or_create(name=name, defaults=defaults)
        if was_created:
            created, updated, unchanged = 1, 0, 0
            update_sync_tracking(obj, content)
        else:
            # Race condition: created between filter and get_or_create — treat as update
            update_defaults = {"policy_json": policy_json, "is_active": is_active, "description": description}
            changed = _apply_field_changes(obj, update_defaults)
            if changed:
                try:
                    obj.full_clean()
                except ValidationError as e:
                    _raise_validation_error(e)
                obj.save()
                created, updated, unchanged = 0, 1, 0
                update_sync_tracking(obj, content)
            else:
                created, updated, unchanged = 0, 0, 1
    else:
        # Updating existing policy — created_by is NOT modified
        update_defaults = {"policy_json": policy_json, "is_active": is_active, "description": description}
        changed = _apply_field_changes(existing, update_defaults)
        if changed:
            try:
                existing.full_clean()
            except ValidationError as e:
                _raise_validation_error(e)
            existing.save()
            created, updated, unchanged = 0, 1, 0
            update_sync_tracking(existing, content)
        else:
            created, updated, unchanged = 0, 0, 1
        obj = existing

    AuditService.create_entry(
        user_id=str(user.id) if user and hasattr(user, "id") else "",
        action_type=AuditActionType.CONFIG_SYNC_POLICY_IMPORT,
        entity_type=AuditEntityType.BUSINESS_RULE_POLICY,
        entity_id=obj.id,
        details={
            "source": "yaml_import",
            "name": name,
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

def export_policies_yaml() -> bytes:
    """Export all business rule policies as multi-document YAML (one document per policy)."""
    names = list(BusinessRulePolicy.objects.values_list('name', flat=True).order_by('name'))
    if not names:
        return b''
    docs = [export_policy_yaml(n).decode('utf-8') for n in names]
    return ('---\n' + '---\n'.join(docs)).encode('utf-8')
