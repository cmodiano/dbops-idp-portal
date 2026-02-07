"""
Custom permissions for DRF RBAC.
"""

from rest_framework import permissions
import structlog

logger = structlog.get_logger(__name__)


class DBOPSProfilePermission(permissions.BasePermission):
    """
    Permission class that requires DBOPS profile.
    MEDIUM-5 fix: Improved profile checking logic.
    """

    def has_permission(self, request, view):
        """Check if user has DBOPS profile."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if user has DBOPS profile via profile attribute
        if hasattr(request.user, 'profile'):
            profile = request.user.profile
            if isinstance(profile, str):
                return profile.lower() == 'dbops'
            elif hasattr(profile, 'name'):
                return profile.name.lower() == 'dbops'
            elif hasattr(profile, 'code'):
                return profile.code.lower() == 'dbops'

        # Check via user's profiles relation (M2M through Profile model)
        if hasattr(request.user, 'profiles'):
            profiles = request.user.profiles.all()
            for p in profiles:
                if hasattr(p, 'code') and p.code.lower() == 'dbops':
                    return True
                if hasattr(p, 'name') and p.name.lower() == 'dbops':
                    return True

        # Check via ad_groups (user may have DBOPS via AD group membership)
        if hasattr(request.user, 'ad_groups'):
            ad_groups = request.user.ad_groups if isinstance(request.user.ad_groups, list) else []
            # Check if any AD group grants DBOPS access
            from profiles.services import ProfileService
            try:
                service = ProfileService()
                for profile in service.get_profiles_by_ad_groups(ad_groups):
                    if profile.code.lower() == 'dbops':
                        return True
            except Exception as e:
                # Story 17.6: Justified broad catch - ProfileService can raise various exceptions
                logger.warning(
                    "profile_service_unavailable_dbops_check",
                    user_id=request.user.id,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )

        # Fallback: superuser always has access (for development/admin)
        if request.user.is_superuser:
            return True

        return False


class OptionalUserPermission(permissions.BasePermission):
    """
    Permission class that allows both authenticated and anonymous users.
    """
    
    def has_permission(self, request, view):
        """Allow all users (authenticated or anonymous)."""
        return True
