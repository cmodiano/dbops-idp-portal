import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from django.test import TestCase

from idp_auth.models import APIKey, User, _hash_key


@pytest.mark.django_db
class APIKeyModelTest(TestCase):

    def _make_user(self, username='testuser'):
        return User.objects.create(username=username, profile='DBA')

    def test_create_key_hashes_raw_key(self):
        user = self._make_user()
        instance, raw_key = APIKey.objects.create_key(user=user, name='my-key')
        expected_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        self.assertEqual(instance.key_hash, expected_hash)
        self.assertNotEqual(raw_key, instance.key_hash)

    def test_create_key_returns_raw_key_once(self):
        user = self._make_user()
        instance, raw_key = APIKey.objects.create_key(user=user, name='my-key')
        self.assertIsNotNone(raw_key)
        self.assertGreater(len(raw_key), 0)
        # raw_key must NOT be stored on the instance
        self.assertFalse(hasattr(instance, 'raw_key'))
        # key_hash must differ from raw_key
        self.assertNotEqual(raw_key, instance.key_hash)

    def test_verify_key_active(self):
        user = self._make_user()
        instance, raw_key = APIKey.objects.create_key(user=user, name='active-key')
        found = APIKey.objects.verify_key(raw_key)
        self.assertIsNotNone(found)
        self.assertEqual(found.pk, instance.pk)

    def test_verify_key_wrong_key(self):
        user = self._make_user()
        APIKey.objects.create_key(user=user, name='some-key')
        found = APIKey.objects.verify_key('this-is-definitely-wrong')
        self.assertIsNone(found)

    def test_verify_key_inactive(self):
        user = self._make_user()
        instance, raw_key = APIKey.objects.create_key(user=user, name='inactive-key')
        instance.is_active = False
        instance.save()
        found = APIKey.objects.verify_key(raw_key)
        self.assertIsNone(found)

    def test_verify_key_expired(self):
        user = self._make_user()
        instance, raw_key = APIKey.objects.create_key(user=user, name='expired-key')
        instance.expires_at = datetime.now(tz=timezone.utc) - timedelta(days=1)
        instance.save()
        found = APIKey.objects.verify_key(raw_key)
        self.assertIsNone(found)

    def test_verify_key_not_yet_expired(self):
        user = self._make_user()
        instance, raw_key = APIKey.objects.create_key(user=user, name='future-key')
        instance.expires_at = datetime.now(tz=timezone.utc) + timedelta(days=30)
        instance.save()
        found = APIKey.objects.verify_key(raw_key)
        self.assertIsNotNone(found)

    def test_key_hash_length(self):
        user = self._make_user()
        instance, _ = APIKey.objects.create_key(user=user, name='hash-len-test')
        self.assertEqual(len(instance.key_hash), 64)

    def test_hash_key_helper(self):
        result = _hash_key('test-value')
        expected = hashlib.sha256('test-value'.encode('utf-8')).hexdigest()
        self.assertEqual(result, expected)

    def test_create_key_invalid_scope_raises(self):
        user = self._make_user()
        with self.assertRaises(ValueError):
            APIKey.objects.create_key(user=user, name='bad-scope-key', scope='invalid_scope')

    def test_create_key_valid_scope_accepted(self):
        user = self._make_user()
        for scope in ('executions', 'catalog', 'full'):
            instance, _ = APIKey.objects.create_key(user=user, name=f'key-{scope}', scope=scope)
            self.assertEqual(instance.scope, scope)
