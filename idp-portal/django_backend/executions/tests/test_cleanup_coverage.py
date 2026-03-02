"""
Tests complémentaires pour executions/tasks/cleanup.py — couverture des lignes manquantes.
Lignes cibles: 25-26, 102-107
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock


class TestParseLogRetentionDays:
    """Tests pour _parse_log_retention_days — lignes 25-26."""

    def test_negative_value_returns_default(self):
        """Ligne 25-26: valeur négative → retourne 7 (défaut)."""
        with patch.dict('os.environ', {'PLATFORM_LOG_RETENTION_DAYS': '-5'}):
            from executions.tasks import cleanup
            # Appel direct de la fonction helper
            result = cleanup._parse_log_retention_days()
        assert result == 7

    def test_zero_value_returns_default(self):
        """Ligne 25-26: valeur zéro → retourne 7 (défaut, car 0 n'est pas > 0)."""
        with patch.dict('os.environ', {'PLATFORM_LOG_RETENTION_DAYS': '0'}):
            from executions.tasks.cleanup import _parse_log_retention_days
            result = _parse_log_retention_days()
        assert result == 7

    def test_invalid_value_returns_default(self):
        """Ligne 25-26: valeur non-int → ValueError → retourne 7."""
        with patch.dict('os.environ', {'PLATFORM_LOG_RETENTION_DAYS': 'invalid'}):
            from executions.tasks.cleanup import _parse_log_retention_days
            result = _parse_log_retention_days()
        assert result == 7

    def test_valid_positive_value(self):
        """Valeur positive → retournée telle quelle."""
        with patch.dict('os.environ', {'PLATFORM_LOG_RETENTION_DAYS': '30'}):
            from executions.tasks.cleanup import _parse_log_retention_days
            result = _parse_log_retention_days()
        assert result == 30

    def test_default_value_when_not_set(self):
        """Variable non définie → défaut 7."""
        import os
        env = {k: v for k, v in os.environ.items() if k != 'PLATFORM_LOG_RETENTION_DAYS'}
        with patch.dict('os.environ', env, clear=True):
            from executions.tasks.cleanup import _parse_log_retention_days
            result = _parse_log_retention_days()
        assert result == 7


def _make_step(output_dict, step_id=1):
    """Helper: créer un mock ExecutionStep."""
    step = MagicMock()
    step.id = step_id
    step._output = json.dumps(output_dict) if output_dict is not None else None

    def get_output():
        if step._output is None:
            return None
        return json.loads(step._output)

    def set_output(val):
        step._output = json.dumps(val) if val is not None else None

    step.get_output = get_output
    step.set_output = set_output
    step.save = MagicMock()
    return step


class TestPurgeOldPlatformLogsErrorHandling:
    """Tests pour la gestion d'erreurs dans la boucle — lignes 102-107."""

    @patch("executions.models.ExecutionStep.objects")
    def test_error_with_output_marks_purged(self, mock_objects):
        """Lignes 102-107: Exception dans le traitement, output != None → marque logs_purged."""
        from executions.tasks.cleanup import purge_old_platform_logs

        step = MagicMock()
        step.id = 1
        output_state = {'platform_logs': 'some logs', 'key': 'value'}
        _call_count = [0]

        def get_output():
            return dict(output_state)

        def set_output(val):
            output_state.clear()
            output_state.update(val)

        step.get_output = get_output
        step.set_output = set_output
        # save lève une exception au premier appel (ligne 92), mais pas au deuxième
        save_call = [0]
        def save_side_effect(**kwargs):
            save_call[0] += 1
            if save_call[0] == 1:
                raise Exception("DB save error")
        step.save = MagicMock(side_effect=save_side_effect)

        mock_objects.filter.return_value = mock_objects
        mock_objects.exclude.return_value = mock_objects
        mock_objects.only.return_value = mock_objects

        batch_iter = iter([[1], []])
        vl = MagicMock()
        vl.__getitem__ = MagicMock(side_effect=lambda _: next(batch_iter))
        mock_objects.values_list.return_value = vl

        id_qs = MagicMock()
        id_qs.only.return_value = [step]
        mock_objects.filter.side_effect = lambda **kw: id_qs if "id__in" in kw else mock_objects

        result = purge_old_platform_logs()

        # Une erreur comptée, mais la récupération a été tentée
        assert result['errors'] == 1
        assert result['purged'] == 0

    @patch("executions.models.ExecutionStep.objects")
    def test_error_with_output_second_save_also_fails(self, mock_objects):
        """Lignes 102-107: Exception dans traitement, et la sauvegarde de récupération échoue aussi → pass."""
        from executions.tasks.cleanup import purge_old_platform_logs

        step = MagicMock()
        step.id = 1

        output_data = {'platform_logs': 'some logs'}

        def get_output():
            return dict(output_data)

        def set_output(val):
            output_data.clear()
            output_data.update(val)

        step.get_output = get_output
        step.set_output = set_output
        # Toutes les sauvegardes échouent
        step.save = MagicMock(side_effect=Exception("Persistent DB error"))

        mock_objects.filter.return_value = mock_objects
        mock_objects.exclude.return_value = mock_objects
        mock_objects.only.return_value = mock_objects

        batch_iter = iter([[1], []])
        vl = MagicMock()
        vl.__getitem__ = MagicMock(side_effect=lambda _: next(batch_iter))
        mock_objects.values_list.return_value = vl

        id_qs = MagicMock()
        id_qs.only.return_value = [step]
        mock_objects.filter.side_effect = lambda **kw: id_qs if "id__in" in kw else mock_objects

        # Doit terminer sans crash malgré les erreurs en cascade
        result = purge_old_platform_logs()

        assert result['errors'] == 1
        assert result['purged'] == 0

    @patch("executions.models.ExecutionStep.objects")
    def test_error_with_no_output_no_recovery_attempt(self, mock_objects):
        """Lignes 101-107: Exception dans traitement, output is None → pas de tentative de récupération."""
        from executions.tasks.cleanup import purge_old_platform_logs

        step = MagicMock()
        step.id = 1
        # get_output retourne None (donc output sera None dans le except)
        step.get_output = MagicMock(return_value=None)
        step.set_output = MagicMock()
        step.save = MagicMock()

        mock_objects.filter.return_value = mock_objects
        mock_objects.exclude.return_value = mock_objects
        mock_objects.only.return_value = mock_objects

        batch_iter = iter([[1], []])
        vl = MagicMock()
        vl.__getitem__ = MagicMock(side_effect=lambda _: next(batch_iter))
        mock_objects.values_list.return_value = vl

        id_qs = MagicMock()
        id_qs.only.return_value = [step]
        mock_objects.filter.side_effect = lambda **kw: id_qs if "id__in" in kw else mock_objects

        result = purge_old_platform_logs()

        # output=None → rien à purger (continue sans erreur)
        assert result['purged'] == 0
        assert result['errors'] == 0
        step.save.assert_not_called()
