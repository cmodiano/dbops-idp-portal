"""DRF serializers for profiles and permissions API (Story M.5)."""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer
from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for Profile read/write operations."""
    
    is_admin = serializers.BooleanField()
    is_auditor = serializers.BooleanField()
    
    class Meta:
        model = Profile
        fields = ['id', 'name', 'description', 'ad_group', 'is_admin', 'is_auditor', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def to_representation(self, instance):
        """Convert is_admin/is_auditor from IntegerField (0/1) to boolean."""
        data = super().to_representation(instance)
        data['is_admin'] = bool(instance.is_admin)
        data['is_auditor'] = bool(instance.is_auditor)
        return data


class ProfileCreateSerializer(serializers.Serializer):
    """Serializer for POST /admin/profiles (validation: name, ad_group required)."""
    
    name = serializers.CharField(min_length=1, max_length=255, trim_whitespace=True)
    description = serializers.CharField(max_length=4000, required=False, allow_null=True, allow_blank=True)
    ad_group = serializers.CharField(min_length=1, max_length=512, trim_whitespace=True)
    is_admin = serializers.BooleanField(default=False)
    is_auditor = serializers.BooleanField(default=False)
    
    def validate_name(self, value):
        """Strip and validate name is not empty."""
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("name cannot be empty or whitespace only")
        return stripped
    
    def validate_ad_group(self, value):
        """Strip and validate ad_group is not empty."""
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("ad_group cannot be empty or whitespace only")
        return stripped


class ProfileUpdateSerializer(serializers.Serializer):
    """Serializer for PUT /admin/profiles/{id} (all fields optional)."""
    
    name = serializers.CharField(min_length=1, max_length=255, required=False, allow_null=True, trim_whitespace=True)
    description = serializers.CharField(max_length=4000, required=False, allow_null=True, allow_blank=True)
    ad_group = serializers.CharField(min_length=1, max_length=512, required=False, allow_null=True, trim_whitespace=True)
    is_admin = serializers.BooleanField(required=False, allow_null=True)
    is_auditor = serializers.BooleanField(required=False, allow_null=True)
    
    def validate_name(self, value):
        """Strip name if provided."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None
    
    def validate_ad_group(self, value):
        """Strip ad_group if provided."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None


class ProfileListSerializer(serializers.ModelSerializer):
    """Serializer for GET /admin/profiles list (with permission_count)."""
    
    is_admin = serializers.BooleanField()
    is_auditor = serializers.BooleanField()
    permission_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Profile
        fields = ['id', 'name', 'ad_group', 'is_admin', 'is_auditor', 'permission_count', 'created_at']
        read_only_fields = ['id', 'permission_count', 'created_at']
    
    def to_representation(self, instance):
        """Convert is_admin/is_auditor from IntegerField (0/1) to boolean."""
        data = super().to_representation(instance)
        data['is_admin'] = bool(instance.is_admin)
        data['is_auditor'] = bool(instance.is_auditor)
        return data


@extend_schema_serializer(
    exclude_fields=[],
    examples=[]
)
class ProfileActionPermissionsSerializer(serializers.Serializer):
    """Serializer for GET/PUT /admin/profiles/{id}/actions."""

    actions_type = serializers.ChoiceField(
        choices=['list', 'pattern', 'all'],
        help_text="Type de permission : list (IDs explicites), pattern (par tags), all (toutes)"
    )
    action_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_null=True,
        default=list
    )
    tag_patterns = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_null=True,
        default=list
    )
    environments = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_null=True,
        default=list
    )

    def validate_environments(self, value: list[str] | None) -> list[str]:
        """Validate environments against inventory (Story 21.6, AC1-3)."""
        from profiles.validation import validate_environments_against_inventory
        from core.exceptions import BadRequestError, ServiceUnavailableError

        if not value:
            return []

        request = self.context.get('request')
        user_id = request.user.id if request and hasattr(request, 'user') and hasattr(request.user, 'id') else None

        try:
            return validate_environments_against_inventory(value, user_id=user_id)
        except BadRequestError as e:
            raise serializers.ValidationError(e.message)
        except ServiceUnavailableError:
            # Re-raise ServiceUnavailableError as-is for HTTP 503 (handled by custom_exception_handler)
            raise

    def validate(self, data):
        """Validate type/fields coherence (equivalent to Pydantic model_validator)."""
        actions_type = data.get('actions_type')
        action_ids = data.get('action_ids')
        tag_patterns = data.get('tag_patterns')
        
        # Normalize empty lists to None for consistent validation
        if action_ids is not None and len(action_ids) == 0:
            action_ids = None
        if tag_patterns is not None and len(tag_patterns) == 0:
            tag_patterns = None
        
        if actions_type == 'list':
            if not action_ids:
                raise serializers.ValidationError({
                    'action_ids': 'action_ids is required when actions_type is "list"'
                })
            if tag_patterns:
                raise serializers.ValidationError({
                    'tag_patterns': 'tag_patterns must be empty when actions_type is "list"'
                })
        elif actions_type == 'pattern':
            if not tag_patterns:
                raise serializers.ValidationError({
                    'tag_patterns': 'tag_patterns is required when actions_type is "pattern"'
                })
            if action_ids:
                raise serializers.ValidationError({
                    'action_ids': 'action_ids must be empty when actions_type is "pattern"'
                })
        else:  # all
            if action_ids or tag_patterns:
                raise serializers.ValidationError({
                    'non_field_errors': 'action_ids and tag_patterns must be empty when actions_type is "all"'
                })
        
        return data
    
    def to_representation(self, instance):
        """Convert ProfileActionPermission model to serializer format."""
        if isinstance(instance, ProfileActionPermission):
            # Map permission_type (LIST/PATTERN/ALL) to actions_type (list/pattern/all)
            type_map = {'LIST': 'list', 'PATTERN': 'pattern', 'ALL': 'all'}
            actions_type = type_map.get(instance.permission_type, 'all')
            
            return {
                'actions_type': actions_type,
                'action_ids': instance.get_action_ids(),
                'tag_patterns': instance.get_tag_patterns(),
                'environments': instance.get_environments(),
            }
        return super().to_representation(instance)


@extend_schema_serializer(
    exclude_fields=[],
    examples=[]
)
class ProfileTargetPermissionsSerializer(serializers.Serializer):
    """Serializer for GET/PUT /admin/profiles/{id}/targets."""

    targets_type = serializers.ChoiceField(
        choices=['list', 'pattern', 'all'],
        help_text="Type de permission : list (noms explicites), pattern (wildcards), all (tous)"
    )
    target_names = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_null=True,
        default=list
    )
    target_patterns = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_null=True,
        default=list
    )
    
    def validate(self, data):
        """Validate type/fields coherence (equivalent to Pydantic model_validator)."""
        targets_type = data.get('targets_type')
        target_names = data.get('target_names')
        target_patterns = data.get('target_patterns')
        
        # Normalize empty lists to None for consistent validation
        if target_names is not None and len(target_names) == 0:
            target_names = None
        if target_patterns is not None and len(target_patterns) == 0:
            target_patterns = None
        
        if targets_type == 'list':
            if not target_names:
                raise serializers.ValidationError({
                    'target_names': 'target_names is required when targets_type is "list"'
                })
            if target_patterns:
                raise serializers.ValidationError({
                    'target_patterns': 'target_patterns must be empty when targets_type is "list"'
                })
        elif targets_type == 'pattern':
            if not target_patterns:
                raise serializers.ValidationError({
                    'target_patterns': 'target_patterns is required when targets_type is "pattern"'
                })
            if target_names:
                raise serializers.ValidationError({
                    'target_names': 'target_names must be empty when targets_type is "pattern"'
                })
        else:  # all
            if target_names or target_patterns:
                raise serializers.ValidationError({
                    'non_field_errors': 'target_names and target_patterns must be empty when targets_type is "all"'
                })
        
        return data
    
    def to_representation(self, instance):
        """Convert ProfileTargetPermission model to serializer format."""
        if isinstance(instance, ProfileTargetPermission):
            # Map permission_type (LIST/PATTERN/ALL) to targets_type (list/pattern/all)
            type_map = {'LIST': 'list', 'PATTERN': 'pattern', 'ALL': 'all'}
            targets_type = type_map.get(instance.permission_type, 'all')
            
            return {
                'targets_type': targets_type,
                'target_names': instance.get_target_names(),
                'target_patterns': instance.get_target_patterns(),
            }
        return super().to_representation(instance)
