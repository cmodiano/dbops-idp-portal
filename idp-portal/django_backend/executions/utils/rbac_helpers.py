"""
Module executions.utils.rbac_helpers — Résolution des action IDs autorisés pour un utilisateur.

Responsabilité unique : calculer l'ensemble des action IDs accessibles à un utilisateur
donné en agrégeant ses permissions de profil (RBAC).
"""
from __future__ import annotations

from typing import Any

import structlog

from catalog.models import ActionStatus
from core.auth_utils import get_user_ad_groups
from core.middleware import get_correlation_id

exec_logger = structlog.get_logger(__name__)


def get_allowed_action_ids_for_user(user: Any) -> set[int] | None:
    """
    Get action IDs the user has access to based on their profile permissions.
    Story 13.6: DBA sees scheduled executions for actions their profile gives access to.
    Story 26.10: Renamed from _get_allowed_action_ids_for_user to respect Python convention (PEP 8).

    Returns:
        Set of action IDs, or None if user has 'all' access (no filtering needed).

    Note: ProfileService is accessed via `import executions.utils` (lazy)
    so that `patch('executions.utils.ProfileService')` in tests correctly intercepts calls.
    """
    if not user or not user.is_authenticated:
        return set()

    import executions.utils as _eu  # noqa: PLC0415

    ad_groups = get_user_ad_groups(user)
    try:
        profile_service = _eu.ProfileService()
        permissions = profile_service.get_cumulative_permissions(user.id, ad_groups)
    except Exception as e:
        # Story 17.6: Justified broad catch - ProfileService can raise various exceptions
        exec_logger.warning(
            "profile_service_unavailable_access_denied",
            user_id=user.id,
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=get_correlation_id(),
            exc_info=True,
        )
        return set()

    if not permissions or not permissions.get('action_permissions'):
        return set()

    # Aggregate action permissions (union across profiles)
    action_ids: set[int] = set()
    tag_patterns: set[str] = set()

    for perm in permissions.get('action_permissions', []):
        if perm.get('actions_type') == 'all':
            # User has full access - no filtering needed
            return None
        action_ids.update(perm.get('action_ids', []) or [])
        tag_patterns.update(perm.get('tag_patterns', []) or [])

    # If there are tag patterns, we need to resolve them to action IDs
    if tag_patterns:
        from catalog.models import ActionTag  # noqa: PLC0415
        tag_action_ids = ActionTag.objects.filter(
            tag__name__in=tag_patterns,
            action__status=ActionStatus.PUBLISHED
        ).values_list('action_id', flat=True)
        action_ids.update(tag_action_ids)

    return action_ids
