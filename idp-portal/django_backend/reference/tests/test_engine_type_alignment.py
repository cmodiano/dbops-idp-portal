"""
Tests de cohérence engine_type ↔ REF_ENGINES.
Story 29.3 — Valide l'alignement entre REF_ENGINES et les valeurs engine_type
utilisées dans les tests d'inventaire et les filtres RBAC.

Ces tests sont informatifs (documentent l'état de cohérence) et non bloquants.
Les écarts sont signalés comme WARNINGS, pas comme erreurs.
"""

import warnings
import structlog

from django.test import TestCase

from reference.models import RefEngine

logger = structlog.get_logger(__name__)


def normalize_engine_code(ref_engine_code: str) -> str:
    """Convertit REF_ENGINES.CODE → engine_type normalisé (minuscules + underscores)."""
    normalized = ref_engine_code.lower().replace(' ', '_')
    logger.debug(
        "normalize_engine_code",
        original=ref_engine_code,
        normalized=normalized,
    )
    return normalized


# Valeurs engine_type utilisées dans les tests d'inventaire existants
# Source: inventory/tests/test_rbac_filter_by_attribute.py
# NOTE: 'sqlserver' devrait être 'sql_server' selon convention, mais fonctionne grâce au matching case-insensitive
INVENTORY_TEST_ENGINE_TYPES = ['oracle', 'sql_server', 'mysql']

# Valeurs engine_type utilisées dans les exemples filter_by_attribute_json RBAC
# Source: inventory/tests/test_rbac_filter_by_attribute.py, docs/rbac-filter-by-attribute.md
RBAC_FILTER_ENGINE_TYPES = ['oracle', 'sql_server', 'postgresql']


class TestRefEnginesNormalizationMapping(TestCase):
    """Test: Charger REF_ENGINES actifs et générer normalized_codes attendus."""

    def test_ref_engines_normalization_mapping(self):
        """Documente le mapping REF_ENGINES.CODE → engine_type normalisé."""
        engines = RefEngine.objects.active().ordered()
        # Pré-calcul du mapping pour éviter appels répétés
        mapping = {e.code: normalize_engine_code(e.code) for e in engines}

        expected_mapping = {
            'Oracle': 'oracle',
            'SQL Server': 'sql_server',
            'DB2': 'db2',
            'PostgreSQL': 'postgresql',
            'MySQL': 'mysql',
            'Workflow': 'workflow',
        }

        for code, expected_normalized in expected_mapping.items():
            actual = mapping.get(code)
            if actual is None:
                warnings.warn(
                    f"REF_ENGINES code '{code}' non trouvé en base — "
                    f"vérifier que la migration V049 a été exécutée",
                    stacklevel=1,
                )
                continue
            self.assertEqual(
                actual, expected_normalized,
                f"Normalisation de '{code}' : attendu '{expected_normalized}', obtenu '{actual}'",
            )

    def test_normalize_engine_code_function(self):
        """Valide la fonction de normalisation sur tous les cas connus."""
        cases = [
            ('Oracle', 'oracle'),
            ('SQL Server', 'sql_server'),
            ('DB2', 'db2'),
            ('PostgreSQL', 'postgresql'),
            ('MySQL', 'mysql'),
            ('Workflow', 'workflow'),
        ]
        for code, expected in cases:
            self.assertEqual(
                normalize_engine_code(code), expected,
                f"normalize_engine_code('{code}') devrait retourner '{expected}'",
            )


class TestInventoryTestFixturesAlignment(TestCase):
    """Test: Valider que les exemples engine_type dans les tests inventaire correspondent."""

    def test_inventory_test_fixtures_use_normalized(self):
        """Vérifie que les valeurs engine_type dans les tests inventaire
        correspondent aux codes REF_ENGINES normalisés."""
        engines = RefEngine.objects.active()
        normalized_codes = {normalize_engine_code(e.code) for e in engines}

        for engine_type in INVENTORY_TEST_ENGINE_TYPES:
            if engine_type not in normalized_codes:
                warnings.warn(
                    f"engine_type '{engine_type}' non aligné. Attendus: {sorted(normalized_codes)}",
                    stacklevel=1,
                )


class TestRBACFilterExamplesAlignment(TestCase):
    """Test: Valider que les exemples filter_by_attribute_json RBAC correspondent."""

    def test_rbac_filter_examples_alignment(self):
        """Vérifie que les valeurs engine_type dans les exemples de filtres RBAC
        correspondent aux codes REF_ENGINES normalisés."""
        engines = RefEngine.objects.active()
        normalized_codes = {normalize_engine_code(e.code) for e in engines}

        for engine_type in RBAC_FILTER_ENGINE_TYPES:
            if engine_type not in normalized_codes:
                warnings.warn(
                    f"RBAC engine_type '{engine_type}' non aligné. Attendus: {sorted(normalized_codes)}",
                    stacklevel=1,
                )


class TestAPIReferenceEnginesEndpoint(TestCase):
    """Test: Confirmer que l'API reference/engines est disponible."""

    def test_api_reference_engines_endpoint_exists(self):
        """Confirme que GET /api/v1/reference/engines est résolu par le routeur URL."""
        from django.urls import reverse

        url = reverse('reference-engines')
        self.assertIn('engines', url)
