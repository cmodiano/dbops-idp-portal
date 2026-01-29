"""Profile YAML export/import service (Story 2.13, AC1–AC5)."""

from __future__ import annotations

import io
from typing import Any

import yaml
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import InvalidStateError
from app.models.profile import (
    ProfileCreate,
    ProfileUpdate,
    ProfileActionPermissionsUpdate,
    ProfileTargetPermissionsUpdate,
)
from app.models.profile_import import ProfileYamlItem, ProfilesYamlImport
from app.repositories import profile_repository
from app.repositories import profile_action_permission_repository
from app.repositories import profile_target_permission_repository


def _build_actions_block(perm_type: str, action_ids: list[int] | None, tag_patterns: list[str] | None) -> dict[str, Any]:
    """Build YAML actions block: type + patterns or list."""
    if perm_type == "all":
        return {"type": "all"}
    if perm_type == "pattern":
        return {"type": "pattern", "patterns": tag_patterns or []}
    return {"type": "list", "list": action_ids or []}


def _build_targets_block(perm_type: str, target_names: list[str] | None, target_patterns: list[str] | None) -> dict[str, Any]:
    """Build YAML targets block: type + patterns or list."""
    if perm_type == "all":
        return {"type": "all"}
    if perm_type == "pattern":
        return {"type": "pattern", "patterns": target_patterns or []}
    return {"type": "list", "list": target_names or []}


async def export_profiles_yaml() -> bytes:
    """Export all profiles and their permissions as YAML (AC1, AC5, Task 2.1–2.2).

    Fetches get_all(), then for each profile: get_by_id, get_actions_permissions, get_target_permissions.
    Builds structure: { profiles: [ { name, description, ad_group, is_admin, is_auditor, actions, targets, environments } ] }.
    Returns UTF-8 bytes for StreamingResponse/Response.
    """
    items = await profile_repository.get_all()
    profiles_data: list[dict[str, Any]] = []

    for item in items:
        full = await profile_repository.get_by_id(item.id)
        if full is None:
            continue
        actions_perm = await profile_action_permission_repository.get_actions_permissions(item.id)
        targets_perm = await profile_target_permission_repository.get_target_permissions(item.id)

        if actions_perm is None:
            actions_block = {"type": "all"}
        else:
            actions_block = _build_actions_block(
                actions_perm.actions_type,
                actions_perm.action_ids,
                actions_perm.tag_patterns,
            )
        if targets_perm is None:
            targets_block = {"type": "all"}
        else:
            targets_block = _build_targets_block(
                targets_perm.targets_type,
                targets_perm.target_names,
                targets_perm.target_patterns,
            )

        profiles_data.append({
            "name": full.name,
            "description": full.description,
            "ad_group": full.ad_group,
            "is_admin": full.is_admin,
            "is_auditor": full.is_auditor,
            "actions": actions_block,
            "targets": targets_block,
            "environments": actions_perm.environments if actions_perm else [],
        })

    root = {"profiles": profiles_data}
    buf = io.StringIO()
    yaml.dump(root, buf, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return buf.getvalue().encode("utf-8")


def _yaml_item_to_action_payload(item: ProfileYamlItem) -> ProfileActionPermissionsUpdate:
    a = item.actions
    # API requires non-empty action_ids for type "list"; empty list → "all"
    actions_type = a.type
    action_ids = a.action_ids
    if a.type == "list" and (not action_ids):
        actions_type = "all"
        action_ids = None
    return ProfileActionPermissionsUpdate(
        actions_type=actions_type,
        action_ids=action_ids,
        tag_patterns=a.patterns,
        environments=item.environments or None,
    )


def _yaml_item_to_target_payload(item: ProfileYamlItem) -> ProfileTargetPermissionsUpdate:
    t = item.targets
    # API requires non-empty target_names for type "list"; empty list → "all"
    targets_type = t.type
    target_names = t.target_names
    if t.type == "list" and (not target_names):
        targets_type = "all"
        target_names = None
    return ProfileTargetPermissionsUpdate(
        targets_type=targets_type,
        target_names=target_names,
        target_patterns=t.patterns,
    )


async def import_profiles_yaml(content: bytes) -> tuple[int, int]:
    """Import profiles from YAML (AC2, AC3, AC4, Task 3.1–3.4).

    Parses YAML, validates with ProfilesYamlImport. For each profile: get_by_name → update or create,
    then set_actions_permissions and set_target_permissions. Returns (created, updated).
    Raises InvalidStateError with code INVALID_YAML_SYNTAX or INVALID_YAML_SCHEMA on parse/validation error.
    AC4: On any error, no changes are applied (all-or-nothing via dry-run validation first).
    """
    try:
        parsed = yaml.safe_load(content.decode("utf-8"))
    except yaml.YAMLError as e:
        raise InvalidStateError(
            code="INVALID_YAML_SYNTAX",
            message="Syntaxe YAML invalide.",
            details={"error": str(e)},
        ) from e

    if parsed is None:
        raise InvalidStateError(
            code="INVALID_YAML_SYNTAX",
            message="Le fichier YAML est vide.",
            details={},
        )

    try:
        data = ProfilesYamlImport.model_validate(parsed)
    except PydanticValidationError as e:
        raise InvalidStateError(
            code="INVALID_YAML_SCHEMA",
            message="Schéma YAML invalide.",
            details={"errors": e.errors()},
        ) from e

    # --- Phase 1: Validation complète AVANT toute modification (AC4) ---
    seen_names: set[str] = set()
    for idx, item in enumerate(data.profiles):
        name_stripped = item.name.strip() if item.name else ""
        if not name_stripped:
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="Un profil a un nom vide.",
                details={"profile_index": idx},
            )
        if not (item.ad_group and item.ad_group.strip()):
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="Un profil a un ad_group vide.",
                details={"profile_name": name_stripped},
            )
        # Check for duplicate names within the YAML file
        if name_stripped.lower() in seen_names:
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message=f"Nom de profil en doublon dans le fichier : '{name_stripped}'.",
                details={"profile_name": name_stripped, "profile_index": idx},
            )
        seen_names.add(name_stripped.lower())

    # --- Phase 2: Apply changes (validation passed) ---
    created = 0
    updated = 0

    for item in data.profiles:
        existing = await profile_repository.get_by_name(item.name.strip())
        if existing:
            await profile_repository.update(
                existing.id,
                ProfileUpdate(
                    name=item.name.strip(),
                    description=item.description,
                    ad_group=item.ad_group.strip(),
                    is_admin=item.is_admin,
                    is_auditor=item.is_auditor,
                ),
            )
            profile_id = existing.id
            updated += 1
        else:
            profile = await profile_repository.create(
                ProfileCreate(
                    name=item.name.strip(),
                    description=item.description,
                    ad_group=item.ad_group.strip(),
                    is_admin=item.is_admin,
                    is_auditor=item.is_auditor,
                ),
            )
            profile_id = profile.id
            created += 1

        actions_payload = _yaml_item_to_action_payload(item)
        targets_payload = _yaml_item_to_target_payload(item)
        await profile_action_permission_repository.set_actions_permissions(profile_id, actions_payload)
        await profile_target_permission_repository.set_target_permissions(profile_id, targets_payload)

    return (created, updated)
