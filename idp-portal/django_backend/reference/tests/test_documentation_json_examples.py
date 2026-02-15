"""
Tests de validation des exemples JSON dans la documentation.
Story 29.3 - S'assure que les exemples dans les docs sont syntaxiquement corrects.
"""

import json

from django.test import TestCase


class TestDocumentationJSONExamples(TestCase):
    """Valide que les exemples JSON de la documentation sont syntaxiquement corrects."""

    def test_inventory_mapper_config_example(self):
        """Valide l'exemple de config InventoryMapper du guide de mapping."""
        example = """
{
  "entities": {
    "servers": {
      "table": "DBOPS_SERVERS",
      "id_column": "SERVER_ID",
      "columns": {
        "name": "HOSTNAME",
        "environment": "ENV",
        "engine_type": "ENGINE"
      }
    },
    "instances": {
      "table": "DBOPS_INSTANCES",
      "id_column": "INSTANCE_ID",
      "columns": {
        "name": "INSTANCE_NAME",
        "environment": "ENV",
        "server_ref": "SERVER_NAME"
      }
    },
    "databases": {
      "table": "DBOPS_DATABASES",
      "id_column": "DB_ID",
      "columns": {
        "name": "DB_NAME",
        "environment": "ENV"
      }
    }
  }
}
"""
        # Ne devrait pas lever d'exception
        config = json.loads(example)
        self.assertIn('entities', config)
        self.assertIn('servers', config['entities'])
        self.assertEqual(config['entities']['servers']['columns']['engine_type'], 'ENGINE')

    def test_rbac_filter_by_attribute_examples(self):
        """Valide les exemples de filter_by_attribute_json."""
        examples = [
            '{"engine_type": ["oracle", "sql_server"]}',
            '{"engine_type": ["oracle"], "zone": ["prod"]}',
            '{"engine_type": ["oracle"]}',
        ]
        for example in examples:
            # Ne devrait pas lever d'exception
            filter_dict = json.loads(example)
            self.assertIsInstance(filter_dict, dict)
            if 'engine_type' in filter_dict:
                self.assertIsInstance(filter_dict['engine_type'], list)

    def test_api_response_example(self):
        """Valide l'exemple de réponse API /api/v1/reference/engines."""
        example = """
[
  {"code": "Oracle", "label": "Oracle", "is_active": true, "normalized_code": "oracle"},
  {"code": "SQL Server", "label": "SQL Server", "is_active": true, "normalized_code": "sql_server"},
  {"code": "DB2", "label": "DB2", "is_active": true, "normalized_code": "db2"},
  {"code": "PostgreSQL", "label": "PostgreSQL", "is_active": true, "normalized_code": "postgresql"},
  {"code": "MySQL", "label": "MySQL", "is_active": true, "normalized_code": "mysql"},
  {"code": "Workflow", "label": "Workflow", "is_active": true, "normalized_code": "workflow"}
]
"""
        # Ne devrait pas lever d'exception
        engines = json.loads(example)
        self.assertIsInstance(engines, list)
        self.assertEqual(len(engines), 6)
        for engine in engines:
            self.assertIn('code', engine)
            self.assertIn('normalized_code', engine)
            # Vérifier que normalized_code est bien normalisé
            self.assertEqual(engine['normalized_code'], engine['code'].lower().replace(' ', '_'))
