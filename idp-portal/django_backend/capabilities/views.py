# capabilities/views.py
from __future__ import annotations

import structlog
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from capabilities.serializers import (
    IntegrationsCapabilityDataSerializer,
    WorkflowStepsCapabilityDataSerializer,
)
from core.middleware import get_correlation_id
from platforms.registry import platform_registry
from services.definitions import service_definition_registry
from executions.gates.registry import gate_registry
from capabilities.step_definitions import workflow_step_registry

logger = structlog.get_logger(__name__)


@extend_schema(tags=['capabilities'], summary='Capacités des intégrations', responses={200: IntegrationsCapabilityDataSerializer})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_integrations_capabilities(request: Request) -> Response:
    """GET /api/v1/capabilities/integrations

    Retourne plateformes et services dérivés des registres backend.
    Consommé par le frontend pour piloter les formulaires d'action/workflow.
    """
    correlation_id = get_correlation_id()
    logger.info("capabilities_integrations_requested", correlation_id=correlation_id)

    platforms = []
    for code in platform_registry.list_types():
        defn = platform_registry.get(code)
        platforms.append({
            'code': defn.code,
            'display_name': defn.display_name,
            'aliases': sorted(defn.aliases),
            'icon': defn.icon,
            'connector_type': defn.connector_type,
            'action_platform_code': defn.action_platform_code,
            'supports_health_check': defn.supports_health_check,
            'action_config_schema': defn.action_config_schema,
            'runtime_config_schema': defn.runtime_config_schema,
            'health_check_policy': defn.health_check_policy,
        })

    services = []
    for code in service_definition_registry.list_types():
        sdefn = service_definition_registry.get(code)
        services.append({
            'code': sdefn.code,
            'display_name': sdefn.display_name,
            'credential_mode': 'integration' if sdefn.requires_integration else 'credential_free',
            'operations': [
                {
                    'code': op_def.code,
                    'label': op_def.label,
                    'input_schema': op_def.input_schema,
                    'output_schema': op_def.output_schema,
                    'ui_hints': op_def.ui_hints,
                }
                for op_def in sorted(sdefn.operation_defs, key=lambda op: op.code)
            ],
            'supports_health_check': sdefn.supports_health_check,
        })

    return Response({'data': {'platforms': platforms, 'services': services}})


@extend_schema(tags=['capabilities'], summary='Capacités des steps workflow', responses={200: WorkflowStepsCapabilityDataSerializer})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_workflow_steps_capabilities(request: Request) -> Response:
    """GET /api/v1/capabilities/workflow-steps

    Retourne les types de steps workflow avec leurs variants (gates).
    Variants gates dérivés de gate_registry (Story 82.5).
    """
    correlation_id = get_correlation_id()
    logger.info("capabilities_workflow_steps_requested", correlation_id=correlation_id)

    step_types = []
    for code in workflow_step_registry.list_types():
        defn = workflow_step_registry.get(code)
        entry: dict = {
            'code': defn.code,
            'label': defn.label,
            'category': defn.category,
            'config_schema': defn.config_schema,
            'constraints': defn.constraints,
        }
        if defn.code == 'gate':
            # Variants dérivés de gate_registry (Story 82.5)
            variants = []
            for gate_type in gate_registry.list_types():
                gdefn = gate_registry.get(gate_type)
                variants.append({
                    'code': gate_type,
                    'label': gdefn.display_name,
                    'config_schema': gdefn.config_schema,
                })
            entry['variants'] = variants
        step_types.append(entry)

    return Response({'data': {'step_types': step_types}})
