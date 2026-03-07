"""
Export/import YAML services for Tags.
Story 64.2 - IaC Tags management.
"""

from typing import Any

from django.db import transaction

from catalog.models import Tag
from core.exceptions import InvalidStateError
from core.models import AuditActionType, AuditEntityType
from core.services import AuditService
from core.services_iac_utils import parse_yaml, serialize_to_yaml, validate_envelope


def export_tags_yaml() -> bytes:
    """
    Export all Tags to YAML bytes.

    Returns:
        UTF-8 YAML bytes with envelope apiVersion: idp/v1 / kind: Tags.
    """
    tags = Tag.objects.all().order_by("name")
    root = {
        "apiVersion": "idp/v1",
        "kind": "Tags",
        "metadata": {},
        "spec": [t.name for t in tags],
    }
    return serialize_to_yaml(root)


@transaction.atomic
def import_tags_yaml(content: bytes, user: Any | None = None) -> tuple[int, int, int]:
    """
    Import Tags from YAML bytes.

    Creates tags that don't exist (name normalized via .strip().lower()).
    Never updates existing tags (name is the only field).

    Args:
        content: UTF-8 YAML bytes.
        user: Optional user performing the import (for audit).

    Returns:
        Tuple (created, 0, unchanged).

    Raises:
        InvalidStateError: If YAML is invalid, envelope is wrong, or a tag name is empty.
    """
    parsed = parse_yaml(content)
    validate_envelope(parsed, expected_kind="Tags")

    spec = parsed.get("spec") or []
    created = unchanged = 0

    for tag_name in spec:
        if not isinstance(tag_name, str) or not tag_name.strip():
            raise InvalidStateError(
                code="INVALID_TAG_NAME",
                message="Chaque tag doit être une chaîne non vide.",
            )
        normalized = tag_name.strip().lower()
        _, was_created = Tag.objects.get_or_create(name=normalized)
        if was_created:
            created += 1
        else:
            unchanged += 1

    AuditService.create_entry(
        user_id=str(user.id) if user and hasattr(user, "id") else "",
        action_type=AuditActionType.CONFIG_SYNC_TAGS_IMPORT,
        entity_type=AuditEntityType.TAGS,
        entity_id=0,
        details={"source": "yaml_import", "created": created, "unchanged": unchanged},
    )

    return (created, 0, unchanged)
