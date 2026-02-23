"""
Tests dédiés aux bornes de retry et au format de réponse d'erreur enrichi.

Story 32.4 : Bornes retry, observabilité et codes d'erreur explicites.

Ces tests couvrent :
- AC #1 : Borne max retries ET borne time window configurables
- AC #2 : Code d'erreur explicite + champ reason + message distinct par cause
- AC #5 : Tests des bornes et du format de réponse d'erreur

Patterns utilisés :
- RequestFactory + DatabaseResilienceMiddleware directe (cohérent avec tests existants)
- patch('core.db_resilience.time.sleep') pour éviter les attentes réelles
- patch('core.db_resilience.time.monotonic') pour simuler dépassement time window
- override_settings pour tester les bornes configurables
"""
from __future__ import annotations

import json
from unittest.mock import patch

from django.db import OperationalError
from django.db.utils import InterfaceError
from django.http import HttpResponse
from django.test import TestCase, RequestFactory, override_settings

from core.db_resilience import DatabaseResilienceMiddleware


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _always_fail_view(exc_factory=None):
    """Return a view that always raises the given exception."""
    if exc_factory is None:
        exc_factory = lambda: OperationalError("ORA-03113: end-of-file on communication channel")  # noqa: E731

    def view(request):
        raise exc_factory()

    return view


def _success_after_n_failures(n_failures, status=200):
    """Return a view that raises n_failures times then returns HTTP 200."""
    call_count = {"value": 0}

    def view(request):
        call_count["value"] += 1
        if call_count["value"] <= n_failures:
            raise OperationalError("ORA-03113: end-of-file on communication channel")
        return HttpResponse("OK", status=status)

    return view


# ---------------------------------------------------------------------------
# Task 5.2 — Borne max retries
# ---------------------------------------------------------------------------

@override_settings(DB_RETRY_MAX_ATTEMPTS=2, DB_RETRY_BACKOFF_BASE=0.01, DB_RETRY_TIME_WINDOW_SECONDS=120)
class TestMaxRetriesBound(TestCase):
    """AC #1 + AC #2 : 503 après épuisement du nombre max de retries configuré."""

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/api/v1/health/')

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_503_after_max_retries(self, mock_close, mock_conn, mock_sleep):
        """503 après DB_RETRY_MAX_ATTEMPTS=2 tentatives échouées."""
        mock_conn.ensure_connection.return_value = None

        middleware = DatabaseResilienceMiddleware(_always_fail_view())
        result = middleware(self.request)

        self.assertEqual(result.status_code, 503)
        body = json.loads(result.content)
        self.assertEqual(body['error']['code'], 'DB_UNAVAILABLE')
        self.assertEqual(body['error']['reason'], 'retry_exhausted')
        self.assertIn('correlation_id', body['error'])
        self.assertIn('message', body['error'])
        self.assertEqual(result.get('Retry-After'), '30')

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_retry_count_respects_max_attempts(self, mock_close, mock_conn, mock_sleep):
        """Le view est appelé 1 (initial) + DB_RETRY_MAX_ATTEMPTS fois au total."""
        mock_conn.ensure_connection.return_value = None
        call_count = {"value": 0}

        def counting_view(request):
            call_count["value"] += 1
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = DatabaseResilienceMiddleware(counting_view)
        result = middleware(self.request)

        self.assertEqual(result.status_code, 503)
        # 1 appel initial dans __call__ + DB_RETRY_MAX_ATTEMPTS=2 retries = 3 appels total
        self.assertEqual(call_count["value"], 3)

    @override_settings(DB_RETRY_MAX_ATTEMPTS=1, DB_RETRY_TIME_WINDOW_SECONDS=120)
    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_max_attempts_1_returns_503_quickly(self, mock_close, mock_conn, mock_sleep):
        """DB_RETRY_MAX_ATTEMPTS=1 → 1 initial + 1 retry = 2 appels, 503."""
        mock_conn.ensure_connection.return_value = None
        call_count = {"value": 0}

        def one_try(request):
            call_count["value"] += 1
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = DatabaseResilienceMiddleware(one_try)
        result = middleware(self.request)

        self.assertEqual(result.status_code, 503)
        # 1 initial dans __call__ + 1 retry = 2 appels total
        self.assertEqual(call_count["value"], 2)
        body = json.loads(result.content)
        self.assertEqual(body['error']['reason'], 'retry_exhausted')


# ---------------------------------------------------------------------------
# Task 5.3 — Borne time window
# ---------------------------------------------------------------------------

@override_settings(DB_RETRY_MAX_ATTEMPTS=5, DB_RETRY_BACKOFF_BASE=0.01, DB_RETRY_TIME_WINDOW_SECONDS=30)
class TestTimeWindowBound(TestCase):
    """AC #1 : 503 si durée totale >= DB_RETRY_TIME_WINDOW_SECONDS."""

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/api/v1/health/')

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    @patch('core.db_resilience.time.monotonic')
    def test_503_after_time_window_exceeded(self, mock_monotonic, mock_close, mock_conn, mock_sleep):
        """503 avec reason=time_window_exceeded quand elapsed >= time_window."""
        mock_conn.ensure_connection.return_value = None
        # start_time=0.0, then elapsed check returns 35.0 > 30s time_window
        mock_monotonic.side_effect = [0.0, 35.0]

        middleware = DatabaseResilienceMiddleware(_always_fail_view())
        result = middleware(self.request)

        self.assertEqual(result.status_code, 503)
        body = json.loads(result.content)
        self.assertEqual(body['error']['code'], 'DB_UNAVAILABLE')
        self.assertEqual(body['error']['reason'], 'time_window_exceeded')
        self.assertIn('correlation_id', body['error'])
        self.assertEqual(result.get('Retry-After'), '30')

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    @patch('core.db_resilience.time.monotonic')
    def test_time_window_message_distinct(self, mock_monotonic, mock_close, mock_conn, mock_sleep):
        """Le message 503 est distinct pour time_window_exceeded vs retry_exhausted."""
        mock_conn.ensure_connection.return_value = None
        mock_monotonic.side_effect = [0.0, 35.0]

        middleware = DatabaseResilienceMiddleware(_always_fail_view())
        result = middleware(self.request)

        body = json.loads(result.content)
        self.assertIn('bascule', body['error']['message'].lower())
        # Ne doit PAS contenir le message générique retry_exhausted
        self.assertNotIn('Veuillez réessayer dans quelques instants', body['error']['message'])

    @override_settings(DB_RETRY_TIME_WINDOW_SECONDS=60)
    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    @patch('core.db_resilience.time.monotonic')
    def test_time_window_respected_via_override_settings(self, mock_monotonic, mock_close, mock_conn, mock_sleep):
        """DB_RETRY_TIME_WINDOW_SECONDS est respecté via override_settings."""
        mock_conn.ensure_connection.return_value = None
        # elapsed=55s < 60s → pas de time window
        # Second call elapsed check: 55s < 60s → no time window yet
        # Third call: 65s > 60s → time window exceeded
        mock_monotonic.side_effect = [0.0, 55.0, 65.0]

        call_count = {"value": 0}

        def counting_fail(request):
            call_count["value"] += 1
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = DatabaseResilienceMiddleware(counting_fail)
        result = middleware(self.request)

        self.assertEqual(result.status_code, 503)
        body = json.loads(result.content)
        # Second attempt passes time window check (55 < 60)
        # Third attempt hits time window (65 >= 60)
        self.assertEqual(body['error']['reason'], 'time_window_exceeded')


# ---------------------------------------------------------------------------
# Task 5.4 — Erreur mid-commit
# ---------------------------------------------------------------------------

@override_settings(DB_RETRY_MAX_ATTEMPTS=3, DB_RETRY_TIME_WINDOW_SECONDS=120)
class TestMidCommitError(TestCase):
    """AC #2 : 503 immédiat pour mid-commit (reason=mid_commit_error), pas de retry."""

    def setUp(self):
        self.factory = RequestFactory()
        # POST = write method → mid-commit check s'applique
        self.request = self.factory.post('/api/v1/executions/', data={})

    @patch('core.db_resilience.connection')
    def test_mid_commit_503_no_retry(self, mock_conn):
        """Erreur ORA-03113 avec in_atomic_block=False → 503 sans retry + reason=mid_commit_error."""
        # in_atomic_block=False → _is_mid_commit_error returns True → unsafe
        mock_conn.in_atomic_block = False

        call_count = {"value": 0}

        def view(request):
            call_count["value"] += 1
            raise OperationalError("ORA-03113: end-of-file on communication channel")

        middleware = DatabaseResilienceMiddleware(view)
        result = middleware(self.request)

        self.assertEqual(result.status_code, 503)
        # Pas de retry : le view est appelé une seule fois
        self.assertEqual(call_count["value"], 1)
        body = json.loads(result.content)
        self.assertEqual(body['error']['reason'], 'mid_commit_error')

    @patch('core.db_resilience.connection')
    def test_mid_commit_reason_in_response(self, mock_conn):
        """La raison mid_commit_error est présente dans la réponse JSON."""
        mock_conn.in_atomic_block = False

        middleware = DatabaseResilienceMiddleware(_always_fail_view())
        result = middleware(self.request)

        body = json.loads(result.content)
        self.assertEqual(body['error']['code'], 'DB_UNAVAILABLE')
        self.assertEqual(body['error']['reason'], 'mid_commit_error')
        self.assertIn('correlation_id', body['error'])

    @patch('core.db_resilience.connection')
    def test_mid_commit_message_distinct(self, mock_conn):
        """Le message mid_commit est distinct des autres raisons."""
        mock_conn.in_atomic_block = False

        middleware = DatabaseResilienceMiddleware(_always_fail_view())
        result = middleware(self.request)

        body = json.loads(result.content)
        self.assertIn('incertain', body['error']['message'].lower())

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_interface_error_is_safe_to_retry(self, mock_close, mock_conn, mock_sleep):
        """InterfaceError = pré-commit → retry safe, PAS un mid_commit_error."""
        mock_conn.ensure_connection.return_value = None
        call_count = {"value": 0}

        def view(request):
            call_count["value"] += 1
            if call_count["value"] <= 1:
                raise InterfaceError("connection is closed")
            return HttpResponse("OK", status=200)

        middleware = DatabaseResilienceMiddleware(view)
        result = middleware(self.request)

        # InterfaceError doit être retried → succès au 2ème appel
        self.assertEqual(result.status_code, 200)
        self.assertEqual(call_count["value"], 2)


# ---------------------------------------------------------------------------
# Task 5.5 — Format de réponse JSON exact
# ---------------------------------------------------------------------------

@override_settings(DB_RETRY_MAX_ATTEMPTS=2, DB_RETRY_BACKOFF_BASE=0.01, DB_RETRY_TIME_WINDOW_SECONDS=120)
class TestResponseFormat(TestCase):
    """AC #2 : Structure JSON exacte {"error": {"code", "reason", "message", "correlation_id"}}."""

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/api/v1/health/')

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    @patch('core.db_resilience.get_correlation_id', return_value='test-corr-id-42')
    def test_response_json_structure_retry_exhausted(self, mock_corr, mock_close, mock_conn, mock_sleep):
        """Structure JSON exacte pour reason=retry_exhausted."""
        mock_conn.ensure_connection.return_value = None

        middleware = DatabaseResilienceMiddleware(_always_fail_view())
        result = middleware(self.request)

        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.get('Retry-After'), '30')
        self.assertEqual(result.get('Content-Type'), 'application/json')

        body = json.loads(result.content)
        error = body['error']
        self.assertIn('code', error)
        self.assertIn('reason', error)
        self.assertIn('message', error)
        self.assertIn('correlation_id', error)
        self.assertEqual(error['code'], 'DB_UNAVAILABLE')
        self.assertEqual(error['reason'], 'retry_exhausted')
        self.assertEqual(error['correlation_id'], 'test-corr-id-42')
        self.assertIsInstance(error['message'], str)
        self.assertGreater(len(error['message']), 0)

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    @patch('core.db_resilience.time.monotonic')
    @patch('core.db_resilience.get_correlation_id', return_value='test-corr-tw-99')
    def test_response_json_structure_time_window(self, mock_corr, mock_monotonic, mock_close, mock_conn, mock_sleep):
        """Structure JSON exacte pour reason=time_window_exceeded."""
        mock_conn.ensure_connection.return_value = None
        mock_monotonic.side_effect = [0.0, 125.0]

        middleware = DatabaseResilienceMiddleware(_always_fail_view())
        result = middleware(self.request)

        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.get('Retry-After'), '30')

        body = json.loads(result.content)
        error = body['error']
        self.assertEqual(error['code'], 'DB_UNAVAILABLE')
        self.assertEqual(error['reason'], 'time_window_exceeded')
        self.assertEqual(error['correlation_id'], 'test-corr-tw-99')
        self.assertIsInstance(error['message'], str)

    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.get_correlation_id', return_value='test-corr-mc-77')
    def test_response_json_structure_mid_commit(self, mock_corr, mock_conn):
        """Structure JSON exacte pour reason=mid_commit_error."""
        mock_conn.in_atomic_block = False
        request = RequestFactory().post('/api/v1/executions/', data={})

        middleware = DatabaseResilienceMiddleware(_always_fail_view())
        result = middleware(request)

        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.get('Retry-After'), '30')

        body = json.loads(result.content)
        error = body['error']
        self.assertEqual(error['code'], 'DB_UNAVAILABLE')
        self.assertEqual(error['reason'], 'mid_commit_error')
        self.assertEqual(error['correlation_id'], 'test-corr-mc-77')

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_retry_after_header_is_30(self, mock_close, mock_conn, mock_sleep):
        """Header Retry-After: 30 présent pour tout type de 503."""
        mock_conn.ensure_connection.return_value = None

        middleware = DatabaseResilienceMiddleware(_always_fail_view())
        result = middleware(self.request)

        self.assertEqual(result.get('Retry-After'), '30')

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_three_distinct_messages_for_three_reasons(self, mock_close, mock_conn, mock_sleep):
        """Les 3 raisons produisent des messages distincts."""
        from core.db_resilience import DatabaseResilienceMiddleware

        mw = DatabaseResilienceMiddleware(lambda r: None)

        r1 = json.loads(mw._build_503_response("c1", reason="retry_exhausted").content)
        r2 = json.loads(mw._build_503_response("c2", reason="time_window_exceeded").content)
        r3 = json.loads(mw._build_503_response("c3", reason="mid_commit_error").content)

        msg1 = r1['error']['message']
        msg2 = r2['error']['message']
        msg3 = r3['error']['message']

        self.assertNotEqual(msg1, msg2)
        self.assertNotEqual(msg1, msg3)
        self.assertNotEqual(msg2, msg3)


# ---------------------------------------------------------------------------
# Task 5.6 — Succès avant épuisement
# ---------------------------------------------------------------------------

@override_settings(DB_RETRY_MAX_ATTEMPTS=3, DB_RETRY_BACKOFF_BASE=0.01, DB_RETRY_TIME_WINDOW_SECONDS=120)
class TestSuccessBeforeExhaustion(TestCase):
    """AC #5 : HTTP 200 si reconnexion réussit avant épuisement des bornes."""

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/api/v1/health/')

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_200_after_2_failures_then_success(self, mock_close, mock_conn, mock_sleep):
        """2 erreurs puis succès → HTTP 200 (pas de 503)."""
        mock_conn.ensure_connection.return_value = None

        middleware = DatabaseResilienceMiddleware(_success_after_n_failures(2))
        result = middleware(self.request)

        self.assertEqual(result.status_code, 200)

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_200_after_1_failure_then_success(self, mock_close, mock_conn, mock_sleep):
        """1 erreur puis succès → HTTP 200."""
        mock_conn.ensure_connection.return_value = None

        middleware = DatabaseResilienceMiddleware(_success_after_n_failures(1))
        result = middleware(self.request)

        self.assertEqual(result.status_code, 200)

    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_no_time_window_triggered_on_quick_success(self, mock_close, mock_conn, mock_sleep):
        """Succès rapide → time_window_exceeded ne se déclenche pas."""
        mock_conn.ensure_connection.return_value = None

        middleware = DatabaseResilienceMiddleware(_success_after_n_failures(1))
        result = middleware(self.request)

        # Doit être 200, pas 503 time_window_exceeded
        self.assertEqual(result.status_code, 200)
        # Pas de header Retry-After sur les succès
        self.assertIsNone(result.get('Retry-After'))


# ---------------------------------------------------------------------------
# Task 5.7 — DB_RETRY_TIME_WINDOW_SECONDS via override_settings
# ---------------------------------------------------------------------------

class TestTimeWindowConfigurable(TestCase):
    """AC #1 : DB_RETRY_TIME_WINDOW_SECONDS est configurable et respecté."""

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/api/v1/health/')

    @override_settings(DB_RETRY_MAX_ATTEMPTS=10, DB_RETRY_BACKOFF_BASE=0.0, DB_RETRY_TIME_WINDOW_SECONDS=5)
    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    @patch('core.db_resilience.time.monotonic')
    def test_time_window_5_seconds_triggers_early(self, mock_monotonic, mock_close, mock_conn, mock_sleep):
        """Avec time_window=5s, le time window se déclenche avant max_attempts=10."""
        mock_conn.ensure_connection.return_value = None
        # start=0, attempt 0 elapsed=6 > 5 → time_window_exceeded
        mock_monotonic.side_effect = [0.0, 6.0]

        middleware = DatabaseResilienceMiddleware(_always_fail_view())
        result = middleware(self.request)

        self.assertEqual(result.status_code, 503)
        body = json.loads(result.content)
        # time_window déclenché AVANT max_attempts (qui est 10)
        self.assertEqual(body['error']['reason'], 'time_window_exceeded')

    @override_settings(DB_RETRY_MAX_ATTEMPTS=2, DB_RETRY_BACKOFF_BASE=0.0, DB_RETRY_TIME_WINDOW_SECONDS=999)
    @patch('core.db_resilience.time.sleep')
    @patch('core.db_resilience.connection')
    @patch('core.db_resilience.close_old_connections')
    def test_large_time_window_allows_max_retries_first(self, mock_close, mock_conn, mock_sleep):
        """Avec time_window=999s (très grand), max_attempts se déclenche en premier."""
        mock_conn.ensure_connection.return_value = None

        middleware = DatabaseResilienceMiddleware(_always_fail_view())
        result = middleware(self.request)

        self.assertEqual(result.status_code, 503)
        body = json.loads(result.content)
        # max_attempts=2 atteint avant time_window
        self.assertEqual(body['error']['reason'], 'retry_exhausted')
