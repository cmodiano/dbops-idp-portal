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

def get_user_profile_ids(user: Any) -> set[int]:
    """Retourne les IDs de profils d'un utilisateur.

    Wrapper autour de _resolve_user_profiles() qui retourne un ensemble d'IDs.
    Utilisé par les vues d'approbation pour vérifier les permissions approver.

    Story 71.9 / NEW-BE-A: Extrait depuis approval_views._get_user_profile_ids pour
    éliminer la duplication de la logique de résolution de profils.
    """
    return {p.id for p in _resolve_user_profiles(user) if hasattr(p, 'id')}


def _resolve_user_profiles(user: Any) -> list['Profile']:
    """Résout la liste des profils ORM d'un utilisateur.

    Story 56.7 : Ordre canonique — ad_groups > M2M > profile string > profile objet.
    Retourne une liste vide si aucun profil résolu (DB indisponible, profil inconnu, etc.).
    """
    # Chemin 1 : ad_groups → Profile.objects.find_by_ad_groups()
    ad_groups = getattr(user, 'ad_groups', None) or []
    if not isinstance(ad_groups, list):
        ad_groups = []
    if ad_groups:
        try:
            return list(Profile.objects.find_by_ad_groups(ad_groups))
        except OperationalError as e:
            logger.warning(
                "profile_db_unavailable_admin_check",
                user_id=getattr(user, 'id', None),
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            return []

    # Chemin 2 : M2M profiles
    if hasattr(user, 'profiles'):
        try:
            return list(user.profiles.all())
        except OperationalError as e:
            logger.warning(
                "profile_db_unavailable_admin_check",
                user_id=getattr(user, 'id', None),
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            return []

    # Chemin 3 : profile string → DB lookup
    profile_val = getattr(user, 'profile', None)
    if isinstance(profile_val, str) and profile_val.strip():
        try:
            p = Profile.objects.filter(name__iexact=profile_val.strip()).first()
            return [p] if p else []
        except OperationalError as e:
            logger.warning(
                "profile_db_unavailable_admin_check",
                user_id=getattr(user, 'id', None),
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            return []

    # Chemin 4 : profile objet ORM direct
    if profile_val is not None and hasattr(profile_val, 'is_admin_bool'):
        return [profile_val]

    return []


def is_admin_user(user: Any) -> bool:
    """
    Check if user has an admin profile (profile string, profiles M2M, or ad_groups).

    Story 56.7: Fully flag-based — uses Profile.is_admin_bool for all auth paths.
    Ordre canonique : ad_groups > M2M > profile string (DB lookup) > profile ORM direct.

    Reusable without a request object. Used by IsAdminUser.has_permission and by
    executions.utils.filters for scope=all admin check.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    profiles = _resolve_user_profiles(user)
    return any(getattr(p, 'is_admin_bool', False) for p in profiles)


def is_auditor_user(user: Any) -> bool:
    """
    Check if user has an auditor profile (profile string, profiles M2M, or ad_groups).

    Story 71.9: Centralised auditor check — replaces duplicated _is_auditor() in
    audit/views.py and inline logic in idp_auth/views/jwt.py.
    Uses _resolve_user_profiles() (same as is_admin_user) to avoid duplication.
    Oracle is_auditor is NUMBER(1) — always compare with == 1, not truthiness.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    profiles = _resolve_user_profiles(user)
    return any(getattr(p, 'is_auditor', 0) == 1 for p in profiles)


class IsAdminUser(permissions.BasePermission):
    """
    Permission DRF : accès aux utilisateurs avec profil admin (is_admin=1).

    Story 56.7: Fully flag-based — utilise Profile.is_admin_bool pour tous les chemins.
    Story 56.4: Renommé depuis IsDBAOrDBOPS.
    Story 26.8: Remplace le pattern fragile _is_dba_or_dbops().

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


class IsAuditorUser(permissions.BasePermission):
    """
    Permission DRF : accès aux utilisateurs avec profil auditor (is_auditor=1).

    Story 71.9: Centralised auditor permission class — same pattern as IsAdminUser.

    Utilisation :
    - View-level : `permission_classes = [IsAuthenticated, IsAuditorUser]`
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        """Check view-level permission : user a-t-il un profil auditor ?"""
        return is_auditor_user(request.user)


class AdminProfilePermission(permissions.BasePermission):
    """
    Permission class that requires an admin profile for admin endpoints.

    Story 56.7: Fully flag-based — uses Profile.is_admin_bool for all auth paths.
    Story 15.2 AC2: DBA is DENIED on admin endpoints (profiles, integrations, actions,
    analytics). Only DBOPS (or profiles with is_admin=1) can access these.
    The distinction between DBA (is_admin=0) and DBOPS (is_admin=1) comes from the DB.

    Story 56.4: Renommé depuis DBOPSProfilePermission.
    Story 22.1 CRIT-1: Uses Profile.objects.find_by_ad_groups() directly.
    Story 22.2 CRIT-2: Superuser fallback conditional on ALLOW_SUPERUSER_FALLBACK setting.
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        """Check if user has an admin profile (is_admin=1 in DB)."""
        if not request.user or not request.user.is_authenticated:
            return False

        profiles = _resolve_user_profiles(request.user)
        if any(getattr(p, 'is_admin_bool', False) for p in profiles):
            return True

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
