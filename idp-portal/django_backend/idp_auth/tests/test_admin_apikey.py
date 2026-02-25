from unittest.mock import MagicMock, patch

import pytest
from django.contrib import messages
from django.contrib.admin.sites import AdminSite
from django.test import TestCase

from idp_auth.admin import APIKeyAdmin, CreateAPIKeyForm
from idp_auth.models import APIKey, User


@pytest.mark.django_db
class TestAPIKeyAdmin(TestCase):

    def setUp(self):
        self.site = AdminSite()
        self.admin = APIKeyAdmin(APIKey, self.site)
        self.user = User.objects.create(
            username='dbops_user',
            display_name='DBOPS User',
            profile='dba_applicatif',
        )

    def _make_request(self):
        request = MagicMock()
        request._messages = MagicMock()
        return request

    def test_has_add_permission_returns_true(self):
        request = self._make_request()
        self.assertTrue(self.admin.has_add_permission(request))

    def test_get_form_returns_create_form_for_new_object(self):
        request = self._make_request()
        form_class = self.admin.get_form(request, obj=None)
        # Django wraps via modelform_factory, so check issubclass rather than identity
        self.assertTrue(issubclass(form_class, CreateAPIKeyForm))

    def test_get_form_returns_default_form_for_existing_object(self):
        request = self._make_request()
        instance, _ = APIKey.objects.create_key(user=self.user, name='Existing Key')
        form_class = self.admin.get_form(request, obj=instance)
        self.assertIsNot(form_class, CreateAPIKeyForm)

    def test_admin_create_key_displays_raw_key(self):
        request = self._make_request()
        # Simuler un objet partiellement rempli (comme le form l'aurait fourni)
        obj = MagicMock()
        obj.user = self.user
        obj.name = 'Admin Created Key'
        obj.scope = 'executions'
        obj.expires_at = None

        fake_instance = MagicMock()
        fake_instance.id = 42
        fake_instance.expires_at = None
        raw_key = 'fake_raw_key_abc123'

        with patch.object(APIKey.objects, 'create_key', return_value=(fake_instance, raw_key)) as mock_create:
            with patch.object(self.admin, 'message_user') as mock_msg:
                self.admin.save_model(request, obj, form=MagicMock(), change=False)

        mock_create.assert_called_once_with(user=self.user, name='Admin Created Key', scope='executions')
        mock_msg.assert_called_once()
        call_args = mock_msg.call_args
        # Le message doit contenir la raw_key
        self.assertIn(raw_key, call_args[0][1])
        # Le niveau doit être SUCCESS
        self.assertEqual(call_args[0][2], messages.SUCCESS)

    def test_admin_create_key_with_expires_at(self):
        from datetime import datetime, timezone as dt_tz
        request = self._make_request()
        obj = MagicMock()
        obj.user = self.user
        obj.name = 'Expiring Admin Key'
        obj.scope = None
        expires = datetime(2027, 1, 1, tzinfo=dt_tz.utc)
        obj.expires_at = expires

        fake_instance = MagicMock()
        fake_instance.id = 99
        fake_instance.expires_at = None
        raw_key = 'another_raw_key'

        with patch.object(APIKey.objects, 'create_key', return_value=(fake_instance, raw_key)):
            with patch.object(self.admin, 'message_user'):
                self.admin.save_model(request, obj, form=MagicMock(), change=False)

        # expires_at doit être assigné et save appelé
        self.assertEqual(fake_instance.expires_at, expires)
        fake_instance.save.assert_called_once_with(update_fields=['expires_at', 'updated_at'])

    def test_admin_save_model_edit_calls_super(self):
        request = self._make_request()
        instance, _ = APIKey.objects.create_key(user=self.user, name='Edit Test Key')

        with patch('django.contrib.admin.ModelAdmin.save_model') as mock_super:
            self.admin.save_model(request, instance, form=MagicMock(), change=True)

        mock_super.assert_called_once()

    def test_admin_revoke_action(self):
        instance1, _ = APIKey.objects.create_key(user=self.user, name='Key 1')
        instance2, _ = APIKey.objects.create_key(user=self.user, name='Key 2')

        request = self._make_request()
        queryset = APIKey.objects.filter(pk__in=[instance1.pk, instance2.pk])

        with patch.object(self.admin, 'message_user') as mock_msg:
            self.admin.revoke_api_keys(request, queryset)

        instance1.refresh_from_db()
        instance2.refresh_from_db()
        self.assertFalse(instance1.is_active)
        self.assertFalse(instance2.is_active)

        mock_msg.assert_called_once()
        call_args = mock_msg.call_args
        self.assertIn('2', call_args[0][1])
        self.assertEqual(call_args[0][2], messages.SUCCESS)
