"""Vues CRUD d'exécutions.

Responsabilité : Opérations CRUD sur les executions (create, retrieve, cancel, steps, logs).
"""
from __future__ import annotations

from typing import Any

from django.conf import settings
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import BadRequestError, NotFoundError, ForbiddenError, ServiceUnavailableError
from core.middleware import get_correlation_id, get_client_ip
from core.throttling import ExecutionThrottle, GeneralAPIThrottle
from core.utils import ensure_utc_isoformat
from executions.builders.response_builder import ExecutionResponseBuilder
from executions.models import Execution, ExecutionStep, ExecutionStatus
from executions.serializers import ExecutionSerializer, ExecutionStepSerializer
from executions.dtos import ExecutionRequest
from executions.services import ExecutionService
from core.permissions import IsAdminUser
from executions.utils import (
    detect_request_source,
)
from executions.validators.pipeline import ExecutionValidationPipeline

from drf_spectacular.utils import extend_schema, inline_serializer
import structlog

# Story 27.9: Use factory pattern for platform adapter instantiation
from adapters import get_platform_adapter
from adapters.base_adapter import ICancellableAdapter

exec_logger = structlog.get_logger(__name__)

# AC2: Story 26.8 — Instance shared across views for owner-or-admin object-level checks
_dba_permission = IsAdminUser()


def _fetch_splunk_logs_for_execution(
    execution_id: int, platform_job_id: str | None = None
) -> str | None:
    """Best-effort retrieval of platform logs from Splunk for a given execution.

    When platform_job_id is provided, returns logs for that platform job only.
    Returns the log content string, or ``None`` on any error.
    """
    try:
        from services.splunk_utils import get_splunk_service  # noqa: PLC0415
        from asgiref.sync import async_to_sync  # noqa: PLC0415

        splunk = get_splunk_service()
        if splunk is None:
            return None

        return async_to_sync(splunk.search_platform_logs)(
            execution_id=execution_id, platform_job_id=platform_job_id
        )
    except Exception:  # noqa: BLE001 — best-effort
        exec_logger.exception(
            "splunk_logs_retrieval_error",
            execution_id=execution_id,
        )
        return None


def _fetch_splunk_logs_mapping_for_execution(execution_id: int) -> dict[str, str]:
    """Best-effort retrieval of all platform logs from Splunk, keyed by platform_job_id."""
    try:
        from services.splunk_utils import get_splunk_service  # noqa: PLC0415
        from asgiref.sync import async_to_sync  # noqa: PLC0415

        splunk = get_splunk_service()
        if splunk is None:
            return {}

        return async_to_sync(splunk.search_platform_logs_mapping)(execution_id=execution_id)
    except Exception:  # noqa: BLE001 — best-effort
        exec_logger.exception(
            "splunk_logs_mapping_retrieval_error",
            execution_id=execution_id,
        )
        return {}


def _retrieve_purged_logs_from_splunk(
    output: dict, execution_id: int, platform_job_id: str | None = None
) -> dict:
    """Best-effort retrieval of purged platform logs from Splunk.

    If successful, injects ``platform_logs`` and ``logs_source`` into *output*.
    On failure, returns *output* unchanged (``logs_purged=True`` stays visible
    to the frontend so it can inform the user).
    """
    content = _fetch_splunk_logs_for_execution(execution_id, platform_job_id=platform_job_id)
    if content is not None:
        output["platform_logs"] = content
        output["logs_source"] = "splunk"
    return output


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
        request=inline_serializer(
            name='ExecutionCreateRequest',
            fields={
                'action_id': serializers.IntegerField(help_text='ID de l\'action à exécuter (requis)'),
                'target_names': serializers.ListField(
                    child=serializers.CharField(),
                    required=False,
                    help_text='Liste de noms de targets (requis si action.requires_target=True)',
                ),
                'environment': serializers.CharField(
                    required=False,
                    help_text='Environnement (requis si pas de target_names)',
                ),
                'parameters': serializers.DictField(
                    required=False,
                    help_text='Paramètres spécifiques à l\'action',
                ),
                'workflow_step_parameters': serializers.DictField(
                    required=False,
                    help_text='Paramètres par étape pour workflows: {"1": {"parameters": {...}}, "2": {...}}',
                ),
                'parent_execution_id': serializers.IntegerField(required=False),
                'page_me': serializers.BooleanField(
                    required=False,
                    default=False,
                    help_text='Injecter user_id/user_name dans parameters',
                ),
            },
        ),
        responses={201: ExecutionSerializer},
    )
    def post(self, request: Request) -> Response:
        """
        Create a new execution.
        Story 13.2: Supports target_names parameter for target-based execution.
        Story 13.4: target_names is REQUIRED for actions with requires_target=True.
                   environment is ALWAYS derived from target(s), never passed directly.
        """
        # Step 1: Detect source and IP (context HTTP, pas validation)
        source = detect_request_source(request)
        ip_address = get_client_ip(request)

        # Step 2: Run unified validation pipeline
        result = ExecutionValidationPipeline.validate(
            request_data=request.data,
            request=request,
            user=request.user,
            ip_address=ip_address,
        )

        # Step 3 (Story 31.8): Inject page_me parameters if requested
        parameters = result.parameters
        if result.page_me:
            parameters = (parameters.copy() if parameters else {})
            parameters['__page_me'] = True
            parameters['__page_me_user_id'] = str(request.user.username)
            parameters['__page_me_user_name'] = getattr(
                request.user, 'display_name', str(request.user.username)
            )

        # Step 4: Create execution
        exec_req = ExecutionRequest(
            user=request.user,  # type: ignore[arg-type]
            action=result.action,
            environment=result.environment,
            parameters=parameters if parameters else None,
            parent_execution_id=result.parent_execution_id,
            correlation_id=result.correlation_id,
            source=source,
            ip_address=ip_address,
            targets=result.target_names if result.target_names else None,
            delegated_referenced_action_ids=result.delegated_referenced_action_ids,
            validated_targets=result.validated_targets if result.target_names else None,
        )
        execution = self.get_execution_service().create_execution(exec_req)

        # Step 5: Launch execution (skip when requires_approval → approval gate step created;
        # DBA will launch via /approve after gate approval). ADR-007: check step-based.
        if not execution.is_pending_approval:
            self._launch_execution(execution, result.action, result.correlation_id or "", request)

        # Step 6: Build response
        return ExecutionResponseBuilder.build(execution, result.action)

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

        # AC2: Story 26.8 — owner-or-admin check via IsAdminUser permission
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

    @extend_schema(tags=['executions'], summary='Annuler une exécution', responses={202: ExecutionSerializer})
    def patch(self, request: Request, execution_id: int) -> Response:
        try:
            execution = Execution.objects.select_related("action", "user", "action__integration").prefetch_related("targets").get(id=execution_id)
        except Execution.DoesNotExist:
            raise NotFoundError(code="NOT_FOUND", message="Execution non trouvée", details={"execution_id": execution_id})

        # AC2: Story 26.8 — owner-or-admin check via IsAdminUser permission
        if not _dba_permission.has_object_permission(request, self, execution):
            raise ForbiddenError(code="FORBIDDEN", message="Accès interdit", details={"execution_id": execution_id})

        if execution.status not in (ExecutionStatus.SUBMITTED, ExecutionStatus.RUNNING):
            raise BadRequestError(
                code="INVALID_STATUS",
                message=f"Impossible d'annuler une opération dans le statut {execution.status}",
                details={"execution_id": execution_id, "current_status": execution.status},
            )

        # Story 78.5: Write durable cancel command instead of inline processing
        from executions.services.workflow_commands import WorkflowCommandService  # noqa: PLC0415
        user_id = str(request.user.id)
        cmd = WorkflowCommandService.write_command(
            execution_id=execution_id,
            command_type="cancel",
            payload={},
            created_by=user_id,
        )

        exec_logger.info(
            "execution_cancel_command_written",
            execution_id=execution_id,
            command_id=cmd.id,
            cancelled_by=request.user.id,
            previous_status=execution.status,
            correlation_id=get_correlation_id(),
        )

        return Response(
            {"data": {"command_id": cmd.id, "status": "accepted"}},
            status=202,
        )

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
            # Story 82.2: kwargs runtime extraits via PlatformRegistry (remplace le bloc manuel)
            from adapters.runtime_config import build_platform_runtime_config
            from platforms.registry import platform_registry
            platform_type = platform_registry.resolve_alias(platform_type)
            platform_kwargs = build_platform_runtime_config(integration)
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

        # AC2: Story 26.8 — owner-or-admin check via IsAdminUser permission
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
        # AC2: Story 26.8 — owner-or-admin check via IsAdminUser permission
        if not _dba_permission.has_object_permission(request, self, execution):
            raise ForbiddenError(code="FORBIDDEN", message="Accès interdit", details={"execution_id": execution_id})

        output = step.get_output() if hasattr(step, "get_output") else None

        # If logs were purged, attempt retrieval from Splunk (only when we have
        # a platform_job_id for platform-specific logs; otherwise skip to avoid
        # execution-wide Splunk search)
        if output and output.get("logs_purged"):
            pid = step.platform_job_id or output.get("platform_job_id")
            if pid:
                output = _retrieve_purged_logs_from_splunk(output, execution_id, platform_job_id=pid)

        return Response(
            {
                "data": {
                    "step_id": step.id,
                    "output": output,
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
            step_outputs = [
                (step, step.get_output() if hasattr(step, "get_output") else None)
                for step in steps
            ]

            # Fetch all Splunk logs once, keyed by platform_job_id
            any_purged = any(o and o.get("logs_purged") for _, o in step_outputs)
            splunk_map: dict[str, str] = {}
            if any_purged:
                splunk_map = _fetch_splunk_logs_mapping_for_execution(execution_id)

            step_logs = []
            for step, output in step_outputs:
                if output and output.get("logs_purged"):
                    pid = step.platform_job_id or output.get("platform_job_id")
                    splunk_logs = splunk_map.get(pid) if pid else None
                    if splunk_logs is not None:
                        output["platform_logs"] = splunk_logs
                        output["logs_source"] = "splunk"
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
        # Story 82.2: kwargs runtime extraits via PlatformRegistry (remplace le bloc manuel)
        from adapters.runtime_config import build_platform_runtime_config
        platform_kwargs = build_platform_runtime_config(integration)
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
