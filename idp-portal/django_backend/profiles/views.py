"""
DRF ViewSets and APIViews for profiles app.
Implements admin profiles endpoints (Story M.5).
"""

from typing import Any

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import serializers
from rest_framework.parsers import MultiPartParser
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from profiles.models import Profile
from profiles.serializers import (
    ProfileSerializer,
    ProfileCreateSerializer,
    ProfileUpdateSerializer,
    ProfileListSerializer,
    ProfileActionPermissionsSerializer,
    ProfileTargetPermissionsSerializer,
)
from profiles.cache import invalidate_permissions_cache
from profiles.services import ProfileService
from profiles.services_export_import import export_profiles_yaml, import_profiles_yaml
from core.permissions import AdminProfilePermission
from core.exceptions import NotFoundError, InvalidStateError


@extend_schema_view(
    list=extend_schema(tags=['profiles'], summary='Lister les profils', responses={200: ProfileListSerializer(many=True)}),
    create=extend_schema(tags=['profiles'], summary='Créer un profil', request=ProfileCreateSerializer, responses={201: ProfileSerializer}),
    retrieve=extend_schema(tags=['profiles'], summary='Détail d\'un profil', responses={200: ProfileSerializer}),
    update=extend_schema(tags=['profiles'], summary='Modifier un profil', request=ProfileUpdateSerializer, responses={200: ProfileSerializer}),
    destroy=extend_schema(tags=['profiles'], summary='Supprimer un profil'),
)
class ProfileViewSet(viewsets.ViewSet):
    """
    ViewSet for admin profiles CRUD operations.

    Story 33.4 (DIP): uses _profile_service_class + get_profile_service() so
    tests can override the service class without monkey-patching.
    """
    permission_classes = [IsAuthenticated, AdminProfilePermission]

    _profile_service_class: type[ProfileService] = ProfileService

    def get_profile_service(self) -> ProfileService:
        """Return a ProfileService instance (overridable in tests)."""
        return self._profile_service_class()

    def _get_profile_id(self, pk: Any) -> int:
        """
        Helper method to extract and validate profile ID from pk parameter.

        Args:
            pk: Primary key (string or int)

        Returns:
            int: Validated profile ID

        Raises:
            NotFoundError: If pk cannot be converted to int
        """
        try:
            return int(pk)
        except (ValueError, TypeError):
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Profil {pk} introuvable",
                details={"profile_id": pk}
            )

    def _get_profile_or_404(self, profile_id: int) -> Profile:
        """
        Helper method to get profile by ID or raise 404.

        Args:
            profile_id: Profile ID (int)

        Returns:
            Profile: Profile instance

        Raises:
            NotFoundError: If profile not found
        """
        service = self.get_profile_service()
        profile = service.get_by_id(profile_id)
        if profile is None:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Profil {profile_id} introuvable",
                details={"profile_id": profile_id}
            )
        return profile

    def get_serializer_class(self) -> type[ProfileCreateSerializer] | type[ProfileListSerializer] | type[ProfileSerializer]:
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return ProfileCreateSerializer
        elif self.action == 'list':
            return ProfileListSerializer
        return ProfileSerializer

    def list(self, request: Request) -> Response:
        """GET /admin/profiles - List all profiles. Supports ?is_approver=true filter (Story 58.4 AC4)."""
        service = self.get_profile_service()
        is_approver_param = request.query_params.get('is_approver', '').lower()
        if is_approver_param == 'true':
            profiles = service.list_approvers()
        else:
            profiles = service.list_all()
        serializer = ProfileListSerializer(profiles, many=True)
        return Response({"data": serializer.data})

    def create(self, request: Request) -> Response:
        """POST /admin/profiles - Create a new profile. Returns 201."""
        serializer = ProfileCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        service = self.get_profile_service()
        try:
            profile = service.create_profile(serializer.validated_data, user=request.user)
        except ValueError as e:
            # Handle duplicate name error
            raise InvalidStateError(
                code="DUPLICATE_NAME",
                message=str(e),
                details={"name": serializer.validated_data.get('name')}
            )
        
        invalidate_permissions_cache()
        response_serializer = ProfileSerializer(profile)
        return Response({"data": response_serializer.data}, status=status.HTTP_201_CREATED)
    
    def retrieve(self, request: Request, pk: Any = None) -> Response:
        """GET /admin/profiles/{id} - Get profile by ID."""
        profile_id = self._get_profile_id(pk)
        profile = self._get_profile_or_404(profile_id)

        serializer = ProfileSerializer(profile)
        return Response({"data": serializer.data})

    def update(self, request: Request, pk: Any = None) -> Response:
        """PUT /admin/profiles/{id} - Update profile."""
        profile_id = self._get_profile_id(pk)
        
        serializer = ProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        service = self.get_profile_service()
        try:
            profile = service.update_profile(profile_id, serializer.validated_data, user=request.user)
        except ValueError as e:
            # Handle duplicate name error
            raise InvalidStateError(
                code="DUPLICATE_NAME",
                message=str(e),
                details={"name": serializer.validated_data.get('name')}
            )
        
        if profile is None:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Profil {profile_id} introuvable",
                details={"profile_id": profile_id}
            )
        
        invalidate_permissions_cache()
        response_serializer = ProfileSerializer(profile)
        return Response({"data": response_serializer.data})
    
    def destroy(self, request: Request, pk: Any = None) -> Response:
        """DELETE /admin/profiles/{id} - Delete profile. Returns 204."""
        profile_id = self._get_profile_id(pk)

        service = self.get_profile_service()
        deleted = service.delete_profile(profile_id, user=request.user)

        if not deleted:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Profil {profile_id} introuvable",
                details={"profile_id": profile_id}
            )

        invalidate_permissions_cache()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get', 'put'])
    def actions(self, request: Request, pk: Any = None) -> Response:
        """GET/PUT /admin/profiles/{id}/actions - Get/set action permissions."""
        profile_id = self._get_profile_id(pk)
        self._get_profile_or_404(profile_id)  # Verify profile exists
        
        service = self.get_profile_service()
        
        if request.method == 'GET':
            # GET /admin/profiles/{id}/actions
            perm = service.get_action_permissions(profile_id)
            if perm is None:
                # Return default "all" permissions
                return Response({"data": {
                    "actions_type": "all",
                    "action_ids": [],
                    "tag_patterns": [],
                    "environments": []
                }})
            
            serializer = ProfileActionPermissionsSerializer(perm)
            return Response({"data": serializer.data})
        
        else:  # PUT
            # PUT /admin/profiles/{id}/actions
            serializer = ProfileActionPermissionsSerializer(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            
            perm = service.set_action_permissions(profile_id, serializer.validated_data, user=request.user)
            if perm is None:
                raise NotFoundError(
                    code="NOT_FOUND",
                    message=f"Profil {profile_id} introuvable",
                    details={"profile_id": profile_id}
                )
            
            invalidate_permissions_cache()
            response_serializer = ProfileActionPermissionsSerializer(perm)
            return Response({"data": response_serializer.data})
    
    @action(detail=True, methods=['get', 'put'])
    def targets(self, request: Request, pk: Any = None) -> Response:
        """GET/PUT /admin/profiles/{id}/targets - Get/set target permissions."""
        profile_id = self._get_profile_id(pk)
        self._get_profile_or_404(profile_id)  # Verify profile exists
        
        service = self.get_profile_service()
        
        if request.method == 'GET':
            # GET /admin/profiles/{id}/targets
            perm = service.get_target_permissions(profile_id)
            if perm is None:
                # Return default "all" permissions
                return Response({"data": {
                    "targets_type": "all",
                    "target_names": [],
                    "target_patterns": []
                }})
            
            serializer = ProfileTargetPermissionsSerializer(perm)
            return Response({"data": serializer.data})
        
        else:  # PUT
            # PUT /admin/profiles/{id}/targets
            serializer = ProfileTargetPermissionsSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            perm = service.set_target_permissions(profile_id, serializer.validated_data, user=request.user)
            if perm is None:
                raise NotFoundError(
                    code="NOT_FOUND",
                    message=f"Profil {profile_id} introuvable",
                    details={"profile_id": profile_id}
                )
            
            invalidate_permissions_cache()
            response_serializer = ProfileTargetPermissionsSerializer(perm)
            return Response({"data": response_serializer.data})


class ProfileExportView(APIView):
    """APIView for GET /admin/profiles/export - Export profiles as YAML."""
    permission_classes = [IsAuthenticated, AdminProfilePermission]

    @extend_schema(tags=['profiles'], summary='Exporter les profils en YAML')
    def get(self, request: Request) -> Any:
        """Export all profiles as YAML."""
        content = export_profiles_yaml()
        from django.http import HttpResponse
        response = HttpResponse(content, content_type="application/x-yaml")
        response['Content-Disposition'] = 'attachment; filename=profiles.yaml'
        return response


class ProfileImportView(APIView):
    """APIView for POST /admin/profiles/import - Import profiles from YAML."""
    permission_classes = [IsAuthenticated, AdminProfilePermission]
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=['profiles'],
        summary='Importer des profils depuis un fichier YAML',
        request=inline_serializer(
            name='ProfileImportRequest',
            fields={
                'file': serializers.FileField(
                    help_text='Fichier YAML (.yaml ou .yml)',
                ),
            },
        ),
    )
    def post(self, request: Request) -> Response:
        """Import profiles from YAML file."""
        file = request.FILES.get('file')
        if not file:
            raise InvalidStateError(
                code="INVALID_FILE",
                message="Le fichier est requis",
                details={}
            )
        
        mode = request.query_params.get('mode', 'additive')
        if mode not in ('additive', 'full'):
            raise InvalidStateError(
                code="INVALID_IMPORT_MODE",
                message="Le paramètre 'mode' doit être 'additive' ou 'full'.",
                details={"mode": mode},
            )
        content = file.read()
        try:
            created, updated, unchanged = import_profiles_yaml(content, user=request.user, mode=mode)
        except InvalidStateError:
            raise

        invalidate_permissions_cache()
        payload = {"data": {"created": created, "updated": updated, "unchanged": unchanged, "mode": mode}}
        status_code = status.HTTP_201_CREATED if created > 0 and updated == 0 else status.HTTP_200_OK
        return Response(payload, status=status_code)
