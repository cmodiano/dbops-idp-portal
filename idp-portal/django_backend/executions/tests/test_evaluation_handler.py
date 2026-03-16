"""
Tests unitaires pour EvaluationHandler (story 57.6).

Teste l'intégration avec RuleEngine via proxy objects (SimpleNamespace).
Pas de base de données nécessaire — tous les accès ORM sont mockés.
"""
import pytest
from unittest.mock import patch, MagicMock

from executions.step_handlers.evaluation_handler import EvaluationHandler
from executions.models import ExecutionStatus
from executions.policy_evaluator import PolicyDecision, PolicyEvaluationError


class TestEvaluationHandler:
    """Tests de EvaluationHandler.execute() (story 57.6)."""

    def setup_method(self):
        self.handler = EvaluationHandler()

    def _make_execution(self, exec_id=1):
        m = MagicMock()
        m.id = exec_id
        return m

    def _make_step_config(self, policy_id=7, artifact_type='terraform_cloud', policy=None):
        cfg = {
            'step_type': 'evaluation',
            'step_id': 'check-plan',
            'name': 'Analyze Plan',
            'artifact_type': artifact_type,
        }
        if policy_id is not None:
            cfg['policy_id'] = policy_id
        if policy is not None:
            cfg['policy'] = policy
        return cfg

    @patch('executions.app.handlers.evaluation_handler.RuleEngine')
    @patch('executions.app.handlers.evaluation_handler.BusinessRulePolicy')
    def test_auto_approved_returns_completed(self, mock_brp_class, mock_engine_class):
        """AC#3 : decision auto_approved → ExecutionStatus.COMPLETED."""
        mock_brp_class.objects.get.return_value = MagicMock(policy_json={})
        mock_engine = mock_engine_class.return_value
        mock_engine.evaluate.return_value = PolicyDecision(
            require_approval=False,
            decision_reason="Auto-approved: no review criteria matched",
        )

        step_config = self._make_step_config()
        result = self.handler.execute(
            step_config=step_config,
            resolved_params={'artifact': {'plan': 'data'}},
            execution=self._make_execution(),
            step=step_config,
            correlation_id='corr-123',
        )

        assert result['decision'] == 'auto_approved'
        assert result['status'] == ExecutionStatus.COMPLETED
        assert result['decision_reason'] == "Auto-approved: no review criteria matched"

    @patch('executions.app.handlers.evaluation_handler.RuleEngine')
    @patch('executions.app.handlers.evaluation_handler.BusinessRulePolicy')
    def test_requires_approval_returns_failed(self, mock_brp_class, mock_engine_class):
        """AC#2 : decision requires_approval → ExecutionStatus.FAILED."""
        mock_brp_class.objects.get.return_value = MagicMock(policy_json={})
        mock_engine = mock_engine_class.return_value
        mock_engine.evaluate.return_value = PolicyDecision(
            require_approval=True,
            decision_reason="Matched 1 review criteria: resource_type=aws_iam_role",
            matched_criteria=[{'criteria_index': 0, 'description': 'resource_type=aws_iam_role'}],
        )

        step_config = self._make_step_config()
        result = self.handler.execute(
            step_config=step_config,
            resolved_params={'artifact': {'changes': []}},
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )

        assert result['decision'] == 'requires_approval'
        assert result['status'] == ExecutionStatus.FAILED
        assert result['matched_criteria'] == [{'criteria_index': 0, 'description': 'resource_type=aws_iam_role'}]

    @patch('executions.app.handlers.evaluation_handler.RuleEngine')
    @patch('executions.app.handlers.evaluation_handler.BusinessRulePolicy')
    def test_policy_id_loaded_from_db(self, mock_brp_class, mock_engine_class):
        """AC#1 : policy_id → BusinessRulePolicy.objects.get(id=policy_id) appelé."""
        mock_policy_obj = MagicMock(policy_json={'on_step_output': []})
        mock_brp_class.objects.get.return_value = mock_policy_obj
        mock_engine_class.return_value.evaluate.return_value = PolicyDecision(
            require_approval=False, decision_reason="No rules"
        )

        step_config = self._make_step_config(policy_id=42)
        self.handler.execute(
            step_config=step_config,
            resolved_params={},
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )

        mock_brp_class.objects.get.assert_called_once_with(id=42)

    @patch('executions.app.handlers.evaluation_handler.RuleEngine')
    @patch('executions.app.handlers.evaluation_handler.BusinessRulePolicy')
    def test_artifact_passed_to_rule_engine(self, mock_brp_class, mock_engine_class):
        """AC#1 : resolved_params['artifact'] passé comme step_output à RuleEngine."""
        mock_brp_class.objects.get.return_value = MagicMock()
        mock_engine = mock_engine_class.return_value
        mock_engine.evaluate.return_value = PolicyDecision(
            require_approval=False, decision_reason="ok"
        )

        artifact = {'health': 'ok', 'databases': ['db1']}
        step_config = self._make_step_config()
        self.handler.execute(
            step_config=step_config,
            resolved_params={'artifact': artifact},
            execution=self._make_execution(),
            step=step_config,
            correlation_id='corr-abc',
        )

        call_args = mock_engine.evaluate.call_args
        assert call_args[0][2] == artifact  # 3ème argument positionnel

    @patch('executions.app.handlers.evaluation_handler.RuleEngine')
    @patch('executions.app.handlers.evaluation_handler.BusinessRulePolicy')
    def test_inline_policy_no_policy_id(self, mock_brp_class, mock_engine_class):
        """AC#5 : pas de policy_id → policy inline utilisée (pas d'accès DB)."""
        mock_engine_class.return_value.evaluate.return_value = PolicyDecision(
            require_approval=False, decision_reason="inline"
        )

        step_config = self._make_step_config(
            policy_id=None,
            policy={'on_step_output': []},
        )
        result = self.handler.execute(
            step_config=step_config,
            resolved_params={},
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )
        assert result['decision'] == 'auto_approved'
        mock_brp_class.objects.get.assert_not_called()

    @patch('executions.app.handlers.evaluation_handler.BusinessRulePolicy')
    def test_policy_not_found_propagates(self, mock_brp_class):
        """AC#6 : policy_id inexistant → DoesNotExist propagée (et loggée via evaluation_handler_error)."""
        mock_brp_class.DoesNotExist = type('DoesNotExist', (Exception,), {})
        mock_brp_class.objects.get.side_effect = mock_brp_class.DoesNotExist("Not found")

        step_config = self._make_step_config(policy_id=999)
        with pytest.raises(mock_brp_class.DoesNotExist):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    @patch('executions.app.handlers.evaluation_handler.RuleEngine')
    @patch('executions.app.handlers.evaluation_handler.BusinessRulePolicy')
    def test_missing_artifact_key_passes_none(self, mock_brp_class, mock_engine_class):
        """AC#7 : resolved_params sans 'artifact' → None passé à RuleEngine (pas d'exception)."""
        mock_brp_class.objects.get.return_value = MagicMock()
        mock_engine = mock_engine_class.return_value
        mock_engine.evaluate.return_value = PolicyDecision(
            require_approval=False, decision_reason="no artifact"
        )

        step_config = self._make_step_config()
        result = self.handler.execute(
            step_config=step_config,
            resolved_params={},  # pas de 'artifact'
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )
        call_args = mock_engine.evaluate.call_args
        assert call_args[0][2] is None  # artifact=None
        assert result['status'] == ExecutionStatus.COMPLETED

    @patch('executions.app.handlers.evaluation_handler.RuleEngine')
    @patch('executions.app.handlers.evaluation_handler.BusinessRulePolicy')
    def test_policy_evaluation_error_propagates(self, mock_brp_class, mock_engine_class):
        """PolicyEvaluationError propagée depuis RuleEngine → step FAILED par runtime."""
        mock_brp_class.objects.get.return_value = MagicMock()
        mock_engine_class.return_value.evaluate.side_effect = PolicyEvaluationError(
            message="Invalid policy format"
        )

        step_config = self._make_step_config()
        with pytest.raises(PolicyEvaluationError):
            self.handler.execute(
                step_config=step_config,
                resolved_params={'artifact': {}},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    @patch('executions.app.handlers.evaluation_handler.RuleEngine')
    @patch('executions.app.handlers.evaluation_handler.BusinessRulePolicy')
    def test_rule_engine_generic_exception_logged_and_propagates(self, mock_brp_class, mock_engine_class):
        """RuleEngine.evaluate raises generic Exception → logger.error called, exception propagated."""
        mock_brp_class.objects.get.return_value = MagicMock()
        mock_engine_class.return_value.evaluate.side_effect = RuntimeError("engine crashed")

        step_config = self._make_step_config()
        with pytest.raises(RuntimeError, match="engine crashed"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={'artifact': {}},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    # ── Structlog tests ──────────────────────────────────────────────────────

    @patch('executions.app.handlers.evaluation_handler.logger')
    @patch('executions.app.handlers.evaluation_handler.RuleEngine')
    @patch('executions.app.handlers.evaluation_handler.BusinessRulePolicy')
    def test_logs_start_and_decision_events(self, mock_brp_class, mock_engine_class, mock_logger):
        """Task 2 : evaluation_handler_start et evaluation_handler_decision loggués lors d'un succès."""
        mock_brp_class.objects.get.return_value = MagicMock()
        mock_engine_class.return_value.evaluate.return_value = PolicyDecision(
            require_approval=False, decision_reason="ok"
        )

        execution = self._make_execution(exec_id=42)
        step_config = self._make_step_config(policy_id=7, artifact_type='terraform_cloud')
        self.handler.execute(
            step_config=step_config,
            resolved_params={'artifact': {'plan': 'data'}},
            execution=execution,
            step=step_config,
            correlation_id='corr-log',
        )

        mock_logger.info.assert_any_call(
            "evaluation_handler_start",
            policy_id=7,
            artifact_type='terraform_cloud',
            execution_id=42,
            correlation_id='corr-log',
        )
        mock_logger.info.assert_any_call(
            "evaluation_handler_decision",
            decision='auto_approved',
            decision_reason='ok',
            num_matched_criteria=0,
            execution_id=42,
            correlation_id='corr-log',
        )

    @patch('executions.app.handlers.evaluation_handler.logger')
    @patch('executions.app.handlers.evaluation_handler.RuleEngine')
    @patch('executions.app.handlers.evaluation_handler.BusinessRulePolicy')
    def test_logs_error_event_on_rule_engine_failure(self, mock_brp_class, mock_engine_class, mock_logger):
        """Task 2 : evaluation_handler_error loggué quand RuleEngine lève une exception."""
        mock_brp_class.objects.get.return_value = MagicMock()
        mock_engine_class.return_value.evaluate.side_effect = RuntimeError("boom")

        execution = self._make_execution(exec_id=5)
        step_config = self._make_step_config(policy_id=3, artifact_type='aap')
        with pytest.raises(RuntimeError):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=execution,
                step=step_config,
                correlation_id='corr-err',
            )

        mock_logger.error.assert_called_once_with(
            "evaluation_handler_error",
            policy_id=3,
            artifact_type='aap',
            execution_id=5,
            correlation_id='corr-err',
            error='boom',
            exc_info=True,
        )

    @patch('executions.app.handlers.evaluation_handler.logger')
    @patch('executions.app.handlers.evaluation_handler.BusinessRulePolicy')
    def test_logs_error_event_on_db_failure(self, mock_brp_class, mock_logger):
        """evaluation_handler_error loggué quand BusinessRulePolicy.objects.get() échoue."""
        mock_brp_class.DoesNotExist = type('DoesNotExist', (Exception,), {})
        mock_brp_class.objects.get.side_effect = mock_brp_class.DoesNotExist("Not found")

        execution = self._make_execution(exec_id=9)
        step_config = self._make_step_config(policy_id=99, artifact_type='terraform_cloud')
        with pytest.raises(mock_brp_class.DoesNotExist):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=execution,
                step=step_config,
                correlation_id='corr-db',
            )

        mock_logger.error.assert_called_once_with(
            "evaluation_handler_error",
            policy_id=99,
            artifact_type='terraform_cloud',
            execution_id=9,
            correlation_id='corr-db',
            error='Not found',
            exc_info=True,
        )
