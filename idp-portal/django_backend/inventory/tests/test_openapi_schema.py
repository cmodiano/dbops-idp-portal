"""
Tests pour vérifier que les endpoints inventaire sont exclus du schéma OpenAPI.
Story 44.3 - Marquer API inventaire comme privée.
"""

from django.test import TestCase
from drf_spectacular.generators import SchemaGenerator


class TestInventoryOpenAPIExclusion(TestCase):
    """Vérifie que les endpoints inventory sont exclus du schéma OpenAPI public."""

    @classmethod
    def setUpClass(cls):
        """Génère le schéma OpenAPI une seule fois pour tous les tests de la classe."""
        super().setUpClass()
        generator = SchemaGenerator()
        schema = generator.get_schema(request=None, public=True)
        cls.schema_paths = set(schema.get('paths', {}).keys())

    def test_inventory_paths_excluded_from_schema(self):
        """Aucun path /inventory/ ne doit apparaître dans le schéma OpenAPI."""
        inventory_paths = [p for p in self.schema_paths if '/inventory/' in p]
        self.assertFalse(
            inventory_paths,
            f"Des paths inventory ont été trouvés dans le schéma public : {inventory_paths}"
        )

    def test_inventory_targets_not_in_schema(self):
        """/inventory/targets/ absent du schéma (SCHEMA_PATH_PREFIX=/api/v1 est strippé)."""
        self.assertNotIn('/inventory/targets/', self.schema_paths)

    def test_inventory_targets_all_not_in_schema(self):
        """/inventory/targets/all/ absent du schéma."""
        self.assertNotIn('/inventory/targets/all/', self.schema_paths)

    def test_inventory_environments_not_in_schema(self):
        """/inventory/environments/ absent du schéma."""
        self.assertNotIn('/inventory/environments/', self.schema_paths)

    def test_inventory_servers_not_in_schema(self):
        """/inventory/servers/ absent du schéma."""
        self.assertNotIn('/inventory/servers/', self.schema_paths)

    def test_inventory_instances_not_in_schema(self):
        """/inventory/instances/ absent du schéma."""
        self.assertNotIn('/inventory/instances/', self.schema_paths)

    def test_inventory_databases_not_in_schema(self):
        """/inventory/databases/ absent du schéma."""
        self.assertNotIn('/inventory/databases/', self.schema_paths)
