"""
CaC export/sync views for core entities (feature-flags).
Story 64.8 — API endpoints for CaC sync (export GET + sync POST).

Pattern: FBV @api_view (Story 63.1 canonical pattern).
"""

import structlog

from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from core.exceptions import InvalidStateError
from core.parsers import YAMLParser, extract_yaml_content
from core.permissions import IsAdminUser
from core.services_export_import import export_feature_flags_yaml, import_feature_flags_yaml

logger = structlog.get_logger(__name__)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_feature_flags(request: Request) -> HttpResponse:
    """GET /api/v1/admin/feature-flags/export/yaml/ — Export all feature flags as YAML."""
    content = export_feature_flags_yaml()
    response = HttpResponse(content, content_type='application/x-yaml')
    response['Content-Disposition'] = 'attachment; filename="feature-flags.yaml"'
    return response


@api_view(['POST'])
@permission_classes([IsAdminUser])
@parser_classes([YAMLParser, MultiPartParser])
def sync_feature_flags(request: Request) -> Response:
    """POST /api/v1/admin/feature-flags/sync/ — Import/sync feature flags from YAML."""
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
    # MEDIUM-5: mode='full' is accepted by this endpoint but import_feature_flags_yaml
    # only supports additive (create-or-update). Full deletion of stale flags is not implemented.
    if mode == 'full':
        logger.warning(
            "feature_flags_sync_mode_full_not_implemented",
            message="mode='full' requested but feature-flags sync only supports additive import. "
                    "Stale flags will NOT be deleted. Use the PATCH endpoint to disable individual flags.",
        )
    try:
        created, updated, unchanged = import_feature_flags_yaml(content_bytes, user=request.user)
    except InvalidStateError as e:
        return Response(
            {"error": {"code": e.code, "message": e.message, "details": getattr(e, 'details', {})}},
            status=400,
        )
    status_code = 201 if created > 0 and updated == 0 else 200
    warnings = []
    if mode == 'full':
        warnings.append("mode='full' not fully implemented for feature-flags: stale flags were not deleted")
    response_data: dict = {"created": created, "updated": updated, "unchanged": unchanged, "mode": mode}
    if warnings:
        response_data["warnings"] = warnings
    return Response({"data": response_data}, status=status_code)
