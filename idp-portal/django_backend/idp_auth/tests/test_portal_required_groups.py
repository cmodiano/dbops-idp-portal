"""
Tests unitaires pour la restriction d'accès par groupes AD — PortalLoginView
Story 68.2 : Restriction d'accès aux comptes à haut privilège via PORTAL_REQUIRED_GROUPS.

AC1  : test_portal_required_groups_setting_is_list, test_portal_required_groups_empty_by_default
AC2  : test_authorised_group_member_can_login
AC3  : test_unauthorised_account_rejected_403
AC4  : test_audit_created_on_insufficient_privileges
AC5  : (couvert via AC1 — variable d'env, pas de valeur en dur)
AC6  : test_no_restriction_when_groups_empty
AC7  : tous les tests ci-dessous
"""

from unittest.mock import MagicMock, patch
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status
from core.models import AuditActionType

ENDPOINT = '/api/v1/auth/portal-login/'


# ============================================================================
# AC1 & AC5 — Configuration PORTAL_REQUIRED_GROUPS
# ============================================================================

def test_portal_required_groups_setting_is_list():
    """AC1 : PORTAL_REQUIRED_GROUPS doit être une liste."""
    assert isinstance(settings.PORTAL_REQUIRED_GROUPS, list), (
        f"PORTAL_REQUIRED_GROUPS doit être une liste, obtenu : {type(settings.PORTAL_REQUIRED_GROUPS)}"
    )


def test_portal_required_groups_empty_by_default():
    """AC1 : La valeur par défaut doit être une liste vide (pas de restriction)."""
    # En test_settings, PORTAL_REQUIRED_GROUPS n'est pas défini → doit être []
    assert settings.PORTAL_REQUIRED_GROUPS == [], (
        f"PORTAL_REQUIRED_GROUPS doit être [] par défaut, obtenu : {settings.PORTAL_REQUIRED_GROUPS}"
    )


# ============================================================================
# AC6 — Rétrocompatibilité (liste vide = pas de restriction)
# ============================================================================

class TestPortalRequiredGroupsEmpty(TestCase):
    """AC6 : Quand PORTAL_REQUIRED_GROUPS est vide, comportement identique à 68-1."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    @override_settings(PORTAL_REQUIRED_GROUPS=[])
    @patch('idp_auth.views.portal_login.AuditService')
    @patch('idp_auth.views.portal_login.create_refresh_token', return_value='refresh_tok')
    @patch('idp_auth.views.portal_login.create_access_token', return_value='access_tok')
    @patch('idp_auth.views.portal_login.AuthService')
    @patch('idp_auth.views.portal_login.Profile')
    @patch('idp_auth.views.portal_login.LDAPService')
    def test_no_restriction_when_groups_empty(
        self, mock_ldap_class, mock_profile, mock_auth_service_class,
        mock_create_access, mock_create_refresh, mock_audit
    ):
        """AC6 : Quand PORTAL_REQUIRED_GROUPS=[], un utilisateur sans groupe spécifique peut se connecter."""
        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.return_value = (
            True,
            ['CN=Domain Users,DC=example,DC=com'],
            'Jane Doe',
        )
        mock_profile_obj = MagicMock()
        mock_profile_obj.name = 'USER'
        mock_profile.objects.find_by_ad_groups.return_value = [mock_profile_obj]
        mock_user = MagicMock()
        mock_user.id = 5
        mock_user.username = 'jdoe'
        mock_user.profile = 'user'
        mock_auth_service_class.return_value.create_or_update_user.return_value = mock_user

        response = self.client.post(
            ENDPOINT,
            {'username': 'jdoe', 'password': 'pass123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ============================================================================
# AC2 & AC3 — Vérification de groupe / rejet 403
# ============================================================================

class TestPortalRequiredGroupsRestriction(TestCase):
    """AC2, AC3, AC4 : Tests avec PORTAL_REQUIRED_GROUPS configuré."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    @override_settings(PORTAL_REQUIRED_GROUPS=['GRP-IDP-ADMIN'])
    @patch('idp_auth.views.portal_login.AuditService')
    @patch('idp_auth.views.portal_login.LDAPService')
    def test_unauthorised_account_rejected_403(self, mock_ldap_class, mock_audit):
        """AC3 : Utilisateur sans groupe requis → 403 INSUFFICIENT_PRIVILEGES."""
        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.return_value = (
            True,
            ['CN=Domain Users,DC=example,DC=com'],  # pas GRP-IDP-ADMIN
            'Jean Dupont',
        )
        response = self.client.post(
            ENDPOINT,
            {'username': 'jdupont-laptop', 'password': 'pass'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error']['code'], 'INSUFFICIENT_PRIVILEGES')

    @override_settings(PORTAL_REQUIRED_GROUPS=['GRP-IDP-ADMIN'])
    @patch('idp_auth.views.portal_login.AuditService')
    @patch('idp_auth.views.portal_login.create_refresh_token', return_value='r')
    @patch('idp_auth.views.portal_login.create_access_token', return_value='a')
    @patch('idp_auth.views.portal_login.AuthService')
    @patch('idp_auth.views.portal_login.Profile')
    @patch('idp_auth.views.portal_login.LDAPService')
    def test_authorised_group_member_can_login(
        self, mock_ldap_class, mock_profile, mock_auth_service_class,
        mock_create_access, mock_create_refresh, mock_audit
    ):
        """AC2 : Utilisateur avec groupe requis → 200 (flow normal)."""
        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.return_value = (
            True,
            ['CN=GRP-IDP-ADMIN,OU=Groups,DC=example,DC=com'],
            'Jean Dupont',
        )
        mock_profile_obj = MagicMock()
        mock_profile_obj.name = 'ADMIN'
        mock_profile.objects.find_by_ad_groups.return_value = [mock_profile_obj]
        mock_user = MagicMock()
        mock_user.id = 10
        mock_user.username = 'jdupont-admin'
        mock_user.profile = 'admin'
        mock_auth_service_class.return_value.create_or_update_user.return_value = mock_user

        response = self.client.post(
            ENDPOINT,
            {'username': 'jdupont-admin', 'password': 'secret'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(PORTAL_REQUIRED_GROUPS=['GRP-IDP-ADMIN'])
    @patch('idp_auth.views.portal_login.AuditService')
    @patch('idp_auth.views.portal_login.LDAPService')
    def test_audit_created_on_insufficient_privileges(self, mock_ldap_class, mock_audit):
        """AC4 : Audit USER_LOGIN avec reason='insufficient_privileges' lors du rejet."""
        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.return_value = (
            True,
            ['CN=Domain Users,DC=example,DC=com'],
            'Jean Dupont',
        )
        response = self.client.post(
            ENDPOINT,
            {'username': 'jdupont-laptop', 'password': 'pass'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error']['code'], 'INSUFFICIENT_PRIVILEGES')
        mock_audit.create_entry.assert_called_once()
        call_kwargs = mock_audit.create_entry.call_args[1]
        self.assertEqual(call_kwargs['action_type'], AuditActionType.USER_LOGIN)
        self.assertEqual(call_kwargs['details']['success'], False)
        self.assertEqual(call_kwargs['details']['reason'], 'insufficient_privileges')

    @override_settings(PORTAL_REQUIRED_GROUPS=['GRP-IDP-ADMIN'])
    @patch('idp_auth.views.portal_login.AuditService')
    @patch('idp_auth.views.portal_login.LDAPService')
    def test_partial_group_name_matches(self, mock_ldap_class, mock_audit):
        """AC2 : Matching substring — nom court correspond au DN complet."""
        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.return_value = (
            True,
            ['CN=GRP-IDP-ADMIN,OU=Groups,DC=example,DC=com'],
            'Alice Admin',
        )
        # Patch Profile pour ne pas lever NO_PROFILE
        with patch('idp_auth.views.portal_login.Profile') as mock_profile, \
             patch('idp_auth.views.portal_login.AuthService') as mock_auth_svc, \
             patch('idp_auth.views.portal_login.create_access_token', return_value='a'), \
             patch('idp_auth.views.portal_login.create_refresh_token', return_value='r'):
            mock_profile_obj = MagicMock()
            mock_profile_obj.name = 'ADMIN'
            mock_profile.objects.find_by_ad_groups.return_value = [mock_profile_obj]
            mock_user = MagicMock()
            mock_user.id = 1
            mock_user.username = 'aadmin'
            mock_user.profile = 'admin'
            mock_auth_svc.return_value.create_or_update_user.return_value = mock_user

            response = self.client.post(
                ENDPOINT,
                {'username': 'aadmin', 'password': 'pass'},
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(PORTAL_REQUIRED_GROUPS=['grp-idp-admin'])
    @patch('idp_auth.views.portal_login.AuditService')
    @patch('idp_auth.views.portal_login.LDAPService')
    def test_case_insensitive_match(self, mock_ldap_class, mock_audit):
        """AC2 : Matching insensible à la casse."""
        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.return_value = (
            True,
            ['CN=GRP-IDP-ADMIN,OU=Groups,DC=example,DC=com'],  # majuscules
            'Alice Admin',
        )
        with patch('idp_auth.views.portal_login.Profile') as mock_profile, \
             patch('idp_auth.views.portal_login.AuthService') as mock_auth_svc, \
             patch('idp_auth.views.portal_login.create_access_token', return_value='a'), \
             patch('idp_auth.views.portal_login.create_refresh_token', return_value='r'):
            mock_profile_obj = MagicMock()
            mock_profile_obj.name = 'ADMIN'
            mock_profile.objects.find_by_ad_groups.return_value = [mock_profile_obj]
            mock_user = MagicMock()
            mock_user.id = 2
            mock_user.username = 'aadmin'
            mock_user.profile = 'admin'
            mock_auth_svc.return_value.create_or_update_user.return_value = mock_user

            response = self.client.post(
                ENDPOINT,
                {'username': 'aadmin', 'password': 'pass'},
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(PORTAL_REQUIRED_GROUPS=['GRP-IDP-ADMIN', 'GRP-IDP-DBA'])
    @patch('idp_auth.views.portal_login.AuditService')
    @patch('idp_auth.views.portal_login.LDAPService')
    def test_one_matching_group_is_sufficient(self, mock_ldap_class, mock_audit):
        """AC2 : OR logic — un seul groupe correspondant suffit."""
        mock_ldap = mock_ldap_class.return_value
        mock_ldap.authenticate.return_value = (
            True,
            # Uniquement GRP-IDP-DBA, pas GRP-IDP-ADMIN
            ['CN=GRP-IDP-DBA,OU=Groups,DC=example,DC=com', 'CN=Domain Users,DC=example,DC=com'],
            'Bob DBA',
        )
        with patch('idp_auth.views.portal_login.Profile') as mock_profile, \
             patch('idp_auth.views.portal_login.AuthService') as mock_auth_svc, \
             patch('idp_auth.views.portal_login.create_access_token', return_value='a'), \
             patch('idp_auth.views.portal_login.create_refresh_token', return_value='r'):
            mock_profile_obj = MagicMock()
            mock_profile_obj.name = 'DBA'
            mock_profile.objects.find_by_ad_groups.return_value = [mock_profile_obj]
            mock_user = MagicMock()
            mock_user.id = 3
            mock_user.username = 'bdba'
            mock_user.profile = 'dba'
            mock_auth_svc.return_value.create_or_update_user.return_value = mock_user

            response = self.client.post(
                ENDPOINT,
                {'username': 'bdba', 'password': 'pass'},
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
