"""
Tests pour DashboardStatsAdoptionView — Story 60.2.

Couvre :
- Permissions (401 non-auth, 200 user standard, 200 DBOPS)
- Structure de réponse (data contient executions_by_profile, active_users_by_profile, adoption_trend)
- Agrégations réelles (counts par profil)
- Utilisateurs actifs distincts
- Scope mine/all (user standard vs DBOPS)
- Série temporelle hebdomadaire
- Paramètres de période invalides (400)
"""
from __future__ import annotations

import pytest
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from tests.factories import UserFactory, ExecutionFactory

URL = '/api/v1/dashboard/stats-adoption/'


# ============================================================================
# Task 3.1 — Permissions
# ============================================================================

@pytest.mark.django_db
class TestDashboardStatsAdoptionPermissions:
    """Tests de permissions pour DashboardStatsAdoptionView."""

    def setup_method(self):
        self.client = APIClient()

    def test_unauthenticated_returns_401(self):
        """Non authentifié → 401."""
        response = self.client.get(URL)
        assert response.status_code == 401

    def test_standard_dba_user_returns_200(self):
        """Utilisateur DBA (pas admin) → 200 (scope mine)."""
        user = UserFactory.create(profile='DBA')
        self.client.force_authenticate(user=user)
        response = self.client.get(URL)
        assert response.status_code == 200

    def test_dbops_user_returns_200(self):
        """Utilisateur DBOPS (admin) → 200 (scope all)."""
        user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=user)
        response = self.client.get(URL)
        assert response.status_code == 200


# ============================================================================
# Task 3.2 — Structure de réponse
# ============================================================================

@pytest.mark.django_db
class TestDashboardStatsAdoptionStructure:
    """Vérifie la structure de réponse."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def test_response_contains_data_key(self):
        response = self.client.get(URL)
        assert response.status_code == 200
        assert 'data' in response.data

    def test_data_contains_required_keys(self):
        response = self.client.get(URL)
        data = response.data['data']
        assert 'executions_by_profile' in data
        assert 'active_users_by_profile' in data
        assert 'adoption_trend' in data

    def test_executions_by_profile_is_list(self):
        response = self.client.get(URL)
        assert isinstance(response.data['data']['executions_by_profile'], list)

    def test_active_users_by_profile_is_list(self):
        response = self.client.get(URL)
        assert isinstance(response.data['data']['active_users_by_profile'], list)

    def test_adoption_trend_is_list(self):
        response = self.client.get(URL)
        assert isinstance(response.data['data']['adoption_trend'], list)

    def test_executions_by_profile_item_structure(self):
        ExecutionFactory.create(user=self.user)
        response = self.client.get(URL)
        items = response.data['data']['executions_by_profile']
        assert len(items) > 0
        item = items[0]
        assert 'profile' in item
        assert 'count' in item

    def test_active_users_by_profile_item_structure(self):
        ExecutionFactory.create(user=self.user)
        response = self.client.get(URL)
        items = response.data['data']['active_users_by_profile']
        assert len(items) > 0
        item = items[0]
        assert 'profile' in item
        assert 'user_count' in item

    def test_adoption_trend_item_structure(self):
        ExecutionFactory.create(user=self.user)
        response = self.client.get(URL)
        items = response.data['data']['adoption_trend']
        assert len(items) > 0
        item = items[0]
        assert 'week_start' in item
        assert 'profile' in item
        assert 'count' in item


# ============================================================================
# Task 3.3 — Agrégations par profil
# ============================================================================

@pytest.mark.django_db
class TestDashboardStatsAdoptionAggregations:
    """Vérifie les counts retournés par profil."""

    def setup_method(self):
        self.client = APIClient()
        self.dbops = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.dbops)

    def test_executions_by_profile_counts(self):
        """DBOPS voit toutes les exécutions groupées par profil."""
        dba_user = UserFactory.create(profile='DBA')
        ExecutionFactory.create(user=dba_user)
        ExecutionFactory.create(user=dba_user)
        ExecutionFactory.create(user=self.dbops)

        response = self.client.get(URL)
        assert response.status_code == 200
        by_profile = {r['profile']: r['count'] for r in response.data['data']['executions_by_profile']}

        assert by_profile.get('DBA', 0) == 2
        assert by_profile.get('DBOPS', 0) >= 1

    def test_executions_by_profile_no_null_in_response(self):
        """La réponse ne doit jamais contenir de valeur None dans le champ profile."""
        dba_user = UserFactory.create(profile='DBA')
        ExecutionFactory.create(user=dba_user)

        response = self.client.get(URL)
        assert response.status_code == 200
        profiles = [r['profile'] for r in response.data['data']['executions_by_profile']]
        assert None not in profiles

    def test_active_users_by_profile_no_null_in_response(self):
        """active_users_by_profile ne doit jamais contenir de valeur None dans le champ profile (AC4)."""
        dba_user = UserFactory.create(profile='DBA')
        ExecutionFactory.create(user=dba_user)

        response = self.client.get(URL)
        assert response.status_code == 200
        profiles = [r['profile'] for r in response.data['data']['active_users_by_profile']]
        assert None not in profiles


# ============================================================================
# Task 3.4 — Utilisateurs actifs distincts
# ============================================================================

@pytest.mark.django_db
class TestDashboardStatsAdoptionActiveUsers:
    """Vérifie que active_users_by_profile compte les utilisateurs distincts."""

    def setup_method(self):
        self.client = APIClient()
        self.dbops = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.dbops)

    def test_active_users_counts_distinct_users(self):
        """3 exécutions user1 DBA + 1 exécution user2 DBA → 2 utilisateurs actifs DBA, 4 exécutions DBA."""
        user1 = UserFactory.create(profile='DBA')
        user2 = UserFactory.create(profile='DBA')

        ExecutionFactory.create(user=user1)
        ExecutionFactory.create(user=user1)
        ExecutionFactory.create(user=user1)
        ExecutionFactory.create(user=user2)

        response = self.client.get(URL)
        assert response.status_code == 200
        data = response.data['data']

        by_exec = {r['profile']: r['count'] for r in data['executions_by_profile']}
        by_active = {r['profile']: r['user_count'] for r in data['active_users_by_profile']}

        assert by_exec.get('DBA', 0) == 4
        assert by_active.get('DBA', 0) == 2

    def test_active_users_not_double_counting(self):
        """Un même user avec N exécutions ne compte que 1 utilisateur actif."""
        user = UserFactory.create(profile='DBA')
        ExecutionFactory.create(user=user)
        ExecutionFactory.create(user=user)
        ExecutionFactory.create(user=user)

        response = self.client.get(URL)
        by_active = {r['profile']: r['user_count'] for r in response.data['data']['active_users_by_profile']}
        assert by_active.get('DBA', 0) == 1


# ============================================================================
# Task 3.5 — Scope mine/all
# ============================================================================

@pytest.mark.django_db
class TestDashboardStatsAdoptionScope:
    """Vérifie le scope mine pour les utilisateurs standards."""

    def setup_method(self):
        self.client = APIClient()

    def test_standard_user_sees_only_own_executions(self):
        """User DBA standard ne voit que ses propres exécutions."""
        user_dba = UserFactory.create(profile='DBA')
        user_other = UserFactory.create(profile='DBA')
        ExecutionFactory.create(user=user_dba)
        ExecutionFactory.create(user=user_other)

        self.client.force_authenticate(user=user_dba)
        response = self.client.get(URL)

        assert response.status_code == 200
        data = response.data['data']
        total = sum(r['count'] for r in data['executions_by_profile'])
        assert total == 1  # Seulement l'exécution de user_dba

    def test_dbops_user_sees_all_executions(self):
        """DBOPS voit toutes les exécutions."""
        user_dba = UserFactory.create(profile='DBA')
        user_other = UserFactory.create(profile='DBA')
        dbops = UserFactory.create(profile='DBOPS')
        ExecutionFactory.create(user=user_dba)
        ExecutionFactory.create(user=user_other)

        self.client.force_authenticate(user=dbops)
        response = self.client.get(URL)

        assert response.status_code == 200
        data = response.data['data']
        total = sum(r['count'] for r in data['executions_by_profile'])
        assert total == 2  # Exactement les 2 exécutions DBA créées

    def test_standard_user_active_users_reflects_scope(self):
        """User standard : active_users_by_profile montre uniquement son propre compte."""
        user_dba = UserFactory.create(profile='DBA')
        user_other = UserFactory.create(profile='DBA')
        ExecutionFactory.create(user=user_dba)
        ExecutionFactory.create(user=user_other)

        self.client.force_authenticate(user=user_dba)
        response = self.client.get(URL)

        by_active = {r['profile']: r['user_count'] for r in response.data['data']['active_users_by_profile']}
        assert by_active.get('DBA', 0) == 1  # Seulement user_dba visible


# ============================================================================
# Task 3.6 — Série temporelle adoption_trend
# ============================================================================

@pytest.mark.django_db
class TestDashboardStatsAdoptionTrend:
    """Vérifie la série temporelle hebdomadaire adoption_trend."""

    def setup_method(self):
        self.client = APIClient()
        self.dbops = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.dbops)

    def test_adoption_trend_contains_entries(self):
        """Après création d'exécutions, adoption_trend est non vide."""
        ExecutionFactory.create(user=self.dbops)
        response = self.client.get(URL)
        trend = response.data['data']['adoption_trend']
        assert len(trend) > 0

    def test_adoption_trend_week_start_format(self):
        """week_start est au format YYYY-MM-DD (validation stricte)."""
        from datetime import datetime
        ExecutionFactory.create(user=self.dbops)
        response = self.client.get(URL)
        trend = response.data['data']['adoption_trend']
        for item in trend:
            week_start = item['week_start']
            # Vérifie format YYYY-MM-DD strict (lève ValueError si invalide)
            parsed = datetime.strptime(week_start, "%Y-%m-%d")
            assert parsed is not None

    def test_adoption_trend_ordered_by_week_start_asc(self):
        """adoption_trend est ordonné par week_start ASC."""
        now = timezone.now()
        user = UserFactory.create(profile='DBA')
        ExecutionFactory.create(user=user)

        response = self.client.get(URL, {'from_date': (now - timedelta(days=30)).strftime('%Y-%m-%d'),
                                          'to_date': now.strftime('%Y-%m-%d')})
        trend = response.data['data']['adoption_trend']
        week_starts = [item['week_start'] for item in trend]
        assert week_starts == sorted(week_starts)

    def test_adoption_trend_no_null_profiles(self):
        """adoption_trend ne doit jamais contenir None dans le champ profile."""
        user = UserFactory.create(profile='DBA')
        ExecutionFactory.create(user=user)

        response = self.client.get(URL)
        profiles = [item['profile'] for item in response.data['data']['adoption_trend']]
        assert None not in profiles

    def test_adoption_trend_ordered_by_profile_asc_within_same_week(self):
        """adoption_trend est ordonné par week_start ASC puis profile ASC (AC6)."""
        now = timezone.now()
        user_z = UserFactory.create(profile='ZZZ')
        user_a = UserFactory.create(profile='AAA')
        # Les deux exécutions dans la même semaine
        ExecutionFactory.create(user=user_z)
        ExecutionFactory.create(user=user_a)

        response = self.client.get(URL, {
            'from_date': (now - timedelta(days=7)).strftime('%Y-%m-%d'),
            'to_date': (now + timedelta(days=1)).strftime('%Y-%m-%d'),
        })
        assert response.status_code == 200
        trend = response.data['data']['adoption_trend']
        # Filtrer les entrées de la semaine courante
        week_groups: dict = {}
        for item in trend:
            week_groups.setdefault(item['week_start'], []).append(item['profile'])
        # Pour chaque semaine, les profils doivent être triés ASC
        for week, profiles in week_groups.items():
            assert profiles == sorted(profiles), (
                f"adoption_trend n'est pas trié par profile ASC pour la semaine {week}: {profiles}"
            )


# ============================================================================
# Task 3.7 — Paramètres de période
# ============================================================================

@pytest.mark.django_db
class TestDashboardStatsAdoptionPeriodParams:
    """Vérifie la gestion des paramètres de période."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def test_invalid_days_returns_400(self):
        """days non entier → 400."""
        response = self.client.get(URL, {'days': 'invalid'})
        assert response.status_code == 400

    def test_negative_days_returns_400(self):
        """days <= 0 → 400."""
        response = self.client.get(URL, {'days': '0'})
        assert response.status_code == 400

    def test_invalid_from_date_returns_400(self):
        """from_date invalide → 400."""
        response = self.client.get(URL, {'from_date': 'not-a-date'})
        assert response.status_code == 400

    def test_invalid_to_date_returns_400(self):
        """to_date invalide → 400."""
        response = self.client.get(URL, {'to_date': '2026/01/01'})
        assert response.status_code == 400

    def test_valid_from_date_to_date_returns_200(self):
        """from_date/to_date valides → 200."""
        response = self.client.get(URL, {'from_date': '2026-01-01', 'to_date': '2026-02-01'})
        assert response.status_code == 200

    def test_from_date_without_to_date_returns_400(self):
        """from_date sans to_date → 400 (from_date et to_date doivent être fournis ensemble)."""
        response = self.client.get(URL, {'from_date': '2026-01-01'})
        assert response.status_code == 400

    def test_period_filter_excludes_out_of_range_executions(self):
        """Exécutions hors période ne doivent pas apparaître."""
        now = timezone.now()
        user = UserFactory.create(profile='DBA')
        # Exécution dans la période
        ExecutionFactory.create(user=user)

        # Période future (aucune exécution existante ne sera dedans)
        future_from = (now + timedelta(days=100)).strftime('%Y-%m-%d')
        future_to = (now + timedelta(days=110)).strftime('%Y-%m-%d')

        response = self.client.get(URL, {'from_date': future_from, 'to_date': future_to})
        assert response.status_code == 200
        data = response.data['data']
        assert data['executions_by_profile'] == []
        assert data['active_users_by_profile'] == []
        assert data['adoption_trend'] == []
