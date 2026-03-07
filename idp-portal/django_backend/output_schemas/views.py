"""
Views for output_schemas app.
Story 63.1 - Infrastructure des Schémas d'Output (Backend).
"""

from django.http import HttpResponse
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated, IsAdminUser
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
        content = request.FILES['file'].read().decode('utf-8')
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
    except Exception as exc:
        return Response(
            {'error': f'Erreur lors de l\'import : {exc}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return Response({'data': stats})
