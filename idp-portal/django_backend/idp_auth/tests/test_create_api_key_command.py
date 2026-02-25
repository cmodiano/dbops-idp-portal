from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from idp_auth.models import APIKey, User


@pytest.mark.django_db
class TestCreateApiKeyCommand(TestCase):

    def setUp(self):
        self.user = User.objects.create(
            username='dbops_user',
            display_name='DBOPS User',
            profile='dba_applicatif',
        )

    def test_create_key_success(self):
        out = StringIO()
        captured = []
        original_create_key = APIKey.objects.create_key

        def capturing_create_key(*args, **kwargs):
            instance, raw_key = original_create_key(*args, **kwargs)
            captured.append(raw_key)
            return instance, raw_key

        with patch.object(APIKey.objects, 'create_key', side_effect=capturing_create_key):
            call_command('create_api_key', '--user=dbops_user', '--name=CI-CD Test', stdout=out)

        output = out.getvalue()
        key = APIKey.objects.get(user=self.user, name='CI-CD Test')
        self.assertIsNotNone(key)
        self.assertTrue(key.is_active)
        # stdout doit contenir le nom de la clé, le séparateur et la raw_key elle-même (AC2)
        self.assertIn('CI-CD Test', output)
        self.assertIn('=' * 60, output)
        self.assertIn('⚠️', output)
        self.assertEqual(len(captured), 1)
        self.assertIn(captured[0], output)

    def test_create_key_unknown_user_fails(self):
        with self.assertRaises(CommandError) as ctx:
            call_command('create_api_key', '--user=inconnu', '--name=Test')
        self.assertIn('inconnu', str(ctx.exception))

    def test_create_key_with_scope(self):
        out = StringIO()
        call_command('create_api_key', '--user=dbops_user', '--name=Catalog Key', '--scope=catalog', stdout=out)
        key = APIKey.objects.get(user=self.user, name='Catalog Key')
        self.assertEqual(key.scope, 'catalog')

    def test_create_key_with_expires(self):
        out = StringIO()
        before = timezone.now()
        call_command(
            'create_api_key',
            '--user=dbops_user',
            '--name=Expiring Key',
            '--expires-in-days=30',
            stdout=out,
        )
        after = timezone.now()
        key = APIKey.objects.get(user=self.user, name='Expiring Key')
        self.assertIsNotNone(key.expires_at)
        expected_min = before + timedelta(days=30)
        expected_max = after + timedelta(days=30)
        self.assertGreaterEqual(key.expires_at, expected_min)
        self.assertLessEqual(key.expires_at, expected_max)

    def test_create_key_invalid_scope_fails(self):
        # Django enveloppe ArgumentError d'argparse dans CommandError
        with self.assertRaises(CommandError):
            call_command('create_api_key', '--user=dbops_user', '--name=Test', '--scope=invalid')

    def test_create_key_negative_expires_fails(self):
        with self.assertRaises(CommandError) as ctx:
            call_command('create_api_key', '--user=dbops_user', '--name=Test', '--expires-in-days=-1')
        self.assertIn('positif', str(ctx.exception))
