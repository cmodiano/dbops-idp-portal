"""
IaC export/sync views for reference data (engines, categories).
Story 64.8 — API endpoints for IaC sync (export GET + sync POST).

Pattern: FBV @api_view (Story 63.1 canonical pattern).
"""

from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from core.exceptions import InvalidStateError
from core.parsers import YAMLParser, extract_yaml_content
from core.permissions import IsAdminUser

from reference.services_export_import import export_reference_yaml, import_reference_yaml


# ---------------------------------------------------------------------------
# Reference — Engines
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_ref_engines(request: Request) -> HttpResponse:
    """GET /api/v1/admin/reference/engines/export/yaml/ — Export all reference engines as YAML."""
    content = export_reference_yaml('engines')
    response = HttpResponse(content, content_type='application/x-yaml')
    response['Content-Disposition'] = 'attachment; filename="reference-engines.yaml"'
    return response


@api_view(['POST'])
@permission_classes([IsAdminUser])
@parser_classes([YAMLParser, MultiPartParser])
def sync_ref_engines(request: Request) -> Response:
    """POST /api/v1/admin/reference/engines/sync/ — Import/sync reference engines from YAML."""
    mode = request.query_params.get('mode', 'additive')
    if mode not in ('additive', 'full'):
        return Response(
            {"error": {"code": "INVALID_IMPORT_MODE", "message": "Le paramètre 'mode' doit être 'additive' ou 'full'."}},
            status=400,
        )
    content_bytes = extract_yaml_content(request)
    if content_bytes is None:
        return Response(
            {"error": {"code": "EMPTY_BODY", "message": "Aucun contenu YAML fourni."}},
            status=400,
        )
    try:
        created, updated, unchanged = import_reference_yaml(
            content_bytes, 'engines', mode=mode, user=request.user
        )
    except InvalidStateError as e:
        return Response(
            {"error": {"code": e.code, "message": e.message, "details": getattr(e, 'details', {})}},
            status=400,
        )
    status_code = 201 if created > 0 and updated == 0 else 200
    return Response(
        {"data": {"created": created, "updated": updated, "unchanged": unchanged, "mode": mode}},
        status=status_code,
    )


# ---------------------------------------------------------------------------
# Reference — Categories
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_ref_categories(request: Request) -> HttpResponse:
    """GET /api/v1/admin/reference/categories/export/yaml/ — Export all reference categories as YAML."""
    content = export_reference_yaml('categories')
    response = HttpResponse(content, content_type='application/x-yaml')
    response['Content-Disposition'] = 'attachment; filename="reference-categories.yaml"'
    return response


@api_view(['POST'])
@permission_classes([IsAdminUser])
@parser_classes([YAMLParser, MultiPartParser])
def sync_ref_categories(request: Request) -> Response:
    """POST /api/v1/admin/reference/categories/sync/ — Import/sync reference categories from YAML."""
    mode = request.query_params.get('mode', 'additive')
    if mode not in ('additive', 'full'):
        return Response(
            {"error": {"code": "INVALID_IMPORT_MODE", "message": "Le paramètre 'mode' doit être 'additive' ou 'full'."}},
            status=400,
        )
    content_bytes = extract_yaml_content(request)
    if content_bytes is None:
        return Response(
            {"error": {"code": "EMPTY_BODY", "message": "Aucun contenu YAML fourni."}},
            status=400,
        )
    try:
        created, updated, unchanged = import_reference_yaml(
            content_bytes, 'categories', mode=mode, user=request.user
        )
    except InvalidStateError as e:
        return Response(
            {"error": {"code": e.code, "message": e.message, "details": getattr(e, 'details', {})}},
            status=400,
        )
    status_code = 201 if created > 0 and updated == 0 else 200
    return Response(
        {"data": {"created": created, "updated": updated, "unchanged": unchanged, "mode": mode}},
        status=status_code,
    )
