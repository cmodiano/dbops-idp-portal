"""
Tests complémentaires pour executions/utils/filters.py — couverture des lignes manquantes.
Lignes cibles: 148-149, 152-153, 157, 161, 165-168, 172, 176
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from datetime import date

from executions.utils.filters import (
    apply_execution_filters,
    apply_scope_filter,
    detect_request_source,
    parse_int,
    parse_date,
    parse_iso_datetime,
)
from core.exceptions import BadRequestError


class TestApplyExecutionFiltersDateFilters:
    """Tests pour apply_execution_filters avec start_date et end_date — lignes 148-153."""

    def _make_request(self, params: dict):
        """Helper: créer un mock de request DRF avec query_params."""
        request = MagicMock()
        request.query_params = params
        return request

    def _make_qs(self):
        """Helper: créer un mock de QuerySet."""
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.exclude.return_value = qs
        return qs

    def test_start_date_filter_applied(self):
        """Lignes 148-149: start_date → filtre created_at__gte."""
        qs = self._make_qs()
        request = self._make_request({'start_date': '2024-01-01'})

        result_qs, start_d, end_d = apply_execution_filters(qs, request=request)

        assert start_d == date(2024, 1, 1)
        # Vérifier que filter a été appelé avec created_at__gte
        filter_calls = qs.filter.call_args_list
        assert any('created_at__gte' in str(call) for call in filter_calls)

    def test_end_date_filter_applied(self):
        """Lignes 152-153: end_date → filtre created_at__lt avec end_exclusive."""
        qs = self._make_qs()
        request = self._make_request({'end_date': '2024-01-31'})

        result_qs, start_d, end_d = apply_execution_filters(qs, request=request)

        assert end_d == date(2024, 1, 31)
        # Vérifier que filter a été appelé avec created_at__lt
        filter_calls = qs.filter.call_args_list
        assert any('created_at__lt' in str(call) for call in filter_calls)

    def test_both_dates_filter_applied(self):
        """start_date et end_date → deux filtres appliqués."""
        qs = self._make_qs()
        request = self._make_request({'start_date': '2024-01-01', 'end_date': '2024-01-31'})

        result_qs, start_d, end_d = apply_execution_filters(qs, request=request)

        assert start_d == date(2024, 1, 1)
        assert end_d == date(2024, 1, 31)
        # Au moins 2 appels à filter (gte + lt)
        assert qs.filter.call_count >= 2

    def test_action_id_filter_applied(self):
        """Ligne 157: action_id → filtre action_id."""
        qs = self._make_qs()
        request = self._make_request({'action_id': '42'})

        result_qs, start_d, end_d = apply_execution_filters(qs, request=request)

        # Vérifier que filter a été appelé avec action_id
        filter_calls = qs.filter.call_args_list
        assert any('action_id' in str(call) for call in filter_calls)

    def test_engine_filter_applied(self):
        """Ligne 161: engine → filtre action__engine."""
        qs = self._make_qs()
        request = self._make_request({'engine': 'terraform'})

        result_qs, start_d, end_d = apply_execution_filters(qs, request=request)

        filter_calls = qs.filter.call_args_list
        assert any('action__engine' in str(call) for call in filter_calls)

    def test_status_filter_applied(self):
        """Ligne 172: status → filtre status."""
        qs = self._make_qs()
        request = self._make_request({'status': 'COMPLETED'})

        result_qs, start_d, end_d = apply_execution_filters(qs, request=request)

        filter_calls = qs.filter.call_args_list
        assert any("status='COMPLETED'" in str(call) or "status" in str(call) for call in filter_calls)

    def test_environment_filter_applied(self):
        """Ligne 176: environment → filtre environment."""
        qs = self._make_qs()
        request = self._make_request({'environment': 'production'})

        result_qs, start_d, end_d = apply_execution_filters(qs, request=request)

        filter_calls = qs.filter.call_args_list
        assert any('environment' in str(call) for call in filter_calls)

    def test_tags_filter_applied(self):
        """Lignes 165-168: tags → split + filtre action_id__in."""
        qs = self._make_qs()
        request = self._make_request({'tags': 'tag1,tag2,tag3'})

        # Mock Action.objects.search_by_tags
        with patch('executions.utils.filters.Action') as MockAction:
            mock_search = MagicMock()
            mock_values = MagicMock()
            mock_search.values.return_value = mock_values
            MockAction.objects.search_by_tags.return_value = mock_search

            result_qs, start_d, end_d = apply_execution_filters(qs, request=request)

            # Vérifier que search_by_tags a été appelé avec la liste correcte
            MockAction.objects.search_by_tags.assert_called_once_with(['tag1', 'tag2', 'tag3'])

    def test_tags_with_spaces_stripped(self):
        """Lignes 165-168: tags avec espaces → strip appliqué."""
        qs = self._make_qs()
        request = self._make_request({'tags': ' tag1 , tag2 , '})

        with patch('executions.utils.filters.Action') as MockAction:
            mock_search = MagicMock()
            mock_values = MagicMock()
            mock_search.values.return_value = mock_values
            MockAction.objects.search_by_tags.return_value = mock_search

            result_qs, start_d, end_d = apply_execution_filters(qs, request=request)

            # Espaces supprimés, entrée vide ignorée
            MockAction.objects.search_by_tags.assert_called_once_with(['tag1', 'tag2'])

    def test_tags_empty_string_no_filter(self):
        """tags="" → pas de filtre appliqué."""
        qs = self._make_qs()
        request = self._make_request({'tags': ''})

        result_qs, start_d, end_d = apply_execution_filters(qs, request=request)

        # filter ne devrait pas être appelé pour tags
        assert qs.filter.call_count == 0

    def test_tags_only_commas_no_filter(self):
        """tags=",,," → tag_list vide après strip → pas de filtre action_id__in."""
        qs = self._make_qs()
        request = self._make_request({'tags': ',,,  '})

        with patch('executions.utils.filters.Action') as MockAction:
            result_qs, start_d, end_d = apply_execution_filters(qs, request=request)

            # search_by_tags ne doit pas être appelé car tag_list vide
            MockAction.objects.search_by_tags.assert_not_called()

    def test_no_filters_returns_qs_unchanged(self):
        """Pas de paramètres → QuerySet non modifié."""
        qs = self._make_qs()
        request = self._make_request({})

        result_qs, start_d, end_d = apply_execution_filters(qs, request=request)

        assert start_d is None
        assert end_d is None
        # Aucun filtre appliqué
        qs.filter.assert_not_called()

    def test_all_filters_combined(self):
        """Tous les filtres ensemble."""
        qs = self._make_qs()
        request = self._make_request({
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
            'action_id': '10',
            'engine': 'ansible',
            'status': 'RUNNING',
            'environment': 'dev',
        })

        result_qs, start_d, end_d = apply_execution_filters(qs, request=request)

        assert start_d == date(2024, 1, 1)
        assert end_d == date(2024, 1, 31)
        # Multiples appels à filter
        assert qs.filter.call_count >= 5


class TestApplyScopeFilter:
    """Tests pour apply_scope_filter."""

    def test_scope_mine_filters_by_user_id(self):
        """scope=mine → filtre par user_id."""
        qs = MagicMock()
        qs.filter.return_value = qs
        user = MagicMock()
        user.id = 42

        result_qs, scope = apply_scope_filter(qs, user=user, scope='mine')

        assert scope == 'mine'
        qs.filter.assert_called_once_with(user_id=42)

    def test_scope_invalid_raises_bad_request(self):
        """scope invalide → BadRequestError."""
        qs = MagicMock()
        user = MagicMock()

        with pytest.raises(BadRequestError):
            apply_scope_filter(qs, user=user, scope='invalid')

    def test_scope_all_admin_returns_all(self):
        """scope=all + admin → pas de filtre."""
        qs = MagicMock()
        user = MagicMock()

        with patch('executions.utils.filters.is_admin_user', return_value=True):
            result_qs, scope = apply_scope_filter(qs, user=user, scope='all')

        assert scope == 'all'
        qs.filter.assert_not_called()

    def test_scope_all_non_admin_returns_mine(self):
        """scope=all + non-admin → scope=mine."""
        qs = MagicMock()
        qs.filter.return_value = qs
        user = MagicMock()
        user.id = 99

        with patch('executions.utils.filters.is_admin_user', return_value=False):
            result_qs, scope = apply_scope_filter(qs, user=user, scope='all')

        assert scope == 'mine'
        qs.filter.assert_called_once_with(user_id=99)


class TestDetectRequestSource:
    """Tests pour detect_request_source."""

    def _make_request(self, meta: dict):
        req = MagicMock()
        req.META = meta
        return req

    def test_bearer_token_returns_api(self):
        """Authorization: Bearer → api."""
        req = self._make_request({'HTTP_AUTHORIZATION': 'Bearer abc123'})
        assert detect_request_source(req) == 'api'

    def test_xmlhttprequest_returns_ui(self):
        """X-Requested-With: XMLHttpRequest → ui."""
        req = self._make_request({'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'})
        assert detect_request_source(req) == 'ui'

    def test_referer_returns_ui(self):
        """HTTP_REFERER présent → ui."""
        req = self._make_request({'HTTP_REFERER': 'https://example.com'})
        assert detect_request_source(req) == 'ui'

    def test_origin_returns_ui(self):
        """HTTP_ORIGIN présent → ui."""
        req = self._make_request({'HTTP_ORIGIN': 'https://example.com'})
        assert detect_request_source(req) == 'ui'

    def test_no_headers_returns_api(self):
        """Aucun header → api."""
        req = self._make_request({})
        assert detect_request_source(req) == 'api'


class TestParseHelpers:
    """Tests pour parse_int, parse_date, parse_iso_datetime."""

    def test_parse_int_none_returns_default(self):
        assert parse_int(None, 10, name='test') == 10

    def test_parse_int_empty_returns_default(self):
        assert parse_int('', 10, name='test') == 10

    def test_parse_int_valid(self):
        assert parse_int('42', 0, name='test') == 42

    def test_parse_int_invalid_raises(self):
        with pytest.raises(BadRequestError):
            parse_int('abc', 0, name='test')

    def test_parse_date_none_returns_none(self):
        assert parse_date(None, name='start_date') is None

    def test_parse_date_valid(self):
        result = parse_date('2024-01-15', name='start_date')
        assert result == date(2024, 1, 15)

    def test_parse_date_invalid_raises(self):
        with pytest.raises(BadRequestError):
            parse_date('not-a-date', name='start_date')

    def test_parse_iso_datetime_none_returns_none(self):
        assert parse_iso_datetime(None, name='dt') is None

    def test_parse_iso_datetime_valid_with_tz(self):
        result = parse_iso_datetime('2024-01-15T10:00:00Z', name='dt')
        assert result is not None

    def test_parse_iso_datetime_naive_becomes_utc(self):
        result = parse_iso_datetime('2024-01-15T10:00:00', name='dt')
        assert result is not None
        # doit avoir une timezone
        assert result.tzinfo is not None

    def test_parse_iso_datetime_invalid_raises(self):
        with pytest.raises(BadRequestError):
            parse_iso_datetime('not-a-datetime', name='dt')
