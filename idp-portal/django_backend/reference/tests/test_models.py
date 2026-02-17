"""
Tests for reference models.
Story 13.7 - Tests for RefEngine and RefPlatform models.
"""

from django.test import TestCase
from reference.models import RefEngine, RefPlatform


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


class RefPlatformModelTests(TestCase):
    """Tests for RefPlatform model."""

    def test_create_platform(self):
        """Test creating a RefPlatform instance."""
        platform = RefPlatform.objects.create(
            code='AAP',
            label='AAP (Ansible Automation Platform)',
            display_order=1,
            is_active=1
        )
        self.assertEqual(platform.code, 'AAP')
        self.assertEqual(platform.label, 'AAP (Ansible Automation Platform)')
        self.assertEqual(platform.display_order, 1)
        self.assertEqual(platform.is_active, 1)

    def test_platform_unique_code(self):
        """Test platform code must be unique."""
        RefPlatform.objects.create(code='AAP', label='AAP', display_order=1, is_active=1)
        
        with self.assertRaises(Exception):  # IntegrityError
            RefPlatform.objects.create(code='AAP', label='Ansible', display_order=2, is_active=1)

    def test_platform_active_manager(self):
        """Test active() manager method."""
        RefPlatform.objects.create(code='AAP', label='AAP', display_order=1, is_active=1)
        RefPlatform.objects.create(code='Terraform', label='Terraform', display_order=2, is_active=0)
        
        active_platforms = RefPlatform.objects.active()
        self.assertEqual(active_platforms.count(), 1)
        self.assertEqual(active_platforms.first().code, 'AAP')

    def test_platform_ordered_manager(self):
        """Test ordered() manager method."""
        RefPlatform.objects.create(code='Terraform', label='Terraform', display_order=4, is_active=1)
        RefPlatform.objects.create(code='AAP', label='AAP', display_order=1, is_active=1)
        RefPlatform.objects.create(code='GitHub Actions', label='GitHub Actions', display_order=2, is_active=1)
        
        ordered = RefPlatform.objects.ordered()
        codes = [p.code for p in ordered]
        self.assertEqual(codes, ['AAP', 'GitHub Actions', 'Terraform'])
