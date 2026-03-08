"""
Shared IaC utilities for YAML parsing, validation, hashing, and serialization.
Story 64.1 - Foundation utilities for the Infrastructure-as-Code system.
"""

from __future__ import annotations

import hashlib

import yaml
from django.utils import timezone

from core.exceptions import InvalidStateError


VALID_KINDS = {
    "Action",
    "Integration",
    "IntegrationTypeCatalogue",
    "BusinessRulePolicy",
    "Profile",
    "ReferenceData",
    "Tags",
    "FeatureFlags",
}


def parse_yaml(content: bytes) -> dict:
    """
    Parse YAML bytes into a dict.

    Args:
        content: Raw YAML bytes (UTF-8).

    Returns:
        Parsed dict.

    Raises:
        InvalidStateError: If the content is malformed or empty.
    """
    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise InvalidStateError(
            code="INVALID_YAML_SYNTAX",
            message=f"Impossible de parser le YAML : {exc}",
        ) from exc

    if not isinstance(parsed, dict):
        raise InvalidStateError(
            code="INVALID_YAML_SYNTAX",
            message="Le contenu YAML est vide ou n'est pas un dictionnaire.",
        )

    return parsed


def validate_envelope(parsed: dict, expected_kind: str | None = None) -> None:
    """
    Validate the IaC YAML envelope structure.

    Args:
        parsed: Parsed YAML dict.
        expected_kind: Optional expected kind value.

    Raises:
        InvalidStateError: If the envelope is invalid.
    """
    if not isinstance(parsed, dict):
        raise InvalidStateError(
            code="INVALID_YAML_SCHEMA",
            message="Le document YAML doit être un dictionnaire.",
        )

    if parsed.get("apiVersion") != "idp/v1":
        raise InvalidStateError(
            code="INVALID_API_VERSION",
            message=f"apiVersion invalide : '{parsed.get('apiVersion')}'. Attendu : 'idp/v1'.",
        )

    kind = parsed.get("kind")
    if kind not in VALID_KINDS:
        raise InvalidStateError(
            code="INVALID_KIND",
            message=f"kind invalide : '{kind}'. Valeurs acceptées : {sorted(VALID_KINDS)}.",
        )

    if expected_kind and kind != expected_kind:
        raise InvalidStateError(
            code="WRONG_KIND",
            message=f"Attendu '{expected_kind}', reçu '{kind}'.",
        )

    if not isinstance(parsed.get("metadata"), dict):
        raise InvalidStateError(
            code="INVALID_METADATA",
            message="Le champ 'metadata' est absent ou invalide.",
        )

    # Tags, FeatureFlags, ReferenceData n'ont pas de metadata.name individuel
    if kind not in ("Tags", "FeatureFlags", "ReferenceData"):
        name = parsed["metadata"].get("name")
        if not isinstance(name, str) or not name.strip():
            raise InvalidStateError(
                code="MISSING_NAME",
                message="Le champ 'metadata.name' est requis pour ce type de document.",
            )


def compute_yaml_hash(content: bytes) -> str:
    """
    Compute the SHA-256 hex digest of YAML content.

    Args:
        content: Raw YAML bytes.

    Returns:
        64-character hex string.
    """
    return hashlib.sha256(content).hexdigest()


def serialize_to_yaml(data: dict) -> bytes:
    """
    Serialize a dict to YAML bytes (UTF-8).

    Args:
        data: Dict to serialize.

    Returns:
        YAML bytes encoded as UTF-8.
    """
    return yaml.dump(
        data,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).encode("utf-8")


def _apply_field_changes(obj: object, defaults: dict) -> bool:
    """
    Apply field updates to a model instance where values differ.

    Does NOT call obj.save() — caller is responsible.

    Args:
        obj: Django model instance.
        defaults: Dict of field_name → new_value.

    Returns:
        True if at least one field was changed, False otherwise.
    """
    changed = False
    for field, value in defaults.items():
        if getattr(obj, field) != value:
            setattr(obj, field, value)
            changed = True
    return changed


def update_sync_tracking(obj: object, yaml_content: bytes) -> None:
    """
    Update last_synced_at and last_synced_hash on a model instance after successful sync.

    Args:
        obj: Django model instance with last_synced_at and last_synced_hash fields.
        yaml_content: Raw YAML bytes representing this specific entity (used to compute hash).

    Note:
        Uses save(update_fields=...) — obj must already exist in DB.
    """
    obj.last_synced_at = timezone.now()  # type: ignore[attr-defined]
    obj.last_synced_hash = compute_yaml_hash(yaml_content)  # type: ignore[attr-defined]
    obj.save(update_fields=["last_synced_at", "last_synced_hash"])  # type: ignore[attr-defined]
