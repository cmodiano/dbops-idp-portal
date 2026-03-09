"""
Export/import YAML services for Action (Actions & Workflows).
Story 64.6 - CaC Action management.
Most complex CaC entity: FK refs (integration, policy), M2M tags, mutex rules, 5 JSON fields.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from catalog.models import Action, ActionMutex, ActionTag, BusinessRulePolicy, Tag
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
from integrations.models import Integration

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FK Resolution helpers
# ---------------------------------------------------------------------------

def _resolve_integration_ref(integration_ref: str | None) -> int | None:
    """
    Resolve integration name → Integration.id.

    Returns None if integration_ref is absent/empty.
    Raises InvalidStateError if name provided but Integration not found.
    """
    if not integration_ref:
        return None
    try:
        return Integration.objects.get(name=integration_ref).id
    except Integration.DoesNotExist:
        raise InvalidStateError(
            code="INTEGRATION_NOT_FOUND",
            message=f"Integration '{integration_ref}' introuvable.",
        )


def _resolve_policy_ref(policy_ref: str | None) -> int | None:
    """
    Resolve policy name → BusinessRulePolicy.id.

    Returns None if policy_ref is absent/empty.
    Raises InvalidStateError if name provided but BusinessRulePolicy not found.
    """
    if not policy_ref:
        return None
    try:
        return BusinessRulePolicy.objects.get(name=policy_ref).id
    except BusinessRulePolicy.DoesNotExist:
        raise InvalidStateError(
            code="POLICY_NOT_FOUND",
            message=f"BusinessRulePolicy '{policy_ref}' introuvable.",
        )


# ---------------------------------------------------------------------------
# Tag sync
# ---------------------------------------------------------------------------

def _sync_tags(action: Action, tag_names: list[str], mode: str) -> None:
    """
    Sync ActionTag for an action.

    Additive: add missing ActionTag entries.
    Full: add missing + remove orphan ActionTag entries (tags present in DB but not in YAML).
    Tag names are normalized to strip().lower() for consistency.
    """
    current_tag_names = {
        name.strip().lower()
        for name in ActionTag.objects.filter(action=action)
        .select_related("tag")
        .values_list("tag__name", flat=True)
    }
    target_tag_names = {n.strip().lower() for n in tag_names if n and n.strip()}

    # Add missing tags (case-insensitive lookup to avoid duplicates with mixed-case DB names)
    for tag_name in target_tag_names - current_tag_names:
        tag = Tag.objects.filter(name__iexact=tag_name).first()
        if tag is None:
            tag = Tag.objects.create(name=tag_name)
        ActionTag.objects.get_or_create(action=action, tag=tag)

    # Remove orphans in full mode (case-insensitive match for DB tags like "Terraform")
    if mode == "full":
        orphan_names = current_tag_names - target_tag_names
        for orphan_name in orphan_names:
            ActionTag.objects.filter(action=action, tag__name__iexact=orphan_name).delete()


# ---------------------------------------------------------------------------
# Mutex sync
# ---------------------------------------------------------------------------

def _sync_mutex(action: Action, mutex_specs: list[dict], mode: str) -> None:
    """
    Sync ActionMutex rules for an action.

    Resolves incompatible_with by Action.name.
    Additive: add/update missing rules.
    Full: add/update missing + remove orphan rules.

    Raises:
        InvalidStateError: If incompatible_with action name is not found.
    """
    # Resolve target mutex rules: {incompatible_with_id: spec_dict}
    target_mutex: dict[int, dict] = {}
    for spec in mutex_specs:
        other_name = (spec.get("incompatible_with") or "").strip()
        if not other_name:
            raise InvalidStateError(
                code="MISSING_MUTEX_TARGET",
                message="mutex[].incompatible_with est requis et ne peut être vide.",
            )
        try:
            other_action = Action.objects.get(name=other_name)
        except Action.DoesNotExist:
            raise InvalidStateError(
                code="ACTION_NOT_FOUND",
                message=f"Action mutex '{other_name}' introuvable.",
            )
        target_mutex[other_action.id] = spec

    # Current mutex rules for this action: {incompatible_with_id: ActionMutex}
    current_mutex = {
        m.incompatible_with_id: m
        for m in ActionMutex.objects.filter(action=action)
    }

    # Add or update
    for other_id, spec in target_mutex.items():
        same_target = spec.get("same_target", False)
        description = spec.get("description") or None
        if other_id not in current_mutex:
            ActionMutex.objects.create(
                action=action,
                incompatible_with_id=other_id,
                same_target=same_target,
                description=description,
            )
        else:
            mutex_obj = current_mutex[other_id]
            changed = _apply_field_changes(
                mutex_obj, {"same_target": same_target, "description": description}
            )
            if changed:
                mutex_obj.save()

    # Remove orphans in full mode
    if mode == "full":
        orphan_ids = set(current_mutex.keys()) - set(target_mutex.keys())
        if orphan_ids:
            ActionMutex.objects.filter(
                action=action, incompatible_with_id__in=orphan_ids
            ).delete()


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_action_yaml(name: str) -> bytes:
    """
    Export a single Action as YAML bytes.

    Args:
        name: Action.name (unique lookup key).

    Returns:
        UTF-8 YAML bytes with envelope apiVersion: idp/v1 / kind: Action.

    Raises:
        InvalidStateError: If the action does not exist.
    """
    try:
        obj = Action.objects.select_related(
            "integration", "business_rule_policy"
        ).get(name=name)
    except Action.DoesNotExist:
        raise InvalidStateError(
            code="ACTION_NOT_FOUND",
            message=f"Action '{name}' introuvable.",
        )

    spec: dict[str, Any] = {
        "engine": obj.engine,
        "platform": obj.platform,
        "status": obj.status,
        "item_type": obj.item_type,
        "requires_target": obj.requires_target,
    }

    # Optional scalar fields — omit if None/empty to avoid polluting the YAML
    if obj.description is not None:
        spec["description"] = obj.description
    if obj.category is not None:
        spec["category"] = obj.category
    if obj.default_impact_level is not None:
        spec["default_impact_level"] = obj.default_impact_level
    if obj.documentation_md is not None:
        spec["documentation_md"] = obj.documentation_md

    # FK refs → names (resolve ID to human-readable name)
    if obj.integration_id is not None:
        spec["integration_ref"] = obj.integration.name
    if obj.business_rule_policy_id is not None:
        spec["business_rule_policy_ref"] = obj.business_rule_policy.name

    # Tags: sorted list of normalized names (strip + lower) to align with import
    tag_names = sorted(
        (n.strip().lower() for n in ActionTag.objects.filter(action=obj)
         .select_related("tag")
         .values_list("tag__name", flat=True)
         if n and n.strip())
    )
    if tag_names:
        spec["tags"] = tag_names

    # Mutex rules: ordered by incompatible action name
    mutex_list: list[dict[str, Any]] = []
    for mutex in (
        ActionMutex.objects.filter(action=obj)
        .select_related("incompatible_with")
        .order_by("incompatible_with__name")
    ):
        entry: dict[str, Any] = {
            "incompatible_with": mutex.incompatible_with.name,
            "same_target": mutex.same_target,
        }
        if mutex.description is not None:
            entry["description"] = mutex.description
        mutex_list.append(entry)
    if mutex_list:
        spec["mutex"] = mutex_list

    # JSON fields (OracleJSONField auto-deserializes to dict — use directly)
    if obj.parameters_schema is not None:
        spec["parameters_schema"] = obj.parameters_schema
    if obj.execution_steps is not None:
        spec["execution_steps"] = obj.execution_steps
    if obj.impact_rules is not None:
        spec["impact_rules"] = obj.impact_rules
    if obj.notification_config is not None:
        spec["notification_config"] = obj.notification_config
    if obj.remediation_rules is not None:
        spec["remediation_rules"] = obj.remediation_rules

    root = {
        "apiVersion": "idp/v1",
        "kind": "Action",
        "metadata": {"name": obj.name},
        "spec": spec,
    }
    return serialize_to_yaml(root)


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

@transaction.atomic
def import_action_yaml(
    content: bytes, mode: str = "additive", user: Any | None = None
) -> tuple[int, int, int]:
    """
    Import an Action from YAML bytes.

    Args:
        content: UTF-8 YAML bytes.
        mode: "additive" (default) or "full".
            Additive: create/update action, add missing tags/mutex rules (leave existing).
            Full: create/update action, sync tags/mutex rules (remove orphans).
        user: User performing the import (optional — created_by is nullable on Action).

    Returns:
        Tuple (created, updated, unchanged).

    Raises:
        InvalidStateError: If YAML is invalid, envelope is wrong, mode invalid,
                           or a referenced entity (integration, policy, mutex action) is not found.
    """
    if mode not in ("additive", "full"):
        raise InvalidStateError(
            code="INVALID_IMPORT_MODE",
            message=f"Mode invalide '{mode}'. Valeurs acceptées : 'additive', 'full'.",
        )

    parsed = parse_yaml(content)
    validate_envelope(parsed, expected_kind="Action")

    metadata = parsed.get("metadata", {})
    spec = parsed.get("spec", {})

    name = (metadata.get("name") or "").strip()

    # Validate required engine and platform before building action_fields
    engine = (spec.get("engine") or "").strip()
    platform = (spec.get("platform") or "").strip()
    if not engine:
        raise InvalidStateError(
            code="MISSING_ENGINE",
            message="Le champ 'spec.engine' est requis et ne peut être vide.",
        )
    if not platform:
        raise InvalidStateError(
            code="MISSING_PLATFORM",
            message="Le champ 'spec.platform' est requis et ne peut être vide.",
        )

    # Resolve FK references (raises if name given but not found)
    integration_id = _resolve_integration_ref(spec.get("integration_ref"))
    policy_id = _resolve_policy_ref(spec.get("business_rule_policy_ref"))

    # Validate execution_steps for workflow items (Story 65.7 — AC #2, #3)
    execution_steps_raw = spec.get("execution_steps")
    item_type_raw = spec.get("item_type", "action")
    if execution_steps_raw is not None and item_type_raw == "workflow":
        from catalog.validation import validate_workflow_steps  # local import to avoid circular deps
        from rest_framework.exceptions import ValidationError as DRFValidationError
        try:
            validate_workflow_steps(execution_steps_raw, action_id=None)
        except DRFValidationError as exc:
            detail = exc.detail
            msg = str(detail)
            if isinstance(detail, list):
                msg = "; ".join(str(e) for e in detail)
            elif isinstance(detail, dict):
                msg = "; ".join(f"{k}: {v}" for k, v in detail.items())
            raise InvalidStateError(
                code="INVALID_WORKFLOW_STEPS",
                message=f"execution_steps invalides : {msg}",
            ) from exc

    # Prepare Action scalar/JSON fields (excluding tags, mutex, runtime fields)
    action_fields: dict[str, Any] = {
        "engine": engine,
        "platform": platform,
        "status": spec.get("status", "draft"),
        "item_type": spec.get("item_type", "action"),
        "requires_target": spec.get("requires_target", True),
        "description": spec.get("description") or None,
        "category": spec.get("category") or None,
        "default_impact_level": spec.get("default_impact_level") or None,
        "documentation_md": spec.get("documentation_md") or None,
        "integration_id": integration_id,
        "business_rule_policy_id": policy_id,
        "parameters_schema": spec.get("parameters_schema"),
        "execution_steps": spec.get("execution_steps"),
        "impact_rules": spec.get("impact_rules"),
        "notification_config": spec.get("notification_config"),
        "remediation_rules": spec.get("remediation_rules"),
    }

    existing = Action.objects.filter(name=name).first()

    if existing is None:
        # Creating — include created_by if user provided (field is nullable)
        defaults: dict[str, Any] = {**action_fields}
        if user is not None:
            defaults["created_by"] = user
        obj, was_created = Action.objects.get_or_create(name=name, defaults=defaults)
        if was_created:
            created, updated, unchanged = 1, 0, 0
            update_sync_tracking(obj, content)
        else:
            # Race condition: created between filter and get_or_create — treat as update
            changed = _apply_field_changes(obj, action_fields)
            if changed:
                obj.save()
                created, updated, unchanged = 0, 1, 0
                update_sync_tracking(obj, content)
            else:
                created, updated, unchanged = 0, 0, 1
    else:
        # Updating — do NOT modify created_by
        obj = existing
        changed = _apply_field_changes(obj, action_fields)
        if changed:
            obj.save()
            created, updated, unchanged = 0, 1, 0
            update_sync_tracking(obj, content)
        else:
            created, updated, unchanged = 0, 0, 1

    # Sync tags
    tag_names: list[str] = spec.get("tags") or []
    _sync_tags(obj, tag_names, mode)

    # Sync mutex rules
    mutex_specs: list[dict] = spec.get("mutex") or []
    _sync_mutex(obj, mutex_specs, mode)

    # Resolve user_id for audit: explicit fallback for None or unexpected user objects
    if user is None:
        user_id = ""
    elif hasattr(user, "id") and user.id is not None:
        user_id = str(user.id)
    else:
        logger.warning(
            "import_action_yaml received user without id (e.g. AnonymousUser), using empty user_id"
        )
        user_id = ""

    AuditService.create_entry(
        user_id=user_id,
        action_type=AuditActionType.CONFIG_SYNC_ACTION_IMPORT,
        entity_type=AuditEntityType.ACTION,
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

def export_actions_yaml() -> bytes:
    """Export all actions as multi-document YAML (one document per action, separated by ---)."""
    names = list(Action.objects.values_list('name', flat=True).order_by('name'))
    if not names:
        return b''
    docs = [export_action_yaml(n).decode('utf-8') for n in names]
    return ('---\n' + '---\n'.join(docs)).encode('utf-8')
