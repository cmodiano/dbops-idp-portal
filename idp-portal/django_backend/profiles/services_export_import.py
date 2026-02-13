"""
Profile YAML export/import service (Story M.5).
"""

import io
import yaml
from typing import Any
from profiles.services import ProfileService
from core.exceptions import InvalidStateError


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


def export_profiles_yaml() -> bytes:
    """
    Export all profiles and their permissions as YAML.
    
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
            actions_block = {"type": "all"}
        else:
            # Map permission_type to actions_type
            type_map = {'LIST': 'list', 'PATTERN': 'pattern', 'ALL': 'all'}
            actions_type = type_map.get(actions_perm.permission_type, 'all')
            actions_block = _build_actions_block(
                actions_type,
                actions_perm.get_action_ids(),
                actions_perm.get_tag_patterns(),
            )
        
        if targets_perm is None:
            targets_block = {"type": "all"}
        else:
            # Map permission_type to targets_type
            type_map = {'LIST': 'list', 'PATTERN': 'pattern', 'ALL': 'all'}
            targets_type = type_map.get(targets_perm.permission_type, 'all')
            targets_block = _build_targets_block(
                targets_type,
                targets_perm.get_target_names(),
                targets_perm.get_target_patterns(),
            )
        
        profiles_data.append({
            "name": full.name,
            "description": full.description,
            "ad_group": full.ad_group,
            "is_admin": bool(full.is_admin),
            "is_auditor": bool(full.is_auditor),
            "actions": actions_block,
            "targets": targets_block,
            "environments": actions_perm.get_environments() if actions_perm else [],
        })
    
    root = {"profiles": profiles_data}
    buf = io.StringIO()
    yaml.dump(root, buf, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return buf.getvalue().encode("utf-8")


def _yaml_item_to_action_payload(item: dict) -> dict:
    """Convert YAML item actions block to ProfileActionPermissionsUpdate format."""
    a = item.get('actions', {})
    actions_type = a.get('type', 'all')
    action_ids = a.get('list')  # YAML uses 'list' as key
    patterns = a.get('patterns')
    
    # API requires non-empty action_ids for type "list"; empty list → "all"
    if actions_type == "list" and (not action_ids):
        actions_type = "all"
        action_ids = None
    
    return {
        "actions_type": actions_type,
        "action_ids": action_ids,
        "tag_patterns": patterns,
        "environments": item.get('environments') or None,
    }


def _yaml_item_to_target_payload(item: dict) -> dict:
    """Convert YAML item targets block to ProfileTargetPermissionsUpdate format."""
    t = item.get('targets', {})
    targets_type = t.get('type', 'all')
    target_names = t.get('list')  # YAML uses 'list' as key
    patterns = t.get('patterns')
    
    # API requires non-empty target_names for type "list"; empty list → "all"
    if targets_type == "list" and (not target_names):
        targets_type = "all"
        target_names = None
    
    return {
        "targets_type": targets_type,
        "target_names": target_names,
        "target_patterns": patterns,
    }


def _validate_yaml_schema(parsed: dict):
    """
    Validate YAML schema structure.
    Raises InvalidStateError if validation fails.
    """
    if not isinstance(parsed, dict):
        raise InvalidStateError(
            code="INVALID_YAML_SCHEMA",
            message="Le fichier YAML doit être un objet.",
            details={}
        )
    
    if 'profiles' not in parsed:
        raise InvalidStateError(
            code="INVALID_YAML_SCHEMA",
            message="Le fichier YAML doit contenir une clé 'profiles'.",
            details={}
        )
    
    if not isinstance(parsed['profiles'], list):
        raise InvalidStateError(
            code="INVALID_YAML_SCHEMA",
            message="La clé 'profiles' doit être une liste.",
            details={}
        )
    
    # Validate each profile item
    seen_names: set[str] = set()
    for idx, item in enumerate(parsed['profiles']):
        if not isinstance(item, dict):
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="Chaque profil doit être un objet.",
                details={"profile_index": idx}
            )
        
        name = item.get('name', '').strip() if item.get('name') else ""
        if not name:
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="Un profil a un nom vide.",
                details={"profile_index": idx}
            )
        
        ad_group = item.get('ad_group', '').strip() if item.get('ad_group') else ""
        if not ad_group:
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="Un profil a un ad_group vide.",
                details={"profile_name": name}
            )
        
        # Check for duplicate names within the YAML file
        if name.lower() in seen_names:
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message=f"Nom de profil en doublon dans le fichier : '{name}'.",
                details={"profile_name": name, "profile_index": idx}
            )
        seen_names.add(name.lower())
        
        # Validate actions block
        actions = item.get('actions')
        if not actions or not isinstance(actions, dict):
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="Chaque profil doit avoir un bloc 'actions'.",
                details={"profile_name": name}
            )
        
        actions_type = actions.get('type')
        if actions_type not in ['list', 'pattern', 'all']:
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="Le type d'actions doit être 'list', 'pattern' ou 'all'.",
                details={"profile_name": name}
            )
        
        if actions_type == 'list' and not actions.get('list'):
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="'list' (action_ids) est requis quand le type d'actions est 'list'.",
                details={"profile_name": name}
            )
        
        if actions_type == 'pattern' and not actions.get('patterns'):
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="'patterns' est requis quand le type d'actions est 'pattern'.",
                details={"profile_name": name}
            )
        
        # Validate targets block
        targets = item.get('targets')
        if not targets or not isinstance(targets, dict):
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="Chaque profil doit avoir un bloc 'targets'.",
                details={"profile_name": name}
            )
        
        targets_type = targets.get('type')
        if targets_type not in ['list', 'pattern', 'all']:
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="Le type de targets doit être 'list', 'pattern' ou 'all'.",
                details={"profile_name": name}
            )
        
        if targets_type == 'list' and not targets.get('list'):
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="'list' (target_names) est requis quand le type de targets est 'list'.",
                details={"profile_name": name}
            )
        
        if targets_type == 'pattern' and not targets.get('patterns'):
            raise InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="'patterns' est requis quand le type de targets est 'pattern'.",
                details={"profile_name": name}
            )


def import_profiles_yaml(content: bytes, user=None) -> tuple[int, int]:
    """
    Import profiles from YAML.
    
    Args:
        content: YAML file content as bytes
        user: Optional user instance for audit logging
    
    Returns:
        Tuple of (created_count, updated_count)
    
    Raises:
        InvalidStateError: If YAML syntax or schema is invalid
    """
    # Parse YAML
    try:
        parsed = yaml.safe_load(content.decode("utf-8"))
    except yaml.YAMLError as e:
        raise InvalidStateError(
            code="INVALID_YAML_SYNTAX",
            message="Syntaxe YAML invalide.",
            details={"error": str(e)}
        ) from e
    
    if parsed is None:
        raise InvalidStateError(
            code="INVALID_YAML_SYNTAX",
            message="Le fichier YAML est vide.",
            details={}
        )
    
    # Validate schema
    _validate_yaml_schema(parsed)
    
    # Apply changes (validation passed)
    service = ProfileService()
    created = 0
    updated = 0
    
    for item in parsed['profiles']:
        name_stripped = item['name'].strip()
        existing = service.get_by_name(name_stripped)
        
        if existing:
            # Update existing profile
            profile_update_data = {
                'name': name_stripped,
                'description': item.get('description'),
                'ad_group': item['ad_group'].strip(),
                'is_admin': item.get('is_admin', False),
                'is_auditor': item.get('is_auditor', False),
            }
            service.update_profile(existing.id, profile_update_data, user=user)
            profile_id = existing.id
            updated += 1
        else:
            # Create new profile
            profile_create_data = {
                'name': name_stripped,
                'description': item.get('description'),
                'ad_group': item['ad_group'].strip(),
                'is_admin': item.get('is_admin', False),
                'is_auditor': item.get('is_auditor', False),
            }
            profile = service.create_profile(profile_create_data, user=user)
            profile_id = profile.id
            created += 1
        
        # Set permissions
        actions_payload = _yaml_item_to_action_payload(item)
        targets_payload = _yaml_item_to_target_payload(item)
        service.set_action_permissions(profile_id, actions_payload)
        service.set_target_permissions(profile_id, targets_payload)
    
    return (created, updated)
