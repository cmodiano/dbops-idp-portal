"""
Tests complémentaires pour idp_auth/views/jwt.py — couverture des lignes manquantes.
Lignes cibles: 49-52, 69-80, 150-157, 193->213, 203-206
"""
import pytest
from unittest.mock import patch, MagicMock
from rest_framework.test import APIRequestFactory, force_authenticate

from idp_auth.views.jwt import (
    CurrentUserProfileView,
    RefreshTokenView,
    LogoutView,
)
from core.exceptions import UnauthorizedError


class TestCurrentUserProfileViewCoverage:
    """Tests pour CurrentUserProfileView — lignes 49-52, 69-80."""

    def _make_user_with_profile_object(self, profile_name='dbops', has_name_attr=True, has_code_attr=False):
        """Helper: créer un user mock avec profile comme objet (pas string)."""
        user = MagicMock()
        user.id = 42
        user.username = 'testuser'
        user.display_name = 'Test User'
        user.ad_groups = []
        user.email = 'test@example.com'

        profile_obj = MagicMock(spec=[])
        if has_name_attr:
            profile_obj.name = profile_name
        if has_code_attr:
            profile_obj.code = profile_name
        user.profile = profile_obj
        return user

    def test_profile_name_from_profile_object_with_name_attr(self):
        """Lignes 49-50: profile est un objet avec .name → profile_name = profile.name.lower()."""
        factory = APIRequestFactory()
        request = factory.get('/auth/me/')
        user = self._make_user_with_profile_object(profile_name='DBOPS', has_name_attr=True)
        force_authenticate(request, user=user)

        with patch('idp_auth.views.jwt.Profile') as mock_profile_model:
            mock_profile_model.objects.find_by_ad_groups.return_value = []
            with patch('idp_auth.views.jwt.get_user_navigation_permissions', return_value=[]):
                with patch('idp_auth.views.jwt.is_business_profile', return_value=False):
                    view = CurrentUserProfileView.as_view()
                    response = view(request)

        assert response.status_code == 200
        # profile_name doit être 'dbops' (lowercased depuis .name)
        assert response.data['data']['profile'] == 'dbops'

    def test_profile_name_from_profile_object_with_code_attr(self):
        """Lignes 51-52: profile est un objet sans .name mais avec .code → profile_name = profile.code.lower()."""
        factory = APIRequestFactory()
        request = factory.get('/auth/me/')
        user = self._make_user_with_profile_object(profile_name='DBA', has_name_attr=False, has_code_attr=True)
        force_authenticate(request, user=user)

        with patch('idp_auth.views.jwt.Profile') as mock_profile_model:
            mock_profile_model.objects.find_by_ad_groups.return_value = []
            with patch('idp_auth.views.jwt.get_user_navigation_permissions', return_value=[]):
                with patch('idp_auth.views.jwt.is_business_profile', return_value=False):
                    view = CurrentUserProfileView.as_view()
                    response = view(request)

        assert response.status_code == 200
        assert response.data['data']['profile'] == 'dba'

    def test_profile_service_exception_handled_gracefully(self):
        """Lignes 69-80: ProfileService.get_cumulative_permissions lève une exception → None + log."""
        factory = APIRequestFactory()
        request = factory.get('/auth/me/')

        user = MagicMock()
        user.id = 42
        user.username = 'testuser'
        user.display_name = 'Test User'
        user.ad_groups = ['dbops']
        user.profile = 'dbops'
        user.email = 'test@example.com'
        force_authenticate(request, user=user)

        mock_profile = MagicMock()
        mock_profile.id = 1
        mock_profile.is_auditor = 0

        with patch('idp_auth.views.jwt.Profile') as mock_profile_model:
            mock_profile_model.objects.find_by_ad_groups.return_value = [mock_profile]
            with patch('idp_auth.views.jwt.ProfileService') as mock_profile_service_cls:
                # ProfileService.get_cumulative_permissions lève une exception
                mock_service_instance = MagicMock()
                mock_service_instance.get_cumulative_permissions.side_effect = Exception("DB error")
                mock_profile_service_cls.return_value = mock_service_instance

                with patch('idp_auth.views.jwt.get_user_navigation_permissions', return_value=['executions']):
                    with patch('idp_auth.views.jwt.is_business_profile', return_value=False):
                        view = CurrentUserProfileView.as_view()
                        response = view(request)

        assert response.status_code == 200
        # cumulative_permissions doit être None (erreur gracieuse)
        assert response.data['data']['cumulative_permissions'] is None


class TestRefreshTokenViewCoverage:
    """Tests pour RefreshTokenView — lignes 150-157."""

    def test_invalid_sub_in_token_raises_unauthorized(self):
        """Lignes 150-157: payload.sub non convertible en int → UnauthorizedError (401)."""
        factory = APIRequestFactory()
        request = factory.post('/auth/refresh/')

        mock_payload = MagicMock()
        mock_payload.sub = 'not-an-integer'
        mock_payload.username = 'testuser'
        mock_payload.profile = 'dbops'
        mock_payload.ad_groups = []

        with patch('idp_auth.views.jwt.verify_token', return_value=mock_payload):
            with patch('idp_auth.views.jwt.create_access_token', return_value='new_token'):
                request.COOKIES = {'refresh_token': 'valid_refresh_token'}
                _view = RefreshTokenView.as_view()
                # La vue DRF convertit UnauthorizedError en réponse 401
                # On vérifie que le code de l'exception est levé correctement
                # en appelant directement la méthode post
                view_instance = RefreshTokenView()
                view_instance.request = request
                view_instance.format_kwarg = None
                with pytest.raises(UnauthorizedError):
                    view_instance.post(request)

    def test_no_refresh_token_cookie_raises_unauthorized(self):
        """Pas de refresh_token cookie → UnauthorizedError."""
        factory = APIRequestFactory()
        request = factory.post('/auth/refresh/')
        request.COOKIES = {}

        view_instance = RefreshTokenView()
        with pytest.raises(UnauthorizedError):
            view_instance.post(request)

    def test_invalid_refresh_token_raises_unauthorized(self):
        """verify_token retourne None → UnauthorizedError."""
        factory = APIRequestFactory()
        request = factory.post('/auth/refresh/')
        request.COOKIES = {'refresh_token': 'bad_token'}

        with patch('idp_auth.views.jwt.verify_token', return_value=None):
            view_instance = RefreshTokenView()
            with pytest.raises(UnauthorizedError):
                view_instance.post(request)

    def test_valid_refresh_token_returns_access_token(self):
        """refresh_token valide + sub int → retourne access_token."""
        factory = APIRequestFactory()
        request = factory.post('/auth/refresh/')
        request.COOKIES = {'refresh_token': 'valid_refresh_token'}

        mock_payload = MagicMock()
        mock_payload.sub = '42'  # sub convertible en int
        mock_payload.username = 'testuser'
        mock_payload.profile = 'dbops'
        mock_payload.ad_groups = ['dbops']

        with patch('idp_auth.views.jwt.verify_token', return_value=mock_payload):
            with patch('idp_auth.views.jwt.create_access_token', return_value='new_access_token'):
                with patch('idp_auth.views.jwt.AuditService') as _mock_audit:
                    view = RefreshTokenView.as_view()
                    response = view(request)

        assert response.status_code == 200
        assert response.data['data']['access_token'] == 'new_access_token'


class TestLogoutViewCoverage:
    """Tests pour LogoutView — lignes 193->213, 203-206."""

    def test_logout_with_valid_refresh_token_audits(self):
        """Lignes 193->213: refresh_token dans cookie + payload valide → audit USER_LOGOUT."""
        factory = APIRequestFactory()
        request = factory.post('/auth/logout/')
        request.COOKIES = {'refresh_token': 'valid_refresh_token'}

        mock_payload = MagicMock()
        mock_payload.sub = '42'
        mock_payload.username = 'testuser'

        with patch('idp_auth.views.jwt.verify_token', return_value=mock_payload):
            with patch('idp_auth.views.jwt.AuditService') as mock_audit:
                view = LogoutView.as_view()
                response = view(request)

        assert response.status_code == 200
        assert response.data['data']['message'] == 'Deconnexion reussie'
        mock_audit.create_entry.assert_called_once()

    def test_logout_without_refresh_token_no_audit(self):
        """Pas de refresh_token → pas d'audit, logout réussi."""
        factory = APIRequestFactory()
        request = factory.post('/auth/logout/')
        request.COOKIES = {}

        with patch('idp_auth.views.jwt.AuditService') as mock_audit:
            view = LogoutView.as_view()
            response = view(request)

        assert response.status_code == 200
        mock_audit.create_entry.assert_not_called()

    def test_logout_with_invalid_sub_logs_warning(self):
        """Lignes 203-206: payload.sub non convertible en int → log warning, pas d'exception."""
        factory = APIRequestFactory()
        request = factory.post('/auth/logout/')
        request.COOKIES = {'refresh_token': 'valid_refresh_token'}

        mock_payload = MagicMock()
        mock_payload.sub = 'not-an-int'  # ValueError lors du int(payload.sub)
        mock_payload.username = 'testuser'

        with patch('idp_auth.views.jwt.verify_token', return_value=mock_payload):
            with patch('idp_auth.views.jwt.AuditService') as mock_audit:
                with patch('idp_auth.views.jwt.get_correlation_id', return_value='corr-123'):
                    view = LogoutView.as_view()
                    # Ne doit PAS lever d'exception
                    response = view(request)

        assert response.status_code == 200
        # Audit ne doit pas être appelé (ValueError capturée)
        mock_audit.create_entry.assert_not_called()

    def test_logout_with_invalid_refresh_token_no_audit(self):
        """verify_token retourne None → pas d'audit."""
        factory = APIRequestFactory()
        request = factory.post('/auth/logout/')
        request.COOKIES = {'refresh_token': 'bad_token'}

        with patch('idp_auth.views.jwt.verify_token', return_value=None):
            with patch('idp_auth.views.jwt.AuditService') as mock_audit:
                view = LogoutView.as_view()
                response = view(request)

        assert response.status_code == 200
        mock_audit.create_entry.assert_not_called()
