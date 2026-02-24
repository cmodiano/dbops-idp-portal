"""
Tests for core services (AuditService).
"""

import csv
import json
from datetime import datetime, timezone

import pytest
from django.test import TestCase
from core.services import AuditService


@pytest.mark.django_db
class TestAuditService(TestCase):
    """Tests for AuditService."""
    
    def test_create_entry(self):
        """Test create_entry() creates audit log entry."""
        entry = AuditService.create_entry(
            user_id='123',
            action_type='ACTION_CREATED',
            entity_type='action',
            entity_id=1,
            details={'name': 'Test Action'}
        )
        
        self.assertIsNotNone(entry.id)
        self.assertEqual(entry.user_id, '123')
        self.assertEqual(entry.action_type, 'ACTION_CREATED')
    
    def test_list_all_with_filters(self):
        """Test list_all() with filters."""
        AuditService.create_entry(
            user_id='123',
            action_type='ACTION_CREATED',
            entity_type='action',
            entity_id=1
        )
        AuditService.create_entry(
            user_id='456',
            action_type='ACTION_UPDATED',
            entity_type='action',
            entity_id=2
        )
        
        # Filter by user_id
        results, total = AuditService.list_all(user_id='123')
        self.assertEqual(total, 1)
        
        # Filter by action_type
        results, total = AuditService.list_all(action_type='ACTION_CREATED')
        self.assertEqual(total, 1)
    
    def test_get_by_entity(self):
        """Test get_by_entity() returns audit entries for entity."""
        AuditService.create_entry(
            user_id='123',
            action_type='ACTION_CREATED',
            entity_type='action',
            entity_id=1
        )
        
        entries = AuditService.get_by_entity('action', 1)
        self.assertEqual(entries.count(), 1)


# ---------------------------------------------------------------------------
# Tâche 3 — Tests export_to_csv / export_to_pdf / list_all étendus
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAuditServiceExport(TestCase):
    """Tests pour export_to_csv() et export_to_pdf()."""

    # 3.1  export_to_csv() sans données → StringIO avec header uniquement
    def test_export_to_csv_empty(self):
        """export_to_csv() on empty DB → only header row present."""
        output = AuditService.export_to_csv()
        content = output.read()
        assert 'Timestamp' in content
        # header seulement : une seule ligne (+ éventuel \r\n final)
        lines = [l for l in content.splitlines() if l.strip()]
        assert len(lines) == 1

    # 3.2  export_to_csv() avec données → lignes CSV correctement formatées
    def test_export_to_csv_with_data(self):
        """export_to_csv() with entries → CSV rows present."""
        AuditService.create_entry(
            user_id='csv-user',
            action_type='ACTION_CREATED',
            entity_type='action',
            entity_id=10,
            details={'key': 'value'},
            ip_address='192.168.1.1',
        )
        output = AuditService.export_to_csv(user_id='csv-user')
        content = output.read()
        reader = csv.reader(content.splitlines())
        rows = list(reader)
        # header + 1 data row
        assert len(rows) == 2
        assert rows[0][0] == 'Timestamp'
        assert 'csv-user' in rows[1]

    # 3.3  Filtres user_id, action_type, entity_type, date_from, date_to
    def test_export_to_csv_filters(self):
        """export_to_csv() with various filters → only matching rows returned."""
        AuditService.create_entry(
            user_id='filter-user',
            action_type='ACTION_CREATED',
            entity_type='filter_entity',
            entity_id=20,
        )
        AuditService.create_entry(
            user_id='other-user',
            action_type='ACTION_DELETED',
            entity_type='other_entity',
            entity_id=21,
        )

        # Filter par user_id
        out = AuditService.export_to_csv(user_id='filter-user')
        content = out.read()
        rows = [r for r in content.splitlines() if r.strip()]
        assert len(rows) == 2  # header + 1
        assert 'filter-user' in rows[1]

        # Filter par action_type
        out2 = AuditService.export_to_csv(action_type='ACTION_DELETED')
        content2 = out2.read()
        rows2 = [r for r in content2.splitlines() if r.strip()]
        assert len(rows2) == 2
        assert 'other-user' in rows2[1]

        # Filter par entity_type
        out3 = AuditService.export_to_csv(entity_type='filter_entity')
        content3 = out3.read()
        rows3 = [r for r in content3.splitlines() if r.strip()]
        assert len(rows3) == 2

        # Filter date_from / date_to (plage large → toutes les entrées)
        date_from = datetime(2000, 1, 1, tzinfo=timezone.utc)
        date_to = datetime(2099, 12, 31, tzinfo=timezone.utc)
        out4 = AuditService.export_to_csv(date_from=date_from, date_to=date_to)
        content4 = out4.read()
        rows4 = [r for r in content4.splitlines() if r.strip()]
        assert len(rows4) >= 3  # header + 2 entrées minimum

    # 3.4  details JSON valide → json.dumps indent=2
    def test_export_to_csv_valid_json_details(self):
        """export_to_csv() with valid JSON details → formatted with indent=2."""
        details_dict = {'action': 'test', 'value': 42}
        AuditService.create_entry(
            user_id='json-user',
            action_type='ACTION_CREATED',
            entity_type='json_entity',
            entity_id=30,
            details=details_dict,
        )
        output = AuditService.export_to_csv(user_id='json-user')
        content = output.read()
        rows = list(csv.reader(content.splitlines()))
        details_cell = rows[1][-1]  # last column is Details
        # Doit être du JSON formaté (indent=2 → présence de newlines ou espaces)
        parsed = json.loads(details_cell)
        assert parsed == details_dict

    # 3.5  details non-JSON → valeur brute conservée
    def test_export_to_csv_non_json_details(self):
        """export_to_csv() with non-JSON details → raw string preserved."""
        from core.models import AuditLog
        from django.utils import timezone as dj_tz

        # Créer une entrée avec details non-JSON directement via le manager
        entry = AuditLog.objects.create(
            user_id='raw-user',
            action_type='ACTION_CREATED',
            entity_type='raw_entity',
            entity_id=40,
            details='not valid json {{}',
            timestamp=dj_tz.now(),
        )
        output = AuditService.export_to_csv(user_id='raw-user')
        content = output.read()
        assert 'not valid json' in content

    # 3.6  export_to_pdf() → lève NotImplementedError
    def test_export_to_pdf_raises(self):
        """export_to_pdf() → raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            AuditService.export_to_pdf()


@pytest.mark.django_db
class TestAuditServiceListAllFilters(TestCase):
    """Tests étendus pour list_all() : date_from, date_to, entity_id, pagination."""

    def setUp(self):
        self.entry1 = AuditService.create_entry(
            user_id='list-user',
            action_type='ACTION_CREATED',
            entity_type='list_entity',
            entity_id=100,
        )
        self.entry2 = AuditService.create_entry(
            user_id='list-user',
            action_type='ACTION_UPDATED',
            entity_type='list_entity',
            entity_id=101,
        )
        self.entry3 = AuditService.create_entry(
            user_id='other-list-user',
            action_type='ACTION_DELETED',
            entity_type='other_entity',
            entity_id=102,
        )

    # 3.7  list_all() avec date_from et date_to → filtre par timestamp
    def test_list_all_date_filters(self):
        """list_all() with date_from/date_to → filters by timestamp."""
        date_from = datetime(2000, 1, 1, tzinfo=timezone.utc)
        date_to = datetime(2099, 12, 31, tzinfo=timezone.utc)
        results, total = AuditService.list_all(date_from=date_from, date_to=date_to)
        assert total >= 3

        # Plage future lointaine → exclut toutes les entrées créées dans setUp
        future_from = datetime(2099, 1, 1, tzinfo=timezone.utc)
        future_to = datetime(2099, 12, 31, tzinfo=timezone.utc)
        results_future, total_future = AuditService.list_all(date_from=future_from, date_to=future_to)
        assert total_future == 0

    # 3.8  list_all() avec entity_id → filtre par entity_id
    def test_list_all_entity_id_filter(self):
        """list_all() with entity_id → returns only matching entries."""
        results, total = AuditService.list_all(entity_id=100)
        assert total == 1
        assert results[0].entity_id == 100

    # 3.9  list_all() pagination : page=2, page_size=1 → résultat correct
    def test_list_all_pagination(self):
        """list_all() with page=2, page_size=1 → returns second item."""
        # Récupérer tous les résultats triés par timestamp DESC
        all_results, total = AuditService.list_all(user_id='list-user')
        assert total == 2

        # Page 1 : 1er élément
        page1, _ = AuditService.list_all(user_id='list-user', page=1, page_size=1)
        assert len(page1) == 1

        # Page 2 : 2ème élément
        page2, _ = AuditService.list_all(user_id='list-user', page=2, page_size=1)
        assert len(page2) == 1

        # Les deux éléments doivent être différents
        assert page1[0].id != page2[0].id
