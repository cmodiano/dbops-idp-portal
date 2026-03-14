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
from executions.step_handlers.gate_handler import GateHandler

logger = structlog.get_logger(__name__)

# Labels d'affichage pour chaque gate_type (clés de GateHandler.condition_type_map)
# NOTE: Ces labels seront remplacés par GateDefinition.display_name en Story 82.5.
_GATE_VARIANT_LABELS: dict[str, str] = {
    'maintenance_window': 'Fenêtre de maintenance',
    'approval': 'Approbation manuelle',
}

# Labels et catégories des step_types statiques
_STEP_TYPES_STATIC = [
    {'code': 'platform',     'label': 'Exécuter', 'category': 'execution'},
    {'code': 'service_call', 'label': 'Service',  'category': 'integration'},
    {'code': 'gate',         'label': 'Attendre', 'category': 'control'},
]


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
        })

    services = []
    for code in service_definition_registry.list_types():
        sdefn = service_definition_registry.get(code)
        services.append({
            'code': sdefn.code,
            'display_name': sdefn.display_name,
            'credential_mode': 'integration' if sdefn.requires_integration else 'credential_free',
            'operations': sorted(sdefn.operations),
            'supports_health_check': sdefn.supports_health_check,
        })

    return Response({'data': {'platforms': platforms, 'services': services}})


@extend_schema(tags=['capabilities'], summary='Capacités des steps workflow', responses={200: WorkflowStepsCapabilityDataSerializer})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_workflow_steps_capabilities(request: Request) -> Response:
    """GET /api/v1/capabilities/workflow-steps

    Retourne les types de steps workflow avec leurs variants (gates).
    NOTE: config_schema est {} à ce stade — sera enrichi en Story 82.5 (GateRegistry).
    """
    correlation_id = get_correlation_id()
    logger.info("capabilities_workflow_steps_requested", correlation_id=correlation_id)

    step_types = []
    for step_meta in _STEP_TYPES_STATIC:
        entry: dict = {
            'code': step_meta['code'],
            'label': step_meta['label'],
            'category': step_meta['category'],
            'config_schema': {},
        }
        if step_meta['code'] == 'gate':
            # Variants dérivés de GateHandler.condition_type_map
            # Clés = gate_type (ce que l'utilisateur configure), valeurs = condition_type (runtime)
            entry['variants'] = [
                {
                    'code': gate_type,
                    'label': _GATE_VARIANT_LABELS.get(gate_type, gate_type),
                    'config_schema': {},
                }
                for gate_type in GateHandler.condition_type_map
            ]
        step_types.append(entry)

    return Response({'data': {'step_types': step_types}})
