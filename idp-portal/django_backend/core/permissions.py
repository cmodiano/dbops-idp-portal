"""
Custom permissions for DRF RBAC.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import OperationalError
from rest_framework import permissions
from profiles.models import Profile
import structlog

logger = structlog.get_logger(__name__)

# Legacy constant kept for backward compatibility (not used internally anymore).
# Use _get_admin_profile_names() to resolve the configurable set.
_ADMIN_PROFILES = {'dbops', 'dba', 'dba_applicatif', 'dba_infrastructure'}


def _get_admin_profile_names() -> set:
    """Résout le set de noms de profils admin depuis settings (configurable).

    Story 56.4: Utilise ADMIN_PROFILE_NAMES si défini, sinon fallback vers _ADMIN_PROFILES
    pour la compatibilité. Permet d'ajouter des profils admin sans changer le code.
    """
    return getattr(settings, 'ADMIN_PROFILE_NAMES', _ADMIN_PROFILES)


def is_admin_user(user: Any) -> bool:
    """
    Check if user has an admin profile (profile string, profiles M2M, or ad_groups).

    Story 56.4: Refactorisé pour utiliser Profile.is_admin_bool sur les objets Profile ORM
    (chemins M2M et ad_groups). Le chemin SAML string conserve la comparaison par nom
    via ADMIN_PROFILE_NAMES (configurable).

    Reusable without a request object. Used by IsAdminUser.has_permission and by
    executions.utils.filters for scope=all admin check.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False

    # Chemin 1 : SAML string → comparaison par nom (configurable via ADMIN_PROFILE_NAMES)
    profile_str = getattr(user, 'profile', None)
    if profile_str and isinstance(profile_str, str) and profile_str.lower() in _get_admin_profile_names():
        return True

    # Chemin 2 : M2M profiles → utiliser is_admin_bool (PAS comparaison de nom)
    if hasattr(user, 'profiles'):
        for profile in user.profiles.all():
            if getattr(profile, 'is_admin_bool', False):
                return True

    # Chemin 3 : ad_groups → Profile.objects.find_by_ad_groups() → is_admin_bool
    if hasattr(user, 'ad_groups'):
        ad_groups = user.ad_groups or []
        if not isinstance(ad_groups, list):
            ad_groups = []
        try:
            for profile in Profile.objects.find_by_ad_groups(ad_groups):
                if profile.is_admin_bool:
                    return True
        except OperationalError as e:
            logger.warning(
                "profile_db_unavailable_admin_check",
                user_id=getattr(user, 'id', None),
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )

    return False


class IsAdminUser(permissions.BasePermission):
    """
    Permission DRF : accès aux utilisateurs avec profil admin (is_admin=1).

    Story 56.4: Renommé depuis IsDBAOrDBOPS. Utilise Profile.is_admin_bool via is_admin_user()
    pour les chemins M2M et ad_groups. Le chemin SAML string utilise ADMIN_PROFILE_NAMES.

    Story 26.8: Remplace le pattern fragile _is_dba_or_dbops().

    Profils autorisés (via ADMIN_PROFILE_NAMES ou is_admin=1 en base) :
    - dbops, dba, dba_applicatif, dba_infrastructure (configurable)

    Utilisation :
    - View-level : `permission_classes = [IsAuthenticated, IsAdminUser]`
    - Object-level : `has_object_permission()` vérifie ownership OU admin

    Voir aussi :
    - `AdminProfilePermission` : permission pour endpoints admin (avec superuser fallback)
    - Pour pattern owner-or-admin : utiliser `has_object_permission()` directement (Story 26.12)
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        """
        Check view-level permission : user a-t-il un profil admin ?

        Returns:
            True si utilisateur authentifié avec profil admin.
            False sinon.
        """
        return is_admin_user(request.user)

    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        """
        Check object-level permission : user est-il owner OU admin ?

        Utilisé pour pattern "owner peut lire/modifier, admin peut tout".

        Args:
            obj: Objet à vérifier (Execution, ScheduledExecution, etc.)
                 Doit avoir un attribut `user_id` ou `user`.

        Returns:
            True si user est owner OU a permission admin.
            False sinon.

        Performance: Owner check first (fast ID comparison), then admin check
        (expensive AD/profile lookups). 99% of requests are from owners.
        """
        # Fast path: Check ownership first (cheap ID comparison)
        obj_user_id = getattr(obj, 'user_id', None) or getattr(getattr(obj, 'user', None), 'id', None)
        if obj_user_id and obj_user_id == request.user.id:
            return True

        # Slow path: Check admin permission (DB queries, AD groups, etc.)
        if self.has_permission(request, view):
            return True

        return False


class AdminProfilePermission(permissions.BasePermission):
    """
    Permission class that requires an admin profile (is_admin=1 ou ADMIN_PROFILE_NAMES).

    Story 56.4: Renommé depuis DBOPSProfilePermission. Utilise maintenant Profile.is_admin_bool
    au lieu de la comparaison hardcodée 'dbops', permettant des profils admin avec d'autres noms
    (AUTOMATION, OPERATOR, etc.).

    Story 22.1 CRIT-1: Fixed AttributeError from non-existent service.get_profiles_by_ad_groups()
    by using Profile.objects.find_by_ad_groups() directly.

    Story 22.2 CRIT-2: Superuser fallback is now conditional on ALLOW_SUPERUSER_FALLBACK setting.
    Default is False (fail-secure). Set to True only in development for bootstrapping/convenience.
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        """Check if user has an admin profile."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Chemin 1 : SAML string → ADMIN_PROFILE_NAMES configurable
        if hasattr(request.user, 'profile'):
            profile = request.user.profile
            if isinstance(profile, str) and profile.lower() in _get_admin_profile_names():
                return True
            elif hasattr(profile, 'is_admin_bool') and profile.is_admin_bool:
                return True

        # Chemin 2 : M2M profiles → is_admin_bool (PAS comparaison de nom)
        if hasattr(request.user, 'profiles'):
            for p in request.user.profiles.all():
                if getattr(p, 'is_admin_bool', False):
                    return True

        # Chemin 3 : ad_groups → Profile → is_admin_bool
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
                    if profile.is_admin_bool:
                        return True
            except OperationalError as e:
                # AC#6 Justification: Catch OperationalError specifically for DB connectivity issues.
                # This handles cases where the database is temporarily unavailable (network issues,
                # connection pool exhausted, DB maintenance). We prefer to deny access (safe denial)
                # rather than allowing unrestricted access when we cannot verify permissions.
                # Story 17.6: Avoid broad Exception catches that mask bugs like AttributeError.
                logger.warning(
                    "profile_db_unavailable_admin_check",
                    user_id=getattr(request.user, 'id', None),
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )

        # Story 22.2 CRIT-2: Conditional superuser fallback (executed ONLY if all profile checks above returned False).
        # This fallback exists for development/bootstrapping convenience ONLY.
        # Controlled by settings.ALLOW_SUPERUSER_FALLBACK (default: False = fail-secure).
        # In production, superusers MUST have an explicit admin profile.
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

    def has_permission(self, request: Any, view: Any) -> bool:
        """Allow all users (authenticated or anonymous)."""
        return True


# Aliases backward-compatible (Story 56.4)
# Les fichiers consommateurs existants continuent de fonctionner sans modification.
DBOPSProfilePermission = AdminProfilePermission
IsDBAOrDBOPS = IsAdminUser
