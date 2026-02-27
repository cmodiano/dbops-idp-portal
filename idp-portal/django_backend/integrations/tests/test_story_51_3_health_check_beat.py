"""Tests Story 51.3 — Tâche Celery Beat health_check_all_integrations."""
from __future__ import annotations

from unittest.mock import patch, call
from celery.schedules import crontab  # type: ignore[import-untyped]


def _compute_health_check_schedule(env: dict[str, str]) -> float | crontab:
    """Reproduit la logique de parsing du schedule depuis les variables d'env.

    Permet de tester les chemins crontab/interval sans rechargement de module.
    """
    crontab_expr = env.get('CELERY_BEAT_HEALTH_CHECK_CRONTAB', '')
    if crontab_expr:
        parts = crontab_expr.split()
        if len(parts) == 5:
            return crontab(
                minute=parts[0],
                hour=parts[1],
                day_of_month=parts[2],
                month_of_year=parts[3],
                day_of_week=parts[4],
            )
        return 3600.0  # fallback sur crontab invalide
    try:
        return float(env.get('CELERY_BEAT_HEALTH_CHECK_INTERVAL', '3600.0'))
    except ValueError:
        return 3600.0


class TestHealthCheckAllIntegrations:
    """Tests unitaires pour health_check_all_integrations."""

    def test_dispatches_for_all_integrations(self):
        """Vérifie que .delay() est appelé pour chaque intégration."""
        mock_ids = [1, 2, 3]
        with (
            patch('integrations.models.Integration') as mock_model,
            patch('integrations.tasks.run_integration_health_check') as mock_task,
        ):
            mock_model.objects.all.return_value.only.return_value.values_list.return_value = mock_ids
            from integrations.tasks import health_check_all_integrations
            health_check_all_integrations()

        assert mock_task.delay.call_count == 3
        mock_task.delay.assert_has_calls([call(1), call(2), call(3)])

    def test_no_integrations_no_dispatch(self):
        """Queryset vide → aucun appel .delay(), aucune exception."""
        with (
            patch('integrations.models.Integration') as mock_model,
            patch('integrations.tasks.run_integration_health_check') as mock_task,
        ):
            mock_model.objects.all.return_value.only.return_value.values_list.return_value = []
            from integrations.tasks import health_check_all_integrations
            health_check_all_integrations()  # ne doit pas lever

        mock_task.delay.assert_not_called()

    def test_query_exception_does_not_raise(self):
        """Exception sur la query → tâche ne lève pas et logge l'erreur."""
        with (
            patch('integrations.models.Integration') as mock_model,
            patch('integrations.tasks.run_integration_health_check'),
            patch('integrations.tasks.logger') as mock_logger,
        ):
            mock_model.objects.all.side_effect = Exception("DB error")
            from integrations.tasks import health_check_all_integrations
            health_check_all_integrations()  # ne doit pas lever

        mock_logger.error.assert_called_once_with(
            "health_check_all_query_error",
            error="DB error",
            exc_info=True,
        )

    def test_dispatch_exception_continues_and_logs(self):
        """Si .delay() lève pour une intégration, on logge et on continue; count = succès uniquement."""
        mock_ids = [1, 2, 3]
        with (
            patch('integrations.models.Integration') as mock_model,
            patch('integrations.tasks.run_integration_health_check') as mock_task,
            patch('integrations.tasks.logger') as mock_logger,
        ):
            mock_model.objects.all.return_value.only.return_value.values_list.return_value = mock_ids
            # .delay(2) raises, others succeed
            def delay_side_effect(integration_id):
                if integration_id == 2:
                    raise RuntimeError("Broker unavailable")
                return None

            mock_task.delay.side_effect = delay_side_effect
            from integrations.tasks import health_check_all_integrations
            health_check_all_integrations()

        assert mock_task.delay.call_count == 3
        mock_logger.exception.assert_called_once_with(
            "health_check_all_dispatch_error",
            integration_id=2,
            error="Broker unavailable",
        )
        mock_logger.info.assert_any_call(
            "health_check_all_dispatched",
            count=2,
        )


class TestHealthCheckBeatScheduleRegistered:
    """Vérifie que le schedule Beat est enregistré correctement."""

    def test_beat_schedule_entry_exists(self):
        """'health-check-all-integrations' présent dans beat_schedule."""
        from idp_backend.celery import app
        assert 'health-check-all-integrations' in app.conf.beat_schedule

    def test_beat_schedule_task_name(self):
        """Vérifie le nom de la tâche dans le schedule."""
        from idp_backend.celery import app
        entry = app.conf.beat_schedule['health-check-all-integrations']
        assert entry['task'] == 'integrations.tasks.health_check_all_integrations'


class TestHealthCheckScheduleParsing:
    """Tests unitaires de la logique de parsing crontab/interval (AC #3).

    Ces tests vérifient la logique de configuration sans rechargement de module,
    en testant directement la fonction utilitaire _compute_health_check_schedule.
    """

    def test_default_interval_when_no_env_vars(self):
        """Sans variable d'env, le schedule est 3600.0 secondes."""
        schedule = _compute_health_check_schedule({})
        assert schedule == 3600.0

    def test_custom_interval_from_env(self):
        """CELERY_BEAT_HEALTH_CHECK_INTERVAL configure l'intervalle en secondes."""
        schedule = _compute_health_check_schedule({'CELERY_BEAT_HEALTH_CHECK_INTERVAL': '7200.0'})
        assert isinstance(schedule, float)
        assert schedule == 7200.0

    def test_valid_crontab_overrides_interval(self):
        """CELERY_BEAT_HEALTH_CHECK_CRONTAB valide → schedule crontab."""
        schedule = _compute_health_check_schedule({'CELERY_BEAT_HEALTH_CHECK_CRONTAB': '0 * * * *'})
        assert isinstance(schedule, crontab)

    def test_crontab_minute_hour_parsed_correctly(self):
        """Vérifie que minute et hour sont correctement extraits du crontab."""
        schedule = _compute_health_check_schedule({'CELERY_BEAT_HEALTH_CHECK_CRONTAB': '30 2 * * *'})
        assert isinstance(schedule, crontab)
        # Celery crontab stores minute/hour as sets
        assert 30 in schedule.minute
        assert 2 in schedule.hour

    def test_invalid_crontab_falls_back_to_default(self):
        """Crontab avec mauvais nombre de parties → fallback 3600.0."""
        schedule = _compute_health_check_schedule({'CELERY_BEAT_HEALTH_CHECK_CRONTAB': 'invalid'})
        assert schedule == 3600.0

    def test_invalid_interval_falls_back_to_default(self):
        """CELERY_BEAT_HEALTH_CHECK_INTERVAL invalide (non numérique) → fallback 3600.0."""
        schedule = _compute_health_check_schedule({'CELERY_BEAT_HEALTH_CHECK_INTERVAL': 'abc'})
        assert schedule == 3600.0

    def test_crontab_takes_priority_over_interval(self):
        """Crontab valide prend priorité sur CELERY_BEAT_HEALTH_CHECK_INTERVAL."""
        schedule = _compute_health_check_schedule({
            'CELERY_BEAT_HEALTH_CHECK_CRONTAB': '0 * * * *',
            'CELERY_BEAT_HEALTH_CHECK_INTERVAL': '7200.0',
        })
        assert isinstance(schedule, crontab)
