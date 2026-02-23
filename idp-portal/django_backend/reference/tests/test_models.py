"""
Tests for reference models.
Story 13.7 - Tests for RefEngine model.
Story 31.9 - RefPlatformModelTests removed (RefPlatform deleted).
"""

from django.test import TestCase
from reference.models import RefEngine


class RefEngineModelTests(TestCase):
    """Tests for RefEngine model."""

    def test_create_engine(self):
        """Test creating a RefEngine instance."""
        engine = RefEngine.objects.create(
            code='Oracle',
            label='Oracle Database',
            display_order=1,
            is_active=1
        )
        self.assertEqual(engine.code, 'Oracle')
        self.assertEqual(engine.label, 'Oracle Database')
        self.assertEqual(engine.display_order, 1)
        self.assertEqual(engine.is_active, 1)

    def test_engine_unique_code(self):
        """Test engine code must be unique."""
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        
        with self.assertRaises(Exception):  # IntegrityError
            RefEngine.objects.create(code='Oracle', label='Oracle DB', display_order=2, is_active=1)

    def test_engine_active_manager(self):
        """Test active() manager method."""
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        RefEngine.objects.create(code='DB2', label='DB2', display_order=2, is_active=0)
        
        active_engines = RefEngine.objects.active()
        self.assertEqual(active_engines.count(), 1)
        self.assertEqual(active_engines.first().code, 'Oracle')

    def test_engine_ordered_manager(self):
        """Test ordered() manager method."""
        RefEngine.objects.create(code='DB2', label='DB2', display_order=3, is_active=1)
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        RefEngine.objects.create(code='SQL Server', label='SQL Server', display_order=2, is_active=1)
        
        ordered = RefEngine.objects.ordered()
        codes = [e.code for e in ordered]
        self.assertEqual(codes, ['Oracle', 'SQL Server', 'DB2'])


