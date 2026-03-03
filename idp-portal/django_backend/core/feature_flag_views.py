"""
Story 17.12: Feature Flag API views.

Provides endpoints for listing, querying, and modifying feature flags.
"""

from __future__ import annotations

import re
from typing import Any

import structlog
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework import serializers
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer

from core import feature_flags
from core.middleware import get_correlation_id
from core.models import AuditActionType, AuditEntityType, AuditLog, FeatureFlag
from core.permissions import AdminProfilePermission
from core.utils import ensure_utc_isoformat

logger = structlog.get_logger(__name__)

FLAG_KEY_PATTERN = re.compile(r'^[a-z0-9][a-z0-9_-]*$')


class FeatureFlagListView(APIView):
    """
    GET /api/v1/feature-flags/ - List all feature flags (admin only).
    """
    permission_classes = [IsAuthenticated, AdminProfilePermission]

    def get(self, request: Any) -> Response:
        source = feature_flags._get_flags_source()

        if source == 'database':
            flags = FeatureFlag.objects.all()
            data = [
                {
                    'flag_key': f.flag_key,
                    'enabled': f.enabled,
                    'rollout_percent': f.rollout_percent,
                    'description': f.description,
                    'updated_at': ensure_utc_isoformat(f.updated_at),
                    'updated_by': f.updated_by,
                }
                for f in flags
            ]
        else:
            all_flags = feature_flags._get_all_flags()
            data = [
                {
                    'flag_key': key,
                    'enabled': config.get('enabled', False),
                    'rollout_percent': config.get('rollout_percent', 100),
                    'description': config.get('description', ''),
                    'updated_at': None,
                    'updated_by': '',
                }
                for key, config in all_flags.items()
            ]

        # Story 30.6 note: This endpoint returns {"data": [...], "source": "..."} format
        # which differs from standard {"data": [...]} but is intentional for admin context.
        # Frontend uses apiFetchRaw to handle this custom format.
        return Response({'data': data, 'source': source})


class FeatureFlagStatusView(APIView):
    """
    GET /api/v1/feature-flags/status - Get flag status for current user.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Any) -> Response:
        user = request.user
        context = {
            'user_id': str(user.id) if hasattr(user, 'id') else str(user),
        }
        if hasattr(user, 'profile'):
            context['profile'] = str(user.profile)

        flags_status = feature_flags.get_all_flags_status(context)
        return Response({'data': flags_status})


class FeatureFlagUpdateView(APIView):
    """
    PATCH /api/v1/feature-flags/<flag_key>/ - Update a feature flag (admin only).
    """
    permission_classes = [IsAuthenticated, AdminProfilePermission]

    @extend_schema(
        tags=['feature-flags'],
        summary='Modifier un feature flag',
        parameters=[
            OpenApiParameter('flag_key', str, location=OpenApiParameter.PATH, description='Clé du flag (a-z0-9_-)'),
        ],
        request=inline_serializer(
            name='FeatureFlagUpdateRequest',
            fields={
                'enabled': serializers.BooleanField(
                    required=False,
                    help_text='Activer ou désactiver le flag',
                ),
                'rollout_percent': serializers.IntegerField(
                    required=False,
                    min_value=0,
                    max_value=100,
                    help_text='Pourcentage de rollout (0-100)',
                ),
            },
        ),
    )
    def patch(self, request: Any, flag_key: str) -> Response:
        if not FLAG_KEY_PATTERN.match(flag_key):
            return Response(
                {'error': {'code': 'INVALID_FLAG_KEY', 'message': 'Flag key must match [a-z0-9][a-z0-9_-]*'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        enabled = request.data.get('enabled')
        rollout_percent = request.data.get('rollout_percent')

        if enabled is None and rollout_percent is None:
            return Response(
                {'error': {'code': 'NO_CHANGES', 'message': 'Provide enabled and/or rollout_percent'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if rollout_percent is not None:
            try:
                rollout_percent = int(rollout_percent)
            except (ValueError, TypeError):
                return Response(
                    {'error': {'code': 'INVALID_ROLLOUT', 'message': 'rollout_percent must be an integer'}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if rollout_percent < 0 or rollout_percent > 100:
                return Response(
                    {'error': {'code': 'INVALID_ROLLOUT', 'message': 'rollout_percent must be 0-100'}},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if enabled is not None and not isinstance(enabled, bool):
            return Response(
                {'error': {'code': 'INVALID_ENABLED', 'message': 'enabled must be a boolean'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        source = feature_flags._get_flags_source()
        user_id = str(request.user.id) if hasattr(request.user, 'id') else str(request.user)

        if source == 'database':
            flag, created = FeatureFlag.objects.get_or_create(
                flag_key=flag_key,
                defaults={
                    'enabled': enabled if enabled is not None else False,
                    'rollout_percent': rollout_percent if rollout_percent is not None else 100,
                    'updated_by': user_id,
                },
            )
            if not created:
                if enabled is not None:
                    flag.enabled = enabled
                if rollout_percent is not None:
                    flag.rollout_percent = rollout_percent
                flag.updated_by = user_id
                flag.save()

            result = {
                'flag_key': flag.flag_key,
                'enabled': flag.enabled,
                'rollout_percent': flag.rollout_percent,
                'updated_at': ensure_utc_isoformat(flag.updated_at),
                'updated_by': flag.updated_by,
            }
        else:
            # env source: update cache only (env var is read-only at runtime)
            all_flags = feature_flags._get_all_flags()
            current = all_flags.get(flag_key, {})
            if enabled is not None:
                current['enabled'] = enabled
            if rollout_percent is not None:
                current['rollout_percent'] = rollout_percent
            all_flags[flag_key] = current

            result = {
                'flag_key': flag_key,
                'enabled': current.get('enabled', False),
                'rollout_percent': current.get('rollout_percent', 100),
                'updated_at': ensure_utc_isoformat(timezone.now()),
                'updated_by': user_id,
            }

        # Audit trail BEFORE cache invalidation (SOC1 compliance - HIGH-1 fix)
        action_type = AuditActionType.FEATURE_FLAG_CREATED if source == 'database' and created else AuditActionType.FEATURE_FLAG_UPDATED
        try:
            AuditLog.objects.create_entry(
                user_id=user_id,
                action_type=action_type,
                entity_type=AuditEntityType.FEATURE_FLAG,
                entity_id=flag.id if source == 'database' else 0,
                details={
                    'flag_key': flag_key,
                    'enabled': result['enabled'],
                    'rollout_percent': result['rollout_percent'],
                },
                correlation_id=get_correlation_id(),
            )
        except Exception as e:  # noqa: BLE001 — best-effort-non-critical: audit failure must not block flag update
            # Story 22.11: Justified broad catch - Audit failures must not block flag updates
            logger.warning(
                "feature_flag_audit_error",
                error=str(e),
                error_type=type(e).__name__,
                flag_key=flag_key,
                correlation_id=get_correlation_id(),
            )
            # If audit fails, don't invalidate cache to maintain consistency
            return Response(
                {'error': {'code': 'AUDIT_FAILED', 'message': 'Feature flag updated but audit logging failed'}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Invalidate cache AFTER successful audit
        feature_flags.invalidate_cache(flag_key)

        logger.info(
            "feature_flag_updated",
            flag_key=flag_key,
            enabled=result['enabled'],
            rollout_percent=result['rollout_percent'],
            updated_by=user_id,
        )

        return Response({'data': result})
