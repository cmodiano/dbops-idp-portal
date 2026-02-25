from unittest.mock import MagicMock

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group, User as AuthUser
from django.test import TestCase

from idp_auth.admin import APIKeyAdmin, CustomGroupAdmin, CustomUserAdmin, IDPUserAdmin
from idp_auth.models import APIKey
from idp_auth.models import User as IDPUser


class TestCustomUserAdmin(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.admin = CustomUserAdmin(AuthUser, self.site)

    def test_list_display(self):
        self.assertEqual(
            self.admin.list_display,
            ('username', 'email', 'is_staff', 'is_active', 'date_joined'),
        )

    def test_list_filter(self):
        self.assertIn('is_staff', self.admin.list_filter)
        self.assertIn('is_active', self.admin.list_filter)

    def test_search_fields(self):
        self.assertIn('username', self.admin.search_fields)
        self.assertIn('email', self.admin.search_fields)


class TestCustomGroupAdmin(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.admin = CustomGroupAdmin(Group, self.site)

    def test_list_display(self):
        self.assertIn('name', self.admin.list_display)

    def test_search_fields(self):
        self.assertIn('name', self.admin.search_fields)


class TestIDPUserAdmin(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.admin = IDPUserAdmin(IDPUser, self.site)

    def test_list_display(self):
        for field in ('username', 'display_name', 'profile', 'created_at'):
            self.assertIn(field, self.admin.list_display)

    def test_list_filter(self):
        self.assertIn('profile', self.admin.list_filter)

    def test_search_fields(self):
        self.assertIn('username', self.admin.search_fields)
        self.assertIn('display_name', self.admin.search_fields)

    def test_has_add_permission_false(self):
        request = MagicMock()
        self.assertFalse(self.admin.has_add_permission(request))

    def test_has_delete_permission_false(self):
        request = MagicMock()
        self.assertFalse(self.admin.has_delete_permission(request))

    def test_has_delete_permission_false_with_obj(self):
        request = MagicMock()
        obj = MagicMock()
        self.assertFalse(self.admin.has_delete_permission(request, obj))


class TestAPIKeyAdminListFilter(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.admin = APIKeyAdmin(APIKey, self.site)

    def test_list_filter_includes_user(self):
        self.assertIn('user', self.admin.list_filter)

    def test_list_filter_preserves_existing(self):
        self.assertIn('is_active', self.admin.list_filter)
        self.assertIn('scope', self.admin.list_filter)
