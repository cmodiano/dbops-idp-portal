"""
Tests pour l'intégration du polling AAP avec output_fields.
Story 63.2 - AC3: Convention AAP dans le polling.

Couvre:
- Stockage des champs AAP standard dans l'output du step
- Preservation de platform_logs si déjà présent
- Construction de error_summary depuis failed_tasks
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from executions.tasks.polling import _update_execution_from_poll
from tests.factories import ExecutionFactory, ExecutionStepFactory


# ---------------------------------------------------------------------------
# Tests _update_execution_from_poll avec output_fields
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUpdateExecutionFromPollWithOutputFields:
    """AC3: _update_execution_from_poll stocke output_fields dans l'output du step."""

    def _make_execution_and_step(self, job_id='job-123'):
        """Créer une exécution avec un step platform via factories."""
        execution = ExecutionFactory(status='RUNNING')
        step = ExecutionStepFactory(
            execution=execution,
            platform_job_id=job_id,
            status='RUNNING',
        )
        return execution, step

    def test_output_fields_stored_in_step(self):
        """AC3: Les champs output_fields sont stockés dans l'output du step."""
        execution, step = self._make_execution_and_step()

        output_fields = {
            'platform_job_id': 'job-123',
            'job_status': 'COMPLETED',
        }
        _update_execution_from_poll(
            execution_id=execution.id,
            platform_job_id='job-123',
            idp_status='RUNNING',
            logs_content='',
            output_fields=output_fields,
        )
        step.refresh_from_db()
        output = step.get_output() or {}
        assert output.get('platform_job_id') == 'job-123'
        assert output.get('job_status') == 'COMPLETED'

    def test_platform_logs_preserved_with_output_fields(self):
        """AC3: platform_logs est préservé quand output_fields est fourni."""
        execution, step = self._make_execution_and_step(job_id='job-456')

        output_fields = {
            'platform_job_id': 'job-456',
            'job_status': 'RUNNING',
        }
        _update_execution_from_poll(
            execution_id=execution.id,
            platform_job_id='job-456',
            idp_status='RUNNING',
            logs_content='Log line 1\nLog line 2',
            output_fields=output_fields,
        )
        step.refresh_from_db()
        output = step.get_output() or {}
        assert output.get('platform_logs') == 'Log line 1\nLog line 2'
        assert output.get('platform_job_id') == 'job-456'
        assert output.get('job_status') == 'RUNNING'

    def test_no_output_fields_backward_compat(self):
        """AC3: Sans output_fields, le comportement existant est préservé."""
        execution, step = self._make_execution_and_step(job_id='job-789')

        _update_execution_from_poll(
            execution_id=execution.id,
            platform_job_id='job-789',
            idp_status='RUNNING',
            logs_content='Some logs',
            output_fields=None,
        )
        step.refresh_from_db()
        output = step.get_output() or {}
        assert output.get('platform_logs') == 'Some logs'
        assert 'platform_job_id' not in output


# ---------------------------------------------------------------------------
# Tests de construction de output_fields dans poll_platform_job_status
# ---------------------------------------------------------------------------


class TestPollPlatformJobStatusOutputFields:
    """AC3: poll_platform_job_status construit et passe output_fields correctement."""

    @patch('executions.tasks._broadcast_execution_update')
    @patch('executions.tasks._update_execution_from_poll')
    @patch('executions.tasks.get_correlation_id', return_value='test-corr-output')
    def test_output_fields_passed_to_update(
        self,
        mock_corr: MagicMock,
        mock_update: MagicMock,
        mock_broadcast: MagicMock,
    ):
        """AC3: poll_platform_job_status passe output_fields avec platform_job_id et job_status."""
        from unittest.mock import AsyncMock
        from executions.tasks.polling import poll_platform_job_status

        mock_adapter = MagicMock()
        mock_adapter.get_status = AsyncMock(return_value={
            'status': 'RUNNING',
            'aap_status': 'running',
        })
        mock_adapter.get_job_logs = AsyncMock(return_value={
            'complete': False,
            'content': 'running...',
        })

        with patch('adapters.get_platform_adapter', return_value=mock_adapter):
            with patch('adapters.utils.build_auth_headers_from_credentials', return_value={}):
                with patch.object(poll_platform_job_status, 'apply_async'):
                    poll_platform_job_status(
                        execution_id=1,
                        platform_job_id='job-aap-001',
                        platform_type='aap',
                    )

        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args.kwargs
        assert 'output_fields' in call_kwargs
        output_fields = call_kwargs['output_fields']
        assert output_fields['platform_job_id'] == 'job-aap-001'
        assert output_fields['job_status'] == 'running'

    @patch('executions.tasks._broadcast_execution_update')
    @patch('executions.tasks._update_execution_from_poll')
    @patch('executions.tasks.get_correlation_id', return_value='test-corr-error-summary')
    def test_error_summary_built_from_failed_tasks(
        self,
        mock_corr: MagicMock,
        mock_update: MagicMock,
        mock_broadcast: MagicMock,
    ):
        """AC3: error_summary est extrait depuis failed_tasks si disponible."""
        from unittest.mock import AsyncMock
        from executions.tasks.polling import poll_platform_job_status

        mock_adapter = MagicMock()
        mock_adapter.get_status = AsyncMock(return_value={
            'status': 'FAILED',
            'aap_status': 'failed',
            'failed_tasks': [{'task': 'Install packages', 'host': 'web01'}],
        })
        mock_adapter.get_job_logs = AsyncMock(return_value={
            'complete': True,
            'content': 'failed',
        })

        with patch('adapters.get_platform_adapter', return_value=mock_adapter):
            with patch('adapters.utils.build_auth_headers_from_credentials', return_value={}):
                poll_platform_job_status(
                    execution_id=1,
                    platform_job_id='job-failed-001',
                    platform_type='aap',
                )

        call_kwargs = mock_update.call_args.kwargs
        output_fields = call_kwargs['output_fields']
        assert output_fields.get('error_summary') == 'Install packages sur web01'
        assert output_fields.get('failed_tasks') == [{'task': 'Install packages', 'host': 'web01'}]

    @patch('executions.tasks._broadcast_execution_update')
    @patch('executions.tasks._update_execution_from_poll')
    @patch('executions.tasks.get_correlation_id', return_value='test-corr-no-failed')
    def test_no_error_summary_when_no_failed_tasks(
        self,
        mock_corr: MagicMock,
        mock_update: MagicMock,
        mock_broadcast: MagicMock,
    ):
        """AC3: Pas d'error_summary si failed_tasks est vide."""
        from unittest.mock import AsyncMock
        from executions.tasks.polling import poll_platform_job_status

        mock_adapter = MagicMock()
        mock_adapter.get_status = AsyncMock(return_value={
            'status': 'COMPLETED',
            'aap_status': 'successful',
        })
        mock_adapter.get_job_logs = AsyncMock(return_value={
            'complete': True,
            'content': 'done',
        })

        with patch('adapters.get_platform_adapter', return_value=mock_adapter):
            with patch('adapters.utils.build_auth_headers_from_credentials', return_value={}):
                poll_platform_job_status(
                    execution_id=1,
                    platform_job_id='job-ok-001',
                    platform_type='aap',
                )

        call_kwargs = mock_update.call_args.kwargs
        output_fields = call_kwargs['output_fields']
        assert 'error_summary' not in output_fields
        assert 'failed_tasks' not in output_fields

    @patch('executions.tasks._broadcast_execution_update')
    @patch('executions.tasks._update_execution_from_poll')
    @patch('executions.tasks.get_correlation_id', return_value='test-corr-artifacts')
    def test_artifacts_stored_in_output_fields(
        self,
        mock_corr: MagicMock,
        mock_update: MagicMock,
        mock_broadcast: MagicMock,
    ):
        """AC3: output_fields contient "artifacts" avec les vars custom set_stats."""
        from unittest.mock import AsyncMock
        from executions.tasks.polling import poll_platform_job_status

        mock_adapter = MagicMock()
        mock_adapter.get_status = AsyncMock(return_value={
            'status': 'COMPLETED',
            'aap_status': 'successful',
            'artifacts': {'app_version': '2.0.0', 'deploy_env': 'prod'},
        })
        mock_adapter.get_job_logs = AsyncMock(return_value={
            'complete': True,
            'content': 'done',
        })

        with patch('adapters.get_platform_adapter', return_value=mock_adapter):
            with patch('adapters.utils.build_auth_headers_from_credentials', return_value={}):
                poll_platform_job_status(
                    execution_id=1,
                    platform_job_id='job-artifacts-001',
                    platform_type='aap',
                )

        call_kwargs = mock_update.call_args.kwargs
        output_fields = call_kwargs['output_fields']
        assert 'artifacts' in output_fields
        assert output_fields['artifacts'] == {'app_version': '2.0.0', 'deploy_env': 'prod'}

    @patch('executions.tasks._broadcast_execution_update')
    @patch('executions.tasks._update_execution_from_poll')
    @patch('executions.tasks.get_correlation_id', return_value='test-corr-no-artifacts')
    def test_artifacts_empty_when_no_set_stats(
        self,
        mock_corr: MagicMock,
        mock_update: MagicMock,
        mock_broadcast: MagicMock,
    ):
        """AC3: artifacts={} dans output_fields quand le playbook n'utilise pas set_stats."""
        from unittest.mock import AsyncMock
        from executions.tasks.polling import poll_platform_job_status

        mock_adapter = MagicMock()
        mock_adapter.get_status = AsyncMock(return_value={
            'status': 'COMPLETED',
            'aap_status': 'successful',
            # pas de clé "artifacts"
        })
        mock_adapter.get_job_logs = AsyncMock(return_value={
            'complete': True,
            'content': 'done',
        })

        with patch('adapters.get_platform_adapter', return_value=mock_adapter):
            with patch('adapters.utils.build_auth_headers_from_credentials', return_value={}):
                poll_platform_job_status(
                    execution_id=1,
                    platform_job_id='job-no-artifacts-001',
                    platform_type='aap',
                )

        call_kwargs = mock_update.call_args.kwargs
        output_fields = call_kwargs['output_fields']
        assert 'artifacts' in output_fields
        assert output_fields['artifacts'] == {}

    @patch('executions.tasks._broadcast_execution_update')
    @patch('executions.tasks._update_execution_from_poll')
    @patch('executions.tasks.get_correlation_id', return_value='test-corr-gha-outputs')
    def test_github_actions_outputs_and_artifacts_in_output_fields(
        self,
        mock_corr: MagicMock,
        mock_update: MagicMock,
        mock_broadcast: MagicMock,
    ):
        """AC4: output_fields contient outputs et artifacts pour github_actions."""
        from unittest.mock import AsyncMock
        from executions.tasks.polling import poll_platform_job_status

        mock_adapter = MagicMock()
        mock_adapter.get_status = AsyncMock(return_value={
            'status': 'COMPLETED',
            'github_actions_status': 'completed',
            'job_conclusion': 'success',
            'outputs': {'build': 'success', 'deploy': 'success'},
            'artifacts': [{'name': 'dist', 'archive_download_url': 'https://...', 'size_in_bytes': 1024, 'expired': False}],
        })
        mock_adapter.get_job_logs = AsyncMock(return_value={
            'complete': True, 'content': 'logs...',
        })

        with patch('adapters.get_platform_adapter', return_value=mock_adapter):
            with patch('adapters.utils.build_auth_headers_from_credentials', return_value={}):
                poll_platform_job_status(
                    execution_id=1,
                    platform_job_id='run-gha-001',
                    platform_type='github_actions',
                )

        call_kwargs = mock_update.call_args.kwargs
        output_fields = call_kwargs['output_fields']
        assert output_fields['outputs'] == {'build': 'success', 'deploy': 'success'}
        assert output_fields['artifacts'] == [{'name': 'dist', 'archive_download_url': 'https://...', 'size_in_bytes': 1024, 'expired': False}]
        assert output_fields['job_conclusion'] == 'success'

    @patch('executions.tasks._broadcast_execution_update')
    @patch('executions.tasks._update_execution_from_poll')
    @patch('executions.tasks.get_correlation_id', return_value='test-corr-no-artifacts-default')
    def test_artifacts_defaults_to_empty_dict_when_absent(
        self,
        mock_corr: MagicMock,
        mock_update: MagicMock,
        mock_broadcast: MagicMock,
    ):
        """AC4: non-régression AAP — artifacts={} par défaut quand status_data sans 'artifacts'."""
        from unittest.mock import AsyncMock
        from executions.tasks.polling import poll_platform_job_status

        mock_adapter = MagicMock()
        mock_adapter.get_status = AsyncMock(return_value={
            'status': 'COMPLETED',
            'aap_status': 'successful',
            # Pas de clé "artifacts"
        })
        mock_adapter.get_job_logs = AsyncMock(return_value={
            'complete': True, 'content': '',
        })

        with patch('adapters.get_platform_adapter', return_value=mock_adapter):
            with patch('adapters.utils.build_auth_headers_from_credentials', return_value={}):
                poll_platform_job_status(
                    execution_id=1,
                    platform_job_id='job-no-artifacts',
                    platform_type='aap',
                )

        call_kwargs = mock_update.call_args.kwargs
        output_fields = call_kwargs['output_fields']
        assert output_fields['artifacts'] == {}
        assert 'outputs' not in output_fields
