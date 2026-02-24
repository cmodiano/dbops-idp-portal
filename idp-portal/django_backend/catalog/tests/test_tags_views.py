"""
Tests for tags API endpoints (DRF ViewSets).
Tests: GET /tags, GET /catalog/tags
Story 39.3: cache hit, category filter, RBAC branches (AC#2).
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch

from catalog.models import Tag, ActionTag, ActionStatus, ActionItemType, ActionEngine, ActionPlatform
from catalog.services import CatalogService
from catalog.views._shared import _tags_cache
from tests.factories import UserFactory


@pytest.mark.django_db
class TestTagViewSet(TestCase):
    """Tests for TagViewSet (tags endpoints)."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        # Vider le cache pour éviter les effets de bord entre tests
        _tags_cache.clear()

        # Create user
        self.user = UserFactory(
            username='testuser',
            profile='dba'
        )

        # Create tags
        self.tag1 = Tag.objects.create(name='oracle')
        self.tag2 = Tag.objects.create(name='database')
        self.tag3 = Tag.objects.create(name='patching')

        # Create action as DRAFT then publish (valid transition: draft → published)
        self.service = CatalogService()
        self.action_data = {
            'name': 'Test Action',
            'description': 'Test Description',
            'engine': ActionEngine.ORACLE,
            'platform': ActionPlatform.AAP,
            'status': ActionStatus.DRAFT,
            'item_type': ActionItemType.ACTION,
        }
        self.action = self.service.create_action(self.action_data, self.user)
        self.service.update_status(self.action.id, 'publish', self.user)

        # Add tags to action
        ActionTag.objects.create(action=self.action, tag=self.tag1)
        ActionTag.objects.create(action=self.action, tag=self.tag2)

    def test_list_tags_public(self):
        """Test GET /tags is public (no authentication required)."""
        response = self.client.get('/api/v1/tags/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIsInstance(response.data['data'], list)
        # Should return all tags
        tag_names = [tag['name'] for tag in response.data['data']]
        self.assertIn('oracle', tag_names)
        self.assertIn('database', tag_names)
        self.assertIn('patching', tag_names)

    def test_list_tags_format(self):
        """Test GET /tags returns correct format."""
        response = self.client.get('/api/v1/tags/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        # Each tag should have id, name, created_at
        for tag in response.data['data']:
            self.assertIn('id', tag)
            self.assertIn('name', tag)
            self.assertIn('created_at', tag)

    def test_list_catalog_tags_public(self):
        """Test GET /catalog/tags is public (no authentication required)."""
        response = self.client.get('/api/v1/catalog/tags/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIsInstance(response.data['data'], list)

    def test_list_catalog_tags_format(self):
        """Test GET /catalog/tags returns correct format."""
        response = self.client.get('/api/v1/catalog/tags/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        # Each tag should have name and action_count
        for tag in response.data['data']:
            self.assertIn('name', tag)

    # -----------------------------------------------------------------------
    # Story 39.3 — branches manquantes (AC#2)
    # -----------------------------------------------------------------------

    def test_list_catalog_tags_cache_hit(self):
        """2.1: Second call returns cached response (cache hit branch)."""
        _tags_cache.clear()
        # Premier appel → populate le cache
        self.client.get('/api/v1/catalog/tags/')
        # Injecter une valeur distincte dans le cache.
        # Le format de clé est défini dans tags_views.py:
        #   f"tags_user_{user_id}_cat_{category or 'all'}"
        # Pour un appel anonyme sans category : "tags_user_None_cat_all"
        # Si ce format change, ce test doit être mis à jour.
        cache_key = "tags_user_None_cat_all"
        _tags_cache[cache_key] = [{"id": 999, "name": "cached-tag", "action_count": 42}]
        # Deuxième appel → doit retourner la valeur du cache
        response = self.client.get('/api/v1/catalog/tags/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [t["name"] for t in response.data["data"]]
        self.assertIn("cached-tag", names)

    def test_list_catalog_tags_with_category_filter(self):
        """2.2: ?category=oracle filtre les tags sur les actions ayant ce tag."""
        _tags_cache.clear()
        # Créer une deuxième action PUBLIÉE avec seulement le tag 'patching' (sans oracle).
        # Ceci rend l'assertion assertNotIn('patching') non-vacuoire : sans filtre,
        # 'patching' apparaîtrait ; avec ?category=oracle il doit être exclu.
        user2 = UserFactory(username='testuser_cat_filter', profile='dba')
        action2_data = {
            'name': 'Action Patching Only',
            'description': 'Action sans tag oracle',
            'engine': ActionEngine.ORACLE,
            'platform': ActionPlatform.AAP,
            'status': ActionStatus.DRAFT,
            'item_type': ActionItemType.ACTION,
        }
        action2 = self.service.create_action(action2_data, user2)
        self.service.update_status(action2.id, 'publish', user2)
        ActionTag.objects.create(action=action2, tag=self.tag3)  # tag3 = 'patching'
        _tags_cache.clear()

        response = self.client.get('/api/v1/catalog/tags/?category=oracle')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        names = [t["name"] for t in response.data["data"]]
        # Tags de l'action oracle (oracle + database) apparaissent
        self.assertIn('oracle', names)
        self.assertIn('database', names)
        # 'patching' est uniquement sur action2 (sans tag oracle) → exclu par le filtre
        self.assertNotIn('patching', names)

    def test_list_catalog_tags_category_tout_no_filter(self):
        """2.3: ?category=tout n'applique pas le filtre de catégorie."""
        _tags_cache.clear()
        # Référence : appel sans paramètre de catégorie
        response_no_cat = self.client.get('/api/v1/catalog/tags/')
        self.assertEqual(response_no_cat.status_code, status.HTTP_200_OK)
        names_no_cat = sorted([t["name"] for t in response_no_cat.data["data"]])
        _tags_cache.clear()

        response = self.client.get('/api/v1/catalog/tags/?category=tout')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = sorted([t["name"] for t in response.data["data"]])
        # ?category=tout doit retourner exactement les mêmes tags qu'un appel sans filtre
        self.assertEqual(names, names_no_cat)

    def test_list_catalog_tags_category_all_no_filter(self):
        """2.3b: ?category=all n'applique pas le filtre de catégorie."""
        _tags_cache.clear()
        response = self.client.get('/api/v1/catalog/tags/?category=all')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [t["name"] for t in response.data["data"]]
        self.assertIn('oracle', names)

    def test_list_catalog_tags_rbac_actions_type_all(self):
        """2.4: RBAC actions_type='all' → pas de filtrage sur IDs."""
        _tags_cache.clear()
        self.client.force_authenticate(user=self.user)
        permissions = {
            'actions_type': 'all',
            'action_ids': [],
            'tag_patterns': [],
        }
        with patch('catalog.views.tags_views.CatalogRBACService.get_permissions', return_value=permissions):
            response = self.client.get('/api/v1/catalog/tags/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [t["name"] for t in response.data["data"]]
        self.assertIn('oracle', names)
        self.assertIn('database', names)

    def test_list_catalog_tags_rbac_with_action_ids(self):
        """2.5: RBAC restrictif avec action_ids seuls → filtre les actions visibles."""
        _tags_cache.clear()
        self.client.force_authenticate(user=self.user)
        permissions = {
            'actions_type': 'restricted',
            'action_ids': [self.action.id],
            'tag_patterns': [],
        }
        with patch('catalog.views.tags_views.CatalogRBACService.get_permissions', return_value=permissions):
            response = self.client.get('/api/v1/catalog/tags/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [t["name"] for t in response.data["data"]]
        # L'action est visible → ses tags apparaissent
        self.assertIn('oracle', names)
        self.assertIn('database', names)

    def test_list_catalog_tags_rbac_with_tag_patterns(self):
        """2.6: RBAC avec tag_patterns → récupère les IDs d'actions correspondantes."""
        _tags_cache.clear()
        self.client.force_authenticate(user=self.user)
        permissions = {
            'actions_type': 'restricted',
            'action_ids': [],
            'tag_patterns': ['oracle'],
        }
        with patch('catalog.views.tags_views.CatalogRBACService.get_permissions', return_value=permissions):
            response = self.client.get('/api/v1/catalog/tags/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # L'action tagged 'oracle' est incluse via tag_patterns
        names = [t["name"] for t in response.data["data"]]
        self.assertIn('oracle', names)

    def test_list_catalog_tags_unauthenticated(self):
        """2.7: Utilisateur non authentifié → tags des actions publiées sans filtre RBAC."""
        _tags_cache.clear()
        # Pas d'authentification → get_permissions retourne None
        response = self.client.get('/api/v1/catalog/tags/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [t["name"] for t in response.data["data"]]
        self.assertIn('oracle', names)
        self.assertIn('database', names)

    def test_list_catalog_tags_action_count(self):
        """2.8: Chaque tag inclut un action_count correct."""
        _tags_cache.clear()
        response = self.client.get('/api/v1/catalog/tags/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tags_data = response.data["data"]
        oracle_tag = next((t for t in tags_data if t["name"] == "oracle"), None)
        self.assertIsNotNone(oracle_tag)
        self.assertIn("action_count", oracle_tag)
        self.assertEqual(oracle_tag["action_count"], 1)

    def test_list_catalog_tags_rbac_no_access(self):
        """RBAC restrictif sans action_ids ni tag_patterns → aucun tag visible."""
        _tags_cache.clear()
        self.client.force_authenticate(user=self.user)
        permissions = {
            'actions_type': 'restricted',
            'action_ids': [],
            'tag_patterns': [],
        }
        with patch('catalog.views.tags_views.CatalogRBACService.get_permissions', return_value=permissions):
            response = self.client.get('/api/v1/catalog/tags/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Aucune action visible → aucun tag
        self.assertEqual(response.data["data"], [])
