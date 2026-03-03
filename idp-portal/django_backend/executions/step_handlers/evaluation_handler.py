"""
EvaluationHandler — implémentation story 57.6

Handler pour les steps de type evaluation (ADR-007 §4d).
Réutilise le RuleEngine existant et les OutputInterpreters (Terraform, AAP).
Mappe la décision sur SUCCESS/ERROR pour le branching du runtime.
"""
from __future__ import annotations

import types

import structlog

from catalog.models import BusinessRulePolicy
from executions.models import Execution, ExecutionStatus
from executions.rule_engine import RuleEngine

logger = structlog.get_logger(__name__)


class EvaluationHandler:
    """Handler pour les steps de type evaluation (ADR-007 §4d).

    Charge la politique (par policy_id ou inline), délègue à RuleEngine,
    et traduit la décision en ExecutionStatus pour le routing du runtime :
    - require_approval=True  → ExecutionStatus.FAILED  → on_error_step_id
    - require_approval=False → ExecutionStatus.COMPLETED → on_success_step_id
    """

    def execute(
        self,
        step_config: dict,
        resolved_params: dict,
        execution: Execution,
        step: dict,
        correlation_id: str | None,
    ) -> dict:
        """
        Évalue l'artifact résolu via RuleEngine.

        Args:
            step_config: Définition du step (policy_id, artifact_type, ...)
            resolved_params: Paramètres résolus via input_mapping (contient 'artifact')
            execution: Instance Execution en cours
            step: Même dict que step_config (alias pour _execute_handler_step)
            correlation_id: ID de corrélation pour les logs

        Returns:
            dict: {'decision', 'decision_reason', 'matched_criteria', 'status': ExecutionStatus}

        Raises:
            BusinessRulePolicy.DoesNotExist: si policy_id introuvable
            PolicyEvaluationError: si l'évaluation échoue
        """
        policy_id = step_config.get('policy_id')
        artifact_type = step_config.get('artifact_type')  # step_type pour l'interpréteur

        logger.info(
            "evaluation_handler_start",
            policy_id=policy_id,
            artifact_type=artifact_type,
            execution_id=execution.id,
            correlation_id=correlation_id,
        )

        # Construire l'action proxy selon source de la policy
        if policy_id is not None:
            try:
                policy_obj = BusinessRulePolicy.objects.get(id=policy_id)
            except Exception:
                logger.error(
                    "evaluation_handler_error",
                    policy_id=policy_id,
                    artifact_type=artifact_type,
                    execution_id=execution.id,
                    correlation_id=correlation_id,
                    exc_info=True,
                )
                raise
            action_proxy = types.SimpleNamespace(
                business_rule_policy_id=policy_id,
                business_rule_policy=policy_obj,  # évite requête DB supplémentaire
                business_rule_policies=None,
            )
        else:
            # Policy inline dans le step config
            action_proxy = types.SimpleNamespace(
                business_rule_policy_id=None,
                business_rule_policy=None,
                business_rule_policies=step_config.get('policy', {}),
            )

        # Construire le step proxy (step_type = artifact_type pour matching interpréteur)
        step_proxy = types.SimpleNamespace(
            step_type=artifact_type,
            execution_id=execution.id,
            id=None,
        )

        artifact: dict | str = resolved_params.get('artifact') or {}

        try:
            engine = RuleEngine()
            decision = engine.evaluate(action_proxy, step_proxy, artifact)
        except Exception:
            logger.error(
                "evaluation_handler_error",
                policy_id=policy_id,
                artifact_type=artifact_type,
                execution_id=execution.id,
                correlation_id=correlation_id,
                exc_info=True,
            )
            raise

        decision_label = 'requires_approval' if decision.require_approval else 'auto_approved'
        result_status = (
            ExecutionStatus.FAILED
            if decision.require_approval
            else ExecutionStatus.COMPLETED
        )

        logger.info(
            "evaluation_handler_decision",
            decision=decision_label,
            decision_reason=decision.decision_reason,
            num_matched_criteria=len(decision.matched_criteria),
            execution_id=execution.id,
            correlation_id=correlation_id,
        )

        return {
            'decision': decision_label,
            'decision_reason': decision.decision_reason,
            'matched_criteria': decision.matched_criteria,
            'status': result_status,
        }
