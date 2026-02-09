"""
Integration tests for profile environment validation (Story 21.6).
Tests serializer validation and HTTP endpoints.
"""

import pytest
from unittest.mock import patch
from rest_framework.test import APIClient
from rest_framework import status as http_status

from profiles.serializers import ProfileActionPermissionsSerializer
from profiles.models import Profile
from inventory.services import InventoryServiceError
from core.exceptions import ServiceUnavailableError
from idp_auth.models import User


class TestProfileActionPermissionsSerializerEnvironmentValidation:
    """Integration tests for environment validation in serializer (Story 21.6)."""

    def test_valid_environments_pass(self, mocker):
        """Serializer accepts valid environments (AC1)."""
        mock = mocker.patch('profiles.validation.InventoryService')
        mock.return_value.list_environments.return_value = ['lab', 'dev', 'staging']

        serializer = ProfileActionPermissionsSerializer(data={
            'actions_type': 'all',
            'environments': ['lab', 'dev'],
        })

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['environments'] == ['lab', 'dev']

    def test_invalid_environments_fail(self, mocker):
        """Serializer rejects invalid environments with ValidationError (AC1, AC5)."""
        mock = mocker.patch('profiles.validation.InventoryService')
        mock.return_value.list_environments.return_value = ['lab', 'dev']
        mocker.patch('profiles.validation.AuditService')

        serializer = ProfileActionPermissionsSerializer(data={
            'actions_type': 'all',
            'environments': ['lab', 'invalid_env'],
        })

        assert not serializer.is_valid()
        assert 'environments' in serializer.errors
        assert 'invalid_env' in str(serializer.errors['environments'])

    def test_inventory_unavailable_raises_503(self, mocker):
        """Serializer raises ServiceUnavailableError if inventory down (AC3)."""
        mock = mocker.patch('profiles.validation.InventoryService')
        mock.return_value.list_environments.side_effect = InventoryServiceError("DB down")

        serializer = ProfileActionPermissionsSerializer(data={
            'actions_type': 'all',
            'environments': ['lab'],
        })

        with pytest.raises(ServiceUnavailableError):
            serializer.is_valid(raise_exception=True)

    def test_case_insensitive_normalization(self, mocker):
        """Serializer normalizes environments to lowercase (AC2)."""
        mock = mocker.patch('profiles.validation.InventoryService')
        mock.return_value.list_environments.return_value = ['lab', 'dev']

        serializer = ProfileActionPermissionsSerializer(data={
            'actions_type': 'all',
            'environments': ['LAB', 'DEV'],
        })

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['environments'] == ['lab', 'dev']

    def test_empty_environments_pass(self):
        """Serializer accepts empty environments without calling inventory (AC4)."""
        serializer = ProfileActionPermissionsSerializer(data={
            'actions_type': 'all',
            'environments': [],
        })

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['environments'] == []

    def test_null_environments_pass(self):
        """Serializer accepts null environments (AC4)."""
        serializer = ProfileActionPermissionsSerializer(data={
            'actions_type': 'all',
            'environments': None,
        })

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['environments'] == []

    def test_error_message_is_explicit(self, mocker):
        """Error message lists the invalid environments (AC1)."""
        mock = mocker.patch('profiles.validation.InventoryService')
        mock.return_value.list_environments.return_value = ['lab', 'dev']
        mocker.patch('profiles.validation.AuditService')

        serializer = ProfileActionPermissionsSerializer(data={
            'actions_type': 'all',
            'environments': ['typo_env', 'fake_env'],
        })

        assert not serializer.is_valid()
        error_msg = str(serializer.errors['environments'])
        assert 'typo_env' in error_msg
        assert 'fake_env' in error_msg


@pytest.mark.django_db
class TestProfileEnvironmentValidationViews:
    """HTTP endpoint tests for profile environment validation (Story 21.6)."""

    @pytest.fixture(autouse=True)
    def setup_data(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create(username='dbops_user', profile='dbops')
        self.profile = Profile.objects.create(name='Test Profile', ad_group='GRP-TEST')
        self.client.force_authenticate(user=self.user)

    def test_put_actions_invalid_environment_http_400(self, mocker):
        """PUT /admin/profiles/{id}/actions/ with invalid env returns HTTP 400 (AC1)."""
        mock = mocker.patch('profiles.validation.InventoryService')
        mock.return_value.list_environments.return_value = ['lab', 'dev']
        mocker.patch('profiles.validation.AuditService')

        response = self.client.put(
            f'/api/v1/admin/profiles/{self.profile.id}/actions/',
            {'actions_type': 'all', 'environments': ['lab', 'invalid_env']},
            format='json',
        )

        assert response.status_code == http_status.HTTP_400_BAD_REQUEST
        assert 'invalid_env' in str(response.data)

    def test_put_actions_valid_environments_succeed(self, mocker):
        """PUT /admin/profiles/{id}/actions/ with valid envs succeeds (AC1)."""
        mock = mocker.patch('profiles.validation.InventoryService')
        mock.return_value.list_environments.return_value = ['lab', 'dev', 'staging', 'prod']

        response = self.client.put(
            f'/api/v1/admin/profiles/{self.profile.id}/actions/',
            {'actions_type': 'all', 'environments': ['lab', 'dev']},
            format='json',
        )

        assert response.status_code == http_status.HTTP_200_OK
        assert response.data['data']['environments'] == ['lab', 'dev']

    def test_put_actions_mixed_case_normalized(self, mocker):
        """PUT /admin/profiles/{id}/actions/ normalizes case (AC2)."""
        mock = mocker.patch('profiles.validation.InventoryService')
        mock.return_value.list_environments.return_value = ['lab', 'dev']

        response = self.client.put(
            f'/api/v1/admin/profiles/{self.profile.id}/actions/',
            {'actions_type': 'all', 'environments': ['LAB', 'Dev']},
            format='json',
        )

        assert response.status_code == http_status.HTTP_200_OK
        # Environments stored as lowercase
        assert response.data['data']['environments'] == ['lab', 'dev']

    def test_put_actions_inventory_unavailable_http_503(self, mocker):
        """PUT /admin/profiles/{id}/actions/ with inventory down returns HTTP 503 (AC3)."""
        mock = mocker.patch('profiles.validation.InventoryService')
        mock.return_value.list_environments.side_effect = InventoryServiceError("DB down")

        response = self.client.put(
            f'/api/v1/admin/profiles/{self.profile.id}/actions/',
            {'actions_type': 'all', 'environments': ['lab']},
            format='json',
        )

        assert response.status_code == http_status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Inventaire indisponible" in str(response.data)

    def test_put_actions_empty_environments_succeed(self, mocker):
        """PUT /admin/profiles/{id}/actions/ with empty envs succeeds (AC4)."""
        response = self.client.put(
            f'/api/v1/admin/profiles/{self.profile.id}/actions/',
            {'actions_type': 'all', 'environments': []},
            format='json',
        )

        assert response.status_code == http_status.HTTP_200_OK

    def test_put_actions_invalid_env_profile_unchanged(self, mocker):
        """PUT with invalid env does not modify profile (AC5 - transaction rollback)."""
        mock = mocker.patch('profiles.validation.InventoryService')
        mock.return_value.list_environments.return_value = ['lab']
        mocker.patch('profiles.validation.AuditService')

        # First: set valid permissions
        mock.return_value.list_environments.return_value = ['lab', 'dev']
        self.client.put(
            f'/api/v1/admin/profiles/{self.profile.id}/actions/',
            {'actions_type': 'all', 'environments': ['lab']},
            format='json',
        )

        # Then: attempt invalid update
        mock.return_value.list_environments.return_value = ['lab']
        response = self.client.put(
            f'/api/v1/admin/profiles/{self.profile.id}/actions/',
            {'actions_type': 'all', 'environments': ['invalid_env']},
            format='json',
        )

        assert response.status_code == http_status.HTTP_400_BAD_REQUEST

        # Verify profile unchanged - get current permissions
        get_response = self.client.get(
            f'/api/v1/admin/profiles/{self.profile.id}/actions/',
        )
        assert get_response.status_code == http_status.HTTP_200_OK
        # Original permissions should be preserved (lab was set, invalid_env rejected)
        assert 'invalid_env' not in str(get_response.data['data'].get('environments', []))
