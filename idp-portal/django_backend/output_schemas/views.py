"""
Views for output_schemas app.
Story 63.1 - Infrastructure des Schémas d'Output (Backend).
"""

import structlog
from django.http import HttpResponse
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated

from core.permissions import IsAdminUser
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, BaseParser
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework import status

from output_schemas.models import OutputSchema
from output_schemas.serializers import OutputSchemaSerializer
from output_schemas.services_export_import import (
    export_output_schemas_yaml,
    import_output_schemas_yaml,
)


class YAMLParser(BaseParser):
    """Accept application/x-yaml raw body."""
    media_type = 'application/x-yaml'

    def parse(self, stream, media_type=None, parser_context=None):
        # Fix M2: handle non-UTF-8 uploads with a proper 400 instead of 500
        try:
            return stream.read().decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ParseError(f"Le contenu YAML doit être encodé en UTF-8 : {exc}") from exc


class OutputSchemaViewSet(ReadOnlyModelViewSet):
    """
    Public read-only viewset for output schemas.
    Filterable by schema_type and target_name.
    """
    queryset = OutputSchema.objects.select_related('inherits_from').order_by('id')
    serializer_class = OutputSchemaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        schema_type = self.request.query_params.get('schema_type')
        target_name = self.request.query_params.get('target_name')
        if schema_type:
            qs = qs.filter(schema_type=schema_type)
        if target_name:
            qs = qs.filter(target_name=target_name)
        return qs


@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_output_schemas(request):
    """Export all output schemas as YAML."""
    content = export_output_schemas_yaml()
    return HttpResponse(content, content_type='application/x-yaml')


@api_view(['POST'])
@permission_classes([IsAdminUser])
@parser_classes([YAMLParser, MultiPartParser])
def sync_output_schemas(request):
    """
    Import/sync output schemas from YAML body.
    Query param: mode=additive (default) | full
    Accepts: application/x-yaml body or multipart file upload (key: 'file').
    """
    mode = request.query_params.get('mode', 'additive')
    if mode not in ('additive', 'full'):
        return Response(
            {'error': "Le paramètre 'mode' doit être 'additive' ou 'full'."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Accept multipart file upload or yaml parsed body (YAMLParser sets request.data to str)
    if 'file' in request.FILES:
        try:
            content = request.FILES['file'].read().decode('utf-8')
        except UnicodeDecodeError:
            structlog.get_logger(__name__).exception(
                "sync_output_schemas_decode_error",
                exc_info=True,
            )
            return Response(
                {'error': 'Aucun contenu YAML fourni ou encodage non valide.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    elif request.data and isinstance(request.data, str) and request.data.strip():
        content = request.data
    else:
        return Response(
            {'error': 'Aucun contenu YAML fourni.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        stats = import_output_schemas_yaml(content, mode=mode)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        structlog.get_logger(__name__).exception(
            "sync_output_schemas_import_error",
            exc_info=True,
            error=str(e),
        )
        return Response(
            {'error': "Erreur lors de l'import."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return Response({'data': stats})


def _resolve_action_schema(action, schema_registry) -> dict | None:
    """
    Story 63.9: Résout le schéma output d'une action.
    FK en priorité (si output_schema_id défini), fallback par nom via le registre.
    """
    if action.output_schema_id and action.output_schema:
        return dict(schema_registry._resolve(action.output_schema) or {}) or None
    return dict(schema_registry.get_action_schema(action.name) or {}) or None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_step_output_schema(request, workflow_id: int, step_id: str):
    """
    GET /api/v1/output-schemas/workflows/{workflow_id}/steps/{step_id}/output-schema/
    Retourne le schéma d'output résolu pour un step spécifique d'un workflow.
    """
    from catalog.models import Action  # noqa: PLC0415 — import tardif pour éviter les cycles
    from output_schemas.registry import schema_registry  # noqa: PLC0415

    try:
        workflow = Action.objects.get(id=workflow_id, item_type='workflow')
    except Action.DoesNotExist:
        return Response({'error': f'Workflow {workflow_id} introuvable.'}, status=404)

    steps = workflow.execution_steps or []
    step = next((s for s in steps if s.get('step_id') == step_id), None)
    if step is None:
        return Response({'error': f'Step "{step_id}" introuvable dans le workflow {workflow_id}.'}, status=404)

    step_type = step.get('step_type', 'platform')
    schema = None

    if step_type == 'platform':
        ref_action_id = step.get('referenced_action_id')
        if ref_action_id:
            try:
                ref_action = Action.objects.select_related(
                    'output_schema', 'output_schema__inherits_from'
                ).get(id=ref_action_id)
                schema = _resolve_action_schema(ref_action, schema_registry)
            except Action.DoesNotExist:
                pass
        if schema is None:
            schema = schema_registry.get_platform_convention('aap')
    elif step_type == 'service_call':
        integration_type = step.get('integration_type', '')
        operation = step.get('operation', '')
        if integration_type and operation:
            schema = schema_registry.get_integration_schema(integration_type, operation)

    return Response({
        'step_id': step_id,
        'step_name': step.get('name', ''),
        'step_type': step_type,
        'schema': schema,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_variables(request, workflow_id: int):
    """
    GET /api/v1/output-schemas/workflows/{workflow_id}/available-variables/
    Retourne toutes les variables disponibles par step pour le variable picker.
    """
    from catalog.models import Action  # noqa: PLC0415 — import tardif pour éviter les cycles
    from output_schemas.registry import schema_registry  # noqa: PLC0415

    try:
        workflow = Action.objects.get(id=workflow_id, item_type='workflow')
    except Action.DoesNotExist:
        return Response({'error': f'Workflow {workflow_id} introuvable.'}, status=404)

    steps = sorted(
        workflow.execution_steps or [],
        key=lambda s: (s.get('step_order') is None, s.get('step_order', 0)),
    )
    # Pré-charger les actions référencées pour éviter N+1
    ref_ids = [
        s.get('referenced_action_id')
        for s in steps
        if s.get('step_type', 'platform') == 'platform' and s.get('referenced_action_id')
    ]
    ref_actions = {
        a.id: a for a in Action.objects.filter(id__in=ref_ids).select_related(
            'output_schema', 'output_schema__inherits_from'
        )
    } if ref_ids else {}

    result = []
    for step in steps:
        step_id = step.get('step_id', '')
        step_type = step.get('step_type', 'platform')
        step_name = step.get('name', step_id)
        schema = None

        if step_type == 'platform':
            ref_id = step.get('referenced_action_id')
            if ref_id and ref_id in ref_actions:
                schema = _resolve_action_schema(ref_actions[ref_id], schema_registry)
            if schema is None:
                schema = schema_registry.get_platform_convention('aap')
        elif step_type == 'service_call':
            integration_type = step.get('integration_type', '')
            operation = step.get('operation', '')
            if integration_type and operation:
                schema = schema_registry.get_integration_schema(integration_type, operation)

        if schema and schema.get('output_fields'):
            result.append({
                'step_id': step_id,
                'step_name': step_name,
                'step_type': step_type,
                'variables': schema['output_fields'],
            })

    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_action_output_schema(request, action_id: int):
    """
    Story 63.9: GET /api/v1/output-schemas/actions/{action_id}/schema/
    Retourne le schéma résolu pour une action donnée.
    FK en priorité si configurée, sinon résolution par nom, sinon null.
    """
    from catalog.models import Action  # noqa: PLC0415 — import tardif pour éviter les cycles
    from output_schemas.registry import schema_registry  # noqa: PLC0415

    try:
        action = Action.objects.select_related(
            'output_schema', 'output_schema__inherits_from'
        ).get(id=action_id)
    except Action.DoesNotExist:
        return Response({'error': f'Action {action_id} introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    schema: dict[str, object] | None
    if action.output_schema_id and action.output_schema:
        schema_type = 'fk'
        schema = dict(schema_registry._resolve(action.output_schema) or {}) or None
    else:
        schema_type = 'name'
        schema = dict(schema_registry.get_action_schema(action.name) or {}) or None

    return Response({
        'action_id': action_id,
        'schema_type': schema_type,
        'schema': schema,
    })
