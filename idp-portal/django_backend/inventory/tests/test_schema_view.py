"""
Tests for GET /api/v1/inventory/schema/ endpoint.
Story 62.3 — Available column concepts per inventory entity type.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from django.test import TestCase
from rest_framework.test import APIClient



class GetInventorySchemaViewTests(TestCase):
    """Tests for get_inventory_schema endpoint. Task 3."""

    SCHEMA_URL = '/api/v1/inventory/schema/'

    def setUp(self):
        self.client = APIClient()
        self.mock_user = MagicMock()
        self.mock_user.id = 1
        self.mock_user.is_authenticated = True

    def _authenticate(self):
        self.client.force_authenticate(user=self.mock_user)

    def _make_mock_mapper(self, entity_configs: dict, is_multi_table: bool = True) -> MagicMock:
        """Build a mapper mock with the given entity config mapping."""
        mock_mapper = MagicMock()
        mock_mapper.is_multi_table = is_multi_table
        mock_mapper.get_entity_config.side_effect = lambda t: entity_configs.get(t)
        return mock_mapper

    def _make_mock_service(self, mapper) -> MagicMock:
        mock_service = MagicMock()
        mock_service._get_inventory_mapper.return_value = mapper
        return mock_service

    # --- Task 3.1 — AC1: multi-table mapper with enriched columns ---

    @patch('inventory.views._inventory_service_factory')
    def test_returns_columns_from_config_multi_table(self, mock_factory):
        """AC1: mapper multi-table configuré avec colonnes enrichies → réponse correcte."""
        mock_mapper = self._make_mock_mapper({
            'servers': {'columns': {'name': 'HOSTNAME', 'environment': 'ENV', 'engine_type': 'ENGINE', 'region': 'REGION'}},
            'instances': {'columns': {'name': 'INST', 'server_ref': 'SRV_ID'}},
            'databases': {'columns': {'name': 'DB'}},
        })
        mock_factory.return_value = self._make_mock_service(mock_mapper)

        self._authenticate()
        response = self.client.get(self.SCHEMA_URL)

        self.assertEqual(response.status_code, 200)
        data = response.data

        # Servers: id first + config keys
        self.assertIn('servers', data)
        self.assertEqual(data['servers'][0], 'id', "'id' must be first for servers (AC1)")
        self.assertIn('id', data['servers'])
        self.assertIn('name', data['servers'])
        self.assertIn('environment', data['servers'])
        self.assertIn('engine_type', data['servers'])
        self.assertIn('region', data['servers'])

        # All three types present
        self.assertIn('instances', data)
        self.assertIn('databases', data)

    # --- Task 3.2 — AC2: mapper returns None → default columns, no 500 ---

    @patch('inventory.views._inventory_service_factory')
    def test_mapper_none_returns_default_columns(self, mock_factory):
        """AC2: _get_inventory_mapper() retourne None → HTTP 200 colonnes par défaut."""
        mock_service = MagicMock()
        mock_service._get_inventory_mapper.return_value = None
        mock_factory.return_value = mock_service

        self._authenticate()
        response = self.client.get(self.SCHEMA_URL)

        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data['servers'], ['id', 'name'])
        self.assertEqual(data['instances'], ['id', 'name'])
        self.assertEqual(data['databases'], ['id', 'name'])

    # --- Task 3.3 — AC2 bis: flat_table mapper → default columns for all types ---

    @patch('inventory.views._inventory_service_factory')
    def test_flat_table_mapper_returns_default_columns(self, mock_factory):
        """AC2 bis: mapper en mode flat_table → colonnes par défaut pour tous les types."""
        mock_mapper = MagicMock()
        mock_mapper.is_multi_table = False
        mock_factory.return_value = self._make_mock_service(mock_mapper)

        self._authenticate()
        response = self.client.get(self.SCHEMA_URL)

        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data['servers'], ['id', 'name'])
        self.assertEqual(data['instances'], ['id', 'name'])
        self.assertEqual(data['databases'], ['id', 'name'])

    # --- Task 3.4 — AC4: unauthenticated → 401 ---

    def test_unauthenticated_returns_401(self):
        """AC4: utilisateur non authentifié → HTTP 401."""
        response = self.client.get(self.SCHEMA_URL)
        self.assertEqual(response.status_code, 401)

    # --- Task 3.5 — AC5: databases not defined in config → fallback ["id", "name"] ---

    @patch('inventory.views._inventory_service_factory')
    def test_missing_entity_type_falls_back_to_defaults(self, mock_factory):
        """AC5: mapper sans databases défini → fallback ["id", "name"] pour databases."""
        mock_mapper = self._make_mock_mapper({
            'servers': {'columns': {'name': 'HOSTNAME', 'environment': 'ENV'}},
            'instances': {'columns': {'name': 'INST', 'server_ref': 'SRV'}},
            # databases not defined → returns None from get_entity_config
        })
        mock_factory.return_value = self._make_mock_service(mock_mapper)

        self._authenticate()
        response = self.client.get(self.SCHEMA_URL)

        self.assertEqual(response.status_code, 200)
        data = response.data

        # Real columns for servers and instances
        self.assertIn('name', data['servers'])
        self.assertIn('environment', data['servers'])
        self.assertIn('name', data['instances'])
        self.assertIn('server_ref', data['instances'])

        # Fallback for databases
        self.assertEqual(data['databases'], ['id', 'name'])

    # --- Task 3.6 — AC1: id always first, even if absent from config columns ---

    @patch('inventory.views._inventory_service_factory')
    def test_id_always_first_even_if_absent_from_config(self, mock_factory):
        """AC1: id toujours présent en premier, même si absent des colonnes config."""
        mock_mapper = self._make_mock_mapper({
            'servers': {'columns': {'name': 'HOSTNAME', 'region': 'REGION'}},
            'instances': {'columns': {'name': 'INST'}},
            'databases': {'columns': {'name': 'DB'}},
        })
        mock_factory.return_value = self._make_mock_service(mock_mapper)

        self._authenticate()
        response = self.client.get(self.SCHEMA_URL)

        self.assertEqual(response.status_code, 200)
        data = response.data

        # id present and first for all entity types
        for entity_type in ('servers', 'instances', 'databases'):
            self.assertIn(entity_type, data)
            columns = data[entity_type]
            self.assertIn('id', columns)
            self.assertEqual(columns[0], 'id', f"'id' should be first for {entity_type}")

    # --- Task 3.x — InventoryServiceError → 503 (cohérence avec les autres vues) ---

    @patch('inventory.views._inventory_service_factory')
    def test_inventory_service_error_returns_503(self, mock_factory):
        """Service error → HTTP 503 (gestion d'erreur cohérente avec list_environments, etc.)."""
        from inventory.services import InventoryServiceError
        mock_service = MagicMock()
        mock_service._get_inventory_mapper.side_effect = InventoryServiceError("DB unavailable")
        mock_factory.return_value = mock_service

        self._authenticate()
        response = self.client.get(self.SCHEMA_URL)

        self.assertEqual(response.status_code, 503)

    # --- Additional: response structure validation ---

    @patch('inventory.views._inventory_service_factory')
    def test_response_contains_all_three_entity_types(self, mock_factory):
        """AC5: réponse inclut toujours servers, instances, databases."""
        mock_service = MagicMock()
        mock_service._get_inventory_mapper.return_value = None
        mock_factory.return_value = mock_service

        self._authenticate()
        response = self.client.get(self.SCHEMA_URL)

        self.assertEqual(response.status_code, 200)
        data = response.data
        for entity_type in ('servers', 'instances', 'databases'):
            self.assertIn(entity_type, data)
            self.assertIsInstance(data[entity_type], list)
