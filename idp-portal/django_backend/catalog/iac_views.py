"""
IaC export/sync views for catalog entities (actions, policies, tags).
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

from catalog.services_export_import import export_actions_yaml, import_action_yaml
from catalog.services_export_import_policies import export_policies_yaml, import_policy_yaml
from catalog.services_export_import_tags import export_tags_yaml, import_tags_yaml


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_actions(request: Request) -> HttpResponse:
    """GET /api/v1/admin/actions/export/yaml/ — Export all actions as multi-doc YAML."""
    content = export_actions_yaml()
    response = HttpResponse(content, content_type='application/x-yaml')
    response['Content-Disposition'] = 'attachment; filename="actions.yaml"'
    return response


@api_view(['POST'])
@permission_classes([IsAdminUser])
@parser_classes([YAMLParser, MultiPartParser])
def sync_actions(request: Request) -> Response:
    """POST /api/v1/admin/actions/sync/ — Import/sync actions from YAML."""
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
        created, updated, unchanged = import_action_yaml(content_bytes, mode=mode, user=request.user)
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
# Policies
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_policies(request: Request) -> HttpResponse:
    """GET /api/v1/admin/policies/export/yaml/ — Export all policies as multi-doc YAML."""
    content = export_policies_yaml()
    response = HttpResponse(content, content_type='application/x-yaml')
    response['Content-Disposition'] = 'attachment; filename="policies.yaml"'
    return response


@api_view(['POST'])
@permission_classes([IsAdminUser])
@parser_classes([YAMLParser, MultiPartParser])
def sync_policies(request: Request) -> Response:
    """POST /api/v1/admin/policies/sync/ — Import/sync policies from YAML."""
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
        created, updated, unchanged = import_policy_yaml(content_bytes, mode=mode, user=request.user)
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
# Tags
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_tags(request: Request) -> HttpResponse:
    """GET /api/v1/admin/tags/export/yaml/ — Export all tags as YAML."""
    content = export_tags_yaml()
    response = HttpResponse(content, content_type='application/x-yaml')
    response['Content-Disposition'] = 'attachment; filename="tags.yaml"'
    return response


@api_view(['POST'])
@permission_classes([IsAdminUser])
@parser_classes([YAMLParser, MultiPartParser])
def sync_tags(request: Request) -> Response:
    """POST /api/v1/admin/tags/sync/ — Import/sync tags from YAML."""
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
        created, updated, unchanged = import_tags_yaml(content_bytes, user=request.user)
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
