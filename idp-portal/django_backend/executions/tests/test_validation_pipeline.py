"""
Story 71.5 (AC6): Tests unitaires du ExecutionValidationPipeline.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from core.exceptions import BadRequestError, ForbiddenError
from executions.validators.pipeline import ExecutionValidationPipeline
from executions.validators.result import ExecutionValidationResult
from tests.factories import UserFactory, ActionFactory


@pytest.mark.django_db
class TestExecutionValidationPipeline(TestCase):
    """Tests unitaires pour ExecutionValidationPipeline."""

    def setUp(self) -> None:
        self.rf = APIRequestFactory()
        self.user = UserFactory(username='pipeline_test_user', profile='DBA')
        self.action = ActionFactory(
            status='published', created_by=self.user,
            item_type='action', requires_target=True,
        )
        self.wf_action = ActionFactory(
            status='published', created_by=self.user,
            item_type='workflow', requires_target=True,
        )

    def _make_request(self, data: dict | None = None) -> MagicMock:
        """Create a mock DRF request."""
        request = MagicMock()
        request.data = data or {}
        request.META = {
            'HTTP_X_CORRELATION_ID': 'test-corr-pipeline',
        }
        request.user = self.user
        return request

    def _mock_env_config(self) -> dict:
        return {
            'change_required': False,
            'change_model_code': None,
            'impact_level': 'low',
            'requires_maintenance_window': False,
            'requires_approval': False,
            'env_str': 'dev',
        }

    # ── Test 1: Payload invalide (action_id manquant) ─────────────────────

    def test_payload_invalid_missing_action_id(self) -> None:
        """Payload sans action_id -> BadRequestError."""
        request = self._make_request(data={})
        with pytest.raises(BadRequestError) as exc_info:
            ExecutionValidationPipeline.validate(
                request_data={},
                request=request,
                user=self.user,
                ip_address='127.0.0.1',
            )
        assert exc_info.value.code == 'BAD_REQUEST'
        assert 'action_id' in exc_info.value.message

    # ── Test 2: Payload invalide (action non publiée) ─────────────────────

    def test_payload_invalid_unpublished_action(self) -> None:
        """action_id d'une action non publiée -> NotFoundError."""
        from core.exceptions import NotFoundError
        unpublished = ActionFactory(status='draft', created_by=self.user)
        request = self._make_request()
        with pytest.raises(NotFoundError) as exc_info:
            ExecutionValidationPipeline.validate(
                request_data={'action_id': unpublished.id},
                request=request,
                user=self.user,
                ip_address='127.0.0.1',
            )
        assert exc_info.value.code == 'ACTION_NOT_FOUND'

    # ── Test 3: Target non autorisée -> ForbiddenError ────────────────────

    def test_target_unauthorized_raises_forbidden(self) -> None:
        """Target non autorisée -> ForbiddenError."""
        request = self._make_request()
        payload = {
            'action_id': self.action.id,
            'target_names': ['forbidden_server'],
        }

        with patch(
            'executions.validators.payload_validator.ExecutionPayloadValidator.validate_action',
            return_value=self.action,
        ):
            with patch(
                'executions.validators.target_validator.TargetValidator.validate_targets',
                side_effect=ForbiddenError(
                    code='FORBIDDEN',
                    message='Cible non autorisée: forbidden_server',
                    details={'target_name': 'forbidden_server'},
                ),
            ):
                with pytest.raises(ForbiddenError) as exc_info:
                    ExecutionValidationPipeline.validate(
                        request_data=payload,
                        request=request,
                        user=self.user,
                        ip_address='127.0.0.1',
                    )
                assert exc_info.value.code == 'FORBIDDEN'
                assert 'forbidden_server' in exc_info.value.message

    # ── Test 4: Mutex bloqué -> BadRequestError ───────────────────────────

    def test_mutex_blocked_raises_bad_request(self) -> None:
        """Mutex violation -> BadRequestError."""
        request = self._make_request()
        payload = {
            'action_id': self.action.id,
            'target_names': ['server1'],
        }

        with patch(
            'executions.validators.payload_validator.ExecutionPayloadValidator.validate_action',
            return_value=self.action,
        ):
            with patch(
                'executions.validators.target_validator.TargetValidator.validate_targets',
                return_value=([{'name': 'server1', 'environment': 'dev'}], 'dev'),
            ):
                with patch(
                    'executions.validators.env_config_resolver.EnvironmentConfigResolver.resolve',
                    return_value=self._mock_env_config(),
                ):
                    with patch(
                        'executions.validators.workflow_validator.WorkflowValidator.reject_step_parameters_for_non_workflow',
                    ):
                        with patch(
                            'executions.validators.mutex_validator.MutexValidator.validate',
                            side_effect=BadRequestError(
                                code='MUTEX_VIOLATION',
                                message='Action mutex constraint violated',
                                details={},
                            ),
                        ):
                            with pytest.raises(BadRequestError) as exc_info:
                                ExecutionValidationPipeline.validate(
                                    request_data=payload,
                                    request=request,
                                    user=self.user,
                                    ip_address='127.0.0.1',
                                )
                            assert exc_info.value.code == 'MUTEX_VIOLATION'

    # ── Test 5: Workflow valide complet -> ExecutionValidationResult ───────

    def test_workflow_valid_complete(self) -> None:
        """Workflow complet avec targets -> ExecutionValidationResult correct."""
        request = self._make_request()
        payload = {
            'action_id': self.wf_action.id,
            'target_names': ['server1', 'server2'],
            'workflow_step_parameters': {'1': {'param': 'val'}},
        }

        validated_targets = [
            {'name': 'server1', 'environment': 'dev'},
            {'name': 'server2', 'environment': 'dev'},
        ]

        with patch(
            'executions.validators.payload_validator.ExecutionPayloadValidator.validate_action',
            return_value=self.wf_action,
        ):
            with patch(
                'executions.validators.target_validator.TargetValidator.validate_targets',
                return_value=(validated_targets, 'dev'),
            ):
                with patch(
                    'executions.validators.env_config_resolver.EnvironmentConfigResolver.resolve',
                    return_value=self._mock_env_config(),
                ):
                    with patch(
                        'executions.validators.workflow_validator.WorkflowValidator.validate_referenced_actions',
                        return_value=[10, 20],
                    ):
                        with patch(
                            'executions.validators.workflow_validator.WorkflowValidator.validate_step_parameters',
                            return_value={'1': {'param': 'val'}},
                        ):
                            with patch(
                                'executions.validators.mutex_validator.MutexValidator.validate',
                            ):
                                result = ExecutionValidationPipeline.validate(
                                    request_data=payload,
                                    request=request,
                                    user=self.user,
                                    ip_address='127.0.0.1',
                                )

        assert isinstance(result, ExecutionValidationResult)
        assert result.action == self.wf_action
        assert result.environment == 'dev'
        assert result.validated_targets == validated_targets
        assert result.delegated_referenced_action_ids == [10, 20]
        assert result.target_names == ['server1', 'server2']
        assert result.correlation_id == 'test-corr-pipeline'

    # ── Test 6: Exécution sans target (environment direct) ────────────────

    def test_execution_without_target_environment_direct(self) -> None:
        """Action sans target (requires_target=False, environment direct) -> validated_targets is None."""
        no_target_action = ActionFactory(
            status='published', created_by=self.user,
            item_type='action', requires_target=False,
        )
        request = self._make_request()
        payload = {
            'action_id': no_target_action.id,
            'environment': 'prod',
        }

        with patch(
            'executions.validators.payload_validator.ExecutionPayloadValidator.validate_action',
            return_value=no_target_action,
        ):
            with patch(
                'executions.validators.env_config_resolver.EnvironmentConfigResolver.resolve',
                return_value={
                    'change_required': False, 'change_model_code': None,
                    'impact_level': 'high', 'requires_maintenance_window': False,
                    'requires_approval': False, 'env_str': 'prod',
                },
            ):
                with patch(
                    'executions.validators.workflow_validator.WorkflowValidator.reject_step_parameters_for_non_workflow',
                ):
                    with patch(
                        'executions.validators.mutex_validator.MutexValidator.validate',
                    ):
                        result = ExecutionValidationPipeline.validate(
                            request_data=payload,
                            request=request,
                            user=self.user,
                            ip_address='127.0.0.1',
                        )

        assert isinstance(result, ExecutionValidationResult)
        assert result.validated_targets is None
        assert result.target_names is None
        assert result.environment == 'prod'
        assert result.requires_target is False

    # ── Test 7: Pipeline préserve page_me et correlation_id ───────────────

    def test_pipeline_preserves_page_me_and_correlation(self) -> None:
        """page_me et correlation_id sont correctement propagés."""
        request = self._make_request()
        payload = {
            'action_id': self.action.id,
            'environment': 'dev',
            'target_names': ['server1'],
            'page_me': True,
        }

        with patch(
            'executions.validators.payload_validator.ExecutionPayloadValidator.validate_action',
            return_value=self.action,
        ):
            with patch(
                'executions.validators.target_validator.TargetValidator.validate_targets',
                return_value=([{'name': 'server1', 'environment': 'dev'}], 'dev'),
            ):
                with patch(
                    'executions.validators.env_config_resolver.EnvironmentConfigResolver.resolve',
                    return_value=self._mock_env_config(),
                ):
                    with patch(
                        'executions.validators.workflow_validator.WorkflowValidator.reject_step_parameters_for_non_workflow',
                    ):
                        with patch(
                            'executions.validators.mutex_validator.MutexValidator.validate',
                        ):
                            result = ExecutionValidationPipeline.validate(
                                request_data=payload,
                                request=request,
                                user=self.user,
                                ip_address='127.0.0.1',
                            )

        assert result.correlation_id == 'test-corr-pipeline'
        assert result.page_me is True
        assert result.env_config is not None
        assert result.env_config['impact_level'] == 'low'
