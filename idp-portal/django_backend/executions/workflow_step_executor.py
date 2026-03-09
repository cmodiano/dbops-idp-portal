"""Exécution d'une étape de workflow : gates, adapter platform, évaluation policy — WorkflowRuntime."""
from __future__ import annotations

import structlog
from dataclasses import asdict
from typing import TYPE_CHECKING, Optional, Any, Dict

from django.db import transaction
from django.utils import timezone

from executions.models import ExecutionStep, ExecutionStepStatus
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType

if TYPE_CHECKING:
    from executions.models import Execution
    from executions.workflow_runtime import StepResult

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

        # Story 57.15: Route par step_type AVANT le check gate_conditions.
        # schedule_execution → handler dédié ; parallel_group → guard défensif (Story 65.3).
        step_type_routing = step.get('step_type', 'platform')
        if step_type_routing == 'schedule_execution':
            return self._execute_schedule_step(step, step_order, step_parameters)

        # Story 65.3: WorkflowRuntime est legacy et strictement séquentiel.
        # Les workflows avec parallel_group doivent utiliser ContainerWorkflowRuntime.
        # Ce guard évite une ValueError générique si un parallel_group atteignait ce code.
        if step_type_routing == 'parallel_group':
            logger.error(
                "workflow_step_executor_parallel_group_not_supported",
                execution_id=self.execution.id,
                step_id=step_id,
                step_name=step_name,
                correlation_id=self.correlation_id,
            )
            return StepResult(
                outcome=StepOutcome.ERROR,
                error_message=(
                    f"WorkflowRuntime ne supporte pas step_type 'parallel_group' (step_id={step_id or 'N/A'}). "
                    "Utiliser ContainerWorkflowRuntime pour les workflows avec parallel_group."
                ),
                error_details={
                    'step_type': 'parallel_group',
                    'step_id': step_id,
                    'remedy': 'ContainerWorkflowRuntime gère les parallel_group (Story 65.2)',
                },
            )

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
                step_type=step_type_routing,  # Story 58.3 fix: utiliser le type réel du step (ex. 'gate') plutôt que 'platform' hardcodé
                status=ExecutionStepStatus.WAITING,
            )

            waiting_context = build_waiting_context(execution_step, gate_conditions)
            execution_step.set_output(waiting_context)
            execution_step.save()

            # Story 58.3: broadcast step_update pour que la vue d'exécution s'actualise en temps réel
            from executions.utils.websocket_broadcast import broadcast_step_update  # noqa: PLC0415
            broadcast_step_update(self.execution.id, execution_step)

            # V113: Durable event for UI catch-up on reconnect
            from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
            WorkflowEventService.emit_step_status_changed(
                self.execution.id, execution_step, old_status="",
            )

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
                    'execution_id': str(self.execution.id),
                    'action_name': self.execution.action.name if self.execution.action else None,
                    'step_id': step_id,
                    'step_name': step_name,
                    'step_order': step_order,
                    'gate_conditions_count': len(gate_conditions),
                    'gate_types': [c.get('type') for c in gate_conditions],
                },
                correlation_id=self.correlation_id,
            )

            # Story 57.8: Notification approbation requise (on_approval_required)
            is_approval_gate = any(
                isinstance(c, dict) and c.get('type') == 'approval_granted'
                for c in gate_conditions
            )
            if is_approval_gate:
                self._send_approval_notification_if_configured()
                # V113: Durable approval_requested event — survives page reload
                WorkflowEventService.emit_approval_requested(
                    self.execution.id, execution_step,
                )

            # V113: Enqueue WAITING step as runnable (gate evaluator will process it)
            from executions.services.runnable_steps import RunnableStepService  # noqa: PLC0415
            RunnableStepService.enqueue(execution_step)

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

        # Create ExecutionStep record
        execution_step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=step_order,
            step_name=step_name,
            step_type=step_type_routing,  # Code Review: use actual step_type instead of hardcoded 'platform'
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

            # Story 47.2: Dispatch async si integration, simulated si pas d'integration
            if integration:
                from executions.tasks.trigger import trigger_platform_job  # noqa: PLC0415
                from executions.tasks.polling import get_platform_queue  # noqa: PLC0415

                # Calculer trigger_kwargs (même logique que call_platform_adapter lignes 425–434)
                trigger_kwargs: dict[str, Any] = {"correlation_id": self.correlation_id}
                params = adapter_payload.get("parameters") or {}
                if params.get("template_id"):
                    trigger_kwargs["template_id"] = str(params["template_id"])
                if params.get("resource_type"):
                    trigger_kwargs["resource_type"] = params["resource_type"]
                if params.get("extra_vars"):
                    trigger_kwargs["extra_vars"] = params["extra_vars"]

                trigger_platform_job.apply_async(
                    kwargs={
                        "execution_step_id": execution_step.id,
                        "execution_id": self.execution.id,
                        "integration_id": integration.id,
                        "trigger_kwargs": trigger_kwargs,
                    },
                    queue=get_platform_queue(integration.type),
                )

                logger.info(
                    "workflow_step_trigger_dispatched_async",
                    execution_id=self.execution.id,
                    step_id=execution_step.id,
                    platform=referenced_action.platform,
                    integration_id=integration.id,
                    correlation_id=self.correlation_id,
                )

                step_output_data = {
                    'adapter_ready': True,
                    'async_dispatched': True,
                    'step_id': step_id,
                    'step_name': step_name,
                    'outcome': StepOutcome.SUCCESS.value,
                    'parameters_used': step_parameters,
                    'delegated_from_workflow': True,
                    'referenced_action_id': referenced_action.id,
                    'referenced_action_name': referenced_action.name,
                }
                execution_step.set_output(step_output_data)
                execution_step.save()  # status reste RUNNING — trigger_platform_job gère la suite

                return StepResult(
                    outcome=StepOutcome.SUCCESS,
                    output={
                        'step_id': step_id,
                        'step_name': step_name,
                        'async_dispatched': True,
                        'referenced_action_id': referenced_action.id,
                    },
                )

            else:
                # Story 47.3 : fail fast — pas d'integration = erreur explicite, pas de succès simulé
                error_msg = (
                    f"No integration configured for action {referenced_action.id} "
                    f"(platform: {referenced_action.platform}). "
                    f"Configure an integration to enable platform execution."
                )
                execution_step.status = ExecutionStepStatus.FAILED
                execution_step.completed_at = timezone.now()
                execution_step.error_message = error_msg
                execution_step.save()

                logger.critical(
                    "workflow_step_no_integration_fail_fast",
                    execution_id=self.execution.id,
                    step_id=execution_step.id,
                    action_id=referenced_action.id,
                    platform=referenced_action.platform,
                    correlation_id=self.correlation_id,
                )
                AuditService.create_entry(
                    user_id=str(self.execution.user_id),
                    action_type=AuditActionType.EXECUTION_INTEGRATION_ERROR,
                    entity_type=AuditEntityType.EXECUTION,
                    entity_id=self.execution.id,
                    details={
                        'error': 'NO_INTEGRATION',
                        'action_id': referenced_action.id,
                        'platform': referenced_action.platform,
                        'step_id': execution_step.id,
                    },
                    correlation_id=self.correlation_id,
                )
                return StepResult(
                    outcome=StepOutcome.ERROR,
                    error_message=error_msg,
                    error_details={
                        'step_id': step_id,
                        'step_name': step_name,
                        'error_type': 'NO_INTEGRATION',
                        'platform': referenced_action.platform,
                    },
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

        except Exception as e:  # noqa: BLE001 — catch-all-mark-failed: step failure marks step FAILED, logged with full traceback
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
        """Call the real platform adapter. Raises ValueError if no integration configured.

        Story 47.3: Fail-fast — no simulated responses. Missing integration raises ValueError.
        Adapter exceptions are re-raised to be handled by execute() except handler.
        """
        if not integration:
            raise ValueError(
                f"No integration configured for action {referenced_action.id} "
                f"(platform: {referenced_action.platform}). "
                f"Cannot call platform adapter without integration."
            )

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

        except Exception as exc:  # noqa: BLE001 — re-raised: adapter errors propagated to execute() except handler
            logger.critical(
                "workflow_step_adapter_call_failed",
                execution_id=self.execution.id,
                step_id=execution_step.id,
                platform=referenced_action.platform,
                error=str(exc),
                error_type=type(exc).__name__,
                correlation_id=self.correlation_id,
                exc_info=True,
            )
            raise  # Story 47.3: fail fast — re-raise pour que execute() marque step FAILED

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
                    'execution_id': str(self.execution.id),
                    'action_name': self.execution.action.name if self.execution.action else None,
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

            # Story 58.3: broadcast step_update (cohérence avec gate_conditions path)
            from executions.utils.websocket_broadcast import broadcast_step_update  # noqa: PLC0415
            broadcast_step_update(self.execution.id, execution_step)

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
                    'execution_id': str(self.execution.id),
                    'action_name': self.execution.action.name if self.execution.action else None,
                    'step_id': execution_step.id,
                    'step_name': execution_step.step_name,
                    'policy_decision': decision_dict,
                },
                correlation_id=self.correlation_id,
            )

            # Story 57.8: Notification approbation requise
            self._send_approval_notification_if_configured()

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
                    'execution_id': str(self.execution.id),
                    'action_name': self.execution.action.name if self.execution.action else None,
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

    # -------------------------------------------------------------------------
    # Story 57.8 — approval notification helper
    # -------------------------------------------------------------------------

    def _send_approval_notification_if_configured(self) -> None:
        """
        Story 57.8: Envoie notification on_approval_required si configurée sur l'action.

        Charge l'action depuis l'exécution, vérifie la notification_config,
        et envoie via NotificationService en on_commit.
        """
        try:
            from catalog.models import Action  # noqa: PLC0415

            action = Action.objects.filter(id=self.execution.action_id).first()
            if not action:
                return

            config = action.notification_config or {}
            has_approval_notif = any(
                ch.get("enabled") and "on_approval_required" in (ch.get("conditions") or [])
                for ch in config.get("channels", [])
            )
            if not has_approval_notif:
                return

            _execution = self.execution
            _action = action
            _correlation_id = self.correlation_id

            def _send() -> None:
                try:
                    from services.notification_service import NotificationService  # noqa: PLC0415
                    notif = NotificationService()
                    notif.notify_execution_event(
                        execution=_execution,
                        action=_action,
                        event="on_approval_required",
                        correlation_id=_correlation_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "approval_notification_failed",
                        execution_id=_execution.id,
                        error=str(exc),
                        correlation_id=_correlation_id,
                    )

            transaction.on_commit(_send)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "approval_notification_setup_failed",
                execution_id=self.execution.id,
                error=str(exc),
                correlation_id=self.correlation_id,
            )

    # -------------------------------------------------------------------------
    # Story 57.15 — schedule_execution step handler
    # -------------------------------------------------------------------------

    def _execute_schedule_step(
        self,
        step: Dict[str, Any],
        step_order: int,
        step_parameters: Dict[str, Any],
    ) -> "StepResult":
        """
        Handle a step of type 'schedule_execution'.

        Creates a ScheduledExecution via SchedulingService, stores correlation_id,
        creates audit entry WORKFLOW_STEP_SCHEDULE_CREATED, and returns StepResult.

        Story 57.15 AC #1–#8.
        """
        from executions.workflow_runtime import StepResult, StepOutcome  # noqa: PLC0415
        from executions.scheduling_service import SchedulingService  # noqa: PLC0415
        from catalog.models import Action  # noqa: PLC0415

        step_id = step.get('step_id')
        step_name = step.get('name', f"Step {step.get('order', 0)}")

        logger.info(
            "workflow_schedule_step_executing",
            execution_id=self.execution.id,
            step_id=step_id,
            step_name=step_name,
            step_order=step_order,
            correlation_id=self.correlation_id,
        )

        execution_step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=step_order,
            step_name=step_name,
            step_type='schedule_execution',
            status=ExecutionStepStatus.RUNNING,
            started_at=timezone.now(),
        )

        try:
            schedule_config = step.get('schedule_config', {})
            referenced_action_id = step.get('referenced_action_id')

            if not referenced_action_id:
                raise ValueError(f"Workflow schedule step {step_id} missing referenced_action_id")

            try:
                target_action = Action.objects.get(id=referenced_action_id)
            except Action.DoesNotExist:
                raise ValueError(
                    f"Referenced action {referenced_action_id} not found for schedule step {step_id}"
                )

            scheduled_at = self._resolve_schedule_date(schedule_config, step_parameters)
            recurring_pattern_data = self._resolve_recurring_pattern(schedule_config)
            scheduled_params = self._build_scheduled_parameters(schedule_config, step_parameters, step)

            scheduled_execution = SchedulingService().create_scheduled_execution(
                user=self.execution.user,
                action=target_action,
                environment=self.execution.environment,
                parameters=scheduled_params,
                scheduled_at=scheduled_at,
                recurring_pattern_data=recurring_pattern_data,
            )

            # Store correlation_id and source_execution_id on the created ScheduledExecution
            scheduled_execution.correlation_id = self.correlation_id
            # Story 57.17: stocker l'ID de l'exécution source pour la traçabilité UI
            scheduled_execution.source_execution_id = self.execution.id
            scheduled_execution.save()

            # Mark step COMPLETED with output
            # Story 57.17: enrichir pour la traçabilité UI
            step_output = {
                'scheduled_execution_id': scheduled_execution.id,
                'action_name': target_action.name,
                'scheduled_at': (
                    scheduled_execution.scheduled_at.isoformat()
                    if scheduled_execution.scheduled_at
                    else None
                ),
            }
            execution_step.status = ExecutionStepStatus.COMPLETED
            execution_step.completed_at = timezone.now()
            execution_step.set_output(step_output)
            execution_step.save()

            # Audit trail
            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.WORKFLOW_STEP_SCHEDULE_CREATED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'step_id': step_id,
                    'step_name': step_name,
                    'step_order': step_order,
                    'scheduled_execution_id': scheduled_execution.id,
                    'referenced_action_id': referenced_action_id,
                    'correlation_id': self.correlation_id,
                },
                correlation_id=self.correlation_id,
            )

            logger.info(
                "workflow_schedule_step_completed",
                execution_id=self.execution.id,
                step_id=step_id,
                scheduled_execution_id=scheduled_execution.id,
                correlation_id=self.correlation_id,
            )

            return StepResult(
                outcome=StepOutcome.SUCCESS,
                output=step_output,
            )

        except Exception as e:  # noqa: BLE001 — catch-all: marks step FAILED
            execution_step.status = ExecutionStepStatus.FAILED
            execution_step.completed_at = timezone.now()
            execution_step.error_message = f"{type(e).__name__}: {str(e)}"
            execution_step.save()

            logger.error(
                "workflow_schedule_step_failed",
                execution_id=self.execution.id,
                step_id=step_id,
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
                },
            )

    def _resolve_schedule_date(self, schedule_config: Dict[str, Any], step_parameters: Dict[str, Any]) -> Any:
        """
        Resolve the scheduled_at datetime from schedule_config and step_parameters.

        Story 57.15 AC #2 (parameter), #3 (fixed_offset), #4 (recurring → None).
        """
        source = schedule_config.get('schedule_source', 'parameter')
        if source == 'parameter':
            param_name = schedule_config.get('schedule_parameter_name', 'scheduled_at')
            date_str = step_parameters.get(param_name)
            if not date_str:
                global_params = self.execution.get_parameters() or {}
                date_str = global_params.get(param_name)
            if not date_str:
                raise ValueError(f"Paramètre '{param_name}' requis pour schedule_source='parameter'")
            from django.utils.dateparse import parse_datetime  # noqa: PLC0415
            parsed = parse_datetime(date_str)
            if not parsed:
                raise ValueError(f"Format de date invalide pour '{param_name}': {date_str}")
            return parsed
        elif source == 'fixed_offset':
            offset_str = schedule_config.get('fixed_offset', '+1d')
            return self._parse_fixed_offset(offset_str)
        elif source == 'recurring':
            return None
        else:
            raise ValueError(f"schedule_source inconnu: {source}")

    def _parse_fixed_offset(self, offset_str: str) -> Any:
        """
        Parse a fixed offset string (+Nd/+Nh/+Nw/+Nm) and return now() + offset.

        Story 57.15 AC #3.
        """
        import re  # noqa: PLC0415
        from datetime import timedelta  # noqa: PLC0415

        match = re.match(r'^\+(\d+)([dhwm])$', offset_str)
        if not match:
            raise ValueError(f"Format d'offset invalide: {offset_str}. Attendu: +Nd, +Nh, +Nw, +Nm")
        value = int(match.group(1))
        unit = match.group(2)
        deltas = {
            'd': timedelta(days=value),
            'h': timedelta(hours=value),
            'w': timedelta(weeks=value),
            'm': timedelta(minutes=value),
        }
        return timezone.now() + deltas[unit]

    def _resolve_recurring_pattern(self, schedule_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Build recurring_pattern_data dict for SchedulingService if schedule_source is 'recurring'.

        Story 57.15 AC #4.
        """
        if schedule_config.get('schedule_source') != 'recurring':
            return None
        pattern_data = schedule_config.get('recurring_pattern', {})
        pattern_type = pattern_data.get('pattern_type')
        pattern_config = pattern_data.get('pattern_config', {})
        if not pattern_type:
            raise ValueError("recurring_pattern.pattern_type requis pour schedule_source='recurring'")
        from executions.utils import calculate_next_execution_date  # noqa: PLC0415
        next_date = calculate_next_execution_date(pattern_type, pattern_config, timezone.now())
        return {
            'pattern_type': pattern_type,
            'pattern_config': pattern_config,
            'next_execution_date': next_date,
        }

    def _build_scheduled_parameters(
        self,
        schedule_config: Dict[str, Any],
        step_parameters: Dict[str, Any],
        step: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Build the parameters dict for the ScheduledExecution.

        Story 57.15 AC #5 (inherit_parameters) and #6 (parameter_mapping JSONPath).
        """
        params: Dict[str, Any] = {}

        if schedule_config.get('inherit_parameters', False):
            global_params = self.execution.get_parameters() or {}
            for key, value in global_params.items():
                if key != 'workflow_step_parameters':
                    params[key] = value

        mapping = schedule_config.get('parameter_mapping', {})
        for target_key, source_expr in mapping.items():
            if isinstance(source_expr, str) and source_expr.startswith('$.'):
                params[target_key] = self._resolve_jsonpath(source_expr)
            else:
                params[target_key] = source_expr

        if step_parameters:
            schedule_param_name = schedule_config.get('schedule_parameter_name')
            for key, value in step_parameters.items():
                if key != schedule_param_name:
                    params[key] = value

        return params if params else None

    def _resolve_jsonpath(self, expr: str) -> Any:
        """
        Resolve a simplified JSONPath expression of the form $.steps.<step_id>.output.<field>.

        Story 57.15 AC #6.
        """
        parts = expr.split('.')
        if len(parts) >= 5 and parts[1] == 'steps' and parts[3] == 'output':
            step_name = parts[2]
            field_name = '.'.join(parts[4:])
            prev_step = ExecutionStep.objects.filter(
                execution=self.execution, step_name=step_name
            ).order_by('-step_order').first()
            if prev_step:
                output = prev_step.get_output() or {}
                return output.get(field_name)
        return None
