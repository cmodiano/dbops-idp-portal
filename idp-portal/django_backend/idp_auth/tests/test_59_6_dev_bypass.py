"""
Story 59.6 — SEC-6: Dev bypass auth — blocage prod + audit.
Tests unitaires pour authenticate() dans JWTAuthentication.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from idp_auth.authentication import JWTAuthentication


@pytest.mark.django_db
class TestDevBypassAuthSec6:
    """SEC-6: Dev bypass auth bloqué en prod, audit en dev."""

    def setup_method(self):
        self.auth = JWTAuthentication()
        self.factory = APIRequestFactory()

    @override_settings(AUTH_DEV_BYPASS=True, DEBUG=False)
    def test_59_6_a_production_dev_bypass_returns_none(self):
        """59-6-a: DEBUG=False + mock token → authenticate() retourne None."""
        request = self.factory.get('/', HTTP_AUTHORIZATION='Bearer dev-mock-token-for-testing')
        result = self.auth.authenticate(request)
        assert result is None  # Non authentifié — pas de user créé

    @override_settings(AUTH_DEV_BYPASS=True, DEBUG=True)
    def test_59_6_b_dev_bypass_creates_audit_entry(self):
        """59-6-b: DEBUG=True + mock token → dev_user retourné + audit créé."""
        with patch('idp_auth.authentication.AuditService') as mock_audit:
            request = self.factory.get('/', HTTP_AUTHORIZATION='Bearer dev-mock-token-for-testing')
            result = self.auth.authenticate(request)
            assert result is not None
            user, token = result
            assert user.username == 'dev-user'
            assert token is None
            # Vérifier que AuditService.create_entry a été appelé
            mock_audit.create_entry.assert_called_once()
            call_kwargs = mock_audit.create_entry.call_args.kwargs
            assert call_kwargs['action_type'].value == 'AUTH_DEV_BYPASS_LOGIN'

    @override_settings(AUTH_DEV_BYPASS=False, DEBUG=True)
    def test_59_6_c_bypass_disabled_mock_token_not_recognized(self):
        """59-6-c: AUTH_DEV_BYPASS=False → mock token non reconnu, flow JWT normal."""
        from rest_framework.exceptions import AuthenticationFailed
        request = self.factory.get('/', HTTP_AUTHORIZATION='Bearer dev-mock-token-for-testing')
        # Avec AUTH_DEV_BYPASS=False, le token mock n'est pas reconnu → JWT invalide → AuthenticationFailed
        with pytest.raises(AuthenticationFailed):
            self.auth.authenticate(request)

    @override_settings(AUTH_DEV_BYPASS=True, DEBUG=False)
    def test_59_6_d_production_normal_jwt_not_blocked(self):
        """59-6-d: DEBUG=False + token JWT normal → guard ne bloque pas (flow JWT normal)."""
        # Un token JWT normal (non mock) ne passe pas par le guard dev bypass
        with patch('idp_auth.authentication.verify_token') as mock_verify:
            mock_payload = MagicMock()
            mock_payload.sub = '99999'
            mock_payload.ad_groups = ['dbops']
            mock_verify.return_value = mock_payload
            with patch('idp_auth.authentication.User.objects.get') as mock_get:
                mock_user = MagicMock()
                mock_get.return_value = mock_user
                request = self.factory.get('/', HTTP_AUTHORIZATION='Bearer some-real-jwt-token')
                result = self.auth.authenticate(request)
                assert result is not None
                mock_verify.assert_called_once_with('some-real-jwt-token', expected_type='access')
