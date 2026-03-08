"""
IaC export/sync views for core entities (feature-flags, config-sync status).
Story 64.8 — API endpoints for IaC sync (export GET + sync POST).
Story 64.14 — Config sync dashboard endpoint.

Pattern: FBV @api_view (Story 63.1 canonical pattern).
"""

from django.db import models
from django.db.models import Count, Max, Q
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from core.exceptions import InvalidStateError
from core.parsers import YAMLParser, extract_yaml_content
from core.permissions import IsAdminUser
from core.services_export_import import export_feature_flags_yaml, import_feature_flags_yaml


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
    try:
        created, updated, unchanged = import_feature_flags_yaml(content_bytes, user=request.user)
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


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_config_sync_status(request: Request) -> Response:
    """GET /api/v1/admin/config-sync/status/ — Dashboard statut sync IaC (Story 64.14)."""
    from catalog.models import Action, BusinessRulePolicy
    from integrations.models import Integration, IntegrationTypeCatalogue
    from profiles.models import Profile
    from reference.models import RefEngine, RefCategory
    from core.models import FeatureFlag

    def aggregate(queryset: models.QuerySet) -> dict:
        has_updated_at = any(
            f.name == 'updated_at' for f in queryset.model._meta.get_fields()
        )
        # Single DB query using conditional aggregation (replaces 5 separate queries).
        if has_updated_at:
            result = queryset.aggregate(
                total=Count('pk'),
                synced=Count('pk', filter=Q(
                    last_synced_at__isnull=False,
                    updated_at__lte=models.F('last_synced_at'),
                )),
                diverged=Count('pk', filter=Q(
                    last_synced_at__isnull=False,
                    updated_at__gt=models.F('last_synced_at'),
                )),
                never_synced=Count('pk', filter=Q(last_synced_at__isnull=True)),
                last_sync=Max('last_synced_at'),
            )
        else:
            # Modèles sans updated_at : divergence impossible à détecter.
            result = queryset.aggregate(
                total=Count('pk'),
                synced=Count('pk', filter=Q(last_synced_at__isnull=False)),
                never_synced=Count('pk', filter=Q(last_synced_at__isnull=True)),
                last_sync=Max('last_synced_at'),
            )
            result['diverged'] = 0
        last_sync = result['last_sync']
        return {
            'total': result['total'],
            'synced': result['synced'],
            'diverged': result['diverged'],
            'never_synced': result['never_synced'],
            'last_sync_date': last_sync.isoformat() if last_sync else None,
        }

    entity_configs = [
        ('actions', Action.objects.all()),
        ('integrations', Integration.objects.all()),
        ('profiles', Profile.objects.all()),
        ('policies', BusinessRulePolicy.objects.all()),
        ('engines', RefEngine.objects.all()),
        ('categories', RefCategory.objects.all()),
        ('integration-types', IntegrationTypeCatalogue.objects.all()),
        ('feature-flags', FeatureFlag.objects.all()),
    ]

    entity_types = [
        {'entity_type': name, **aggregate(qs)}
        for name, qs in entity_configs
    ]

    all_totals = {k: sum(e[k] for e in entity_types if isinstance(e[k], int))
                  for k in ('total', 'synced', 'diverged', 'never_synced')}
    all_dates = [e['last_sync_date'] for e in entity_types if e['last_sync_date']]
    all_totals['last_sync_date'] = max(all_dates) if all_dates else None

    return Response({'data': {'global': all_totals, 'entity_types': entity_types}})
