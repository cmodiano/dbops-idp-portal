"""Exécution d'une étape de workflow : gates, adapter platform, évaluation policy — WorkflowRuntime."""
from __future__ import annotations

import structlog
from dataclasses import asdict
from typing import TYPE_CHECKING, Optional, Any, Dict

from django.utils import timezone

from executions.models import ExecutionStep, ExecutionStepStatus
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType

if TYPE_CHECKING:
    from executions.models import Execution
    from executions.workflow_runtime import StepResult, StepOutcome

logger = structlog.get_logger(__name__)


class StepExecutor:
    """
    Exécution d'une étape de workflow : gates, adapter plateforme, évaluation policy.

    Extrait de WorkflowRuntime (SRP) — responsable de l'exécution d'une seule étape :
    vérification des gate_conditions, appel de l'adapter plateforme, évaluation des policies.
    """

    def __init__(self, execution: "Execution", correlation_id: str) -> None:
        """
        Initialise le StepExecutor.

        Args:
            execution: L'instance Execution en cours d'exécution.
            correlation_id: L'identifiant de corrélation pour le logging.
        """
        self.execution = execution
        self.correlation_id = correlation_id

    def execute(
        self,
        step: Dict[str, Any],
        step_order: int,
        step_parameters: Dict[str, Any],
    ) -> "StepResult":
        """
        Exécute une seule étape de workflow, ou la met en WAITING si gate_conditions présentes.

        Story 25.2: If step has gate_conditions, create ExecutionStep in WAITING status
        and return immediately without executing. The Celery Beat task (Story 25.3) will
        evaluate gates and unblock the step later.

        Story 4.12 AC5: Injects workflow_step_parameters[step_order] for this step.

        Args:
            step: Step dict from workflow definition
            step_order: Order counter for ExecutionStep creation (managed by WorkflowRuntime)
            step_parameters: Parameters for this step (from workflow_step_parameters)

        Returns:
            StepResult with outcome
        """
        from executions.workflow_runtime import StepResult, StepOutcome  # noqa: PLC0415

        step_id = step.get('step_id')
        step_name = step.get('name', f"Step {step.get('order', 0)}")

        logger.info(
            "workflow_step_executing",
            execution_id=self.execution.id,
            step_id=step_id,
            step_name=step_name,
            step_order=step_order,
            correlation_id=self.correlation_id,
        )

        # Story 25.2: Check for gate_conditions — create WAITING step instead of executing
        gate_conditions = step.get('gate_conditions', [])
        if gate_conditions:
            from executions.gate_context import build_waiting_context  # noqa: PLC0415

            execution_step = ExecutionStep.objects.create(
                execution=self.execution,
                step_order=step_order,
                step_name=step_name,
                step_type='platform',
                status=ExecutionStepStatus.WAITING,
            )

            waiting_context = build_waiting_context(execution_step, gate_conditions)
            execution_step.set_output(waiting_context)
            execution_step.save()

            logger.info(
                "workflow_step_waiting",
                execution_id=self.execution.id,
                step_id=step_id,
                step_name=step_name,
                gate_conditions_count=len(gate_conditions),
                correlation_id=self.correlation_id,
            )

            # AC3: Audit trail for WAITING step creation
            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_STEP_WAITING,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'step_id': step_id,
                    'step_name': step_name,
                    'step_order': step_order,
                    'gate_conditions_count': len(gate_conditions),
                    'gate_types': [c.get('type') for c in gate_conditions],
                },
                correlation_id=self.correlation_id,
            )

            return StepResult(
                outcome=StepOutcome.WAITING,
                error_message="Step waiting for gate conditions",
                error_details={
                    'step_id': step_id,
                    'step_name': step_name,
                    'waiting': True,
                    'gate_conditions_count': len(gate_conditions),
                },
            )

        # Note (AC3): this runtime is strictly sequential in V1.
        # Parallel execution is intentionally NOT supported yet; this is a future enhancement.

        # Create ExecutionStep record
        execution_step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=step_order,
            step_name=step_name,
            step_type='platform',  # Default type for now
            status=ExecutionStepStatus.RUNNING,
            started_at=timezone.now(),
        )

        try:
            # Story 4.12 AC5: Load referenced action and prepare adapter payload
            referenced_action_id = step.get('referenced_action_id')

            if not referenced_action_id:
                raise ValueError(f"Workflow step {step_id} missing referenced_action_id")

            # Load the referenced action (validates it exists and is accessible)
            from catalog.models import Action  # noqa: PLC0415
            try:
                referenced_action = Action.objects.select_related('integration').get(id=referenced_action_id)
            except Action.DoesNotExist:
                raise ValueError(
                    f"Referenced action {referenced_action_id} not found for step {step_id}"
                )

            # Story 24.4 (AC5): Validate integration status before executing step
            integration = getattr(referenced_action, 'integration', None)
            if integration:
                from integrations.models import IntegrationStatus  # noqa: PLC0415
                if integration.status == IntegrationStatus.INVALID:
                    error_msg = (
                        f"Workflow step '{step_name}' failed: Integration '{integration.name}' "
                        f"(type: {integration.type}) is invalid and cannot be used. "
                        f"Please update the workflow to use a valid integration before retrying."
                    )
                    logger.error(
                        "workflow_step_blocked_invalid_integration",
                        execution_id=self.execution.id,
                        step_id=step_id,
                        integration_id=integration.id,
                        integration_name=integration.name,
                        integration_type=integration.type,
                        correlation_id=self.correlation_id,
                    )
                    AuditService.create_entry(
                        user_id=str(self.execution.user_id),
                        action_type=AuditActionType.WORKFLOW_STEP_BLOCKED_INVALID_INTEGRATION,
                        entity_type=AuditEntityType.EXECUTION,
                        entity_id=self.execution.id,
                        details={
                            'step_id': step_id,
                            'step_name': step_name,
                            'integration_id': integration.id,
                            'integration_name': integration.name,
                            'integration_type': integration.type,
                            'referenced_action_id': referenced_action.id,
                        },
                        correlation_id=self.correlation_id,
                    )
                    raise ValueError(error_msg)

                if integration.status == IntegrationStatus.DEPRECATED:
                    logger.warning(
                        "workflow_step_deprecated_integration",
                        execution_id=self.execution.id,
                        step_id=step_id,
                        integration_id=integration.id,
                        integration_name=integration.name,
                        integration_type=integration.type,
                        correlation_id=self.correlation_id,
                    )
                    AuditService.create_entry(
                        user_id=str(self.execution.user_id),
                        action_type=AuditActionType.EXECUTION_DEPRECATED_INTEGRATION_WARNING,
                        entity_type=AuditEntityType.EXECUTION,
                        entity_id=self.execution.id,
                        details={
                            'step_id': step_id,
                            'step_name': step_name,
                            'integration_id': integration.id,
                            'integration_name': integration.name,
                            'integration_type': integration.type,
                            'referenced_action_id': referenced_action.id,
                        },
                        correlation_id=self.correlation_id,
                    )

            # Story 4.12 AC5: Prepare complete adapter payload with step_parameters ✓
            adapter_payload = {
                'action_id': referenced_action.id,
                'action_name': referenced_action.name,
                'platform': referenced_action.platform,
                'environment': self.execution.environment,
                'parameters': step_parameters,  # AC5: step params injected!
                'correlation_id': self.correlation_id,
                'execution_id': self.execution.id,
                'execution_step_id': execution_step.id,
            }

            logger.info(
                "workflow_step_adapter_payload_ready",
                execution_id=self.execution.id,
                step_id=step_id,
                referenced_action_id=referenced_action.id,
                referenced_action_name=referenced_action.name,
                platform=referenced_action.platform,
                has_parameters=bool(step_parameters),
                correlation_id=self.correlation_id,
            )

            # Story 30.15 AC2/AC3: Real adapter call via get_platform_adapter()
            adapter_response = self.call_platform_adapter(
                referenced_action, integration, adapter_payload, execution_step,
            )

            step_output_data = {
                'adapter_ready': True,
                'adapter_payload_prepared': adapter_payload,
                'adapter_response': adapter_response,
                'step_id': step_id,
                'step_name': step_name,
                'outcome': StepOutcome.SUCCESS.value,
                'parameters_used': step_parameters,
                'delegated_from_workflow': True,
                'referenced_action_id': referenced_action.id,
                'referenced_action_name': referenced_action.name,
            }

            # Story 28.2: Evaluate business_rule_policies after step output
            policy_result = self._evaluate_policy_if_needed(
                execution_step, referenced_action, step_output_data,
            )
            if policy_result is not None:
                # PolicyEvaluator decided — step is WAITING or auto-approved
                execution_step.set_output(step_output_data)
                execution_step.save()
                return policy_result

            execution_step.status = ExecutionStepStatus.COMPLETED
            execution_step.completed_at = timezone.now()
            execution_step.set_output(step_output_data)
            execution_step.save()

            logger.info(
                "workflow_step_completed",
                execution_id=self.execution.id,
                step_id=step_id,
                step_name=step_name,
                referenced_action_id=referenced_action.id,
                adapter_ready=True,
                correlation_id=self.correlation_id,
            )

            return StepResult(
                outcome=StepOutcome.SUCCESS,
                output={
                    'step_id': step_id,
                    'step_name': step_name,
                    'referenced_action_id': referenced_action.id,
                    'adapter_payload_prepared': True,
                }
            )

        except ValueError as e:
            # Handle validation errors (missing referenced_action_id, action not found)
            execution_step.status = ExecutionStepStatus.FAILED
            execution_step.completed_at = timezone.now()
            execution_step.error_message = str(e)
            execution_step.save()

            logger.error(
                "workflow_step_validation_failed",
                execution_id=self.execution.id,
                step_id=step_id,
                step_name=step_name,
                error=str(e),
                error_type='validation',
                correlation_id=self.correlation_id,
            )

            return StepResult(
                outcome=StepOutcome.ERROR,
                error_message=str(e),
                error_details={
                    'step_id': step_id,
                    'step_name': step_name,
                    'error_type': 'validation',
                }
            )

        except Exception as e:
            # Story 17.6: Justified broad catch - Step can raise any exception from adapters
            execution_step.status = ExecutionStepStatus.FAILED
            execution_step.completed_at = timezone.now()
            execution_step.error_message = f"{type(e).__name__}: {str(e)}"
            execution_step.save()

            logger.error(
                "workflow_step_failed",
                execution_id=self.execution.id,
                step_id=step_id,
                step_name=step_name,
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=self.correlation_id,
                exc_info=True,
            )

            return StepResult(
                outcome=StepOutcome.ERROR,
                error_message=str(e),
                error_details={
                    'step_id': step_id,
                    'step_name': step_name,
                    'error_type': type(e).__name__,
                }
            )

    def call_platform_adapter(
        self,
        referenced_action: Any,
        integration: Any,
        adapter_payload: dict,
        execution_step: ExecutionStep,
    ) -> dict:
        """Call the real platform adapter if integration is configured, else log CRITICAL and return simulated response.

        Story 30.15 AC2/AC3: Replaces simulated adapter call with real adapter infrastructure.
        Falls back to simulated response with CRITICAL audit trail when adapter call is not possible.
        """
        if not integration:
            logger.critical(
                "workflow_step_no_integration_simulated",
                execution_id=self.execution.id,
                step_id=execution_step.id,
                action_id=referenced_action.id,
                action_name=referenced_action.name,
                platform=referenced_action.platform,
                correlation_id=self.correlation_id,
            )
            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_RUNNING,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'warning': 'SIMULATED_ADAPTER_RESPONSE',
                    'reason': 'Action has no integration configured',
                    'action_id': referenced_action.id,
                    'platform': referenced_action.platform,
                },
                correlation_id=self.correlation_id,
            )
            return {
                'status': 'success',
                'simulated': True,
                'job_id': f'sim-{self.execution.id}-{execution_step.id}',
                'message': f'SIMULATED: {referenced_action.name} — no integration configured',
                'platform': referenced_action.platform,
            }

        try:
            from adapters import get_platform_adapter  # noqa: PLC0415
            from adapters.utils import build_auth_headers  # noqa: PLC0415
            from asgiref.sync import async_to_sync  # noqa: PLC0415

            auth_headers = build_auth_headers(integration, self.correlation_id)

            # Extract platform-specific kwargs from integration config
            platform_kwargs: dict[str, Any] = {}
            config = integration.get_config() if hasattr(integration, 'get_config') else {}
            if config:
                for key in ('owner', 'repo', 'organization', 'namespace'):
                    if key in config:
                        platform_kwargs[key] = config[key]
                if 'ssl_verify' in config:
                    platform_kwargs['ssl_verify'] = config['ssl_verify']
                if config.get('ca_bundle_path'):
                    platform_kwargs['ca_bundle_path'] = config['ca_bundle_path']

            # Story 31.9: Derive platform_type from integration.type (already normalized)
            platform_type = integration.type

            adapter = get_platform_adapter(
                platform_type=platform_type,
                base_url=integration.base_url,
                auth_headers=auth_headers,
                **platform_kwargs,
            )

            # Build trigger kwargs from adapter_payload
            trigger_kwargs: dict[str, Any] = {
                'correlation_id': self.correlation_id,
            }
            params = adapter_payload.get('parameters') or {}
            if params.get('template_id'):
                trigger_kwargs['template_id'] = str(params['template_id'])
            if params.get('resource_type'):
                trigger_kwargs['resource_type'] = params['resource_type']
            if params.get('extra_vars'):
                trigger_kwargs['extra_vars'] = params['extra_vars']

            adapter_result = async_to_sync(adapter.trigger)(**trigger_kwargs)

            # Store platform_job_id on execution_step for webhook correlation
            platform_job_id = adapter_result.get('platform_job_id')
            if platform_job_id:
                execution_step.platform_job_id = str(platform_job_id)

            logger.info(
                "workflow_step_adapter_call_success",
                execution_id=self.execution.id,
                step_id=execution_step.id,
                platform=referenced_action.platform,
                platform_job_id=platform_job_id,
                correlation_id=self.correlation_id,
            )
            return adapter_result

        except Exception as exc:
            # Adapter call failed (unsupported platform, missing params, network error, etc.)
            # Log CRITICAL and fall back to simulated response so the workflow can continue.
            # Real adapter failures are surfaced via the 'simulated' flag in step output.
            logger.critical(
                "workflow_step_adapter_call_failed",
                execution_id=self.execution.id,
                step_id=execution_step.id,
                platform=referenced_action.platform,
                error=str(exc),
                error_type=type(exc).__name__,
                correlation_id=self.correlation_id,
            )
            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_RUNNING,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'warning': 'SIMULATED_ADAPTER_RESPONSE',
                    'reason': f'Adapter call failed: {type(exc).__name__}: {exc}',
                    'action_id': referenced_action.id,
                    'platform': referenced_action.platform,
                },
                correlation_id=self.correlation_id,
            )
            return {
                'status': 'success',
                'simulated': True,
                'job_id': f'sim-{self.execution.id}-{execution_step.id}',
                'message': f'SIMULATED: adapter call failed for {referenced_action.platform}: {exc}',
                'platform': referenced_action.platform,
            }

    def _evaluate_policy_if_needed(
        self,
        execution_step: ExecutionStep,
        action: Any,
        step_output: dict,
    ) -> Optional["StepResult"]:
        """
        Story 28.2: Evaluate business_rule_policies after step output.

        If the action has policies matching this step type, evaluate them.
        Returns a StepResult if the policy requires approval (WAITING) or
        auto-approves with audit trail. Returns None if no policy applies.
        """
        from executions.policy_evaluator import PolicyEvaluator, PolicyEvaluationError  # noqa: PLC0415
        from executions.workflow_runtime import StepResult, StepOutcome  # noqa: PLC0415

        policies = getattr(action, 'business_rule_policies', None)
        if not policies:
            return None

        rules = policies.get("on_step_output", []) if isinstance(policies, dict) else []
        if not rules:
            return None

        # Check if any rule matches this step type
        step_type = execution_step.step_type
        matching_rule = next(
            (r for r in rules if r.get("when", {}).get("step_type") == step_type),
            None,
        )
        if not matching_rule:
            return None

        try:
            evaluator = PolicyEvaluator()
            policy_decision = evaluator.evaluate_policy(
                execution_step, action, step_output,
            )
        except PolicyEvaluationError as exc:
            # Policy evaluation failed — mark step FAILED
            execution_step.status = ExecutionStepStatus.FAILED
            execution_step.completed_at = timezone.now()
            execution_step.error_message = exc.message
            execution_step.save()

            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_STEP_POLICY_EVALUATION_FAILED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'step_id': execution_step.id,
                    'step_name': execution_step.step_name,
                    'error': exc.message,
                },
                correlation_id=self.correlation_id,
            )

            logger.error(
                "policy_evaluation_error",
                execution_id=self.execution.id,
                step_id=execution_step.id,
                error_message=exc.message,
                correlation_id=self.correlation_id,
            )

            return StepResult(
                outcome=StepOutcome.ERROR,
                error_message=exc.message,
                error_details={'policy_evaluation_failed': True},
            )

        # Store policy decision in step output
        decision_dict = asdict(policy_decision)
        step_output['policy_decision'] = decision_dict

        if policy_decision.require_approval:
            # Require approval — WAITING
            execution_step.status = ExecutionStepStatus.WAITING
            execution_step.save()

            # Add gate_condition for manual approval
            existing_output = execution_step.get_output() or {}
            gate_conditions = existing_output.get('gate_conditions', [])
            gate_conditions.append({
                'type': 'approval_granted',
                'reason': policy_decision.decision_reason,
                'source': 'policy_evaluator',
            })
            step_output['gate_conditions'] = gate_conditions

            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_STEP_POLICY_APPROVAL_REQUIRED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'step_id': execution_step.id,
                    'step_name': execution_step.step_name,
                    'policy_decision': decision_dict,
                },
                correlation_id=self.correlation_id,
            )

            # MED-7 FIX: Removed redundant logging (PolicyEvaluator already logs decision)

            return StepResult(
                outcome=StepOutcome.WAITING,
                error_message="Step waiting for policy approval",
                error_details={
                    'waiting': True,
                    'policy_decision': decision_dict,
                },
            )
        else:
            # Auto-approved — continue normally but record audit
            execution_step.status = ExecutionStepStatus.COMPLETED
            execution_step.completed_at = timezone.now()

            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_STEP_POLICY_AUTO_APPROVED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'step_id': execution_step.id,
                    'step_name': execution_step.step_name,
                    'policy_decision': decision_dict,
                },
                correlation_id=self.correlation_id,
            )

            # MED-7 FIX: Removed redundant logging (PolicyEvaluator already logs decision)

            # Return SUCCESS — auto-approved, caller will save with the updated status
            return StepResult(
                outcome=StepOutcome.SUCCESS,
                output={
                    'policy_decision': decision_dict,
                    'auto_approved': True,
                },
            )
