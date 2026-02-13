"""
Custom permissions for DRF RBAC.
"""

from django.conf import settings
from django.db import OperationalError
from rest_framework import permissions
from profiles.models import Profile
import structlog

logger = structlog.get_logger(__name__)


class IsDBAOrDBOPS(permissions.BasePermission):
    """
    Permission DRF permettant l'accès aux utilisateurs ayant un profil admin DBA/DBOPS.

    Story 26.8 — Remplace le pattern fragile `_is_dba_or_dbops()` (startswith dangerous).

    Profils autorisés (liste exhaustive) :
    - dbops
    - dba
    - dba_applicatif
    - dba_infrastructure

    Utilisation :
    - View-level : `permission_classes = [IsAuthenticated, IsDBAOrDBOPS]`
    - Object-level : `has_object_permission()` vérifie ownership OU admin

    Voir aussi :
    - `DBOPSProfilePermission` : permission stricte DBOPS uniquement (admin endpoints)
    - `IsOwnerOrDBA` mixin : helper pour pattern owner-or-admin (Story 26.12)

    Exemples :
        # View-level permission (requiert DBA/DBOPS pour tous GET/POST/etc.)
        class AdminOnlyView(APIView):
            permission_classes = [IsAuthenticated, IsDBAOrDBOPS]

        # Object-level permission (owner peut lire, DBA/DBOPS peut tout)
        class ExecutionDetailView(APIView):
            permission_classes = [IsAuthenticated, IsDBAOrDBOPS]

            def get(self, request, execution_id):
                execution = get_object_or_404(Execution, pk=execution_id)
                self.check_object_permissions(request, execution)
                # ...
    """

    ADMIN_PROFILES = {'dbops', 'dba', 'dba_applicatif', 'dba_infrastructure'}

    def has_permission(self, request, view):
        """
        Check view-level permission : user a-t-il un profil admin DBA/DBOPS ?

        Returns:
            True si utilisateur authentifié avec profil dans ADMIN_PROFILES.
            False sinon.
        """
        if not request.user or not request.user.is_authenticated:
            return False

        # Check via user.profile attribute (SAML string)
        profile_str = getattr(request.user, 'profile', None)
        if profile_str:
            if isinstance(profile_str, str) and profile_str.lower() in self.ADMIN_PROFILES:
                return True

        # Check via user.profiles M2M relation (Profile model)
        if hasattr(request.user, 'profiles'):
            user_profiles = request.user.profiles.all()
            for profile in user_profiles:
                if hasattr(profile, 'name') and profile.name.lower() in self.ADMIN_PROFILES:
                    return True

        # Check via ad_groups → Profile resolution
        if hasattr(request.user, 'ad_groups'):
            ad_groups = request.user.ad_groups or []
            if not isinstance(ad_groups, list):
                ad_groups = []

            try:
                for profile in Profile.objects.find_by_ad_groups(ad_groups):
                    if profile.name.lower() in self.ADMIN_PROFILES:
                        return True
            except OperationalError as e:
                logger.warning(
                    "profile_db_unavailable_dba_check",
                    user_id=getattr(request.user, 'id', None),
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )

        return False

    def has_object_permission(self, request, view, obj):
        """
        Check object-level permission : user est-il owner OU admin DBA/DBOPS ?

        Utilisé pour pattern "owner peut lire/modifier, admin peut tout".

        Args:
            obj: Objet à vérifier (Execution, ScheduledExecution, etc.)
                 Doit avoir un attribut `user_id` ou `user`.

        Returns:
            True si user est owner OU a permission admin.
            False sinon.
        """
        # Si user a déjà permission admin (has_permission), autoriser
        if self.has_permission(request, view):
            return True

        # Sinon, vérifier ownership
        obj_user_id = getattr(obj, 'user_id', None) or getattr(getattr(obj, 'user', None), 'id', None)
        if obj_user_id and obj_user_id == request.user.id:
            return True

        return False


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
