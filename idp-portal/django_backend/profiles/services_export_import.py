"""
Profile YAML export/import service (Story M.5 / Story 64.7).

Story 64.7: Upgrade to IaC envelope format with portable action_names,
is_approver, exclusion_patterns, filter_by_attribute support.
"""

import structlog
from typing import Any

from django.db import transaction

from catalog.models import Action
from core.exceptions import InvalidStateError
from core.services_iac_utils import parse_yaml, serialize_to_yaml, update_sync_tracking, validate_envelope
from profiles.models import Profile
from profiles.services import ProfileService

logger = structlog.get_logger(__name__)

_PERMISSION_TYPE_MAP = {"LIST": "list", "PATTERN": "pattern", "ALL": "all"}


# ──────────────────────────────────────────────────────────────────
# Helpers — résolution action IDs ↔ noms
# ──────────────────────────────────────────────────────────────────

def _resolve_action_ids_to_names(action_ids: list[int]) -> list[str]:
    """Resolve Action IDs to sorted names. Orphan IDs are skipped with a warning."""
    if not action_ids:
        return []
    found = {a.id: a.name for a in Action.objects.filter(id__in=action_ids)}
    names = []
    for aid in action_ids:
        if aid in found:
            names.append(found[aid])
        else:
            logger.warning("action_id_not_found_at_export", action_id=aid)
    return sorted(names)


def _resolve_action_names_to_ids(action_names: list[str]) -> list[int]:
    """Resolve Action names to IDs. Unknown names raise REF_NOT_FOUND."""
    if not action_names:
        return []
    found = {a.name: a.id for a in Action.objects.filter(name__in=action_names)}
    ids = []
    missing = []
    for name in action_names:
        if name in found:
            ids.append(found[name])
        else:
            missing.append(name)
    if missing:
        raise InvalidStateError(
            code="REF_NOT_FOUND",
            message=f"Actions introuvables : {', '.join(missing)}",
            details={"missing_actions": missing},
        )
    return ids


# ──────────────────────────────────────────────────────────────────
# Bloc builders
# ──────────────────────────────────────────────────────────────────

def _build_actions_block(
    perm_type: str,
    action_names: list[str] | None,
    tag_patterns: list[str] | None,
) -> dict[str, Any]:
    """Build YAML actions block using portable action_names (not raw IDs)."""
    if perm_type == "all":
        return {"type": "all"}
    if perm_type == "pattern":
        return {"type": "pattern", "patterns": tag_patterns or []}
    return {"type": "list", "action_names": action_names or []}


def _build_targets_block(
    perm_type: str,
    target_names: list[str] | None,
    target_patterns: list[str] | None,
) -> dict[str, Any]:
    """Build YAML targets block: type + patterns or list."""
    if perm_type == "all":
        return {"type": "all"}
    if perm_type == "pattern":
        return {"type": "pattern", "patterns": target_patterns or []}
    return {"type": "list", "list": target_names or []}


# ──────────────────────────────────────────────────────────────────
# Single-profile export (new IaC envelope format)
# ──────────────────────────────────────────────────────────────────

def export_profile_yaml(name: str) -> bytes:
    """
    Export a single profile as YAML with IaC envelope (apiVersion/kind/metadata/spec).

    Args:
        name: Profile name to export.

    Returns:
        UTF-8 YAML bytes.

    Raises:
        InvalidStateError(code="PROFILE_NOT_FOUND") if the profile does not exist.
    """
    try:
        profile = Profile.objects.get(name=name)
    except Profile.DoesNotExist:
        raise InvalidStateError(
            code="PROFILE_NOT_FOUND",
            message=f"Profil introuvable : '{name}'.",
            details={"name": name},
        )

    service = ProfileService()
    actions_perm = service.get_action_permissions(profile.id)
    targets_perm = service.get_target_permissions(profile.id)

    # --- metadata ---
    metadata: dict[str, Any] = {"name": profile.name}
    if profile.description:
        metadata["description"] = profile.description
    if profile.ad_group:
        metadata["ad_group"] = profile.ad_group

    # --- spec ---
    spec: dict[str, Any] = {
        "is_admin": bool(profile.is_admin),
        "is_auditor": bool(profile.is_auditor),
        "is_approver": bool(profile.is_approver),
    }

    # actions block
    if actions_perm is None:
        spec["actions"] = {"type": "all"}
    else:
        actions_type = _PERMISSION_TYPE_MAP.get(actions_perm.permission_type, "all")
        if actions_type == "list":
            action_names = _resolve_action_ids_to_names(actions_perm.get_action_ids())
            spec["actions"] = _build_actions_block(actions_type, action_names, None)
        else:
            spec["actions"] = _build_actions_block(
                actions_type, None, actions_perm.get_tag_patterns()
            )
        envs = actions_perm.get_environments()
        if envs:
            spec["environments"] = envs

    # targets block
    if targets_perm is None:
        spec["targets"] = {"type": "all"}
    else:
        targets_type = _PERMISSION_TYPE_MAP.get(targets_perm.permission_type, "all")
        targets_block = _build_targets_block(
            targets_type,
            targets_perm.get_target_names(),
            targets_perm.get_target_patterns(),
        )
        exclusion_patterns = targets_perm.get_exclusion_patterns()
        if exclusion_patterns:
            targets_block["exclusion_patterns"] = exclusion_patterns
        filter_by_attribute = targets_perm.get_filter_by_attribute()
        if filter_by_attribute is not None:
            targets_block["filter_by_attribute"] = filter_by_attribute
        spec["targets"] = targets_block

    doc = {
        "apiVersion": "idp/v1",
        "kind": "Profile",
        "metadata": metadata,
        "spec": spec,
    }
    return serialize_to_yaml(doc)


# ──────────────────────────────────────────────────────────────────
# Bulk export (extended flat format — backward compat + new fields)
# ──────────────────────────────────────────────────────────────────

def export_profiles_yaml() -> bytes:
    """
    Export all profiles and their permissions as YAML (flat format).
    Includes is_approver, exclusion_patterns, filter_by_attribute, action_names.

    Returns:
        UTF-8 bytes for Response
    """
    service = ProfileService()
    items = service.list_all()
    profiles_data: list[dict[str, Any]] = []

    for item in items:
        full = service.get_by_id(item.id)
        if full is None:
            continue

        actions_perm = service.get_action_permissions(item.id)
        targets_perm = service.get_target_permissions(item.id)

        if actions_perm is None:
            actions_block: dict[str, Any] = {"type": "all"}
        else:
            actions_type = _PERMISSION_TYPE_MAP.get(actions_perm.permission_type, "all")
            if actions_type == "list":
                action_names = _resolve_action_ids_to_names(actions_perm.get_action_ids())
                actions_block = _build_actions_block(actions_type, action_names, None)
            else:
                actions_block = _build_actions_block(
                    actions_type, None, actions_perm.get_tag_patterns()
                )

        if targets_perm is None:
            targets_block: dict[str, Any] = {"type": "all"}
        else:
            targets_type = _PERMISSION_TYPE_MAP.get(targets_perm.permission_type, "all")
            targets_block = _build_targets_block(
                targets_type,
                targets_perm.get_target_names(),
                targets_perm.get_target_patterns(),
            )
            exclusion_patterns = targets_perm.get_exclusion_patterns()
            if exclusion_patterns:
                targets_block["exclusion_patterns"] = exclusion_patterns
            filter_by_attribute = targets_perm.get_filter_by_attribute()
            if filter_by_attribute is not None:
                targets_block["filter_by_attribute"] = filter_by_attribute

        profiles_data.append({
            "name": full.name,
            "description": full.description,
            "ad_group": full.ad_group,
            "is_admin": bool(full.is_admin),
            "is_auditor": bool(full.is_auditor),
            "is_approver": bool(full.is_approver),
            "actions": actions_block,
            "targets": targets_block,
            "environments": actions_perm.get_environments() if actions_perm else [],
        })

    root = {"profiles": profiles_data}
    return serialize_to_yaml(root)


# ──────────────────────────────────────────────────────────────────
# Payload helpers (YAML item → service call)
# ──────────────────────────────────────────────────────────────────

def _yaml_item_to_action_payload(item: dict) -> dict:
    """Convert YAML item actions block to ProfileActionPermissionsUpdate format.

    Supports:
    - New format: actions.action_names (list of strings — portable)
    - Old format: actions.list (list of ints — backward compat)
    """
    a = item.get("actions", {})
    actions_type = a.get("type", "all")
    action_names = a.get("action_names")   # nouveau format (noms portables)
    action_ids_raw = a.get("list")          # ancien format (IDs — backward compat)
    patterns = a.get("patterns")

    action_ids: list[int] | None = None

    if actions_type == "list":
        if action_names:
            # New format: resolve names to IDs
            action_ids = _resolve_action_names_to_ids(action_names)
        elif action_ids_raw:
            # Old format: IDs directly
            action_ids = action_ids_raw
        else:
            # Empty — fall back to all
            actions_type = "all"

    return {
        "actions_type": actions_type,
        "action_ids": action_ids,
        "tag_patterns": patterns,
        "environments": item.get("environments") or None,
    }


def _permissions_differ(
    service: ProfileService,
    profile_id: int,
    actions_payload: dict,
    targets_payload: dict,
) -> bool:
    """Return True if incoming payload differs from current permissions."""
    type_map = {"list": "LIST", "pattern": "PATTERN", "all": "ALL"}
    incoming_actions_type = type_map.get(actions_payload.get("actions_type", "all"), "ALL")
    incoming_targets_type = type_map.get(targets_payload.get("targets_type", "all"), "ALL")

    actions_perm = service.get_action_permissions(profile_id)
    current_actions_type = actions_perm.permission_type if actions_perm else "ALL"
    if current_actions_type != incoming_actions_type:
        return True
    if actions_perm and incoming_actions_type == "PATTERN":
        incoming_pt = tuple(actions_payload.get("tag_patterns") or [])
        current_pt = tuple(actions_perm.get_tag_patterns() or [])
        if incoming_pt != current_pt:
            return True
    if actions_perm and incoming_actions_type == "LIST":
        incoming_ids = tuple(sorted(actions_payload.get("action_ids") or []))
        current_ids = tuple(sorted(actions_perm.get_action_ids() or []))
        if incoming_ids != current_ids:
            return True

    targets_perm = service.get_target_permissions(profile_id)
    current_targets_type = targets_perm.permission_type if targets_perm else "ALL"
    if current_targets_type != incoming_targets_type:
        return True
    if targets_perm and incoming_targets_type == "PATTERN":
        incoming_pt = tuple(targets_payload.get("target_patterns") or [])
        current_pt = tuple(targets_perm.get_target_patterns() or [])
        if incoming_pt != current_pt:
            return True
    if targets_perm and incoming_targets_type == "LIST":
        incoming_names = tuple(sorted(targets_payload.get("target_names") or []))
        current_names = tuple(sorted(targets_perm.get_target_names() or []))
        if incoming_names != current_names:
            return True
    return False


def _yaml_item_to_target_payload(item: dict) -> dict:
    """Convert YAML item targets block to ProfileTargetPermissionsUpdate format."""
    t = item.get("targets", {})
    targets_type = t.get("type", "all")
    target_names = t.get("list")
    patterns = t.get("patterns")

    if targets_type == "list" and (not target_names):
        targets_type = "all"
        target_names = None

    return {
        "targets_type": targets_type,
        "target_names": target_names,
        "target_patterns": patterns,
        "exclusion_patterns": t.get("exclusion_patterns") or None,
        "filter_by_attribute": t.get("filter_by_attribute") or None,
    }


# ──────────────────────────────────────────────────────────────────
# Schema validation (flat format only)
# ──────────────────────────────────────────────────────────────────

def _validate_yaml_schema(parsed: dict[str, Any]) -> None:
    """
    Validate YAML schema structure (flat format only).
    Raises InvalidStateError if validation fails.
    """
    if not isinstance(parsed, dict):
        raise InvalidStateError(
            code="INVALID_YAML_SCHEMA",
            message="Le fichier YAML doit être un objet.",
            details={}
        )

    if "profiles" not in parsed:
        raise InvalidStateError(
            code="INVALID_YAML_SCHEMA",
            message="Le fichier YAML doit contenir une clé 'profiles'.",
            details={}
        )

    if not isinstance(parsed["profiles"], list):
        raise InvalidStateError(
            code="INVALID_YAML_SCHEMA",
            message="La clé 'profiles' doit être une liste.",
            details={}
        )

    seen_names: set[str] = set()
    for idx, item in enumerate(parsed["profiles"]):
        if not isinstance(item, dict):
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="Chaque profil doit être un objet.",
                details={"profile_index": idx}
            )

        name = item.get("name", "").strip() if item.get("name") else ""
        if not name:
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="Un profil a un nom vide.",
                details={"profile_index": idx}
            )

        ad_group = item.get("ad_group", "").strip() if item.get("ad_group") else ""
        if not ad_group:
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="Un profil a un ad_group vide.",
                details={"profile_name": name}
            )

        if name.lower() in seen_names:
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message=f"Nom de profil en doublon dans le fichier : '{name}'.",
                details={"profile_name": name, "profile_index": idx}
            )
        seen_names.add(name.lower())

        actions = item.get("actions")
        if not actions or not isinstance(actions, dict):
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="Chaque profil doit avoir un bloc 'actions'.",
                details={"profile_name": name}
            )

        actions_type = actions.get("type")
        if actions_type not in ["list", "pattern", "all"]:
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="Le type d'actions doit être 'list', 'pattern' ou 'all'.",
                details={"profile_name": name}
            )

        # Accept action_names (new format) OR list (old format with IDs)
        if actions_type == "list" and not actions.get("list") and not actions.get("action_names"):
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="'action_names' ou 'list' (action_ids) est requis quand le type d'actions est 'list'.",
                details={"profile_name": name}
            )

        if actions_type == "pattern" and not actions.get("patterns"):
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="'patterns' est requis quand le type d'actions est 'pattern'.",
                details={"profile_name": name}
            )

        targets = item.get("targets")
        if not targets or not isinstance(targets, dict):
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="Chaque profil doit avoir un bloc 'targets'.",
                details={"profile_name": name}
            )

        targets_type = targets.get("type")
        if targets_type not in ["list", "pattern", "all"]:
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="Le type de targets doit être 'list', 'pattern' ou 'all'.",
                details={"profile_name": name}
            )

        if targets_type == "list" and not targets.get("list"):
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="'list' (target_names) est requis quand le type de targets est 'list'.",
                details={"profile_name": name}
            )

        if targets_type == "pattern" and not targets.get("patterns"):
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="'patterns' est requis quand le type de targets est 'pattern'.",
                details={"profile_name": name}
            )


# ──────────────────────────────────────────────────────────────────
# Import
# ──────────────────────────────────────────────────────────────────

def _envelope_to_item(parsed: dict) -> dict:
    """Convert envelope format (apiVersion/kind/metadata/spec) to a flat item dict."""
    if not isinstance(parsed, dict):
        raise InvalidStateError(
            code="INVALID_YAML_SCHEMA",
            message="Le document parsé doit être un objet.",
            details={},
        )
    metadata = parsed.get("metadata")
    spec = parsed.get("spec")
    if not isinstance(metadata, dict):
        metadata = {}
    if not isinstance(spec, dict):
        spec = {}
    name = metadata.get("name")
    if not name or not isinstance(name, str) or not str(name).strip():
        raise InvalidStateError(
            code="INVALID_METADATA",
            message="Le champ 'metadata.name' est requis et doit être une chaîne non vide.",
            details={},
        )
    actions = spec.get("actions")
    if not isinstance(actions, dict):
        actions = {"type": "all"}
    targets = spec.get("targets")
    if not isinstance(targets, dict):
        targets = {"type": "all"}
    environments = spec.get("environments")
    if environments is not None and not isinstance(environments, list):
        environments = None
    return {
        "name": str(name).strip(),
        "ad_group": metadata.get("ad_group", "") or "",
        "description": metadata.get("description"),
        "is_admin": spec.get("is_admin", False),
        "is_auditor": spec.get("is_auditor", False),
        "is_approver": spec.get("is_approver", False),
        "actions": actions,
        "targets": targets,
        "environments": environments,
    }


@transaction.atomic
def import_profiles_yaml(content: bytes, user: Any = None, mode: str = "additive") -> tuple[int, int, int]:
    """
    Import profiles from YAML. Auto-detects format:
    - Envelope format: apiVersion/kind/metadata/spec (new — single profile)
    - Flat format: profiles: [...] (legacy — multiple profiles)

    Args:
        content: YAML file content as bytes
        user: Optional user instance for audit logging
        mode: Import mode (currently unused functionally; kept for IaC interface consistency)

    Returns:
        Tuple of (created_count, updated_count, unchanged_count)

    Raises:
        InvalidStateError: If YAML syntax or schema is invalid, or action names not found
    """
    parsed = parse_yaml(content)

    if parsed.get("apiVersion") == "idp/v1":
        # New envelope format — single profile
        validate_envelope(parsed, expected_kind="Profile")
        item = _envelope_to_item(parsed)
        if not item.get("ad_group", "").strip():
            raise InvalidStateError(
                code="INVALID_METADATA",
                message="L'envelope Profile requiert 'metadata.ad_group'.",
                details={"name": item.get("name", "")},
            )
        items = [item]
        is_envelope = True
    else:
        # Flat format — backward compat
        _validate_yaml_schema(parsed)
        items = parsed["profiles"]
        is_envelope = False

    service = ProfileService()
    created = 0
    updated = 0
    unchanged = 0

    for item in items:
        name_stripped = item["name"].strip()
        existing = service.get_by_name(name_stripped)

        # Determine yaml bytes for this specific entity (for sync tracking)
        if is_envelope:
            item_yaml: bytes = content
        else:
            item_yaml = serialize_to_yaml({
                "apiVersion": "idp/v1",
                "kind": "Profile",
                "metadata": {
                    "name": item["name"],
                    "ad_group": item.get("ad_group", ""),
                },
                "spec": {
                    "is_admin": bool(item.get("is_admin", False)),
                    "is_auditor": bool(item.get("is_auditor", False)),
                    "is_approver": bool(item.get("is_approver", False)),
                    "actions": item.get("actions", {"type": "all"}),
                    "targets": item.get("targets", {"type": "all"}),
                },
            })

        actions_payload = _yaml_item_to_action_payload(item)
        targets_payload = _yaml_item_to_target_payload(item)

        if existing:
            profile_update_data = {
                "name": name_stripped,
                "description": item.get("description"),
                "ad_group": item.get("ad_group", "").strip(),
                "is_admin": item.get("is_admin", False),
                "is_auditor": item.get("is_auditor", False),
                "is_approver": item.get("is_approver", False),
            }
            fields_changed = (
                (existing.description or None) != (profile_update_data["description"] or None)
                or existing.ad_group != profile_update_data["ad_group"]
                or bool(existing.is_admin) != bool(profile_update_data["is_admin"])
                or bool(existing.is_auditor) != bool(profile_update_data["is_auditor"])
                or bool(existing.is_approver) != bool(profile_update_data["is_approver"])
            )
            perms_changed = _permissions_differ(
                service, existing.id, actions_payload, targets_payload
            )
            if fields_changed or perms_changed:
                service.update_profile(existing.id, profile_update_data, user=user)
                updated += 1
                update_sync_tracking(existing, item_yaml)
            else:
                unchanged += 1
            profile_id = existing.id
        else:
            profile_create_data = {
                "name": name_stripped,
                "description": item.get("description"),
                "ad_group": item.get("ad_group", "").strip(),
                "is_admin": item.get("is_admin", False),
                "is_auditor": item.get("is_auditor", False),
                "is_approver": item.get("is_approver", False),
            }
            profile = service.create_profile(profile_create_data, user=user)
            profile_id = profile.id
            created += 1
            update_sync_tracking(profile, item_yaml)

        service.set_action_permissions(profile_id, actions_payload)
        service.set_target_permissions(profile_id, targets_payload)

    return (created, updated, unchanged)
