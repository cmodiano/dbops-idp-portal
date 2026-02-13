"""
Tests for InventoryMapper.get_available_concepts().
Story 23.4 - AC5, AC8: Tests for concept key retrieval.
"""

from django.test import TestCase
from unittest.mock import patch
from inventory.mapper import InventoryMapper


MULTI_TABLE_CONFIG = {
    "entities": {
        "servers": {
            "table": "DBOPS_SERVERS",
            "id_column": "SERVER_ID",
            "columns": {
                "name": "HOSTNAME",
                "environment": "ENV",
                "engine_type": "ENGINE",
                "zone": "ZONE",
            }
        },
        "instances": {
            "table": "DBOPS_INSTANCES",
            "id_column": "INSTANCE_ID",
            "columns": {
                "name": "INSTANCE_NAME",
                "environment": "ENV",
                "server_ref": "SERVER_NAME",
            }
        },
        "databases": {
            "table": "DBOPS_DATABASES",
            "id_column": "DB_ID",
            "columns": {
                "name": "DB_NAME",
                "environment": "ENV",
            }
        }
    }
}


class TestGetAvailableConcepts(TestCase):
    """Tests for InventoryMapper.get_available_concepts static method."""

    @patch('inventory.services.InventoryService')
    def test_returns_server_concepts_with_multi_table_config(self, MockService):
        """Multi-table config → returns server concept keys."""
        mock_service = MockService.return_value
        mock_mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        mock_service._get_inventory_mapper.return_value = mock_mapper

        result = InventoryMapper.get_available_concepts('servers')
        self.assertIn('name', result)
        self.assertIn('environment', result)
        self.assertIn('engine_type', result)
        self.assertIn('zone', result)
        self.assertEqual(len(result), 4)

    @patch('inventory.services.InventoryService')
    def test_returns_instance_concepts(self, MockService):
        """Multi-table config → returns instance concept keys."""
        mock_service = MockService.return_value
        mock_mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        mock_service._get_inventory_mapper.return_value = mock_mapper

        result = InventoryMapper.get_available_concepts('instances')
        self.assertIn('name', result)
        self.assertIn('environment', result)
        self.assertIn('server_ref', result)

    @patch('inventory.services.InventoryService')
    def test_returns_fallback_when_no_config(self, MockService):
        """No multi-table config → returns fallback concepts."""
        mock_service = MockService.return_value
        mock_service._get_inventory_mapper.return_value = None

        result = InventoryMapper.get_available_concepts('servers')
        self.assertEqual(result, ['name', 'environment', 'type'])

    @patch('inventory.services.InventoryService')
    def test_returns_fallback_when_flat_table_only(self, MockService):
        """Flat table config only → returns fallback concepts."""
        mock_service = MockService.return_value
        flat_config = {"flat_table": {"table": "DBOPS_INVENTORY", "columns": {"name": "NAME"}}}
        mock_mapper = InventoryMapper(flat_config)
        mock_service._get_inventory_mapper.return_value = mock_mapper

        result = InventoryMapper.get_available_concepts('servers')
        self.assertEqual(result, ['name', 'environment', 'type'])

    @patch('inventory.services.InventoryService')
    def test_returns_fallback_for_unknown_entity(self, MockService):
        """Unknown entity → returns fallback concepts."""
        mock_service = MockService.return_value
        mock_mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        mock_service._get_inventory_mapper.return_value = mock_mapper

        result = InventoryMapper.get_available_concepts('unknown_entity')
        self.assertEqual(result, ['name', 'environment', 'type'])

    @patch('inventory.services.InventoryService')
    def test_default_entity_is_servers(self, MockService):
        """Default entity_name parameter is 'servers'."""
        mock_service = MockService.return_value
        mock_mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        mock_service._get_inventory_mapper.return_value = mock_mapper

        result = InventoryMapper.get_available_concepts()
        self.assertIn('engine_type', result)
