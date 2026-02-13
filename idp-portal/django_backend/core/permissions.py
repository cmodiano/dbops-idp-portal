"""
Custom permissions for DRF RBAC.
"""

from django.conf import settings
from django.db import OperationalError
from rest_framework import permissions
from profiles.models import Profile
import structlog

logger = structlog.get_logger(__name__)


class DBOPSProfilePermission(permissions.BasePermission):
    """
    Permission class that requires DBOPS profile.

    Story 22.1 CRIT-1: Fixed AttributeError from non-existent service.get_profiles_by_ad_groups()
    by using Profile.objects.find_by_ad_groups() directly.

    Story 22.2 CRIT-2: Superuser fallback is now conditional on ALLOW_SUPERUSER_FALLBACK setting.
    Default is False (fail-secure). Set to True only in development for bootstrapping/convenience.
    """

    def has_permission(self, request, view):
        """Check if user has DBOPS profile."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if user has DBOPS profile via profile attribute
        if hasattr(request.user, 'profile'):
            profile = request.user.profile
            if isinstance(profile, str) and profile.lower() == 'dbops':
                return True
            elif hasattr(profile, 'name') and profile.name.lower() == 'dbops':
                return True

        # Check via user's profiles relation (M2M through Profile model)
        if hasattr(request.user, 'profiles'):
            profiles = request.user.profiles.all()
            for p in profiles:
                if hasattr(p, 'name') and p.name.lower() == 'dbops':
                    return True

        # Check via ad_groups (user may have DBOPS via AD group membership)
        if hasattr(request.user, 'ad_groups'):
            ad_groups = request.user.ad_groups
            # Normalize ad_groups to list (handle None, string, or non-list values)
            if ad_groups is None:
                ad_groups = []
            elif not isinstance(ad_groups, list):
                ad_groups = []

            # Resolve profiles from AD groups via ProfileManager (Story 22.1: CRIT-1 fix)
            try:
                for profile in Profile.objects.find_by_ad_groups(ad_groups):
                    if profile.name.lower() == 'dbops':
                        return True
            except OperationalError as e:
                # AC#6 Justification: Catch OperationalError specifically for DB connectivity issues.
                # This handles cases where the database is temporarily unavailable (network issues,
                # connection pool exhausted, DB maintenance). We prefer to deny access (safe denial)
                # rather than allowing unrestricted access when we cannot verify permissions.
                # Story 17.6: Avoid broad Exception catches that mask bugs like AttributeError.
                logger.warning(
                    "profile_db_unavailable_dbops_check",
                    user_id=getattr(request.user, 'id', None),
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )

        # Story 22.2 CRIT-2: Conditional superuser fallback (executed ONLY if all profile checks above returned False).
        # This fallback exists for development/bootstrapping convenience ONLY.
        # Controlled by settings.ALLOW_SUPERUSER_FALLBACK (default: False = fail-secure).
        # In production, superusers MUST have an explicit DBOPS profile.
        # WARNING: Enabling this in production bypasses RBAC for superusers — violates
        # principle of least privilege and SOC1 compliance requirements.
        if getattr(settings, 'ALLOW_SUPERUSER_FALLBACK', False) and request.user.is_superuser:
            logger.warning(
                "security_rbac_bypass_superuser_fallback",
                user_id=getattr(request.user, 'id', None),
                username=getattr(request.user, 'username', None),
                allow_superuser_fallback=True,
                debug_mode=getattr(settings, 'DEBUG', False),
            )
            return True

        return False


class OptionalUserPermission(permissions.BasePermission):
    """
    Permission class that allows both authenticated and anonymous users.
    """
    
    def has_permission(self, request, view):
        """Allow all users (authenticated or anonymous)."""
        return True
