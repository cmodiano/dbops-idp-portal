"""
Export/import YAML services for Tags.
Story 64.2 - CaC Tags management.
"""

import structlog
from typing import Any

from django.db import IntegrityError, transaction

from catalog.models import Tag
from core.exceptions import InvalidStateError
from core.models import AuditActionType, AuditEntityType
from core.services import AuditService
from core.services_cac_utils import parse_yaml, serialize_to_yaml, validate_envelope

logger = structlog.get_logger(__name__)


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
def import_tags_yaml(content: bytes, mode: str = "additive", user: Any | None = None) -> tuple[int, int, int]:
    """
    Import Tags from YAML bytes.

    Creates tags that don't exist (name normalized via .strip().lower()).
    Never updates existing tags (name is the only field).

    Args:
        content: UTF-8 YAML bytes.
        mode: "additive" (default) or "full" — reserved for future use (e.g. orphan removal).
        user: Optional user performing the import (for audit).

    Returns:
        Tuple (created, 0, unchanged).

    Raises:
        InvalidStateError: If YAML is invalid, envelope is wrong, mode invalid, or a tag name is empty.
    """
    if mode not in ("additive", "full"):
        raise InvalidStateError(
            code="INVALID_IMPORT_MODE",
            message=f"Mode invalide '{mode}'. Valeurs acceptées : 'additive', 'full'.",
        )
    parsed = parse_yaml(content)
    validate_envelope(parsed, expected_kind="Tags")

    spec = parsed.get("spec") or []
    created = unchanged = 0

    # Detect duplicate tag names in spec (after normalization) — DUPLICATE_KEY
    # Only check non-empty strings; empty/whitespace items are validated below as INVALID_TAG_NAME.
    seen_normalized: set[str] = set()
    for tag_name in spec:
        if isinstance(tag_name, str) and tag_name.strip():
            normalized_check = tag_name.strip().lower()
            if normalized_check in seen_normalized:
                raise InvalidStateError(
                    code="DUPLICATE_KEY",
                    message=f"Tag dupliqué dans le YAML : '{normalized_check}' apparaît plusieurs fois.",
                )
            seen_normalized.add(normalized_check)

    for tag_name in spec:
        if not isinstance(tag_name, str) or not tag_name.strip():
            raise InvalidStateError(
                code="INVALID_TAG_NAME",
                message="Chaque tag doit être une chaîne non vide.",
            )
        normalized = tag_name.strip().lower()
        # Case-insensitive lookup first (avoids IntegrityError with mixed-case existing tags)
        existing = Tag.objects.filter(name__iexact=normalized).first()
        if existing:
            unchanged += 1
            continue
        try:
            _, was_created = Tag.objects.get_or_create(name=normalized)
            if was_created:
                created += 1
            else:
                unchanged += 1
        except IntegrityError:
            # Race: another process created it; re-query case-insensitively and treat as existing
            existing = Tag.objects.filter(name__iexact=normalized).first()
            if existing:
                unchanged += 1
            else:
                logger.exception(
                    "tag_import_integrity_error",
                    extra={"normalized": normalized},
                )
                raise

    AuditService.create_entry(
        user_id=str(user.id) if user and hasattr(user, "id") else "",
        action_type=AuditActionType.CONFIG_SYNC_TAGS_IMPORT,
        entity_type=AuditEntityType.TAGS,
        entity_id=0,
        details={"source": "yaml_import", "created": created, "unchanged": unchanged, "mode": mode},
    )

    return (created, 0, unchanged)
