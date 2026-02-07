"""
Auth utilities for RBAC resolution across catalog, executions, inventory.
"""
import structlog

logger = structlog.get_logger(__name__)


def get_user_ad_groups(user) -> list[str]:
    """
    Get AD groups for a user, with profile fallback.

    JWT auth sets user.ad_groups from token. When empty, use user.profile
    (from USERS.PROFILE) so DBOPS/DBA users resolve correctly.

    Returns:
        List of AD group identifiers (profile names, group DNs, etc.)
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return []

    ad_groups = []

    if hasattr(user, 'get_ad_groups') and callable(user.get_ad_groups):
        try:
            ad_groups = user.get_ad_groups() or []
        except Exception as e:
            # Story 17.6: Justified broad catch - get_ad_groups() can raise various exceptions
            logger.warning(
                "get_ad_groups_failed",
                user_id=getattr(user, 'id', None),
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
    elif hasattr(user, 'ad_groups'):
        attr = user.ad_groups
        if isinstance(attr, list):
            ad_groups = attr
        elif isinstance(attr, str):
            ad_groups = [g.strip() for g in attr.split(',') if g.strip()]
        elif hasattr(attr, 'values_list'):
            ad_groups = list(attr.values_list('name', flat=True))

    # Fallback: use profile name (matches audit view, idp_auth /users/me)
    if not ad_groups and hasattr(user, 'profile') and user.profile:
        profile_name = (
            user.profile
            if isinstance(user.profile, str)
            else getattr(user.profile, 'name', None)
        )
        if profile_name:
            ad_groups = [str(profile_name).strip()]

    return ad_groups
