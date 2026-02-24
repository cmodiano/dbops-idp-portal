"""Vues CRUD d'exécutions.

Responsabilité : Opérations CRUD sur les executions (create, retrieve, cancel, steps, logs).
"""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.auth_utils import get_user_ad_groups
from core.exceptions import BadRequestError, NotFoundError, ForbiddenError, ServiceUnavailableError
from core.middleware import get_correlation_id, get_client_ip
from core.throttling import ExecutionThrottle, GeneralAPIThrottle
from core.utils import ensure_utc_isoformat
from executions.builders.response_builder import ExecutionResponseBuilder
from executions.models import Execution, ExecutionStep, ExecutionStatus
from executions.serializers import ExecutionSerializer, ExecutionStepSerializer
from executions.services import ExecutionService
from core.permissions import IsDBAOrDBOPS
from executions.utils import (
    detect_request_source,
)
from executions.validators.payload_validator import ExecutionPayloadValidator
from executions.validators.target_validator import TargetValidator
from executions.validators.env_config_resolver import EnvironmentConfigResolver
from executions.validators.mutex_validator import MutexValidator
from executions.validators.workflow_validator import WorkflowValidator

from drf_spectacular.utils import extend_schema
import structlog

# Story 27.9: Use factory pattern for platform adapter instantiation
from adapters import get_platform_adapter
from adapters.base_adapter import ICancellableAdapter

exec_logger = structlog.get_logger(__name__)

# AC2: Story 26.8 — Instance shared across views for owner-or-admin object-level checks
_dba_permission = IsDBAOrDBOPS()


class ExecutionsCreateView(APIView):
    """POST /executions -> {data: ExecutionCreateResponse}

    Story 33.4 (DIP): uses _execution_service_class + get_execution_service() so
    tests can override the service class without monkey-patching.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [GeneralAPIThrottle, ExecutionThrottle]

    _execution_service_class: type[ExecutionService] = ExecutionService

    def get_execution_service(self) -> ExecutionService:
        """Return an ExecutionService instance (overridable in tests)."""
        return self._execution_service_class()

    @extend_schema(
        tags=['executions'],
        summary='Créer une exécution',
        description="Lance une nouvelle exécution d'action. target_names requis si requires_target=True.",
        responses={201: ExecutionSerializer},
    )
    def post(self, request: Request) -> Response:
        """
        Create a new execution.
        Story 13.2: Supports target_names parameter for target-based execution.
        Story 13.4: target_names is REQUIRED for actions with requires_target=True.
                   environment is ALWAYS derived from target(s), never passed directly.
        """
        # Step 1: Validate payload
        validated = ExecutionPayloadValidator.validate(request.data, request)
        action = validated['action']
        action_id = validated['action_id']
        environment = validated['environment']
        target_names = validated['target_names']
        parameters = validated['parameters']
        workflow_step_parameters = validated['workflow_step_parameters']
        parent_execution_id = validated['parent_execution_id']
        correlation_id = validated['correlation_id']

        # Step 2: Validate targets (if applicable)
        validated_targets: list[dict[str, Any]] = []
        if target_names:
            ad_groups = get_user_ad_groups(request.user)
            validated_targets, environment = TargetValidator.validate_targets(
                target_names=target_names,
                action_id=action_id,
                user=request.user,
                ad_groups=ad_groups,
                correlation_id=correlation_id,
            )
            parameters = parameters.copy() if parameters else {}
            parameters['_targets'] = target_names

            exec_logger.info(
                "execution_with_targets",
                user_id=request.user.id,
                action_id=action_id,
                target_count=len(target_names),
                derived_environment=environment,
                correlation_id=correlation_id,
            )

        # Step 3: Resolve environment config
        env_config = EnvironmentConfigResolver.resolve(
            action=action,
            environment=environment,
            correlation_id=correlation_id,
        )

        # Store environment config in parameters
        parameters = parameters.copy() if parameters else {}
        parameters['_env_config'] = {
            'change_required': env_config['change_required'],
            'change_model_code': env_config['change_model_code'],
            'impact_level': env_config['impact_level'],
            'requires_maintenance_window': env_config['requires_maintenance_window'],
            'requires_approval': env_config['requires_approval'],
        }

        # Step 4: Detect source and IP
        source = detect_request_source(request)
        ip_address = get_client_ip(request)

        # Step 5: Validate workflow (if applicable)
        delegated_referenced_action_ids: list[int] | None = None
        if action.item_type == "workflow":
            delegated_referenced_action_ids = WorkflowValidator.validate_referenced_actions(
                workflow_action=action,
                correlation_id=correlation_id,
                user_id=request.user.id,
                ip_address=ip_address,
            )
        else:
            WorkflowValidator.reject_step_parameters_for_non_workflow(action, workflow_step_parameters)

        if action.item_type == "workflow" and workflow_step_parameters is not None:
            normalized_wsp = WorkflowValidator.validate_step_parameters(
                workflow_action=action,
                workflow_step_parameters=workflow_step_parameters,
            )
            parameters = parameters.copy() if parameters else {}
            parameters["workflow_step_parameters"] = normalized_wsp

        # Step 5b (Story 31.8): Inject page_me parameters if requested
        page_me = validated.get('page_me', False)
        if page_me:
            parameters = parameters.copy() if parameters else {}
            parameters['__page_me'] = True
            parameters['__page_me_user_id'] = str(request.user.username)
            parameters['__page_me_user_name'] = getattr(
                request.user, 'display_name', str(request.user.username)
            )

        # Step 6: Validate mutex
        target_ids_for_mutex = [t['name'] for t in validated_targets] if validated_targets else []
        MutexValidator.validate(
            action=action,
            target_ids=target_ids_for_mutex,
            correlation_id=correlation_id,
            user_id=str(request.user.id),
        )

        # Step 7: Create execution
        execution = self.get_execution_service().create_execution(
            user=request.user,  # type: ignore[arg-type]
            action=action,
            environment=env_config['env_str'],
            parameters=parameters if parameters else None,
            parent_execution_id=parent_execution_id,
            correlation_id=correlation_id,
            source=source,
            ip_address=ip_address,
            targets=target_names if target_names else None,
            delegated_referenced_action_ids=delegated_referenced_action_ids,
            validated_targets=validated_targets if target_names else None,
        )

        # Step 8: Launch execution (skip when requires_approval → PENDING_APPROVAL; DBA will launch via /approve)
        from executions.models import ExecutionStatus
        if execution.status != ExecutionStatus.PENDING_APPROVAL:
            self._launch_execution(execution, action, correlation_id, request)

        # Step 9: Build response
        return ExecutionResponseBuilder.build(execution, action)

    def _launch_execution(self, execution: Any, action: Any, correlation_id: str, request: Request) -> None:
        """Launch the execution via the appropriate runtime."""
        try:
            if action.item_type == "workflow":
                from executions.container_workflow_runtime import ContainerWorkflowRuntime
                runtime = ContainerWorkflowRuntime(execution)
                runtime.run()
                exec_logger.info(
                    "container_workflow_execution_launched",
                    execution_id=execution.id,
                    correlation_id=correlation_id,
                )
            elif getattr(settings, 'SIMULATE_EXECUTION_DEV', False):
                from executions.simulation_service import SimulationService
                SimulationService.create_simulated_steps(execution)
                SimulationService.start_simulation(execution)
                exec_logger.info(
                    "execution_simulation_started",
                    execution_id=execution.id,
                    correlation_id=correlation_id,
                )
            else:
                pass
        except Exception as e:  # noqa: BLE001 — catch-all-mark-failed: execution launch failure marks INTEGRATION_ERROR
            # Story 22.11: Justified broad catch - multiple services
            exec_logger.error(
                "integration_error_on_execution",
                execution_id=execution.id,
                action_id=action.id,
                error_type=type(e).__name__,
                error_message=str(e),
                correlation_id=correlation_id,
                exc_info=True,
            )

            execution_service = self.get_execution_service()
            try:
                execution_service.update_status(
                    execution.id,
                    ExecutionStatus.INTEGRATION_ERROR,
                    str(request.user.id),
                )
            except ValueError as ve:
                exec_logger.error(
                    "unexpected_state_machine_error",
                    execution_id=execution.id,
                    error=str(ve),
                    correlation_id=correlation_id,
                )
                execution.status = ExecutionStatus.INTEGRATION_ERROR
                execution.save(update_fields=["status"])

            execution.error_message = str(e)
            execution.save(update_fields=["error_message"])


class ExecutionDetailView(APIView):
    """GET /executions/{id} -> {data: ExecutionResponse}"""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['executions'], summary="Détail d'une exécution", responses={200: ExecutionSerializer})
    def get(self, request: Request, execution_id: int) -> Response:
        try:
            execution = Execution.objects.select_related(
                "action", "user", "action__integration", "parent_execution__action"
            ).prefetch_related("targets").get(id=execution_id)
        except Execution.DoesNotExist:
            raise NotFoundError(code="NOT_FOUND", message="Execution non trouvée", details={"execution_id": execution_id})

        # AC2: Story 26.8 — owner-or-admin check via IsDBAOrDBOPS permission
        if not _dba_permission.has_object_permission(request, self, execution):
            raise ForbiddenError(code="FORBIDDEN", message="Accès interdit", details={"execution_id": execution_id})

        return Response({"data": ExecutionSerializer(execution).data})


class ExecutionCancelView(APIView):
    """PATCH /executions/{id}/cancel/ -> cancel an execution

    Story 33.4 (DIP): uses _execution_service_class + get_execution_service() so
    tests can override the service class without monkey-patching.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [GeneralAPIThrottle]

    _execution_service_class: type[ExecutionService] = ExecutionService

    def get_execution_service(self) -> ExecutionService:
        """Return an ExecutionService instance (overridable in tests)."""
        return self._execution_service_class()

    @extend_schema(tags=['executions'], summary='Annuler une exécution', responses={200: ExecutionSerializer})
    def patch(self, request: Request, execution_id: int) -> Response:
        try:
            execution = Execution.objects.select_related("action", "user", "action__integration").get(id=execution_id)
        except Execution.DoesNotExist:
            raise NotFoundError(code="NOT_FOUND", message="Execution non trouvée", details={"execution_id": execution_id})

        # AC2: Story 26.8 — owner-or-admin check via IsDBAOrDBOPS permission
        if not _dba_permission.has_object_permission(request, self, execution):
            raise ForbiddenError(code="FORBIDDEN", message="Accès interdit", details={"execution_id": execution_id})

        if execution.status not in (ExecutionStatus.SUBMITTED, ExecutionStatus.RUNNING):
            raise BadRequestError(
                code="INVALID_STATUS",
                message=f"Impossible d'annuler une opération dans le statut {execution.status}",
                details={"execution_id": execution_id, "current_status": execution.status},
            )

        with transaction.atomic():
            if execution.status == ExecutionStatus.RUNNING:
                self._attempt_remote_cancellation(execution)

            cancelled_by_admin = execution.user_id != request.user.id
            try:
                updated = self.get_execution_service().update_status(execution_id, ExecutionStatus.CANCELLED, str(request.user.id))
            except ValueError as e:
                raise BadRequestError(
                    code="INVALID_STATUS",
                    message=str(e),
                    details={"execution_id": execution_id},
                )

            if updated is None:
                raise NotFoundError(code="NOT_FOUND", message="Execution non trouvée", details={"execution_id": execution_id})

            exec_logger.info(
                "execution_cancelled",
                execution_id=execution_id,
                cancelled_by=request.user.id,
                cancelled_by_admin=cancelled_by_admin,
                previous_status=execution.status,
                correlation_id=get_correlation_id(),
            )

            return Response({"data": ExecutionSerializer(updated).data})

    def _attempt_remote_cancellation(self, execution: Any) -> None:
        """Best-effort remote cancellation on execution engine.

        Story 27.1: AAPAdapter now requires base_url + auth_headers from the
        action's integration config.  When the integration is missing or
        incomplete we skip silently (best-effort).

        MEDIUM-3 FIX: Use asyncio.new_event_loop() instead of deprecated get_event_loop()
        """
        import asyncio

        platform_job_id = None
        integration = None
        if execution.action and execution.action.integration:
            integration = execution.action.integration
            params = execution.get_parameters() if hasattr(execution, 'get_parameters') else {}
            platform_job_id = (params or {}).get('platform_job_id')

        if not platform_job_id:
            exec_logger.debug(
                "remote_cancellation_skipped_no_job_id",
                execution_id=execution.id,
                correlation_id=get_correlation_id(),
            )
            return

        if not integration or not integration.base_url:
            exec_logger.debug(
                "remote_cancellation_skipped_no_integration",
                execution_id=execution.id,
                correlation_id=get_correlation_id(),
            )
            return

        loop = None
        try:
            from adapters.utils import build_auth_headers
            auth_headers = build_auth_headers(integration)
            resource_type = (execution.get_parameters() or {}).get("resource_type", "job_template")
            # Story 27.9: Get platform type from integration, use type field as fallback
            platform_type = getattr(integration, "integration_type", None) or integration.type
            if not platform_type:
                raise BadRequestError(
                    code="MISSING_INTEGRATION_TYPE",
                    message="Integration missing type field",
                    details={"integration_id": integration.id},
                )
            config = getattr(integration, "get_config", lambda: None)() or {}
            platform_kwargs = {}
            if "ssl_verify" in config:
                platform_kwargs["ssl_verify"] = config["ssl_verify"]
            if config.get("ca_bundle_path"):
                platform_kwargs["ca_bundle_path"] = config["ca_bundle_path"]
            adapter = get_platform_adapter(
                platform_type=platform_type,
                base_url=integration.base_url,
                auth_headers=auth_headers,
                **platform_kwargs,
            )
            # Story 34.15: ISP — skip remote cancel if adapter does not support it
            if not isinstance(adapter, ICancellableAdapter):
                exec_logger.warning(  # type: ignore[unreachable]
                    "cancel_not_supported",
                    platform_type=platform_type,
                    execution_id=str(execution.id),
                    correlation_id=get_correlation_id(),
                )
                return
            # MEDIUM-3 FIX: Create new event loop instead of get_event_loop() (deprecated Python 3.10+)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                adapter.cancel_execution(
                    platform_job_id,
                    resource_type=resource_type,
                    correlation_id=get_correlation_id(),
                )
            )
            exec_logger.info(
                "remote_cancellation_success",
                execution_id=execution.id,
                platform_job_id=platform_job_id,
                correlation_id=get_correlation_id(),
            )
        except Exception as e:  # noqa: BLE001 — best-effort-non-critical: adapter may raise various exceptions, remote cancellation is best-effort
            # Story 17.6: Justified broad catch — adapter may raise various exceptions
            exec_logger.warning(
                "remote_cancellation_failed",
                execution_id=execution.id,
                platform_job_id=platform_job_id,
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=get_correlation_id(),
                exc_info=True,
            )
        finally:
            # MEDIUM-3 FIX: Ensure event loop is closed
            if loop is not None:
                loop.close()


class ExecutionStepsView(APIView):
    """GET /executions/{id}/steps -> {data: ExecutionStepResponse[]}"""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['executions'], summary="Étapes d'une exécution", responses={200: ExecutionStepSerializer(many=True)})
    def get(self, request: Request, execution_id: int) -> Response:
        try:
            execution = Execution.objects.get(id=execution_id)
        except Execution.DoesNotExist:
            raise NotFoundError(code="NOT_FOUND", message="Execution non trouvée", details={"execution_id": execution_id})

        # AC2: Story 26.8 — owner-or-admin check via IsDBAOrDBOPS permission
        if not _dba_permission.has_object_permission(request, self, execution):
            raise ForbiddenError(code="FORBIDDEN", message="Accès interdit", details={"execution_id": execution_id})

        steps = ExecutionStep.objects.filter(execution_id=execution_id).order_by("step_order")
        return Response({"data": ExecutionStepSerializer(steps, many=True).data})


class ExecutionStepLogsView(APIView):
    """GET /executions/{id}/steps/{step_id}/logs -> {data: StepLogsResponse}"""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['executions'], summary="Logs d'une étape d'exécution")
    def get(self, request: Request, execution_id: int, step_id: int) -> Response:
        try:
            step = ExecutionStep.objects.select_related("execution").get(id=step_id, execution_id=execution_id)
        except ExecutionStep.DoesNotExist:
            raise NotFoundError(
                code="NOT_FOUND",
                message="Step non trouvé",
                details={"execution_id": execution_id, "step_id": step_id},
            )

        execution = step.execution
        # AC2: Story 26.8 — owner-or-admin check via IsDBAOrDBOPS permission
        if not _dba_permission.has_object_permission(request, self, execution):
            raise ForbiddenError(code="FORBIDDEN", message="Accès interdit", details={"execution_id": execution_id})

        return Response(
            {
                "data": {
                    "step_id": step.id,
                    "output": step.get_output() if hasattr(step, "get_output") else None,
                    "error_message": step.error_message,
                    "started_at": ensure_utc_isoformat(step.started_at),
                    "completed_at": ensure_utc_isoformat(step.completed_at),
                }
            }
        )


class ExecutionLogsView(APIView):
    """GET /executions/{id}/logs -> {data: ExecutionLogsResponse}

    Story 27.1 (AC3): Retrieve AAP job logs for an execution via the adapter.
    Returns logs from the AAP platform for the execution's platform_job_id.
    Falls back to stored step output if no platform integration is available.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [GeneralAPIThrottle]

    @extend_schema(tags=['executions'], summary="Logs d'une exécution (AAP)")
    def get(self, request: Request, execution_id: int) -> Response:
        import asyncio
        from adapters.utils import build_auth_headers

        try:
            execution = Execution.objects.select_related('action__integration').get(id=execution_id)
        except Execution.DoesNotExist:
            raise NotFoundError(
                code="NOT_FOUND",
                message="Execution non trouvée",
                details={"execution_id": execution_id},
            )

        # RBAC: owner or DBA/DBOPS
        if not _dba_permission.has_object_permission(request, self, execution):
            raise ForbiddenError(
                code="FORBIDDEN",
                message="Accès interdit",
                details={"execution_id": execution_id},
            )

        correlation_id = get_correlation_id()
        params = execution.get_parameters() or {}
        platform_job_id = params.get("platform_job_id")
        integration = getattr(execution.action, "integration", None) if execution.action else None

        # If no platform_job_id or no AAP integration, return stored logs from steps
        if not platform_job_id or not integration or not integration.base_url:
            exec_logger.debug(
                "execution_logs_fallback_to_steps",
                execution_id=execution_id,
                has_platform_job_id=bool(platform_job_id),
                has_integration=bool(integration),
                correlation_id=correlation_id,
            )
            steps = ExecutionStep.objects.filter(execution_id=execution_id).order_by("step_order")
            step_logs = []
            for step in steps:
                output = step.get_output() if hasattr(step, "get_output") else None
                step_logs.append({
                    "step_id": step.id,
                    "step_name": step.step_name,
                    "step_order": step.step_order,
                    "status": step.status,
                    "output": output,
                    "error_message": step.error_message,
                })
            return Response({"data": {"source": "steps", "logs": step_logs}})

        # Fetch logs from AAP via adapter
        resource_type = params.get("resource_type", "job_template")
        auth_headers = build_auth_headers(integration)
        # Story 27.9: Get platform type from integration, use type field as fallback
        platform_type = getattr(integration, "integration_type", None) or integration.type
        if not platform_type:
            raise BadRequestError(
                code="MISSING_INTEGRATION_TYPE",
                message="Integration missing type field",
                details={"integration_id": integration.id},
            )
        config = getattr(integration, "get_config", lambda: None)() or {}
        platform_kwargs = {}
        if "ssl_verify" in config:
            platform_kwargs["ssl_verify"] = config["ssl_verify"]
        if config.get("ca_bundle_path"):
            platform_kwargs["ca_bundle_path"] = config["ca_bundle_path"]
        adapter = get_platform_adapter(
            platform_type=platform_type,
            base_url=integration.base_url,
            auth_headers=auth_headers,
            **platform_kwargs,
        )

        # CRITICAL-4 FIX: Handle both ASGI (event loop running) and WSGI (no event loop) contexts
        try:
            # Check if there's already a running event loop (ASGI/Channels context)
            try:
                asyncio.get_running_loop()
                # Running loop exists → use async_to_sync pattern for Django Channels compatibility
                from asgiref.sync import async_to_sync
                logs = async_to_sync(adapter.get_job_logs)(
                    platform_job_id=platform_job_id,
                    resource_type=resource_type,
                    correlation_id=correlation_id,
                )
            except RuntimeError:
                # No running loop (WSGI context) → create new event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    logs = loop.run_until_complete(
                        adapter.get_job_logs(
                            platform_job_id=platform_job_id,
                            resource_type=resource_type,
                            correlation_id=correlation_id,
                        )
                    )
                finally:
                    loop.close()
        except ServiceUnavailableError:
            raise
        except Exception as e:  # noqa: BLE001 — logged-and-wrapped: adapter error logged then wrapped in ServiceUnavailableError
            exec_logger.error(
                "execution_logs_adapter_error",
                execution_id=execution_id,
                platform_job_id=platform_job_id,
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
                exc_info=True,
            )
            raise ServiceUnavailableError(
                code="AAP_LOGS_UNAVAILABLE",
                message="Impossible de récupérer les logs AAP",
                details={"execution_id": execution_id, "platform_job_id": platform_job_id},
            ) from e

        exec_logger.info(
            "execution_logs_retrieved",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            log_length=len(logs.get("content", "")),
            correlation_id=correlation_id,
        )

        return Response({"data": {"source": "aap", **logs}})
