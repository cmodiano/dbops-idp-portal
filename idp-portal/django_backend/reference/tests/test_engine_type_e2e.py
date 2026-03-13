"""
Test end-to-end de cohérence RBAC filter + API inventaire avec engine_type.
Story 29.3 - Valide que les profils et l'API utilisent les mêmes valeurs normalisées.
"""

from django.test import TestCase

from profiles.models import Profile, ProfileTargetPermission
from profiles.services import ProfileService
from profiles.target_permission_repository import get_filter_by_attribute


class TestE2EEngineTypeConsistency(TestCase):
    """Test end-to-end : profil RBAC avec engine_type → cohérence valeurs normalisées."""

    def setUp(self):
        """Configure profil et permission avec filtre engine_type."""
        self.profile = Profile.objects.create(
            name='Oracle DBAs',
            description='Profil pour DBAs Oracle',
            ad_group='GRP-ORACLE-DBAS',
        )

        # Permission avec filtre engine_type aligné sur REF_ENGINES normalisé
        ProfileService().set_target_permissions(
            self.profile.id,
            {'targets_type': 'all', 'filter_by_attribute': {'engine_type': ['oracle', 'sql_server']}},
        )
        self.permission = ProfileTargetPermission.objects.get(profile=self.profile)

    def test_rbac_filter_uses_normalized_values(self):
        """Vérifie que filter_by_attribute utilise valeurs normalisées (minuscules + underscores)."""
        filter_attr = get_filter_by_attribute(self.permission)
        self.assertIn('engine_type', filter_attr)
        engine_types = filter_attr['engine_type']
        self.assertEqual(sorted(engine_types), ['oracle', 'sql_server'])

        # Vérifier que ces valeurs sont alignées sur REF_ENGINES normalisées
        for et in engine_types:
            self.assertEqual(et, et.lower(), f"engine_type '{et}' doit être en minuscules")
            self.assertNotIn(' ', et, f"engine_type '{et}' ne doit pas contenir d'espaces")

    def test_filter_values_match_normalized_convention(self):
        """Vérifie que les valeurs suivent la convention : minuscules, underscores pour espaces."""
        filter_attr = get_filter_by_attribute(self.permission)
        engine_types = filter_attr['engine_type']

        # "sql_server" = normalisation de "SQL Server" (REF_ENGINES.CODE)
        self.assertIn('sql_server', engine_types, "Convention : 'SQL Server' → 'sql_server'")
        self.assertNotIn('sqlserver', engine_types, "Pas de concaténation sans underscore")
        self.assertNotIn('SQL Server', engine_types, "Pas d'espaces dans valeurs normalisées")
