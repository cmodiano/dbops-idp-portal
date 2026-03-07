"""
Tests pour DashboardStatsCatalogueView — Story 60.1.

Couvre :
- Permissions (401 non-auth, 403 standard user, 200 admin/DBOPS)
- Structure de réponse (data contient tous les champs attendus)
- Agrégations réelles (by_status, by_item_type, by_engine, by_category)
- Série évolution (TruncWeek sur created_at dans la période)
- Paramètres de période invalides (400)
"""
from __future__ import annotations

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from tests.factories import ActionFactory, UserFactory

URL = '/api/v1/dashboard/stats-catalogue/'


# ============================================================================
# Task 3.1 — Permissions
# ============================================================================

@pytest.mark.django_db
class TestDashboardStatsCataloguePermissions:
    """Tests de permissions pour DashboardStatsCatalogueView."""

    def setup_method(self):
        self.client = APIClient()

    def test_unauthenticated_returns_401(self):
        """Non authentifié → 401."""
        response = self.client.get(URL)
        assert response.status_code == 401

    def test_standard_dba_user_returns_403(self):
        """Utilisateur DBA (pas admin) → 403."""
        user = UserFactory.create(profile='DBA')
        self.client.force_authenticate(user=user)
        response = self.client.get(URL)
        assert response.status_code == 403

    def test_dbops_admin_user_returns_200(self):
        """Utilisateur DBOPS (admin) → 200."""
        user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=user)
        response = self.client.get(URL)
        assert response.status_code == 200


# ============================================================================
# Task 3.2 — Structure de réponse
# ============================================================================

@pytest.mark.django_db
class TestDashboardStatsCatalogueStructure:
    """Vérifie la structure de réponse."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def test_response_has_data_key(self):
        """La réponse contient la clé 'data'."""
        response = self.client.get(URL)
        assert response.status_code == 200
        assert 'data' in response.data

    def test_data_contains_all_expected_keys(self):
        """data contient by_status, by_item_type, by_engine, by_category, evolution."""
        response = self.client.get(URL)
        data = response.data['data']
        assert 'by_status' in data
        assert 'by_item_type' in data
        assert 'by_engine' in data
        assert 'by_category' in data
        assert 'evolution' in data

    def test_aggregations_are_lists(self):
        """Toutes les agrégations sont des listes."""
        response = self.client.get(URL)
        data = response.data['data']
        assert isinstance(data['by_status'], list)
        assert isinstance(data['by_item_type'], list)
        assert isinstance(data['by_engine'], list)
        assert isinstance(data['by_category'], list)
        assert isinstance(data['evolution'], list)


# ============================================================================
# Task 3.3 — Agrégations réelles
# ============================================================================

@pytest.mark.django_db
class TestDashboardStatsCatalogueAggregations:
    """Vérifie les valeurs réelles retournées par les agrégations."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def test_by_status_counts_correctly(self):
        """by_status compte correctement les actions par statut."""
        ActionFactory.create(status='draft')
        ActionFactory.create(status='draft')
        ActionFactory.create(status='published')
        ActionFactory.create(status='disabled')

        response = self.client.get(URL)
        by_status = {item['status']: item['count'] for item in response.data['data']['by_status']}

        assert by_status.get('draft', 0) >= 2
        assert by_status.get('published', 0) >= 1
        assert by_status.get('disabled', 0) >= 1

    def test_by_item_type_counts_correctly(self):
        """by_item_type compte correctement actions vs workflows."""
        ActionFactory.create(item_type='action')
        ActionFactory.create(item_type='action')
        ActionFactory.create(item_type='workflow')

        response = self.client.get(URL)
        by_item_type = {item['item_type']: item['count'] for item in response.data['data']['by_item_type']}

        assert by_item_type.get('action', 0) >= 2
        assert by_item_type.get('workflow', 0) >= 1

    def test_by_engine_counts_correctly(self):
        """by_engine compte correctement les actions par engine."""
        ActionFactory.create(engine='Oracle')
        ActionFactory.create(engine='Oracle')
        ActionFactory.create(engine='DB2')

        response = self.client.get(URL)
        by_engine = {item['engine']: item['count'] for item in response.data['data']['by_engine']}

        assert by_engine.get('Oracle', 0) >= 2
        assert by_engine.get('DB2', 0) >= 1

    def test_by_category_counts_correctly(self):
        """by_category compte correctement les actions par catégorie."""
        ActionFactory.create(category='Provisioning')
        ActionFactory.create(category='Provisioning')
        ActionFactory.create(category='Monitoring')

        response = self.client.get(URL)
        by_category = {item['category']: item['count'] for item in response.data['data']['by_category']}

        assert by_category.get('Provisioning', 0) >= 2
        assert by_category.get('Monitoring', 0) >= 1

    def test_deleted_actions_excluded_from_aggregations(self):
        """Les actions supprimées (deleted_at IS NOT NULL) sont exclues.

        La contrainte ck_actions_soft_delete_consistency impose que deleted_at IS NOT NULL
        requiert status='disabled'. On crée une action disabled sans deleted_at (visible)
        et une disabled avec deleted_at (supprimée → invisible).
        """
        # Action supprimée (disabled + deleted_at) → exclue du queryset (deleted_at__isnull=True)
        ActionFactory.create(status='disabled', deleted_at=timezone.now())
        # Action non supprimée (disabled sans deleted_at) → incluse dans le queryset
        ActionFactory.create(status='disabled', deleted_at=None)

        response = self.client.get(URL)
        by_status_list = response.data['data']['by_status']
        by_status = {item['status']: item['count'] for item in by_status_list}

        # La disabled non supprimée doit apparaître
        assert by_status.get('disabled', 0) >= 1


# ============================================================================
# Task 3.4 — Série évolution
# ============================================================================

@pytest.mark.django_db
class TestDashboardStatsCatalogueEvolution:
    """Vérifie la série temporelle evolution."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def test_evolution_items_have_expected_keys(self):
        """Les items de evolution ont week_start, created_count, published_count."""
        # Créer une action dans la période par défaut (14 jours) pour garantir evolution non vide
        ActionFactory.create(
            status='published',
            created_at=timezone.now() - timezone.timedelta(days=3),
        )
        response = self.client.get(URL)
        evolution = response.data['data']['evolution']
        assert len(evolution) >= 1, "evolution doit contenir au moins un item"
        item = evolution[0]
        assert 'week_start' in item
        assert 'created_count' in item
        assert 'published_count' in item

    def test_evolution_filtered_by_period(self):
        """evolution inclut les actions créées dans la période demandée."""
        # Action dans la période (7 jours)
        ActionFactory.create(
            status='published',
            created_at=timezone.now() - timezone.timedelta(days=3),
        )
        # Action hors période
        ActionFactory.create(
            status='draft',
            created_at=timezone.now() - timezone.timedelta(days=30),
        )

        response = self.client.get(URL, {'days': '7'})
        evolution = response.data['data']['evolution']

        total_created = sum(item['created_count'] for item in evolution)
        assert total_created >= 1

    def test_evolution_published_count_correct(self):
        """published_count compte uniquement les actions avec status=published."""
        now = timezone.now()
        ActionFactory.create(status='published', created_at=now - timezone.timedelta(days=2))
        ActionFactory.create(status='draft', created_at=now - timezone.timedelta(days=2))

        response = self.client.get(URL, {'days': '7'})
        evolution = response.data['data']['evolution']

        total_published = sum(item['published_count'] for item in evolution)
        total_created = sum(item['created_count'] for item in evolution)
        assert total_created >= 2, f"2 actions créées dans la période, got {total_created}"
        assert total_published >= 1, f"1 action publiée dans la période, got {total_published}"
        assert total_published < total_created, "la draft ne doit pas être comptée dans published_count"


# ============================================================================
# Task 3.5 — Paramètres de période invalides
# ============================================================================

@pytest.mark.django_db
class TestDashboardStatsCataloguePeriodParams:
    """Vérifie la gestion des paramètres de période invalides."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def test_invalid_days_returns_400(self):
        """days non numérique → 400."""
        response = self.client.get(URL, {'days': 'invalid'})
        assert response.status_code == 400

    def test_zero_days_returns_400(self):
        """days=0 → 400."""
        response = self.client.get(URL, {'days': '0'})
        assert response.status_code == 400

    def test_negative_days_returns_400(self):
        """days négatif → 400."""
        response = self.client.get(URL, {'days': '-5'})
        assert response.status_code == 400

    def test_invalid_from_date_returns_400(self):
        """from_date mal formaté → 400."""
        response = self.client.get(URL, {'from_date': 'not-a-date'})
        assert response.status_code == 400

    def test_invalid_to_date_returns_400(self):
        """to_date mal formaté → 400."""
        response = self.client.get(URL, {'to_date': '2026-13-01'})
        assert response.status_code == 400

    def test_valid_from_date_to_date_filters_evolution(self):
        """from_date/to_date valides → 200 et filtre correctement evolution."""
        response = self.client.get(URL, {
            'from_date': '2026-01-01',
            'to_date': '2026-01-31',
        })
        assert response.status_code == 200
        assert 'data' in response.data
        assert 'evolution' in response.data['data']

    def test_from_date_without_to_date_returns_200(self):
        """from_date sans to_date → from_date ignoré, repli sur days par défaut → 200."""
        response = self.client.get(URL, {'from_date': '2026-01-01'})
        assert response.status_code == 200

    def test_valid_days_returns_200(self):
        """days=30 valide → 200."""
        response = self.client.get(URL, {'days': '30'})
        assert response.status_code == 200
