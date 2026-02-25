from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from idp_auth.models import APIKey, User


@pytest.mark.django_db
class TestRevokeApiKeyCommand(TestCase):

    def setUp(self):
        self.user = User.objects.create(
            username='dbops_user',
            display_name='DBOPS User',
            profile='dba_applicatif',
        )
        self.instance, _ = APIKey.objects.create_key(user=self.user, name='Test Key')

    def test_revoke_by_id_success(self):
        out = StringIO()
        call_command('revoke_api_key', f'--id={self.instance.pk}', stdout=out)
        self.instance.refresh_from_db()
        self.assertFalse(self.instance.is_active)
        self.assertIn('révoquée', out.getvalue())

    def test_revoke_by_name_and_user_success(self):
        out = StringIO()
        call_command('revoke_api_key', '--name=Test Key', '--user=dbops_user', stdout=out)
        self.instance.refresh_from_db()
        self.assertFalse(self.instance.is_active)
        self.assertIn('révoquée', out.getvalue())

    def test_revoke_by_name_only_success(self):
        out = StringIO()
        call_command('revoke_api_key', '--name=Test Key', stdout=out)
        self.instance.refresh_from_db()
        self.assertFalse(self.instance.is_active)

    def test_revoke_not_found_fails(self):
        with self.assertRaises(CommandError) as ctx:
            call_command('revoke_api_key', '--id=999999')
        self.assertIn('introuvable', str(ctx.exception))

    def test_revoke_no_args_fails(self):
        with self.assertRaises(CommandError) as ctx:
            call_command('revoke_api_key')
        self.assertIn('--id', str(ctx.exception))

    def test_revoke_already_revoked_warns(self):
        self.instance.is_active = False
        self.instance.save()
        out = StringIO()
        call_command('revoke_api_key', f'--id={self.instance.pk}', stdout=out)
        self.assertIn('déjà révoquée', out.getvalue())

    def test_revoke_multiple_matches_without_user_fails(self):
        # Créer une seconde clé avec le même nom
        APIKey.objects.create_key(user=self.user, name='Test Key')
        with self.assertRaises(CommandError) as ctx:
            call_command('revoke_api_key', '--name=Test Key')
        self.assertIn('Plusieurs', str(ctx.exception))
